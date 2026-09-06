"""报告 Service（Report）—— 对应需求中的"实验记录/报表"。

对应需求文档章节：6.2（报告生成 P1）、6.8.5（报告数据范围）。

模型：app.models.report.Report。

说明：ORM 中没有 ExperimentLog 表；需求文档中的"报告生成"（态势报告）由
report 表承载，此处 ReportService 即"实验记录/报表"能力的实现。

业务规则（需求 6.8.5）：
1. 普通用户生成报告时只能使用本人数据 → target_user_id 只能为空（本人）或等于本人。
2. 管理员生成报告时可以选择全平台（target_user_id=None）或指定用户数据。
3. 普通用户查看报告：本人生成的或定向给自己的（target_user_id == 本人）。
4. 管理员可查看全部报告，并按 target_user_id 过滤。
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import false, or_, select

from app.models.app_user import AppUser
from app.models.dataset import Dataset
from app.models.inference_record import InferenceRecord
from app.models.model_version import ModelVersion
from app.models.report import Report
from app.models.risk_event import RiskEvent
from app.models.scenario import Scenario
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    DATASET_VISIBILITY_PLATFORM,
    REPORT_FORMATS,
    REPORT_TYPES,
    ROLE_SCENARIO_ADMIN,
    ROLE_SCENARIO_USER,
    ROLE_SUPER_ADMIN,
    is_risk_label,
)
from app.services.situation_snapshot_service import SituationSnapshotService
from app.utils.common import (
    get_logger,
    paginate,
    row_to_dict,
    validate_enum,
    validate_required,
)

logger = get_logger("report")


class ReportService(ServiceBase):
    """报告生成（P1）/ 查询 / 删除。"""

    def _get(self, report_id: int) -> Report:
        report = self.db.get(Report, report_id)
        if report is None:
            raise ServiceError(404, "报告不存在")
        return report

    def _serialize(self, report: Report, include_report_data: bool = False) -> dict:
        """Expose stable display fields while retaining the database field names.

        include_report_data=True 时才附带结构化 report_data（较大，仅详情/生成时返回，
        列表默认排除以避免载荷膨胀）。
        """
        data = row_to_dict(
            report, exclude=() if include_report_data else ("report_data",)
        )
        data.update(
            {
                "report_id": str(report.id),
                "created_at": data.get("generated_at"),
                "status": "completed",
                "summary": report.content,
            }
        )
        if report.scenario_id is not None:
            scenario = self.db.get(Scenario, report.scenario_id)
            if scenario is not None:
                data["scenario_code"] = scenario.code
                data["scenario_name"] = scenario.name
        return data

    @staticmethod
    def _can_view(user, report: Report) -> bool:
        return (
            report.generated_by == user.id
            or report.target_user_id == user.id
        )

    # ------------------------------------------------------------------
    # 生成（需求 6.8.5：报告数据范围）
    # ------------------------------------------------------------------
    @service_call
    def create(
        self,
        current_user,
        title: str,
        report_type: str,
        content: str,
        target_user_id: Optional[int] = None,
        file_path: Optional[str] = None,
        scenario_id: Optional[int] = None,
        format: str = "markdown",
        scheduled: bool = False,
        interval_days: Optional[int] = None,
    ):
        """生成态势报告。

        - 普通用户：只能基于本人数据（target_user_id 必须为空或本人），否则 403。
        - 系统管理员：可生成全平台或指定用户报告，可指定任意场景。
        - 场景管理员/用户：scenario_id 强制为本人绑定场景。
        - 格式 / 定时：format 取值 markdown/html/pdf；定时时 interval_days 必填。
        """
        self.require_login(current_user)
        err = validate_enum(report_type, REPORT_TYPES, "report_type")
        if err:
            raise ServiceError(400, err)
        err = validate_enum(format, REPORT_FORMATS, "format")
        if err:
            raise ServiceError(400, err)
        err = validate_required({"title": title, "content": content}, ("title", "content"))
        if err:
            raise ServiceError(400, err)
        if scheduled and (interval_days is None or interval_days < 1):
            raise ServiceError(400, "定时生成需指定有效周期（至少 1 天）")

        role = getattr(current_user, "role", None)
        if role != ROLE_SUPER_ADMIN:
            # 场景角色只能生成本人绑定场景的报告。
            if scenario_id is not None and scenario_id != current_user.scenario_id:
                raise ServiceError(403, "只能生成本人绑定场景的报告")
            scenario_id = current_user.scenario_id
            if role == ROLE_SCENARIO_USER and target_user_id is not None and target_user_id != current_user.id:
                raise ServiceError(403, "普通用户只能基于本人数据生成报告")
            if role == ROLE_SCENARIO_ADMIN and target_user_id is not None:
                target = self.db.get(AppUser, target_user_id)
                if target is None:
                    raise ServiceError(404, "目标用户不存在")
                if target.scenario_id != scenario_id:
                    raise ServiceError(403, "只能指定本人绑定场景内的用户")
        elif target_user_id is not None:
            target = self.db.get(AppUser, target_user_id)
            if target is None:
                raise ServiceError(404, "目标用户不存在")

        report = Report(
            generated_by=current_user.id,
            title=title.strip(),
            report_type=report_type,
            target_user_id=target_user_id,
            content=content,
            file_path=file_path,
            scenario_id=scenario_id,
            format=format,
            scheduled=scheduled,
            interval_days=interval_days if scheduled else None,
            generated_at=datetime.now(timezone.utc),
        )
        self.db.add(report)
        self.commit()
        return ok(data=self._serialize(report), message="报告已生成")

    # ------------------------------------------------------------------
    # 自动生成（服务端基于真实数据 + 算法解释组装报告内容，替代前端占位文案）
    # ------------------------------------------------------------------
    @service_call
    def generate(
        self,
        current_user,
        title: str,
        scenario_id: Optional[int] = None,
        scope: str = "self",
        target_user_id: Optional[int] = None,
        format: str = "markdown",
    ):
        """生成态势报告：统计 + 算法多视图研判 + NL 态势分析/风险规避指导。

        权限与数据范围沿用 create 的三级隔离逻辑；内容由服务端基于真实
        RiskEvent 与推理记录（含 explain_data）组装，落库 report.content 与
        report.report_data（结构化，供前端渲染图表）。
        """
        self.require_login(current_user)
        err = validate_enum(format, REPORT_FORMATS, "format")
        if err:
            raise ServiceError(400, err)
        err = validate_required({"title": title}, ("title",))
        if err:
            raise ServiceError(400, err)

        role = getattr(current_user, "role", None)
        if role != ROLE_SUPER_ADMIN:
            if scenario_id is not None and scenario_id != current_user.scenario_id:
                raise ServiceError(403, "只能生成本人绑定场景的报告")
            scenario_id = current_user.scenario_id
            if role == ROLE_SCENARIO_USER:
                scope = "self"
                target_user_id = current_user.id
            elif role == ROLE_SCENARIO_ADMIN and target_user_id is not None:
                target = self.db.get(AppUser, target_user_id)
                if target is None:
                    raise ServiceError(404, "目标用户不存在")
                if target.scenario_id != scenario_id:
                    raise ServiceError(403, "只能指定本人绑定场景内的用户")
        elif target_user_id is not None:
            target = self.db.get(AppUser, target_user_id)
            if target is None:
                raise ServiceError(404, "目标用户不存在")

        # 1) 汇总真实数据（风险事件 + 推理记录，按 6.10.1 三级角色隔离）
        events = self._gather_events(current_user, role, scenario_id, scope, target_user_id)
        records = self._gather_records(current_user, role, scenario_id, scope, target_user_id)

        # 2) 组装 6.10.2 定义的完整 report_data（九大部分）
        report_data = self._build_report_data(
            title=title,
            scenario_id=scenario_id,
            scope=scope,
            current_user=current_user,
            events=events,
            records=records,
        )

        # 3) 自然语言态势分析 + 风险规避指导（6.10.4：规则+场景模板，LLM 仅 P2 润色）
        from app.services.report_nl import generate_report_narrative

        narrative = generate_report_narrative(report_data)
        report_data.update(narrative)

        # 4) 渲染正文（Markdown，供导出与纯文本查看）
        content = self._render_content(report_data)

        report = Report(
            generated_by=current_user.id,
            title=title.strip(),
            report_type="USER_SNAPSHOT" if scope == "self" else "SCENE_SNAPSHOT",
            target_user_id=target_user_id if scope == "user" else None,
            scenario_id=scenario_id,
            content=content,
            report_data=report_data,
            format=format,
            scheduled=False,
            interval_days=None,
            generated_at=datetime.now(timezone.utc),
        )
        self.db.add(report)
        self.commit()
        return ok(data=self._serialize(report, include_report_data=True), message="报告已生成")

    # ------------------------------------------------------------------
    # 数据汇总（6.10.1 三级角色隔离口径）
    # ------------------------------------------------------------------
    def _gather_events(self, current_user, role, scenario_id, scope, target_user_id):
        stmt = select(RiskEvent)
        if scenario_id is not None:
            stmt = stmt.where(RiskEvent.scenario_id == scenario_id)
        if role == ROLE_SUPER_ADMIN:
            stmt = stmt.join(Dataset, Dataset.id == RiskEvent.dataset_id).where(
                Dataset.visibility == DATASET_VISIBILITY_PLATFORM
            )
        elif role == ROLE_SCENARIO_USER:
            stmt = stmt.where(RiskEvent.created_by_user_id == current_user.id)
        if scope == "user" and target_user_id is not None:
            stmt = stmt.where(RiskEvent.created_by_user_id == target_user_id)
        stmt = stmt.order_by(RiskEvent.occurred_at.desc())
        return self.db.scalars(stmt).all()

    def _gather_records(self, current_user, role, scenario_id, scope, target_user_id):
        stmt = (
            select(InferenceRecord, ModelVersion)
            .join(ModelVersion, ModelVersion.id == InferenceRecord.model_version_id)
        )
        if scenario_id is not None:
            stmt = stmt.where(ModelVersion.scenario_id == scenario_id)
        if role == ROLE_SUPER_ADMIN:
            stmt = stmt.join(Dataset, Dataset.id == ModelVersion.dataset_id).where(
                Dataset.visibility == DATASET_VISIBILITY_PLATFORM
            )
        elif role == ROLE_SCENARIO_USER:
            stmt = stmt.where(InferenceRecord.user_id == current_user.id)
        if scope == "user" and target_user_id is not None:
            stmt = stmt.where(InferenceRecord.user_id == target_user_id)
        stmt = stmt.order_by(InferenceRecord.executed_at.desc())
        return self.db.execute(stmt).all()

    # ------------------------------------------------------------------
    # 组装 6.10.2 定义的完整 report_data
    # ------------------------------------------------------------------
    def _build_report_data(self, title, scenario_id, scope, current_user, events, records):
        scenario = self.db.get(Scenario, scenario_id) if scenario_id else None

        times = [r.executed_at for r, _m in records if r.executed_at]
        times += [e.occurred_at for e in events if e.occurred_at]
        period = self._period(times)

        datasets, algorithms, models = {}, {}, {}
        for _record, model in records:
            if model.dataset:
                datasets[model.dataset.logical_id] = model.dataset.version
            if model.algorithm:
                algorithms[model.algorithm.code] = model.algorithm.display_name
            models[model.id] = model.algorithm.code if model.algorithm else None

        report_info = {
            "title": title.strip(),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "report_period": period,
            "generated_by": getattr(current_user, "display_name", None)
            or getattr(current_user, "username", ""),
            "scenario_name": scenario.name if scenario else None,
            "scenario_code": scenario.code if scenario else None,
            "data_scope": {"self": "本人数据", "all": "全平台/本场景数据", "user": "指定用户数据"}.get(
                scope, scope
            ),
            "datasets": [{"logical_id": k, "version": v} for k, v in datasets.items()],
            "algorithms": [{"code": k, "name": v} for k, v in algorithms.items()],
            "model_versions": [{"id": k, "algorithm_code": v} for k, v in models.items()],
        }

        overview = self._overview(events, records)
        model_analysis = self._model_analysis(records)

        return {
            "report_info": report_info,
            "overview": overview,
            "prediction": self._prediction(records),
            "model_analysis": model_analysis,
            "feature_analysis": self._feature_analysis(records),
            "trend": self._trend(records),
            "key_events": self._key_events(events, records),
            "data_notes": self._data_notes(report_info, overview, model_analysis),
        }

    @staticmethod
    def _period(times):
        if not times:
            return None
        lo, hi = min(times), max(times)
        lo_s, hi_s = lo.strftime("%Y-%m-%d"), hi.strftime("%Y-%m-%d")
        return lo_s if lo_s == hi_s else f"{lo_s} 至 {hi_s}"

    @staticmethod
    def _overview(events, records):
        total = len(records)
        risk_count = sum(1 for r, _m in records if r.is_risk_event)
        normal_count = total - risk_count
        stats = SituationSnapshotService._aggregate(events)
        risk_scores = [
            float(r.risk_score) for r, _m in records if r.is_risk_event and r.risk_score is not None
        ]
        avg_risk_prob = (sum(risk_scores) / len(risk_scores)) if risk_scores else None

        ordered = sorted(records, key=lambda x: x[0].executed_at or datetime(1970, 1, 1))
        trend = "样本不足，无法判断"
        if total >= 4:
            half = total // 2

            def ratio(recs):
                if not recs:
                    return 0.0
                return sum(1 for r, _m in recs if r.is_risk_event) / len(recs)

            r1, r2 = ratio(ordered[:half]), ratio(ordered[half:])
            if r2 - r1 > 0.05:
                trend = "上升"
            elif r1 - r2 > 0.05:
                trend = "下降"
            else:
                trend = "平稳"

        return {
            "total_inferences": total,
            "risk_count": risk_count,
            "normal_count": normal_count,
            "risk_ratio": (risk_count / total) if total else None,
            "normal_ratio": (normal_count / total) if total else None,
            "high_count": stats.get("high_count", 0),
            "medium_count": stats.get("medium_count", 0),
            "low_count": stats.get("low_count", 0),
            "pending_count": stats.get("pending_count", 0),
            "processing_count": stats.get("processing_count", 0),
            "resolved_count": stats.get("resolved_count", 0),
            "avg_risk_prob": avg_risk_prob,
            "risk_trend": trend,
        }

    @staticmethod
    def _prediction(records):
        label_counts = {}
        class_prob_sums = {}
        class_prob_counts = {}
        low_confidence = 0
        risk_scores = []
        for record, _model in records:
            label = record.prediction_label or "未知"
            label_counts[label] = label_counts.get(label, 0) + 1
            explain = record.explain_data or {}
            prob = explain.get("probability")
            if prob is None and record.risk_score is not None:
                prob = float(record.risk_score)
            if prob is not None and 0.4 <= float(prob) <= 0.6:
                low_confidence += 1
            for cp in explain.get("class_distribution") or []:
                c, p = cp.get("class"), cp.get("probability")
                if c is not None and p is not None:
                    class_prob_sums[c] = class_prob_sums.get(c, 0.0) + float(p)
                    class_prob_counts[c] = class_prob_counts.get(c, 0) + 1
            if record.is_risk_event and record.risk_score is not None:
                risk_scores.append(float(record.risk_score))

        total = len(records)
        label_distribution = [
            {"label": k, "count": v, "ratio": (v / total) if total else None}
            for k, v in sorted(label_counts.items(), key=lambda x: -x[1])
        ]
        class_probability = [
            {
                "class": c,
                "probability": (class_prob_sums[c] / class_prob_counts[c]) if class_prob_counts[c] else None,
            }
            for c in class_prob_sums
        ]

        bucket_edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
        bucket_labels = ["0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
        counts = [0] * 5
        for s in risk_scores:
            for i in range(5):
                if bucket_edges[i] <= s < bucket_edges[i + 1]:
                    counts[i] += 1
                    break
        risk_prob_buckets = [{"range": bucket_labels[i], "count": counts[i]} for i in range(5)]

        return {
            "label_distribution": label_distribution,
            "class_probability": class_probability,
            "risk_prob_buckets": risk_prob_buckets,
            "low_confidence_count": low_confidence,
        }

    @staticmethod
    def _model_analysis(records):
        groups = {}
        for record, model in records:
            key = model.id
            if key not in groups:
                algorithm = model.algorithm
                groups[key] = {
                    "model_version_id": model.id,
                    "algorithm_code": algorithm.code if algorithm else None,
                    "algorithm_name": algorithm.display_name if algorithm else None,
                    "inference_count": 0,
                    "risk_count": 0,
                    "explain": None,
                }
            g = groups[key]
            g["inference_count"] += 1
            if record.is_risk_event:
                g["risk_count"] += 1
            if g["explain"] is None and record.explain_data:
                g["explain"] = record.explain_data

        result = []
        for g in groups.values():
            explain = g["explain"] or {}
            views = explain.get("views") or []
            final_label = explain.get("prediction_label")
            view_entries = []
            for v in views:
                dist = v.get("distribution") or []
                top = max(dist, key=lambda d: d.get("probability", 0) or 0) if dist else {}
                view_entries.append(
                    {
                        "name": v.get("name"),
                        "predicted_label": top.get("class"),
                        "distribution": dist,
                        "consistent_with_final": bool(
                            final_label is not None and top.get("class") == final_label
                        ),
                    }
                )
            result.append(
                {
                    "model_version_id": g["model_version_id"],
                    "algorithm_code": g["algorithm_code"],
                    "algorithm_name": g["algorithm_name"],
                    "inference_count": g["inference_count"],
                    "risk_count": g["risk_count"],
                    "views": view_entries,
                    "view_weights": explain.get("view_weights") or [],
                    "calculation_method": explain.get("calculation_method"),
                    "has_views": len(view_entries) > 0,
                }
            )
        return result

    @staticmethod
    def _feature_analysis(records):
        best = {}
        method = None
        for record, model in records:
            explain = record.explain_data or {}
            if explain.get("calculation_method"):
                method = explain["calculation_method"]
            logical_id = model.dataset.logical_id if model.dataset else None
            for fe in explain.get("feature_evidence") or []:
                attr = fe.get("attribute")
                value = fe.get("value")
                view = fe.get("view")
                contribs = fe.get("class_contributions") or []
                rep = None
                salience = 0.0
                for cc in contribs:
                    w = cc.get("weight")
                    if w is None:
                        continue
                    try:
                        s = abs(float(w) - 1.0)
                    except (TypeError, ValueError):
                        continue
                    if s > salience:
                        salience = s
                        rep = cc
                if rep is None:
                    continue
                top_class = rep.get("class")
                support = "中性"
                if top_class is not None:
                    support = "风险" if is_risk_label(logical_id or "", top_class) else "正常"
                key = (attr, value)
                if key not in best or salience > best[key]["salience"]:
                    best[key] = {
                        "attribute": attr,
                        "value": value,
                        "view": view,
                        "weight": rep.get("weight"),
                        "cond_probs": [
                            {"class": c.get("class"), "cond_prob": c.get("cond_prob")}
                            for c in contribs
                        ],
                        "weighted_contribution": rep.get("contribution"),
                        "support_direction": support,
                        "salience": salience,
                    }
        ranked = sorted(best.values(), key=lambda x: x["salience"], reverse=True)
        for i, item in enumerate(ranked):
            item["rank"] = i + 1
        return {
            "calculation_method": method,
            "top_features": ranked[:10],
            "all_features": ranked,
        }

    @staticmethod
    def _trend(records):
        by_day = {}
        for record, _model in records:
            if not record.executed_at:
                continue
            day = record.executed_at.strftime("%m-%d")
            d = by_day.setdefault(
                day, {"date": day, "inference_count": 0, "risk_count": 0, "risk_scores": []}
            )
            d["inference_count"] += 1
            if record.is_risk_event:
                d["risk_count"] += 1
                if record.risk_score is not None:
                    d["risk_scores"].append(float(record.risk_score))
        result = []
        for day in sorted(by_day):
            d = by_day[day]
            result.append(
                {
                    "date": d["date"],
                    "inference_count": d["inference_count"],
                    "risk_count": d["risk_count"],
                    "risk_ratio": (d["risk_count"] / d["inference_count"]) if d["inference_count"] else 0,
                    "avg_risk_prob": (sum(d["risk_scores"]) / len(d["risk_scores"]))
                    if d["risk_scores"]
                    else None,
                }
            )
        return result

    @staticmethod
    def _key_events(events, records, limit=10):
        event_map = {e.inference_record_id: e for e in events}
        key = []
        for record, _model in records:
            e = event_map.get(record.id)
            if e is None:
                continue
            key.append(
                {
                    "time": e.occurred_at.strftime("%Y-%m-%d %H:%M") if e.occurred_at else None,
                    "risk_level": {"HIGH": "高危", "MEDIUM": "中危", "LOW": "低危"}.get(
                        e.risk_level, e.risk_level
                    ),
                    "probability": float(e.risk_score) if e.risk_score is not None else None,
                    "risk_type": e.risk_type,
                    "status": {"PENDING": "待处置", "PROCESSING": "处理中", "RESOLVED": "已处置"}.get(
                        e.status, e.status
                    ),
                    "key_features": list((e.raw_features or {}).keys())[:5],
                }
            )
        key.sort(key=lambda x: (x["probability"] is not None, x["probability"] or 0), reverse=True)
        return key[:limit]

    @staticmethod
    def _data_notes(report_info, overview, model_analysis):
        parts = [
            f"数据范围：{report_info.get('data_scope')}；样本（推理记录）{overview.get('total_inferences', 0)} 条。"
        ]
        algos = report_info.get("algorithms") or []
        if algos:
            parts.append("涉及算法：" + "、".join(f"{a['name']}({a['code']})" for a in algos) + "。")
        no_view = [m for m in model_analysis if not m["has_views"]]
        if no_view:
            parts.append(
                "以下算法/模型未提供独立视图解释（标注为“无独立视图”）："
                + "、".join(m["algorithm_name"] or m["algorithm_code"] for m in no_view)
                + "。"
            )
        if overview.get("risk_trend") == "样本不足，无法判断":
            parts.append("样本量不足，风险变化方向无法判断。")
        parts.append(
            "本报告结论基于系统真实推理与风险事件数据，预测概率为模型输出，不构成确定性事因判断；"
            "加权贡献值口径见“特征加权条件概率”的 calculation_method。"
        )
        return "".join(parts)

    @staticmethod
    def _render_content(report_data):
        info = report_data.get("report_info") or {}
        ov = report_data.get("overview") or {}
        pred = report_data.get("prediction") or {}
        lines = [
            f"# {info.get('title', '')}",
            "",
            "## 一、报告基本信息",
            f"- 报告期：{info.get('report_period') or '—'}",
            f"- 生成者：{info.get('generated_by')} · 生成时间：{info.get('generated_at')}",
            f"- 场景：{info.get('scenario_name') or '—'} · 数据范围：{info.get('data_scope')}",
            f"- 涉及算法：{'、'.join(a['name'] for a in (info.get('algorithms') or [])) or '—'}",
            "",
            "## 二、态势概况",
            f"- 推理总量：{ov.get('total_inferences', 0)}（风险 {ov.get('risk_count', 0)} / 正常 {ov.get('normal_count', 0)}）",
            f"- 风险等级：高危 {ov.get('high_count', 0)} / 中危 {ov.get('medium_count', 0)} / 低危 {ov.get('low_count', 0)}",
            f"- 平均风险概率：{(ov.get('avg_risk_prob') or 0):.3f}",
            f"- 风险变化方向：{ov.get('risk_trend')}",
            "",
            "## 三、最终预测结果与概率",
        ]
        label_dist = pred.get("label_distribution") or []
        if label_dist:
            lines.append(
                "- 预测标签分布：" + "、".join(f"{x['label']} {x['count']} 条" for x in label_dist)
            )
        lines.append(f"- 低置信度/接近阈值样本：{pred.get('low_confidence_count', 0)} 条")

        lines += ["", "## 四、不同视图预测结果与概率"]
        for m in report_data.get("model_analysis", []):
            name = m["algorithm_name"] or m["algorithm_code"] or "模型"
            if not m["has_views"]:
                lines.append(f"- {name}（模型 {m['model_version_id']}）：无独立视图")
            else:
                lines.append(f"- {name}（模型 {m['model_version_id']}）：")
                for v in m["views"]:
                    mark = "✓一致" if v["consistent_with_final"] else "✗分歧"
                    lines.append(f"  - {v['name']}：预测 {v['predicted_label']}（{mark}）")

        lines += ["", "## 五、特征加权条件概率（Top 10）"]
        feats = (report_data.get("feature_analysis") or {}).get("top_features") or []
        if feats:
            for f in feats:
                lines.append(
                    f"- {f['attribute']} = {f['value']}：权重 {f['weight']:.3f}，支持方向 {f['support_direction']}"
                )
        else:
            lines.append("- 无特征解释数据")

        lines += ["", "## 六、风险趋势与重点事件"]
        for t in report_data.get("trend", []):
            lines.append(
                f"- {t['date']}：推理 {t['inference_count']}，风险 {t['risk_count']}，"
                f"风险占比 {(t['risk_ratio'] * 100):.0f}%"
            )
        if report_data.get("key_events"):
            lines.append("重点风险事件：")
            for e in report_data["key_events"]:
                lines.append(f"- [{e['risk_level']}] {e['time']} · 概率 {e['probability']} · {e['status']}")

        lines += [
            "",
            "## 七、态势分析",
            report_data.get("analysis_nl", ""),
            "",
            "## 八、风险规避指导",
            report_data.get("guidance_nl", ""),
            "",
            "## 九、数据说明",
            report_data.get("data_notes", ""),
            "",
            "---",
            "由多场景贝叶斯分类态势感知系统自动生成",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    @service_call
    def get_list(
        self,
        current_user,
        target_user_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 10,
    ):
        """报告列表（按三级角色隔离）。

        系统管理员：全部报告，可按 target_user_id 过滤；
        场景管理员：自己绑定场景下的报告；
        场景用户：本人生成的或定向给自己的报告。
        """
        self.require_login(current_user)
        role = getattr(current_user, "role", None)
        stmt = select(Report)
        if role == ROLE_SUPER_ADMIN:
            if target_user_id is not None:
                stmt = stmt.where(Report.target_user_id == target_user_id)
        elif role == ROLE_SCENARIO_ADMIN:
            scid = getattr(current_user, "scenario_id", None)
            if scid is None:
                stmt = stmt.where(false())  # 未绑定场景：看不到任何报告
            else:
                stmt = stmt.where(Report.scenario_id == scid)
        else:
            stmt = stmt.where(
                or_(
                    Report.generated_by == current_user.id,
                    Report.target_user_id == current_user.id,
                )
            )
        stmt = stmt.order_by(Report.generated_at.desc())
        result = paginate(self.db, stmt, page, page_size)
        result["items"] = [self._serialize(r) for r in result["items"]]
        return ok(data=result)

    @service_call
    def get(self, current_user, report_id: int):
        """报告详情（普通用户仅本人生成或定向给自己的报告）。"""
        self.require_login(current_user)
        report = self._get(report_id)
        role = getattr(current_user, "role", None)
        if role == ROLE_SCENARIO_ADMIN and report.scenario_id != getattr(current_user, "scenario_id", None):
            raise ServiceError(403, "无权限操作")
        if role not in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN) and not self._can_view(current_user, report):
            raise ServiceError(403, "无权限操作")
        return ok(data=self._serialize(report, include_report_data=True))

    @service_call
    def update_schedule(
        self,
        current_user,
        report_id: int,
        scheduled: bool,
        interval_days: Optional[int] = None,
    ):
        """保存账号设置的定时记录，暂不启动实际调度任务。"""
        self.require_login(current_user)
        report = self._get(report_id)
        role = getattr(current_user, "role", None)
        if role == ROLE_SCENARIO_ADMIN and report.scenario_id != getattr(current_user, "scenario_id", None):
            raise ServiceError(403, "无权限操作")
        if role not in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN) and report.generated_by != current_user.id:
            raise ServiceError(403, "只有报告创建者可以修改定时配置")
        if scheduled and (interval_days is None or interval_days < 1):
            raise ServiceError(400, "定时生成需指定有效周期（至少 1 天）")
        report.scheduled = scheduled
        report.interval_days = interval_days if scheduled else None
        self.commit()
        return ok(data=self._serialize(report), message="定时配置已保存")

    # ------------------------------------------------------------------
    # 删除（生成者本人或 ADMIN）
    # ------------------------------------------------------------------
    @service_call
    def delete(self, current_user, report_id: int):
        """删除报告：生成者本人或管理员。"""
        self.require_login(current_user)
        report = self._get(report_id)
        role = getattr(current_user, "role", None)
        if role == ROLE_SCENARIO_ADMIN and report.scenario_id != getattr(current_user, "scenario_id", None):
            raise ServiceError(403, "无权限操作")
        if role not in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN) and report.generated_by != current_user.id:
            raise ServiceError(403, "无权限操作")
        self.db.delete(report)
        self.commit()
        return ok(message="报告已删除")
