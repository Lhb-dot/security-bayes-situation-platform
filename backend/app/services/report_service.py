"""报告 Service（Report）—— 对应需求中的"实验记录/报表"。

对应需求文档章节：6.2（报告生成 P1）、6.8.5（报告数据范围）。

模型：app.models.report.Report。

说明：ORM 中没有 ExperimentLog 表；需求文档中的"报告生成"（态势报告）由
report 表承载，此处 ReportService 即"实验记录/报表"能力的实现。

业务规则（需求 6.8.5）：
数据范围（三级角色）：
1. 最外层管理员（SUPER_ADMIN）：可统计全平台数据，或本人的个人数据；不支持指定单个用户。
2. 场景管理员（SCENARIO_ADMIN）：可统计本人绑定场景下所有用户的数据，或本人的个人数据。
3. 场景用户（SCENARIO_USER）：只能统计本人的个人数据（scope 强制为 self）。
4. 个人数据 = 当前账号自己产生的推理记录与风险事件（scope=self）。
5. 报告不再包含模型版本评价（模型评价在模型中心单独查看/导出），避免把缓存的 AI 评价文本混入报告。
6. 查看范围：普通用户只能看本人生成的报告；管理员看其管理范围内的报告。
7. 定时报告（scheduled=True）：报告本身就是定时任务的载体，跟随账号（generated_by）
   存在；创建时立刻产出第一份内容，之后由后台调度器按 next_run_at 原地重新生成，
   删除报告即删除定时任务。调度器见 app/services/report_scheduler.py。
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import false, func, or_, select, type_coerce
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import load_only

from app.models.app_user import AppUser
from app.models.dataset import Dataset
from app.models.inference_record import InferenceRecord
from app.models.model_version import ModelVersion
from app.models.report import Report
from app.models.risk_event import RiskEvent
from app.models.scenario import Scenario
from app.schemas.common import ok
from app.services import risk_view
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.report_export import (
    SECTION_FEATURES,
    SECTION_VIEWS,
    build_export,
)
from app.services.constants import (
    DATASET_VISIBILITY_PLATFORM,
    REPORT_FORMATS,
    REPORT_SCOPES,
    REPORT_TYPES,
    ROLE_SCENARIO_ADMIN,
    ROLE_SCENARIO_USER,
    ROLE_SUPER_ADMIN,
    USER_STATUS_ENABLED,
    USER_VISIBLE_MODEL_STATUSES,
    is_risk_label,
)
from app.utils.common import (
    beijing_now_str,
    get_logger,
    paginate,
    row_to_dict,
    to_beijing,
    validate_enum,
    validate_required,
)

logger = get_logger("report")

# 定时报告重新生成失败后的重试间隔（分钟）：不占满整个周期，也不至于每轮空转
RETRY_AFTER_MINUTES = 10

# 风险概率分桶（报告「预测结果分布」章节）：上界用 1.01，保证 prob=1.0 落进最后一桶
PROB_BUCKET_EDGES = (0.0, 0.2, 0.4, 0.6, 0.8, 1.01)
PROB_BUCKET_LABELS = ("0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0")
# 概率落在该闭区间视为「接近阈值」，计入低置信度样本
LOW_CONFIDENCE_MIN = 0.4
LOW_CONFIDENCE_MAX = 0.6
# 趋势判定：样本量下限，以及前后半段风险占比差达到多少才算上升/下降
TREND_MIN_SAMPLES = 4
TREND_DELTA = 0.05
# 时间缺失时的排序兜底（必须带 tzinfo，否则与库里的 aware datetime 比较会 TypeError）
_SORT_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
# 等级 / 处置状态的中文文案（报告正文与重点事件表共用）
RISK_LEVEL_LABELS = {"HIGH": "高危", "MEDIUM": "中危", "LOW": "低危"}
RISK_STATUS_LABELS = {"PENDING": "待处置", "PROCESSING": "处理中", "RESOLVED": "已处置"}

# 报告真正读到的 explain_data 键（见 ReportService._explain_expression）。
# 整列 2394 行反序列化成 dict 实测峰值 748 MB，必须在 SQL 侧把不用的键裁掉。
_REPORT_EXPLAIN_KEYS = (
    "probability",
    "class_distribution",
    "calculation_method",
    "feature_evidence",
    "views",
    "view_weights",
    "prediction_label",
)


class ReportService(ServiceBase):
    """报告生成（P1）/ 查询 / 删除。"""

    def _get(self, report_id: int) -> Report:
        report = self.db.get(Report, report_id)
        if report is None:
            raise ServiceError(404, "报告不存在")
        return report

    def _serialize(
        self,
        report: Report,
        include_report_data: bool = False,
        include_summary: bool = True,
    ) -> dict:
        """Expose stable display fields while retaining the database field names.

        include_report_data=True 时才附带结构化 report_data（较大，仅详情/生成时返回，
        列表默认排除以避免载荷膨胀）。

        include_summary=False 时不下发 summary —— 它与 content 同值（都是正文全文），
        前端列表零消费，每页 10 条等于白传 10 份正文。仅列表接口传 False。
        """
        data = row_to_dict(
            report, exclude=() if include_report_data else ("report_data",)
        )
        extra = {
            "report_id": str(report.id),
            "created_at": data.get("generated_at"),
            "status": "completed",
        }
        if include_summary:
            extra["summary"] = report.content
        data.update(extra)
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

    def _resolve_generation_scope(
        self,
        current_user,
        scenario_id: Optional[int],
        scope: str,
    ) -> tuple[object, Optional[int], str]:
        """Normalize the report data scope after applying the three-level access rules.

        Both report creation paths share this boundary: management roles pick an
        aggregate scope (whole platform / whole scenario) or their own personal
        data, while scenario users are always pinned to their own data.
        """
        role = getattr(current_user, "role", None)
        if role == ROLE_SUPER_ADMIN:
            return role, scenario_id, scope

        bound_scenario_id = getattr(current_user, "scenario_id", None)
        if scenario_id is not None and scenario_id != bound_scenario_id:
            raise ServiceError(403, "只能生成本人绑定场景的报告")
        scenario_id = bound_scenario_id

        if role == ROLE_SCENARIO_USER:
            return role, scenario_id, "self"
        return role, scenario_id, scope

    def _validate_generate_inputs(
        self,
        current_user,
        title: str,
        scenario_id: Optional[int],
        scope: str,
        format: str,
        scheduled: bool,
        interval_days: Optional[int],
    ) -> tuple[object, Optional[int], str]:
        """生成入参校验 + 数据范围归一，返回 (role, scenario_id, scope)。

        同步接口与异步提交共用这一条边界：异步提交要在 POST 时就返回 400 / 403，
        而不是等后台线程跑起来才发现参数不对，所以单独抽出来给两处调用。
        """
        self.require_login(current_user)
        err = validate_enum(scope, REPORT_SCOPES, "scope")
        if err:
            raise ServiceError(400, err)
        err = validate_enum(format, REPORT_FORMATS, "format")
        if err:
            raise ServiceError(400, err)
        err = validate_required({"title": title}, ("title",))
        if err:
            raise ServiceError(400, err)
        if scheduled and (interval_days is None or interval_days < 1):
            raise ServiceError(400, "定时生成需指定有效周期（至少 1 天）")
        return self._resolve_generation_scope(current_user, scenario_id, scope)

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
        file_path: Optional[str] = None,
        scenario_id: Optional[int] = None,
        format: str = "markdown",
        scheduled: bool = False,
        interval_days: Optional[int] = None,
    ):
        """生成态势报告。

        - 内容由调用方给出；数据范围仅用于场景绑定校验（不指定单个用户）。
        - 场景管理员/用户：scenario_id 强制为本人绑定场景。
        - 格式：format 取值 markdown/html/pdf。
        - **不支持定时**：定时报告要求到期时能按真实数据重新生成，而本接口的 content
          是外部给的、无法重生成。以前允许传 scheduled=True，结果写了一条
          next_run_at 为空的记录 —— 出现在「定时报告」列表里显示「下次生成 —」，
          调度器却永远不认（它要求 next_run_at 非空）。现在直接拒绝，指向 /reports/generate。
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
        if scheduled:
            raise ServiceError(
                400,
                "本接口不支持定时报告；定时报告请用 POST /reports/generate 创建",
            )

        _, scenario_id, _ = self._resolve_generation_scope(current_user, scenario_id, "self")

        report = Report(
            generated_by=current_user.id,
            title=title.strip(),
            report_type=report_type,
            target_user_id=None,
            content=content,
            file_path=file_path,
            scenario_id=scenario_id,
            format=format,
            scheduled=False,
            interval_days=None,
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
        format: str = "markdown",
        scheduled: bool = False,
        interval_days: Optional[int] = None,
    ):
        """生成态势报告：统计 + 算法多视图研判 + NL 态势分析/风险规避指导。

        数据范围：管理员 = 全平台 / 本场景聚合 或 本人个人数据；场景用户固定为本人数据。
        内容由服务端基于真实 RiskEvent 与推理记录（含 explain_data）组装，
        落库 report.content 与 report.report_data（结构化，供前端渲染图表）。

        scheduled=True 时同时登记为定时报告：这条记录本身就是定时报告的载体，
        生成时立刻产出一份内容，并把 next_run_at 推到下一个周期，
        到期由后台调度器原地重新生成（见 run_due_scheduled_reports）。
        """
        role, scenario_id, scope = self._validate_generate_inputs(
            current_user, title, scenario_id, scope, format, scheduled, interval_days
        )

        now = datetime.now(timezone.utc)
        report = Report(
            generated_by=current_user.id,
            title=title.strip(),
            report_type="USER_SNAPSHOT" if scope == "self" else "SCENE_SNAPSHOT",
            target_user_id=None,
            scenario_id=scenario_id,
            content="",
            format=format,
            scheduled=scheduled,
            interval_days=interval_days if scheduled else None,
            next_run_at=(now + timedelta(days=interval_days)) if scheduled else None,
            generated_at=now,
        )
        self._refresh(report, current_user, role=role, scenario_id=scenario_id, scope=scope)
        self.db.add(report)
        self.commit()
        return ok(data=self._serialize(report, include_report_data=True), message="报告已生成")

    # ------------------------------------------------------------------
    # 内容刷新（首次生成与定时到期的重新生成共用同一条路径）
    # ------------------------------------------------------------------
    def _refresh(self, report, owner, role=None, scenario_id=None, scope=None):
        """按 owner 的权限范围重算报告内容，就地写回 report 对象（不提交）。

        定时报告到期时复用本方法：报告的身份（generated_by / report_type）不变，
        只有 content / report_data / generated_at 跟着最新数据走，
        所以定时报告在列表里始终是一条记录，不会每次触发都堆一份副本。
        """
        if role is None:
            # 超管保留建报告时选定的场景；其余角色重新钉到本人绑定场景，
            # 避免账号换绑场景后定时任务因越权校验失败而中断。
            requested = (
                report.scenario_id
                if getattr(owner, "role", None) == ROLE_SUPER_ADMIN
                else None
            )
            role, scenario_id, scope = self._resolve_generation_scope(
                owner, requested, self._scope_of(report)
            )
        report.scenario_id = scenario_id

        # 1) 汇总真实数据（风险事件 + 推理记录，按三级角色 + 数据范围隔离）
        events = self._gather_events(owner, role, scenario_id, scope)
        records = self._gather_records(owner, role, scenario_id, scope)

        # 2) 组装 report_data（不含模型版本评价，模型评价在模型中心单独导出）
        report_data = self._build_report_data(
            title=report.title,
            scenario_id=scenario_id,
            scope=scope,
            role=role,
            current_user=owner,
            events=events,
            records=records,
        )

        # 3) 自然语言态势分析 + 风险规避指导（6.10.4：规则+场景模板，LLM 仅 P2 润色）
        from app.services.report_nl import generate_report_narrative

        report_data.update(generate_report_narrative(report_data))

        # 4) 渲染正文（Markdown，供导出与纯文本查看）
        report.content = self._render_content(report_data)
        report.report_data = report_data
        report.generated_at = datetime.now(timezone.utc)
        return report

    @staticmethod
    def _scope_of(report) -> str:
        """从报告类型反推数据范围：USER_SNAPSHOT=本人数据，SCENE_SNAPSHOT=聚合数据。"""
        return "self" if report.report_type == "USER_SNAPSHOT" else "all"

    # ------------------------------------------------------------------
    # 数据汇总（三级角色 + 数据范围隔离口径）
    # ------------------------------------------------------------------
    def _gather_events(self, current_user, role, scenario_id, scope):
        """汇总风险事件。

        - SUPER_ADMIN：**聚合范围**下仅平台数据集派生的事件（公司/个人数据集对超管不可见）；
        - SCENARIO_ADMIN：绑定场景内全部风险事件；
        - scope=self（个人数据）：只按创建者限定为当前账号本人。
          个人数据 = 自己产生的事件，不叠加数据集可见性 —— 否则超管自己的记录
          会因为数据集归属被静默筛掉。
        """
        if role in (ROLE_SCENARIO_ADMIN, ROLE_SCENARIO_USER) and scenario_id is None:
            # 场景角色必须有绑定场景。这里返回空，而不是退化成「不加场景过滤」——
            # 后者一旦账号层允许解绑场景，报告会静默变成全平台可见。
            return []

        stmt = select(RiskEvent)
        if scenario_id is not None:
            stmt = stmt.where(RiskEvent.scenario_id == scenario_id)

        # 可见性规则：与 scope 无关
        if role == ROLE_SUPER_ADMIN and scope != "self":
            stmt = stmt.join(Dataset, Dataset.id == RiskEvent.dataset_id).where(
                Dataset.visibility == DATASET_VISIBILITY_PLATFORM
            )

        # 数据范围
        if scope == "self":
            stmt = stmt.where(RiskEvent.created_by_user_id == current_user.id)
        stmt = stmt.order_by(RiskEvent.occurred_at.desc())
        return self.db.scalars(stmt).all()

    @staticmethod
    def _explain_expression():
        """explain_data 的 SQL 侧裁剪：只保留报告真正读到的键。

        消费点（改动前逐行核对过）：
        - ``_prediction`` 读 ``probability`` / ``class_distribution``；
        - ``_model_analysis`` 读 ``views`` / ``view_weights`` / ``calculation_method``
          / ``prediction_label``；
        - ``_feature_analysis`` 读 ``feature_evidence`` / ``calculation_method``。

        整列反序列化实测峰值 748 MB，是全量加载里最大的一块；其中
        ``input_features`` 在报告生成中完全没被读过。

        必须套 ``type_coerce(..., JSONB)``：``func.jsonb_build_object`` 的返回类型是
        NullType，结果处理器为 None，psycopg2 会把 jsonb 原样当字符串返回，
        下游 ``record.explain_data.get(...)`` 会直接 AttributeError。
        """
        pairs = []
        for key in _REPORT_EXPLAIN_KEYS:
            pairs.append(key)
            pairs.append(InferenceRecord.explain_data[key])
        return type_coerce(func.jsonb_build_object(*pairs), JSONB)

    def _gather_records(self, current_user, role, scenario_id, scope):
        """汇总推理记录（含所属模型版本）。

        - SUPER_ADMIN：**聚合范围**下仅平台数据集训练出的模型版本；
        - SCENARIO_ADMIN：绑定场景内全部记录（含未发布模型）；
        - 场景用户：仅已发布模型（可见性规则，不因 scope=self 而放开）；
        - scope=self（个人数据）：只按创建者限定为当前账号本人。

        这里**不能**写成 ``select(InferenceRecord, ModelVersion)`` 全量加载实体：
        ``inference_record.explain_data`` 整列 2394 行反序列化实测 748 MB，
        ``model_version`` 的 training_parameters / evaluation_metrics /
        model_attributes / ai_evaluation 四个 JSONB 又占约 503 MB，
        叠加峰值 1334 MB，远超 sb-api 的 MemoryMax=900MiB —— 报告生成必被 OOM kill。
        只取用得到的列（裁剪口径见 ``_explain_expression``），实测降到 215 MB。

        返回值仍是 ``(记录, 模型版本)`` 二元组列表，与 ``_build_report_data`` 的解包一致。
        记录是 Row 而不是 ORM 实例：它的属性访问（.id / .executed_at /
        .is_risk_event / .risk_score / .prediction_label / .explain_data）
        与原来的 InferenceRecord 对下游完全等价。
        """
        if role in (ROLE_SCENARIO_ADMIN, ROLE_SCENARIO_USER) and scenario_id is None:
            return []

        stmt = (
            select(
                InferenceRecord.id,
                InferenceRecord.executed_at,
                InferenceRecord.is_risk_event,
                InferenceRecord.risk_score,
                InferenceRecord.prediction_label,
                self._explain_expression().label("explain_data"),
                ModelVersion,
            )
            .join(ModelVersion, ModelVersion.id == InferenceRecord.model_version_id)
            .options(
                load_only(
                    ModelVersion.id,
                    ModelVersion.dataset_id,
                    ModelVersion.algorithm_id,
                )
            )
        )
        if scenario_id is not None:
            stmt = stmt.where(ModelVersion.scenario_id == scenario_id)

        # 可见性规则：与 scope 无关，不能因为「只看本人」就放开
        if role == ROLE_SCENARIO_USER:
            stmt = stmt.where(
                ModelVersion.status.in_(USER_VISIBLE_MODEL_STATUSES),
            )
        elif role == ROLE_SUPER_ADMIN and scope != "self":
            stmt = stmt.join(Dataset, Dataset.id == ModelVersion.dataset_id).where(
                Dataset.visibility == DATASET_VISIBILITY_PLATFORM
            )

        # 数据范围
        if scope == "self":
            stmt = stmt.where(InferenceRecord.user_id == current_user.id)
        stmt = stmt.order_by(InferenceRecord.executed_at.desc())
        return [(row, row.ModelVersion) for row in self.db.execute(stmt).all()]

    # ------------------------------------------------------------------
    # 组装报告结构化数据 report_data（不含模型版本评价）
    # ------------------------------------------------------------------
    def _build_report_data(
        self, title, scenario_id, scope, role, current_user, events, records
    ):
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

        # 阈值只取一次：overview 判级、key_events 判级、data_notes 声明都要用
        thresholds = risk_view.load_thresholds(self.db, current_user)

        report_info = {
            "title": title.strip(),
            "generated_at": beijing_now_str("%Y-%m-%d %H:%M"),
            "report_period": period,
            "generated_by": getattr(current_user, "display_name", None)
            or getattr(current_user, "username", ""),
            "scenario_name": scenario.name if scenario else None,
            "scenario_code": scenario.code if scenario else None,
            "data_scope": self._data_scope_label(role, scope, scenario_id),
            "datasets": [{"logical_id": k, "version": v} for k, v in datasets.items()],
            "algorithms": [{"code": k, "name": v} for k, v in algorithms.items()],
            "model_versions": [{"id": k, "algorithm_code": v} for k, v in models.items()],
        }

        overview = self._overview(events, records, thresholds)
        model_analysis = self._model_analysis(records)
        key_events, key_events_total = self._key_events(
            events, records, thresholds=thresholds
        )

        return {
            "report_info": report_info,
            "overview": overview,
            "prediction": self._prediction(records),
            "model_analysis": model_analysis,
            "feature_analysis": self._feature_analysis(records),
            "trend": self._trend(records),
            # key_events 是概率最高的前 N 条；总数单独给，正文/界面据此说明"共 N 起"
            "key_events": key_events,
            "key_events_total": key_events_total,
            "data_notes": self._data_notes(
                report_info, overview, model_analysis, thresholds, scenario_id
            ),
        }

    @staticmethod
    def _data_scope_label(role, scope, scenario_id=None) -> str:
        """数据范围的中文口径，供报告正文与详情页展示。

        超管也要看 scenario_id：指定了具体场景，统计范围就是那一个场景，
        再标「全平台数据」与实际口径不符（实测与场景管理员的同场景报告逐条一致）。
        """
        if scope == "self":
            return "本人个人数据"
        if role == ROLE_SUPER_ADMIN and scenario_id is None:
            return "全平台数据"
        return "本场景全部用户数据"

    @staticmethod
    def _period(times):
        """数据范围的起止日期（**按北京时间取日**）。

        库里是 UTC，直接 strftime 会拿到 UTC 的日期：例如北京时间 08-22 01:00
        （= UTC 08-21 17:00）会被算成 08-21，报告期整体提前一天。
        比较大小仍用原始 datetime（比的是时刻），只在取日时换算。
        """
        if not times:
            return None
        lo, hi = min(times), max(times)
        lo_s, hi_s = to_beijing(lo).strftime("%Y-%m-%d"), to_beijing(hi).strftime("%Y-%m-%d")
        return lo_s if lo_s == hi_s else f"{lo_s} 至 {hi_s}"

    @staticmethod
    def _overview(events, records, thresholds=None):
        """报告总览。

        等级计数按**生成报告的那个账号**的阈值重算（见 risk_view）：
        报告是他自己的风险视图，不是把别人算好的等级相加。
        """
        total = len(records)
        risk_count = sum(1 for r, _m in records if r.is_risk_event)
        normal_count = total - risk_count
        # 直接走 risk_view.aggregate：原来经 SituationSnapshotService._aggregate 中转，
        # 而那个静态方法只是 `return risk_view.aggregate(events, thresholds or {})` 的空壳。
        stats = risk_view.aggregate(events, thresholds or {})
        risk_scores = [
            float(r.risk_score) for r, _m in records if r.is_risk_event and r.risk_score is not None
        ]
        avg_risk_prob = (sum(risk_scores) / len(risk_scores)) if risk_scores else None

        # 排序键统一换算成 aware 时间：原来用 naive 的 datetime(1970,1,1) 兜底，
        # 只要有一条记录 executed_at 为空，就会和库里的 aware 值比较而抛 TypeError（500）。
        ordered = sorted(
            records,
            key=lambda x: to_beijing(x[0].executed_at) if x[0].executed_at else _SORT_EPOCH,
        )
        trend = "样本不足，无法判断"
        if total >= TREND_MIN_SAMPLES:
            half = total // 2

            def ratio(recs):
                if not recs:
                    return 0.0
                return sum(1 for r, _m in recs if r.is_risk_event) / len(recs)

            r1, r2 = ratio(ordered[:half]), ratio(ordered[half:])
            if r2 - r1 > TREND_DELTA:
                trend = "上升"
            elif r1 - r2 > TREND_DELTA:
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
            if prob is not None and LOW_CONFIDENCE_MIN <= float(prob) <= LOW_CONFIDENCE_MAX:
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

        bucket_count = len(PROB_BUCKET_LABELS)
        counts = [0] * bucket_count
        for s in risk_scores:
            for i in range(bucket_count):
                if PROB_BUCKET_EDGES[i] <= s < PROB_BUCKET_EDGES[i + 1]:
                    counts[i] += 1
                    break
        risk_prob_buckets = [
            {"range": PROB_BUCKET_LABELS[i], "count": counts[i]} for i in range(bucket_count)
        ]

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
            day = to_beijing(record.executed_at).strftime("%m-%d")
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
    def _key_events(events, records, limit=10, thresholds=None):
        """重点风险事件 → ``(前 limit 条, 总起数)``。

        等级按报告生成者的阈值重算，不透传落库的创建者视角。
        **总起数必须一起返回**：只给截断后的列表，正文会把它当成总数
        （历史问题：666 条风险、604 条高危的报告写着「重点风险事件 10 起」）。
        """
        thresholds = thresholds or {}
        event_map = {e.inference_record_id: e for e in events}
        key = []
        for record, _model in records:
            e = event_map.get(record.id)
            if e is None:
                continue
            level = risk_view.level_of(e, thresholds)
            key.append(
                {
                    "time": to_beijing(e.occurred_at).strftime("%Y-%m-%d %H:%M") if e.occurred_at else None,
                    "risk_level": RISK_LEVEL_LABELS.get(level, level),
                    "probability": float(e.risk_score) if e.risk_score is not None else None,
                    "risk_type": e.risk_type,
                    "status": RISK_STATUS_LABELS.get(e.status, e.status),
                    "key_features": list((e.raw_features or {}).keys())[:5],
                }
            )
        key.sort(key=lambda x: (x["probability"] is not None, x["probability"] or 0), reverse=True)
        return key[:limit], len(key)

    @staticmethod
    def _data_notes(report_info, overview, model_analysis, thresholds=None, scenario_id=None):
        parts = [
            f"数据范围：{report_info.get('data_scope')}；样本（推理记录）{overview.get('total_inferences', 0)} 条。"
        ]
        # 阈值随账号：同一份数据在不同账号下等级计数不同，必须声明，否则读者会当成客观事实
        medium, high = risk_view.thresholds_for(thresholds or {}, scenario_id)
        configured = scenario_id is not None and int(scenario_id) in (thresholds or {})
        fallback = "" if configured else "（本账号未配置该场景阈值，使用系统默认值）"
        parts.append(
            f"风险等级按本报告生成账号的阈值判定：中危 ≥ {medium:g}、高危 ≥ {high:g}{fallback}；"
            "同一份数据在不同账号的阈值下，等级计数可能不同。"
        )
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
            "加权贡献值的计算方式见“特征加权条件概率”说明。"
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
            f"- 风险样本平均概率：{(ov.get('avg_risk_prob') or 0):.3f}",
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

        lines += ["", f"## {SECTION_VIEWS}"]
        for m in report_data.get("model_analysis", []):
            name = m["algorithm_name"] or m["algorithm_code"] or "模型"
            if not m["has_views"]:
                lines.append(f"- {name}（模型 {m['model_version_id']}）：无独立视图")
            else:
                lines.append(f"- {name}（模型 {m['model_version_id']}）：")
                for v in m["views"]:
                    mark = "✓一致" if v["consistent_with_final"] else "✗分歧"
                    lines.append(f"  - {v['name']}：预测 {v['predicted_label']}（{mark}）")

        lines += ["", f"## {SECTION_FEATURES}"]
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
        shown_events = report_data.get("key_events") or []
        if shown_events:
            total = report_data.get("key_events_total")
            if total is None:
                # 修复前生成的报告没有总起数：宁可不写数量，也不要拿截断后的长度冒充
                lines.append("重点风险事件：")
            elif total > len(shown_events):
                lines.append(
                    f"重点风险事件（共 {total} 起，下列为概率最高的 {len(shown_events)} 起）："
                )
            else:
                lines.append(f"重点风险事件（共 {total} 起）：")
            for e in shown_events:
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
        page: int = 1,
        page_size: int = 10,
    ):
        """报告列表（按三级角色隔离）。

        系统管理员：全部报告；
        场景管理员：自己绑定场景下的报告；
        场景用户：本人生成的报告。
        """
        self.require_login(current_user)
        role = getattr(current_user, "role", None)
        stmt = select(Report)
        if role == ROLE_SCENARIO_ADMIN:
            scid = getattr(current_user, "scenario_id", None)
            if scid is None:
                stmt = stmt.where(false())  # 未绑定场景：看不到任何报告
            else:
                stmt = stmt.where(Report.scenario_id == scid)
        elif role != ROLE_SUPER_ADMIN:
            stmt = stmt.where(
                or_(
                    Report.generated_by == current_user.id,
                    Report.target_user_id == current_user.id,
                )
            )
        stmt = stmt.order_by(Report.generated_at.desc())
        result = paginate(self.db, stmt, page, page_size)
        result["items"] = [self._serialize(r, include_summary=False) for r in result["items"]]
        return ok(data=result)

    def _load_visible(self, current_user, report_id: int):
        """按三级角色取一条可见的报告，不可见则抛 403（详情与导出共用）。"""
        self.require_login(current_user)
        report = self._get(report_id)
        role = getattr(current_user, "role", None)
        if role == ROLE_SCENARIO_ADMIN and report.scenario_id != getattr(current_user, "scenario_id", None):
            raise ServiceError(403, "无权限操作")
        if role not in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN) and not self._can_view(current_user, report):
            raise ServiceError(403, "无权限操作")
        return report

    @service_call
    def get(self, current_user, report_id: int):
        """报告详情（普通用户仅本人生成或定向给自己的报告）。"""
        report = self._load_visible(current_user, report_id)
        return ok(data=self._serialize(report, include_report_data=True))

    def _export_inputs(self, current_user, report_id: int, fmt: Optional[str]):
        """导出前的权限与格式校验，返回 (report, target_format)。

        返回整条 report 而不是拆散的字段：导出 html/pdf 时还要用 report_data 补图表。
        """
        report = self._load_visible(current_user, report_id)
        target = (fmt or report.format or "markdown").lower()
        err = validate_enum(target, REPORT_FORMATS, "format")
        if err:
            raise ServiceError(400, err)
        return report, target

    def load_export_source(self, report_id: int):
        """取导出所需的标题、正文与结构化数据（后台导出任务用；权限已在提交时校验）。"""
        report = self._get(report_id)
        return report.title, report.content or "", report.report_data

    @service_call
    def export(self, current_user, report_id: int, fmt: Optional[str] = None):
        """导出报告文件（markdown / html / pdf）。

        不传 fmt 时按报告自身的格式导出；传了则以传入值为准 —— 同一条报告
        可以随时换个格式下载，不必重建。
        """
        report, target = self._export_inputs(current_user, report_id, fmt)
        try:
            exported = build_export(
                report.title, report.content or "", report.id, target, report.report_data
            )
        except Exception:
            logger.exception("报告导出失败: report_id=%s format=%s", report.id, target)
            raise ServiceError(500, f"报告导出失败（{target}）")
        return ok(
            data={
                "content": exported.content,
                "filename": exported.filename,
                "media_type": exported.media_type,
                "format": target,
            },
            message="导出成功",
        )

    @service_call
    def submit_export(self, current_user, report_id: int, fmt: Optional[str] = None):
        """提交导出任务：pdf 交后台渲染，markdown / html 立即完成。

        权限与格式校验和 export() 共用同一套（_export_inputs），失败语义不变。
        """
        from app.services.export_job_service import (
            create_finished_job,
            create_job,
            is_running,
        )

        report, target = self._export_inputs(current_user, report_id, fmt)
        rid, title, content = report.id, report.title, report.content or ""

        if target == "pdf":
            if not is_running():
                raise ServiceError(503, "报告导出执行器未启用，无法提交后台导出")
            job_id = create_job(
                user_id=current_user.id, report_id=rid, fmt=target, title=title
            )
            message = "导出任务已提交"
        else:
            try:
                exported = build_export(
                    title, content, rid, target, getattr(report, "report_data", None)
                )
            except Exception:
                logger.exception("报告导出失败: report_id=%s format=%s", rid, target)
                raise ServiceError(500, f"报告导出失败（{target}）")
            job_id = create_finished_job(
                user_id=current_user.id, report_id=rid, fmt=target, title=title,
                exported=exported,
            )
            message = "导出完成"
        return ok(data={"job_id": job_id, "report_id": rid, "format": target}, message=message)

    @service_call
    def get_export_job(self, current_user, job_id: str):
        """查询导出任务进度；任务不存在、已过期或不属于当前用户时 404。"""
        from app.services.export_job_service import get_job

        self.require_login(current_user)
        view = get_job(job_id, current_user.id)
        if view is None:
            raise ServiceError(404, "导出任务不存在或已过期")
        return ok(data=view)

    @service_call
    def list_export_jobs(self, current_user):
        """当前用户的导出任务列表（刷新/切页回来能恢复「已经好了」的状态）。"""
        from app.services.export_job_service import list_jobs

        self.require_login(current_user)
        return ok(data=list_jobs(current_user.id))

    # ------------------------------------------------------------------
    # 异步生成（提交 → 轮询 → 通知；见 app/services/report_generate_runner.py）
    # ------------------------------------------------------------------

    @service_call
    def submit_generate(
        self,
        current_user,
        title: str,
        scenario_id: Optional[int] = None,
        scope: str = "self",
        format: str = "markdown",
        scheduled: bool = False,
        interval_days: Optional[int] = None,
    ):
        """提交异步生成任务：立刻返回 job_id，真正的生成交给后台线程。

        入参校验走与 generate() 同一条边界，参数不对仍然在 POST 时就报 400 / 403，
        不会把一个注定失败的任务丢进队列。执行器未启动时 503（与导出同一套语义）。
        """
        from app.services.report_generate_runner import create_job, is_running

        self._validate_generate_inputs(
            current_user, title, scenario_id, scope, format, scheduled, interval_days
        )
        if not is_running():
            raise ServiceError(503, "报告生成执行器未启用，无法提交后台生成")
        job_id = create_job(
            user_id=current_user.id,
            title=title.strip(),
            params={
                "scenario_id": scenario_id,
                "scope": scope,
                "format": format,
                "scheduled": scheduled,
                "interval_days": interval_days,
            },
        )
        return ok(data={"job_id": job_id}, message="生成任务已提交")

    @service_call
    def get_generate_job(self, current_user, job_id: str):
        """查询生成任务进度；任务不存在、已过期或不属于当前用户时 404。"""
        from app.services.report_generate_runner import get_job

        self.require_login(current_user)
        view = get_job(job_id, current_user.id)
        if view is None:
            raise ServiceError(404, "生成任务不存在或已过期")
        return ok(data=view)

    @service_call
    def list_generate_jobs(self, current_user):
        """当前用户的生成任务列表（刷新 / 切页回来能恢复「还在跑」的状态）。"""
        from app.services.report_generate_runner import list_jobs

        self.require_login(current_user)
        return ok(data=list_jobs(current_user.id))

    @service_call
    def read_export_file(self, current_user, job_id: str):
        """取导出任务产出的文件（与老接口同一份 filename / media_type）。"""
        from app.services.export_job_service import STATUS_FAILED, get_job_record

        self.require_login(current_user)
        job = get_job_record(job_id, current_user.id)
        if job is None:
            raise ServiceError(404, "导出任务不存在或已过期")
        if job.status == STATUS_FAILED:
            raise ServiceError(500, job.error or "报告导出失败")
        if job.content is None:
            raise ServiceError(409, "导出任务尚未完成")
        return ok(
            data={
                "content": job.content,
                "filename": job.filename,
                "media_type": job.media_type,
                "format": job.fmt,
                "report_id": job.report_id,
            }
        )

    @service_call
    def update_schedule(
        self,
        current_user,
        report_id: int,
        scheduled: bool,
        interval_days: Optional[int] = None,
    ):
        """保存账号设置的定时记录。

        启用时把 next_run_at 推到「现在 + 周期」，关闭时清空 —— 调度器只看
        (scheduled, next_run_at) 两列，所以这两个动作就等于登记/注销一条定时任务。
        本接口只改配置，不立刻重新生成报告（首次内容在创建报告时已经产出）。
        """
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
        report.next_run_at = (
            datetime.now(timezone.utc) + timedelta(days=interval_days) if scheduled else None
        )
        self.commit()
        return ok(data=self._serialize(report), message="定时配置已保存")

    @service_call
    def list_scheduled(self, current_user):
        """当前账号配置的定时报告（跟随账号，只返回本人生成的）。"""
        self.require_login(current_user)
        stmt = (
            select(Report)
            .where(Report.generated_by == current_user.id, Report.scheduled.is_(True))
            .order_by(Report.next_run_at.asc().nulls_last(), Report.generated_at.desc())
        )
        return ok(data=[self._serialize(r) for r in self.db.scalars(stmt).all()])

    # ------------------------------------------------------------------
    # 定时报告：到期扫描与重新生成（供后台调度器调用，不走 HTTP）
    # ------------------------------------------------------------------
    def run_due_scheduled_reports(self, batch: int = 20) -> int:
        """处理一批到期的定时报告，返回成功刷新的条数。

        抢占顺序：先用 SELECT ... FOR UPDATE SKIP LOCKED 锁住到期行，把 next_run_at
        推进到下一周期并提交，然后才做耗时的重新生成。这样多进程部署时同一条记录
        只会被一个进程拿到，生成期间也不会被别的进程重复触发。
        重新生成失败时回退为「10 分钟后重试」，不占满整个周期。
        """
        now = datetime.now(timezone.utc)
        due = list(
            self.db.scalars(
                select(Report)
                .where(
                    Report.scheduled.is_(True),
                    Report.next_run_at.is_not(None),
                    Report.next_run_at <= now,
                )
                .order_by(Report.next_run_at.asc())
                .limit(batch)
                .with_for_update(skip_locked=True)
            ).all()
        )
        if not due:
            self.db.rollback()
            return 0

        claimed: list[tuple[int, int]] = []
        for report in due:
            owner = self.db.get(AppUser, report.generated_by)
            if owner is None or getattr(owner, "status", None) != USER_STATUS_ENABLED:
                # 创建者已删除/停用：停掉定时，避免每轮空转刷日志
                report.scheduled = False
                report.next_run_at = None
                logger.warning("定时报告 %s 的创建者不可用，已停用定时", report.id)
                continue
            report.next_run_at = self._advance_next_run(
                report.next_run_at, now, report.interval_days
            )
            claimed.append((report.id, owner.id))
        self.db.commit()

        refreshed = 0
        for report_id, owner_id in claimed:
            report = self.db.get(Report, report_id)
            owner = self.db.get(AppUser, owner_id)
            if report is None or owner is None:
                # 抢占提交与这里重新取行之间，报告/账号可能已被删除。
                # 原来直接 self._refresh(report, owner) 会在 None 上取属性抛 AttributeError。
                logger.warning("定时报告 %s 或其创建者已不存在，跳过本轮", report_id)
                continue
            try:
                self._refresh(report, owner)
                self.db.commit()
                refreshed += 1
                logger.info(
                    "定时报告已重新生成: id=%s title=%s 下次=%s",
                    report.id,
                    report.title,
                    report.next_run_at,
                )
            except Exception:  # noqa: BLE001 - 单条失败不影响同批其它报告
                self.db.rollback()
                stale = self.db.get(Report, report_id)
                if stale is not None:
                    stale.next_run_at = datetime.now(timezone.utc) + timedelta(
                        minutes=RETRY_AFTER_MINUTES
                    )
                    self.db.commit()
                logger.exception("定时报告重新生成失败: id=%s", report_id)
        return refreshed

    @staticmethod
    def _advance_next_run(current, now, interval_days):
        """把下次生成时刻推进到「原定时刻之后的下一个未来时刻」。

        以原定时刻为锚点累加周期，而不是直接用 now —— 每次触发都用 now 会累积漂移，
        时间点会一天天往后跑。服务停机较久时一次性跳过欠下的周期，不补跑历史，
        避免重启后瞬间生成一堆报告。
        """
        step = timedelta(days=max(1, int(interval_days or 1)))
        if current is None:
            return now + step
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        nxt = current + step
        while nxt <= now:
            nxt += step
        return nxt

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
