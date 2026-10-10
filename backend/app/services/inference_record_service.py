"""推理记录 Service（InferenceRecord）—— 单条样本推理 + 风险事件生成触发。

对应需求文档章节：3.1（固定字段校验）、6.7.3（仅 PUBLISHED 模型可推理）、
5.2/5.3（风险事件生成）、6.8（本人推理记录数据隔离）。

模型：app.models.inference_record.InferenceRecord。

关键业务规则：
1. 推理只接收输入特征，不要求用户填写分类标签（需求 3.1.3）。
2. 仅 PUBLISHED 模型可执行新推理（需求 6.7.3.3 / 6.7.5.6）。
3. 输入校验：固定字段必须齐全（缺失/重名/类型不匹配禁止推理）、枚举字段按值域校验（需求 3.1.2/3.1.5）。
4. 推理完成后：若预测标签属于该数据集的正类（风险类，需求 6.4.1 显式映射）→ 生成 RiskEvent；
   正常结果只保存推理记录（需求 4.x）。
5. 普通用户只能查询本人推理记录；管理员可查询全部（需求 6.8.1/6.8.3）。
"""
import csv
import io
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.models.dataset import Dataset
from app.models.inference_record import InferenceRecord
from app.models.model_version import ModelVersion
from app.models.risk_event import RiskEvent
from app.models.user_ai_setting import UserAISetting
from app.schemas.common import ok
from app.services import risk_view
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    ADMIN_ROLES,
    DATASET_RISK_TYPES,
    DATASET_VISIBILITY_COMPANY,
    DATASET_VISIBILITY_PLATFORM,
    EVALUATION_AUDIENCE_MANAGEMENT,
    EVALUATION_AUDIENCE_USER,
    INFERENCE_ALLOWED_MODEL_STATUSES,
    ROLE_SCENARIO_ADMIN,
    ROLE_SUPER_ADMIN,
    MODEL_STATUS_PUBLISHED,
    DATASET_POSITIVE_LABELS,
    dataset_display_name_of,
    evaluation_audience,
    is_risk_label,
)
from app.services.risk_event_service import RiskEventService
from app.utils.common import (
    get_logger,
    normalize_input_features,
    paginate,
    row_to_dict,
    validate_input_features,
)

logger = get_logger("inference_record")

#: fields_schema 里表示数值的 type 取值（与 dataset_file_reader 的约定一致）
_NUMERIC_TYPES = {"numeric", "real", "float", "double", "integer", "int"}

#: 管理级角色（场景管理员 / 推理记录查看）可用的数据集可见性口径。
#: 与 constants.DATASET_VISIBILITY_* 同名同值，集中一处避免多处硬编码 "platform"/"company"。
_INFERABLE_VISIBILITIES = (DATASET_VISIBILITY_PLATFORM, DATASET_VISIBILITY_COMPANY)


def _coerce_value(value: Any, field_type: Optional[str]) -> Any:
    """按字段类型把 CSV 里的字符串转成推理服务期望的类型。

    转不动就原样返回 —— 让 validate_input_features 报出可读的错误，
    不在这里把问题吞掉。
    """
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return value
    if str(field_type or "").lower() in _NUMERIC_TYPES:
        try:
            number = float(text)
        except (TypeError, ValueError):
            return value
        return int(number) if number.is_integer() else number
    return value


def _explanation_artifact_for(explain_data: dict[str, Any] | None, role: str | None) -> dict:
    """取该受众那一格的 AI 研判产物。

    改造前的结构是单格（``ai_explanation`` 顶层直接带 markdown），没有受众键。
    这种老内容对两种受众都可见 —— 升级后历史评价不会突然消失，等各自重新生成
    时再自然收敛到分受众结构（见 ``_explanation_artifacts``）。
    """
    artifact = (explain_data or {}).get("ai_explanation")
    if not isinstance(artifact, dict):
        return {}
    if "markdown" in artifact:
        return artifact
    return artifact.get(evaluation_audience(role)) or {}


def _explanation_artifacts(explain_data: dict[str, Any] | None) -> dict[str, dict]:
    """把 ``ai_explanation`` 归一成 ``{受众: 产物}``，供写入前展开老结构。"""
    artifact = (explain_data or {}).get("ai_explanation")
    if not isinstance(artifact, dict):
        return {}
    if "markdown" in artifact:
        # 老的单格产物：两边各放一份，之后各自重新生成时覆盖自己那份。
        return {
            EVALUATION_AUDIENCE_MANAGEMENT: dict(artifact),
            EVALUATION_AUDIENCE_USER: dict(artifact),
        }
    return {key: value for key, value in artifact.items() if isinstance(value, dict)}


class InferenceRecordService(ServiceBase):
    """推理记录：执行推理（触发风险事件生成）/ 查询 / 删除。"""

    def __init__(self, db):
        super().__init__(db)
        self._risk_event_service = RiskEventService(db)

    def _get(self, record_id: int) -> InferenceRecord:
        record = self.db.get(InferenceRecord, record_id)
        if record is None:
            raise ServiceError(404, "推理记录不存在")
        return record

    def _to_dict(
        self,
        record: InferenceRecord,
        current_user=None,
        thresholds=None,
        include_explain: bool = True,
    ) -> dict:
        """序列化推理记录，并补全展示字段（场景/数据集/算法/风险类型/关联风险事件）。

        ``risk_level`` 按**查看者**的阈值重算（落库值是创建者视角，见 risk_view）。
        仅对确实判为风险的记录（``risk_score`` 非空）重算，未判风险的记录保持 None，
        不能把「无风险」写成 LOW。

        ``thresholds`` 可由调用方预先加载后传入，避免列表逐条查询造成 N+1。

        ``include_explain=False`` 用于列表：``explain_data`` 与 ``generated_explanation``
        实测合计占单条体积的九成以上（20 条约 415KB），而列表页两个都不读 ——
        「查看解释」弹窗走 ``GET /inference-records/{id}/explain`` 单独取。
        详情与预测返回保持下发。
        """
        data = row_to_dict(record)
        model = self.db.get(ModelVersion, record.model_version_id)
        if model is not None:
            data["scenario_id"] = model.scenario_id
            data["scenario_code"] = model.scenario.code if model.scenario else None
            data["algorithm_id"] = model.algorithm_id
            data["algorithm_name"] = model.algorithm.display_name if model.algorithm else None
            dataset = self.db.get(Dataset, model.dataset_id)
            if dataset is not None:
                data["dataset_id"] = dataset.id
                data["dataset_logical_id"] = dataset.logical_id
                data["dataset_name"] = dataset_display_name_of(dataset)
                data["dataset_version"] = dataset.version
                data["risk_type"] = DATASET_RISK_TYPES.get(dataset.logical_id)
        # original_label 只是 prediction_label 的别名（值就是模型预测标签，不是数据集原始真值）
        data["original_label"] = record.prediction_label
        event = self.db.scalar(
            select(RiskEvent).where(RiskEvent.inference_record_id == record.id)
        )
        data["risk_event_id"] = event.id if event is not None else None
        # 风险等级按查看者阈值重算（仅对判为风险的记录；未判风险保持 None）
        if current_user is not None and record.risk_score is not None:
            if thresholds is None:
                thresholds = risk_view.load_thresholds(self.db, current_user)
            scenario_id = (
                event.scenario_id if event is not None else data.get("scenario_id")
            )
            medium, high = risk_view.thresholds_for(thresholds, scenario_id)
            data["risk_level"] = risk_view.classify(float(record.risk_score), medium, high)
        # 列表不下发这两个大字段：explain_data 实测占单条 82%，generated_explanation 占 84%
        # （20 条约 415KB）。列表页两个都不读 —— 「查看解释」弹窗走
        # GET /inference-records/{id}/explain，详情走 GET /inference-records/{id}。
        # 注意 row_to_dict 会把 ORM 列原样带出来，所以「不下发」必须显式 pop，
        # 否则会退化成「绕过角色裁剪、下发原始值」。
        if include_explain:
            data["generated_explanation"] = self._saved_explanation_for_role(
                record, getattr(current_user, "role", None)
            )
            if current_user is not None:
                from app.schemas.explanation_contract import explanation_for_role

                data["explain_data"] = explanation_for_role(
                    record.explain_data, getattr(current_user, "role", None)
                )
        else:
            data.pop("generated_explanation", None)
            data.pop("explain_data", None)
        # Model evaluation is a saved model artifact, independent of this
        # sample's explanation. Reuse it here without calling the AI service.
        role = getattr(current_user, "role", None)
        if model is not None and (
            role in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN)
            or model.status == MODEL_STATUS_PUBLISHED
        ):
            role_key = (
                EVALUATION_AUDIENCE_MANAGEMENT
                if role in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN)
                else EVALUATION_AUDIENCE_USER
            )
            artifact = (model.ai_evaluation or {}).get(role_key) or {}
            data["model_evaluation"] = {
                "available": bool(artifact.get("markdown")),
                "source": artifact.get("source"),
                "markdown": str(artifact["markdown"]) if artifact.get("markdown") else None,
                "generated_at": artifact.get("generated_at"),
            }
        else:
            data["model_evaluation"] = {
                "available": False,
                "source": None,
                "markdown": None,
                "generated_at": None,
            }
        return data

    @staticmethod
    def _saved_explanation_for_role(record: InferenceRecord, role: str | None) -> dict:
        """Expose the persisted wording artifact for the caller's audience.

        Each audience owns its own slot, so an administrator's wording is no
        longer overwritten when a scenario user regenerates the same record.
        The exact facts sent to the AI remain manager-only because they may
        contain raw input features and algorithm internals; the prediction
        itself is always read from the server record.
        """
        artifact = _explanation_artifact_for(record.explain_data, role)
        if not artifact.get("markdown"):
            return {"available": False, "source": None, "generated_at": None}
        result = {
            "available": True,
            "markdown": str(artifact["markdown"]),
            "source": str(artifact.get("source") or "fallback"),
            "generated_at": artifact.get("generated_at"),
        }
        if role in ADMIN_ROLES:
            result["data_snapshot"] = artifact.get("data_snapshot") or {}
        return result

    def _can_infer_from_model(self, current_user, model: ModelVersion, dataset: Dataset) -> bool:
        """Enforce model scenario and dataset-visibility boundaries before inference."""
        role = getattr(current_user, "role", None)
        if role == ROLE_SUPER_ADMIN:
            return self.is_platform_visibility(dataset.visibility)
        if role == ROLE_SCENARIO_ADMIN:
            return (
                model.scenario_id == getattr(current_user, "scenario_id", None)
                and dataset.visibility in _INFERABLE_VISIBILITIES
            )
        return (
            model.scenario_id == getattr(current_user, "scenario_id", None)
            and (
                dataset.visibility in _INFERABLE_VISIBILITIES
                or dataset.uploaded_by == getattr(current_user, "id", None)
            )
        )

    def _resolve_target(self, current_user, model_version_id: int) -> tuple:
        """解析并校验推理目标，返回 (model, dataset)。

        单条与批量共用，保证两条链路的权限与状态口径一致。
        """
        self.require_login(current_user)
        model = self.db.get(ModelVersion, model_version_id)
        if model is None:
            raise ServiceError(404, "模型版本不存在")
        if model.status not in INFERENCE_ALLOWED_MODEL_STATUSES:
            raise ServiceError(400, "仅已发布模型可执行推理")
        dataset = self.db.get(Dataset, model.dataset_id)
        if dataset is None:
            raise ServiceError(404, "模型绑定的数据集不存在")
        if not self._can_infer_from_model(current_user, model, dataset):
            raise ServiceError(403, "无权限使用该模型")
        return model, dataset

    def _predict(self, model: ModelVersion, dataset: Dataset, input_features: Dict[str, Any]) -> tuple:
        """调用服务端统一预测入口，返回 (prediction_label, probability, explain_data)。

        - prediction_label：模型预测的分类标签（argmax 类别）；
        - probability：模型对预测类别的输出概率（当预测为风险类时用作 risk_score）；
        - explain_data：算法可解释性信息（多视图预测 / 视图权重 / 特征加权条件概率），
          由 Java /predict 返回，用于态势报告可视化与自然语言分析。
        """
        from app.services.training_executor import (
            build_model_save_path,
            execute_algorithm_predict,
            resolve_dataset_path,
        )

        algorithm_code = model.algorithm.code if model.algorithm else "PMWNB"
        model_path = build_model_save_path(model.id, algorithm_code)
        arff_path = resolve_dataset_path(dataset.file_path)
        try:
            result = execute_algorithm_predict(
                algorithm_code,
                model_path,
                arff_path,
                input_features,
                risk_labels=sorted(DATASET_POSITIVE_LABELS.get(dataset.logical_id, set())),
            )
        except FileNotFoundError as exc:
            raise ServiceError(400, str(exc))
        except RuntimeError as exc:
            raise ServiceError(503, str(exc))

        label = str(result.get("prediction_label", "")).strip()
        if not label:
            raise ServiceError(500, "预测服务未返回预测标签")
        prob = result.get("probability")
        probability = float(prob) if prob is not None else None
        if probability is not None and not (0 <= probability <= 1):
            raise ServiceError(500, "预测服务返回的概率超出 [0,1]")

        # Keep the probability of the explicitly mapped risk class even when
        # argmax predicts the normal class; this is the public risk metric.
        class_distribution = result.get("class_distribution") or []
        risk_probability = next(
            (
                float(item.get("probability"))
                for item in class_distribution
                if isinstance(item, dict)
                and is_risk_label(dataset.logical_id, item.get("class"))
                and item.get("probability") is not None
            ),
            None,
        )
        if risk_probability is not None:
            result["risk_probability"] = risk_probability

        from app.services.explanation_service import build_unified_explanation

        is_prediction_risk = is_risk_label(dataset.logical_id, label)
        unified = build_unified_explanation(
            scenario_code=model.scenario.code if model.scenario else None,
            sample=input_features,
            model_result=result,
            algorithm_code=algorithm_code,
            is_prediction_risk=is_prediction_risk,
            model_metrics=model.evaluation_metrics,
        )
        explain_data = {
            "prediction_label": label,
            "probability": probability,
            "class_distribution": result.get("class_distribution") or [],
            "views": result.get("views") or [],
            "view_weights": result.get("view_weights") or [],
            "feature_evidence": result.get("feature_evidence") or [],
            **unified,
        }
        return label, probability, explain_data

    # ------------------------------------------------------------------
    # 执行推理（需求 6.7.3 / 5.2 / 5.3）
    # ------------------------------------------------------------------
    @service_call
    def create_inference(
        self,
        current_user,
        model_version_id: int,
        input_features: Dict[str, Any],
        executed_at: Optional[datetime] = None,
    ):
        """执行单条样本推理并落库；预测为风险类时自动生成 RiskEvent。

        预测结果（prediction_label / risk_score）由服务端统一预测入口
        （独立 Java 预测服务）根据 model_version_id + input_features 计算，
        客户端不再提交这两个字段（需求 6.6.2 统一预测结果格式）。
        """
        self.require_login(current_user)

        model, dataset = self._resolve_target(current_user, model_version_id)

        # 枚举值先对齐值域里的写法（带引号 / 去引号两种输入都收敛到 Weka 认的形式），
        # 再做输入校验（需求 3.1.2/3.1.5）：固定字段齐全 + 枚举值域
        input_features = normalize_input_features(dataset.fields_schema, input_features)
        err = validate_input_features(dataset.fields_schema, input_features)
        if err:
            raise ServiceError(400, err)

        # 服务端统一预测入口（需求 6.6.2）：按 model_version_id + input_features 计算
        prediction_label, probability, explain_data = self._predict(model, dataset, input_features)

        # 风险类判定（需求 6.4.1 显式映射：禁止自动推断正类；
        # DIS_Causative 等数值标签走 DATASET_RISK_GT_ZERO 规则，需求 5.3）
        is_risk = is_risk_label(dataset.logical_id, prediction_label)
        score: Optional[float] = probability if is_risk else None

        now = executed_at or datetime.now(timezone.utc)
        record = InferenceRecord(
            user_id=current_user.id,
            model_version_id=model_version_id,
            input_features=input_features,
            prediction_label=str(prediction_label).strip(),
            risk_score=score,
            risk_level=None,  # 仅当预测为风险时由事件回填（数据库设计文档 v2 2.6）
            is_risk_event=is_risk,
            explain_data=explain_data,
            executed_at=now,
        )
        self.db.add(record)
        self.db.flush()  # 获取 record.id，供风险事件外键使用

        generated_event = None
        if is_risk:
            # 需求 5.3：风险类结果 → 生成对应 risk_type 的 RiskEvent
            #（risk_score 缺失时 create_from_inference 会抛 400，整个推理被拒绝）
            generated_event = self._risk_event_service.create_from_inference(
                current_user=current_user,
                record=record,
                model=model,
                dataset=dataset,
                risk_score=score,
            )
            record.risk_level = generated_event.risk_level

        self.commit()

        data = self._to_dict(record, current_user)
        data["risk_event"] = row_to_dict(generated_event) if generated_event else None
        return ok(
            data=data,
            message="推理完成" + ("，已生成风险事件" if generated_event else ""),
        )

    # ------------------------------------------------------------------
    # 批量推理（页面「批量研判」）
    # ------------------------------------------------------------------
    @service_call
    def create_batch_inference(
        self,
        current_user,
        model_version_id: int,
        samples: List[Dict[str, Any]],
    ):
        """批量执行推理：逐条走单条链路（校验 / 预测 / 落库 / 风险事件）。

        - **与单条行为完全一致**：判为风险类的样本照常生成 RiskEvent，
          这样告警中心、态势大屏与看板都能看到这批结果，不会出现
          「研判出来了但别处没有」的断链。
        - **单条失败不影响整批**：失败样本只记录 error 文案，继续跑后面的。
        - 返回汇总（total / succeeded / failed / risk_count）与逐条明细。
        """
        model, dataset = self._resolve_target(current_user, model_version_id)
        if not samples:
            raise ServiceError(400, "没有可研判的样本")

        succeeded, failed, risk_count, items = self._run_batch(
            current_user, model_version_id, dataset, samples
        )
        return ok(
            data={
                "total": len(samples),
                "succeeded": succeeded,
                "failed": failed,
                "risk_count": risk_count,
                "items": items,
            },
            message=(
                f"批量研判完成：成功 {succeeded} 条、风险 {risk_count} 条"
                + (f"、失败 {failed} 条" if failed else "")
            ),
        )

    def _run_batch(
        self,
        current_user,
        model_version_id: int,
        dataset,
        samples: List[Dict[str, Any]],
        on_progress=None,
    ):
        """逐条执行批量推理，返回 (succeeded, failed, risk_count, items)。

        单条失败不影响整批（沿用原语义）；on_progress 仅供后台任务汇报进度。
        """
        items: List[Dict[str, Any]] = []
        succeeded = failed = risk_count = 0

        for index, sample in enumerate(samples):
            # 标签列不参与推理（需求 3.1.3）；样本来自数据集时本来就带标签，这里剥掉
            features = {
                key: value
                for key, value in (sample or {}).items()
                if key != dataset.label_field
            }
            response = self.create_inference(
                current_user=current_user,
                model_version_id=model_version_id,
                input_features=features,
            )
            if response.code != 0:
                failed += 1
                items.append(
                    {
                        "index": index,
                        "prediction_label": None,
                        "risk_probability": None,
                        "risk_level": None,
                        "is_risk_event": False,
                        "inference_record_id": None,
                        "risk_event_id": None,
                        "error": response.message,
                    }
                )
            else:
                data = response.data or {}
                is_risk = bool(data.get("is_risk_event"))
                event = data.get("risk_event") or {}
                succeeded += 1
                if is_risk:
                    risk_count += 1
                items.append(
                    {
                        "index": index,
                        "prediction_label": data.get("prediction_label"),
                        # 风险类概率取模型对风险类的输出概率，正常类也有值（更有参考意义）
                        "risk_probability": (data.get("explain_data") or {}).get(
                            "risk_probability"
                        ),
                        "risk_level": data.get("risk_level"),
                        "is_risk_event": is_risk,
                        "inference_record_id": data.get("id"),
                        "risk_event_id": event.get("id"),
                        "error": None,
                    }
                )
            # 每处理完一条都要汇报进度（含失败条）：失败分支原本 continue 掉了回调，
            # 末尾连续失败时进度会一直停在最后一个成功条数，前端进度条不动。
            if on_progress is not None:
                on_progress(index + 1, succeeded, failed, risk_count)

        return succeeded, failed, risk_count, items

    def _read_dataset_samples(
        self, current_user, model_version_id: int, offset: int, limit: int
    ) -> List[Dict[str, Any]]:
        """校验推理目标并读取数据集 offset..offset+limit 条样本。

        同步（create_batch_from_dataset）与异步（submit_batch_from_dataset）共用，
        样本读取走 ``read_sample_rows``（与数据预览同一口径），ARFF / CSV 都支持。
        """
        _, dataset = self._resolve_target(current_user, model_version_id)

        from app.services.training_executor import resolve_dataset_path
        from app.utils.dataset_file_reader import read_sample_rows

        path = resolve_dataset_path(dataset.file_path)
        if not os.path.exists(path):
            raise ServiceError(404, f"数据集文件不存在: {path}")
        samples = read_sample_rows(path, dataset.fields_schema, offset, limit)
        if not samples:
            raise ServiceError(400, "指定区间内没有样本")
        return samples

    @service_call
    def create_batch_from_dataset(
        self,
        current_user,
        model_version_id: int,
        offset: int = 0,
        limit: int = 50,
    ):
        """从模型绑定数据集读取 offset..offset+limit 条样本并批量研判。"""
        samples = self._read_dataset_samples(current_user, model_version_id, offset, limit)
        return self.create_batch_inference(
            current_user=current_user,
            model_version_id=model_version_id,
            samples=samples,
        )

    @service_call
    def create_batch_from_csv(
        self,
        current_user,
        model_version_id: int,
        filename: str,
        file_bytes: bytes,
        limit: int = 200,
    ):
        """解析上传的 CSV 并批量研判（解析规则见 ``_parse_csv_samples``）。"""
        _, dataset = self._resolve_target(current_user, model_version_id)

        samples = self._parse_csv_samples(dataset, filename, file_bytes, limit)

        result = self.create_batch_inference(
            current_user=current_user,
            model_version_id=model_version_id,
            samples=samples,
        )
        if result.code == 0 and result.data:
            result.data["truncated"] = len(samples) >= limit
        return result

    def _parse_csv_samples(
        self, dataset, filename: str, file_bytes: bytes, limit: int
    ) -> List[Dict[str, Any]]:
        """把上传的 CSV 解析为样本列表（最多 limit 条）。

        列名必须覆盖数据集全部输入特征（顺序任意，多余列忽略，标签列可有可无）。
        列名对不上时直接给出缺哪几列，不把解析细节抛给用户。
        """
        if not str(filename).lower().endswith(".csv"):
            raise ServiceError(400, "仅支持 .csv 文件")
        try:
            text = file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ServiceError(400, "文件编码无法识别，请另存为 UTF-8 编码的 CSV")

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ServiceError(400, "CSV 缺少表头行")
        headers = {str(h).strip() for h in reader.fieldnames if h is not None}

        feature_fields = [
            f for f in (dataset.fields_schema or []) if f.get("role") != "label"
        ]
        required = [str(f.get("name")) for f in feature_fields]
        missing = [name for name in required if name not in headers]
        if missing:
            shown = "、".join(missing[:5])
            suffix = f" 等 {len(missing)} 列" if len(missing) > 5 else ""
            raise ServiceError(400, f"CSV 缺少字段：{shown}{suffix}")

        type_by_name = {str(f.get("name")): f.get("type") for f in feature_fields}
        samples: List[Dict[str, Any]] = []
        for row in reader:
            if len(samples) >= limit:
                break
            samples.append(
                {
                    name: _coerce_value(row.get(name), type_by_name.get(name))
                    for name in required
                }
            )
        if not samples:
            raise ServiceError(400, "CSV 中没有数据行")
        return samples

    # ------------------------------------------------------------------
    # 批量推理（异步：提交任务 + 轮询进度；页面「批量研判」默认走这条）
    # ------------------------------------------------------------------
    def run_batch_job(
        self,
        current_user,
        model_version_id: int,
        samples: List[Dict[str, Any]],
        on_progress=None,
    ) -> Dict[str, Any]:
        """后台执行一次批量研判（供 batch_inference_runner 调用），返回汇总。

        不返回 ResponseModel、也不吞异常：调用方是后台线程，异常由它写进任务表。
        """
        model, dataset = self._resolve_target(current_user, model_version_id)
        if not samples:
            raise ServiceError(400, "没有可研判的样本")
        succeeded, failed, risk_count, items = self._run_batch(
            current_user, model_version_id, dataset, samples, on_progress
        )
        return {
            "total": len(samples),
            "succeeded": succeeded,
            "failed": failed,
            "risk_count": risk_count,
            "items": items,
        }

    @service_call
    def submit_batch_inference(
        self,
        current_user,
        model_version_id: int,
        samples: List[Dict[str, Any]],
        truncated: bool = False,
    ):
        """登记后台批量研判任务并立刻返回 job_id（进度用 get_batch_job 查）。

        校验与同步路径同一套（复用 _resolve_target）；样本已由调用方解析完毕，
        所以这里只判断「能不能跑」，不占请求线程。
        """
        from app.services.batch_inference_runner import create_job, is_running

        if not is_running():
            raise ServiceError(503, "批量研判执行器未启用，无法提交后台任务")
        self._resolve_target(current_user, model_version_id)
        if not samples:
            raise ServiceError(400, "没有可研判的样本")

        job_id = create_job(
            user_id=current_user.id,
            model_version_id=model_version_id,
            samples=samples,
            truncated=truncated,
        )
        return ok(
            data={"job_id": job_id, "total": len(samples), "truncated": truncated},
            message=f"批量研判已提交，共 {len(samples)} 条",
        )

    @service_call
    def get_batch_job(self, current_user, job_id: str):
        """查询批量研判任务进度；任务不存在、已过期或不属于当前用户时 404。"""
        from app.services.batch_inference_runner import get_job

        self.require_login(current_user)
        view = get_job(job_id, current_user.id)
        if view is None:
            raise ServiceError(404, "批量研判任务不存在或已过期")
        return ok(data=view)

    @service_call
    def list_batch_jobs(self, current_user):
        """当前用户的批量研判任务列表（刷新 / 切页回来能恢复「还在跑」的状态）。"""
        from app.services.batch_inference_runner import list_jobs

        self.require_login(current_user)
        return ok(data=list_jobs(current_user.id))

    @service_call
    def submit_batch_from_dataset(
        self,
        current_user,
        model_version_id: int,
        offset: int = 0,
        limit: int = 50,
    ):
        """从模型绑定数据集读取 offset..offset+limit 条样本并提交后台研判。"""
        samples = self._read_dataset_samples(current_user, model_version_id, offset, limit)
        return self.submit_batch_inference(
            current_user=current_user,
            model_version_id=model_version_id,
            samples=samples,
        )

    @service_call
    def submit_batch_from_csv(
        self,
        current_user,
        model_version_id: int,
        filename: str,
        file_bytes: bytes,
        limit: int = 200,
    ):
        """解析上传的 CSV 并提交后台研判（列名必须覆盖数据集全部输入特征）。"""
        _, dataset = self._resolve_target(current_user, model_version_id)

        samples = self._parse_csv_samples(dataset, filename, file_bytes, limit)
        return self.submit_batch_inference(
            current_user=current_user,
            model_version_id=model_version_id,
            samples=samples,
            truncated=len(samples) >= limit,
        )

    # ------------------------------------------------------------------
    # 查询（需求 6.8：USER 仅本人；ADMIN 全部）
    # ------------------------------------------------------------------
    def _require_record_access(self, current_user, record: InferenceRecord) -> None:
        """推理记录访问控制（需求 0.2 / 6.8）。

        - SUPER_ADMIN：仅 platform 数据集派生模型的推理记录
        - SCENARIO_ADMIN：仅绑定场景
        - SCENARIO_USER：仅本人
        """
        self.require_login(current_user)
        role = getattr(current_user, "role", None)
        model = self.db.get(ModelVersion, record.model_version_id)
        if model is None:
            raise ServiceError(404, "关联模型不存在")
        if role == ROLE_SUPER_ADMIN:
            dataset = self.db.get(Dataset, model.dataset_id)
            if dataset is None or not self.is_platform_visibility(dataset.visibility):
                raise ServiceError(403, "无权限操作")
            return
        if role == ROLE_SCENARIO_ADMIN:
            dataset = self.db.get(Dataset, model.dataset_id)
            if (
                model.scenario_id != getattr(current_user, "scenario_id", None)
                or dataset is None
                or dataset.visibility not in _INFERABLE_VISIBILITIES
            ):
                raise ServiceError(403, "无权限操作")
            return
        if record.user_id != getattr(current_user, "id", None):
            raise ServiceError(403, "无权限操作")

    @service_call
    def get_list(
        self,
        current_user,
        model_version_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 10,
    ):
        """推理记录列表。

        - SUPER_ADMIN：仅 platform 数据集派生记录；
        - SCENARIO_ADMIN：自己场景全部记录；
        - SCENARIO_USER：强制按 user_id 过滤（后端强制，需求 6.8.2）。
        """
        self.require_login(current_user)
        role = getattr(current_user, "role", None)
        stmt = select(InferenceRecord)
        if role == ROLE_SUPER_ADMIN:
            stmt = (
                stmt.join(ModelVersion, ModelVersion.id == InferenceRecord.model_version_id)
                .join(Dataset, Dataset.id == ModelVersion.dataset_id)
                .where(Dataset.visibility == DATASET_VISIBILITY_PLATFORM)
            )
        elif role == ROLE_SCENARIO_ADMIN:
            stmt = stmt.join(
                ModelVersion, ModelVersion.id == InferenceRecord.model_version_id
            ).join(Dataset, Dataset.id == ModelVersion.dataset_id).where(
                ModelVersion.scenario_id == getattr(current_user, "scenario_id", None),
                Dataset.visibility.in_(_INFERABLE_VISIBILITIES),
            )
        else:
            stmt = stmt.where(InferenceRecord.user_id == current_user.id)
        if model_version_id is not None:
            stmt = stmt.where(InferenceRecord.model_version_id == model_version_id)
        stmt = stmt.order_by(InferenceRecord.executed_at.desc())
        result = paginate(self.db, stmt, page, page_size)
        # 阈值只查一次，逐条传下去，避免 N+1
        thresholds = risk_view.load_thresholds(self.db, current_user)
        # 列表不下发 explain_data（实测占单条体积 82%），列表页不读它；
        # 「查看解释」弹窗走 GET /inference-records/{id}/explain 单独取。
        result["items"] = [
            self._to_dict(r, current_user, thresholds, include_explain=False)
            for r in result["items"]
        ]
        return ok(data=result)

    @service_call
    def get(self, current_user, record_id: int):
        """推理记录详情。"""
        record = self._get(record_id)
        self._require_record_access(current_user, record)
        return ok(data=self._to_dict(record, current_user))

    @service_call
    def get_explanation_source(self, current_user, record_id: int):
        """Return the authorized, server-side facts used by the explanation stream.

        事实按受众裁剪（``explanation_for_role``）：普通用户拿不到
        ``algorithm_details`` / ``model_quality`` / ``input_snapshot``，
        所以 AI 正文里也不会出现本应对普通用户隐藏的算法内部明细 ——
        正文与「查看解释」弹窗的口径保持一致。
        """
        record = self._get(record_id)
        self._require_record_access(current_user, record)
        from app.schemas.explanation_contract import explanation_for_role
        from app.services.explanation_service import get_scenario_config

        model = self.db.get(ModelVersion, record.model_version_id)
        scenario_code = model.scenario.code if model and model.scenario else None
        scenario = get_scenario_config(scenario_code)
        # A previous wording result is an output artifact, never an input fact.
        model_result = explanation_for_role(
            record.explain_data, getattr(current_user, "role", None)
        )
        model_result.pop("ai_explanation", None)
        model_result.setdefault("prediction_label", record.prediction_label)
        model_result.setdefault("prediction_is_risk", bool(record.is_risk_event))
        if record.risk_score is not None:
            model_result.setdefault("risk_probability", float(record.risk_score))
        return ok(data={
            "scenario": scenario,
            "sample": dict(record.input_features or {}),
            "model_result": model_result,
            "algorithm_details": model_result.get("algorithm_details") or {},
            "recommended_actions": scenario.get("recommended_actions") or [],
        })

    @service_call
    def save_generated_explanation(
        self,
        current_user,
        record_id: int,
        markdown: str,
        source: str,
        data_snapshot: dict[str, Any],
    ):
        """Persist generated Markdown into the caller's audience slot.

        产物按受众分格：管理员生成的完整版不会被场景用户重新生成时覆盖，
        反之亦然。老的单格结构在写入时展开成两份（见 ``_explanation_artifacts``）。
        """
        from app.services.explanation_service import EXPLANATION_PROMPT_VERSION

        record = self._get(record_id)
        self._require_record_access(current_user, record)
        if not markdown or len(markdown) > 100_000:
            raise ServiceError(400, "解释文本为空或超过保存上限")
        source = source if source in {"ai", "fallback"} else "fallback"
        audience = evaluation_audience(getattr(current_user, "role", None))
        setting = self.db.get(UserAISetting, current_user.id)
        explain_data = dict(record.explain_data or {})
        artifacts = _explanation_artifacts(explain_data)
        artifacts[audience] = {
            "markdown": markdown,
            "source": source,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": getattr(current_user, "id", None),
            "model": getattr(setting, "model", None),
            "prompt_version": EXPLANATION_PROMPT_VERSION,
            "data_snapshot": data_snapshot,
        }
        explain_data["ai_explanation"] = artifacts
        record.explain_data = explain_data
        self.commit()
        return ok(data={"saved": True, "source": source, "audience": audience})

    @service_call
    def get_explain(self, current_user, record_id: int):
        """推理记录的可解释性信息（多视图预测 / 视图权重 / 特征加权条件概率）。

        供态势报告与详情页复用；权限同详情（普通用户仅本人，需求 6.8）。
        """
        record = self._get(record_id)
        self._require_record_access(current_user, record)
        from app.schemas.explanation_contract import explanation_for_role

        explanation = explanation_for_role(
            record.explain_data, getattr(current_user, "role", None)
        )
        return ok(data={
            "inference_record_id": record.id,
            "prediction_label": record.prediction_label,
            "explain_data": explanation,
            "generated_explanation": self._saved_explanation_for_role(
                record, getattr(current_user, "role", None)
            ),
        })

    # ------------------------------------------------------------------
    # 删除（仅平台超管 SUPER_ADMIN；已生成风险事件的记录禁止删除，保持可追溯）
    # ------------------------------------------------------------------
    @service_call
    def delete(self, current_user, record_id: int):
        """删除推理记录（仅平台超管 SUPER_ADMIN）。

        已生成风险事件的推理记录禁止删除（风险事件依赖推理记录外键且需保持可追溯，
        需求 5.2 访问控制第 4 条）。
        """
        # require_admin 只认 SUPER_ADMIN，所以 _require_record_access 里的 SCENARIO_ADMIN /
        # 普通用户分支在删除路径上不可达 —— 它在 get / get_explain 等 5 个方法上共用，
        # 那两个分支在别处是活的，不要因为这里读不到就把它们删掉。
        self.require_admin(current_user)
        record = self._get(record_id)
        self._require_record_access(current_user, record)
        event_exists = self.db.scalar(
            select(RiskEvent).where(RiskEvent.inference_record_id == record_id)
        )
        if event_exists:
            raise ServiceError(400, "推理记录已生成风险事件，禁止删除")
        self.db.delete(record)
        self.commit()
        return ok(message="推理记录已删除")
