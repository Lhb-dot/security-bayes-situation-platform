"""模型版本 Service（ModelVersion）—— 生命周期状态机核心。

对应需求文档章节：1.1（场景使用约束）、6.6.3（管理员参数配置规则）、
6.7（模型版本、发布与默认推荐规则）、6.5.2（权限矩阵）。

模型：app.models.model_version.ModelVersion。

状态机（需求 6.7.2）：
    TRAINING → FAILED / DRAFT → PUBLISHED → OFFLINE（→ PUBLISHED 可重新发布，§6.7.5.7）
由 MODEL_STATUS_TRANSITIONS 常量驱动，禁止任意跳转。

关键业务规则：
1. 仅 ADMIN 可训练/发布/下线/设默认模型；普通用户仅可见与使用 PUBLISHED 模型。
2. 训练前必须选择场景、数据集版本和算法；数据集必须属于所选场景（禁止跨场景混合训练）；
   停用的数据集不得用于训练。
3. 每个"场景＋数据集"最多一个默认推荐模型；默认模型必须 PUBLISHED；
   默认模型下线时自动清除默认状态（需求 6.7.4.5）。
4. 发布和下线必须记录操作管理员及操作时间（published_by / published_at）。
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from app.models.algorithm import Algorithm
from app.models.dataset import Dataset
from app.models.inference_record import InferenceRecord
from app.models.model_version import ModelVersion
from app.models.risk_event import RiskEvent
from app.models.scenario import Scenario
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    ALGORITHM_STATUS_AVAILABLE,
    DATASET_STATUS_ACTIVE,
    MODEL_STATUS_DRAFT,
    MODEL_STATUS_FAILED,
    MODEL_STATUS_OFFLINE,
    MODEL_STATUS_PUBLISHED,
    MODEL_STATUS_TRAINING,
    MODEL_STATUS_TRANSITIONS,
    ROLE_ADMIN,
    USER_VISIBLE_MODEL_STATUSES,
)
from app.utils.common import (
    get_logger,
    paginate,
    row_to_dict,
    validate_params_schema,
)

logger = get_logger("model_version")


class ModelVersionService(ServiceBase):
    """模型版本管理：训练启动/完成/失败、发布、下线、默认推荐、查询。"""

    def _get(self, model_id: int) -> ModelVersion:
        model = self.db.get(ModelVersion, model_id)
        if model is None:
            raise ServiceError(404, "模型版本不存在")
        return model

    @staticmethod
    def _to_dict(model: ModelVersion) -> dict:
        return row_to_dict(model)

    def _transition(
        self, model: ModelVersion, to_status: str, operator_id: Optional[int] = None
    ) -> ModelVersion:
        """状态机流转（需求 6.7.2/6.7.3.6：发布和下线记录操作人与时间）。"""
        allowed = MODEL_STATUS_TRANSITIONS.get(model.status, ())
        if to_status not in allowed:
            raise ServiceError(
                400, f"模型状态不允许从 {model.status} 转换到 {to_status}"
            )
        model.status = to_status
        if to_status == MODEL_STATUS_PUBLISHED:
            model.published_by = operator_id
            model.published_at = datetime.now(timezone.utc)
        return model

    # ------------------------------------------------------------------
    # 训练（仅 ADMIN；需求 6.7.1 保存训练参数/评估指标/训练人/时间）
    # ------------------------------------------------------------------
    @service_call
    def create(
        self,
        current_user,
        scenario_id: int,
        dataset_id: int,
        algorithm_id: int,
        training_parameters: Dict[str, Any],
    ):
        """启动训练：生成 TRAINING 状态的模型版本（仅 ADMIN）。

        校验：场景存在；数据集属于所选场景（需求 1.1.3/2.2.3 禁止跨场景混合训练）；
        数据集 ACTIVE；算法 AVAILABLE；training_parameters 必须完整（需求 6.6.3.4）。
        """
        self.require_admin(current_user)

        scenario = self.db.get(Scenario, scenario_id)
        if scenario is None:
            raise ServiceError(404, "场景不存在")

        dataset = self.db.get(Dataset, dataset_id)
        if dataset is None:
            raise ServiceError(404, "数据集不存在")
        if dataset.scenario_id != scenario_id:
            raise ServiceError(400, "数据集不属于所选场景，禁止跨场景混合训练")
        if dataset.status != DATASET_STATUS_ACTIVE:
            raise ServiceError(400, "数据集已停用，不能用于训练")

        algorithm = self.db.get(Algorithm, algorithm_id)
        if algorithm is None:
            raise ServiceError(404, "算法不存在")
        if algorithm.status != ALGORITHM_STATUS_AVAILABLE:
            raise ServiceError(400, "算法不可用，不能用于训练")

        if not isinstance(training_parameters, dict) or not training_parameters:
            raise ServiceError(
                400, "training_parameters 必须是非空 JSON 对象（需完整保存最终生效参数）"
            )
        # 按算法注册的 param_schema 校验必填项、类型与范围（需求 6.6.3.2/6.6.3.4）
        err = validate_params_schema(algorithm.param_schema, training_parameters)
        if err:
            raise ServiceError(400, err)

        now = datetime.now(timezone.utc)
        model = ModelVersion(
            scenario_id=scenario_id,
            dataset_id=dataset_id,
            algorithm_id=algorithm_id,
            training_parameters=training_parameters,
            evaluation_metrics={},
            trained_by=current_user.id,
            trained_at=now,
            status=MODEL_STATUS_TRAINING,
            is_default=False,
        )
        self.db.add(model)
        self.commit()
        return ok(data=self._to_dict(model), message="训练启动，模型版本进入 TRAINING")

    @service_call
    def complete_training(
        self, current_user, model_id: int, evaluation_metrics: Dict[str, Any]
    ):
        """训练成功：TRAINING → DRAFT，保存评估指标（需求 6.7.2 转换条件）。"""
        self.require_admin(current_user)
        if not isinstance(evaluation_metrics, dict):
            raise ServiceError(400, "evaluation_metrics 必须是 JSON 对象")
        model = self._get(model_id)
        self._transition(model, MODEL_STATUS_DRAFT)
        model.evaluation_metrics = evaluation_metrics
        self.commit()
        return ok(data=self._to_dict(model), message="训练完成，模型进入 DRAFT 待发布")

    @service_call
    def fail_training(
        self, current_user, model_id: int, error_message: Optional[str] = None
    ):
        """训练失败：TRAINING → FAILED。"""
        self.require_admin(current_user)
        model = self._get(model_id)
        self._transition(model, MODEL_STATUS_FAILED)
        if error_message:
            metrics = dict(model.evaluation_metrics or {})
            metrics["error"] = str(error_message)
            model.evaluation_metrics = metrics
        self.commit()
        return ok(data=self._to_dict(model), message="训练失败")

    # ------------------------------------------------------------------
    # 发布 / 下线 / 默认推荐（仅 ADMIN）
    # ------------------------------------------------------------------
    @service_call
    def publish(self, current_user, model_id: int):
        """发布模型：DRAFT → PUBLISHED；OFFLINE → PUBLISHED（重新发布，需求 6.7.5.7）。"""
        self.require_admin(current_user)
        model = self._get(model_id)
        self._transition(model, MODEL_STATUS_PUBLISHED, operator_id=current_user.id)
        self.commit()
        return ok(data=self._to_dict(model), message="模型已发布")

    @service_call
    def offline(self, current_user, model_id: int):
        """下线模型：PUBLISHED → OFFLINE。

        需求 6.7.4.5：默认模型被下线时，系统必须同时取消其默认状态（is_default=False）。
        """
        self.require_admin(current_user)
        model = self._get(model_id)
        self._transition(model, MODEL_STATUS_OFFLINE)
        if model.is_default:
            model.is_default = False
        self.commit()
        return ok(data=self._to_dict(model), message="模型已下线，默认推荐状态已清除")

    @service_call
    def set_default(self, current_user, model_id: int):
        """设置默认推荐模型（需求 6.7.4）。

        约束：必须 PUBLISHED；每个"场景＋数据集"最多一个默认模型（先清除同范围旧默认，
        与 uk_mv_default 部分唯一索引保持一致）。
        """
        self.require_admin(current_user)
        model = self._get(model_id)
        if model.status != MODEL_STATUS_PUBLISHED:
            raise ServiceError(400, "只有已发布模型才能设为默认推荐模型")
        others = self.db.scalars(
            select(ModelVersion).where(
                ModelVersion.scenario_id == model.scenario_id,
                ModelVersion.dataset_id == model.dataset_id,
                ModelVersion.id != model.id,
                ModelVersion.is_default.is_(True),
            )
        ).all()
        for other in others:
            other.is_default = False
        model.is_default = True
        self.commit()
        return ok(data=self._to_dict(model), message="已设为默认推荐模型")

    @service_call
    def clear_default(self, current_user, model_id: int):
        """取消默认推荐状态（仅 ADMIN）。"""
        self.require_admin(current_user)
        model = self._get(model_id)
        if not model.is_default:
            raise ServiceError(400, "该模型不是默认推荐模型")
        model.is_default = False
        self.commit()
        return ok(data=self._to_dict(model), message="已取消默认推荐状态")

    # ------------------------------------------------------------------
    # 查询（需求 6.7.3 / 6.7.5：普通用户仅可见已发布模型）
    # ------------------------------------------------------------------
    @service_call
    def get_list(
        self,
        current_user,
        scenario_id: Optional[int] = None,
        dataset_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ):
        """模型版本列表。

        - 普通用户：仅返回 PUBLISHED（需求 6.7.3.4 / 6.7.5.1），忽略 status 过滤。
        - 管理员：全部模型版本，可按状态过滤。
        """
        self.require_login(current_user)
        stmt = select(ModelVersion)
        if getattr(current_user, "role", None) != ROLE_ADMIN:
            stmt = stmt.where(ModelVersion.status.in_(USER_VISIBLE_MODEL_STATUSES))
        elif status:
            stmt = stmt.where(ModelVersion.status == status)
        if scenario_id is not None:
            stmt = stmt.where(ModelVersion.scenario_id == scenario_id)
        if dataset_id is not None:
            stmt = stmt.where(ModelVersion.dataset_id == dataset_id)
        stmt = stmt.order_by(ModelVersion.id.desc())
        result = paginate(self.db, stmt, page, page_size)
        result["items"] = [self._to_dict(m) for m in result["items"]]
        return ok(data=result)

    @service_call
    def get(self, current_user, model_id: int):
        """模型版本详情（含评估指标）。"""
        self.require_login(current_user)
        model = self._get(model_id)
        if (
            getattr(current_user, "role", None) != ROLE_ADMIN
            and model.status not in USER_VISIBLE_MODEL_STATUSES
        ):
            raise ServiceError(403, "无权限操作")
        return ok(data=self._to_dict(model))

    @service_call
    def get_default(
        self, current_user, scenario_id: int, dataset_id: int
    ):
        """获取某"场景＋数据集"的默认推荐模型（需求 6.7.4：无默认则返回 null）。"""
        self.require_login(current_user)
        model = self.db.scalar(
            select(ModelVersion).where(
                ModelVersion.scenario_id == scenario_id,
                ModelVersion.dataset_id == dataset_id,
                ModelVersion.is_default.is_(True),
            )
        )
        if model is None:
            return ok(data=None, message="当前范围暂无默认推荐模型")
        if (
            getattr(current_user, "role", None) != ROLE_ADMIN
            and model.status not in USER_VISIBLE_MODEL_STATUSES
        ):
            return ok(data=None, message="当前范围暂无可用默认推荐模型")
        return ok(data=self._to_dict(model))

    @service_call
    def compare(self, current_user, model_ids: List[int]):
        """模型版本对比（需求 6.2 P1）：普通用户只比较已发布模型。

        返回每个模型的评估指标（evaluation_metrics），供前端横向对比。
        """
        self.require_login(current_user)
        if not model_ids:
            raise ServiceError(400, "缺少模型版本 ID 列表")
        results: List[dict] = []
        for model_id in model_ids:
            model = self._get(model_id)
            if (
                getattr(current_user, "role", None) != ROLE_ADMIN
                and model.status not in USER_VISIBLE_MODEL_STATUSES
            ):
                raise ServiceError(403, "无权限操作")
            results.append(
                {
                    "model_version_id": model.id,
                    "scenario_id": model.scenario_id,
                    "dataset_id": model.dataset_id,
                    "algorithm_id": model.algorithm_id,
                    "evaluation_metrics": model.evaluation_metrics,
                    "status": model.status,
                    "is_default": model.is_default,
                }
            )
        return ok(data=results)

    # ------------------------------------------------------------------
    # 删除（仅 ADMIN；引用保护）
    # ------------------------------------------------------------------
    @service_call
    def delete(self, current_user, model_id: int):
        """删除模型版本（仅 ADMIN）。

        已被推理记录或风险事件引用的模型禁止删除，保持历史可追溯
        （需求 6.7.3.5 / 5.2.4）。
        """
        self.require_admin(current_user)
        model = self._get(model_id)
        ir_count = self.db.scalar(
            select(func.count()).select_from(InferenceRecord).where(
                InferenceRecord.model_version_id == model_id
            )
        )
        re_count = self.db.scalar(
            select(func.count()).select_from(RiskEvent).where(
                RiskEvent.model_version_id == model_id
            )
        )
        if ir_count or re_count:
            raise ServiceError(400, "模型已被推理记录或风险事件引用，禁止删除")
        self.db.delete(model)
        self.commit()
        return ok(message="模型版本已删除")
