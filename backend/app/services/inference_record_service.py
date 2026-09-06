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
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select

from app.models.dataset import Dataset
from app.models.inference_record import InferenceRecord
from app.models.model_version import ModelVersion
from app.models.risk_event import RiskEvent
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    DATASET_RISK_TYPES,
    DATASET_VISIBILITY_PLATFORM,
    INFERENCE_ALLOWED_MODEL_STATUSES,
    ROLE_ADMIN,
    ROLE_SCENARIO_ADMIN,
    ROLE_SUPER_ADMIN,
    is_risk_label,
)
from app.services.risk_event_service import RiskEventService
from app.utils.common import get_logger, paginate, row_to_dict, validate_input_features

logger = get_logger("inference_record")


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

    def _to_dict(self, record: InferenceRecord) -> dict:
        """序列化推理记录，并补全展示字段（场景/数据集/算法/风险类型/关联风险事件）。"""
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
                data["dataset_version"] = dataset.version
                data["risk_type"] = DATASET_RISK_TYPES.get(dataset.logical_id)
        data["original_label"] = record.prediction_label
        event = self.db.scalar(
            select(RiskEvent).where(RiskEvent.inference_record_id == record.id)
        )
        data["risk_event_id"] = event.id if event is not None else None
        return data

    def _can_infer_from_model(self, current_user, model: ModelVersion, dataset: Dataset) -> bool:
        """Enforce model scenario and dataset-visibility boundaries before inference."""
        role = getattr(current_user, "role", None)
        if role == ROLE_SUPER_ADMIN:
            return self.is_platform_visibility(dataset.visibility)
        if role == ROLE_SCENARIO_ADMIN:
            return (
                model.scenario_id == getattr(current_user, "scenario_id", None)
                and dataset.visibility in ("platform", "company")
            )
        return (
            model.scenario_id == getattr(current_user, "scenario_id", None)
            and (
                dataset.visibility in ("platform", "company")
                or dataset.uploaded_by == getattr(current_user, "id", None)
            )
        )

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
            result = execute_algorithm_predict(algorithm_code, model_path, arff_path, input_features)
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

        explain_data = {
            "prediction_label": label,
            "probability": probability,
            "class_distribution": result.get("class_distribution") or [],
            "views": result.get("views") or [],
            "view_weights": result.get("view_weights") or [],
            "feature_evidence": result.get("feature_evidence") or [],
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

        # 输入校验（需求 3.1.2/3.1.5）：固定字段齐全 + 枚举值域
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

        data = row_to_dict(record)
        data["risk_event"] = row_to_dict(generated_event) if generated_event else None
        return ok(
            data=data,
            message="推理完成" + ("，已生成风险事件" if generated_event else ""),
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
                or dataset.visibility not in ("platform", "company")
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
                Dataset.visibility.in_(("platform", "company")),
            )
        else:
            stmt = stmt.where(InferenceRecord.user_id == current_user.id)
        if model_version_id is not None:
            stmt = stmt.where(InferenceRecord.model_version_id == model_version_id)
        stmt = stmt.order_by(InferenceRecord.executed_at.desc())
        result = paginate(self.db, stmt, page, page_size)
        result["items"] = [self._to_dict(r) for r in result["items"]]
        return ok(data=result)

    @service_call
    def get(self, current_user, record_id: int):
        """推理记录详情。"""
        record = self._get(record_id)
        self._require_record_access(current_user, record)
        return ok(data=self._to_dict(record))

    @service_call
    def get_explain(self, current_user, record_id: int):
        """推理记录的可解释性信息（多视图预测 / 视图权重 / 特征加权条件概率）。

        供态势报告与详情页复用；权限同详情（普通用户仅本人，需求 6.8）。
        """
        record = self._get(record_id)
        self._require_record_access(current_user, record)
        return ok(
            data={
                "inference_record_id": record.id,
                "prediction_label": record.prediction_label,
                "explain_data": record.explain_data or {},
            }
        )

    # ------------------------------------------------------------------
    # 删除（仅 ADMIN；已生成风险事件的记录禁止删除，保持可追溯）
    # ------------------------------------------------------------------
    @service_call
    def delete(self, current_user, record_id: int):
        """删除推理记录（仅 ADMIN）。

        已生成风险事件的推理记录禁止删除（风险事件依赖推理记录外键且需保持可追溯，
        需求 5.2 访问控制第 4 条）。
        """
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
