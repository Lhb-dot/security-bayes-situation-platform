"""模型版本 Service（ModelVersion）—— 生命周期状态机核心。

对应需求文档章节：1.1（场景使用约束）、6.6.3（管理员参数配置规则）、
6.7（模型版本、发布与默认推荐规则）、6.5.2（权限矩阵）。

模型：app.models.model_version.ModelVersion。

状态机（需求 6.7.2）：
    TRAINING → FAILED / DRAFT → PUBLISHED → DISABLED
由 MODEL_STATUS_TRANSITIONS 常量驱动，禁止任意跳转。

关键业务规则：
1. 仅 ADMIN 可训练/发布/下线/设默认模型；普通用户仅可见与使用 PUBLISHED 模型。
2. 训练前必须选择场景、数据集版本和算法；数据集必须属于所选场景（禁止跨场景混合训练）；
   停用的数据集不得用于训练。
3. 每个"场景＋数据集"最多一个默认推荐模型；默认模型必须 PUBLISHED；
   默认模型下线时自动清除默认状态（需求 6.7.4.5）。
4. 发布和下线必须记录操作管理员及操作时间（published_by / published_at）。
"""
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_, select

from app.models.algorithm import Algorithm
from app.models.app_user import AppUser
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
    DATASET_VISIBILITY_PLATFORM,
    MODEL_STATUS_DRAFT,
    MODEL_STATUS_DISABLED,
    MODEL_STATUS_FAILED,
    MODEL_STATUS_OFFLINE,
    MODEL_STATUS_PUBLISHED,
    MODEL_STATUS_TRAINING,
    MODEL_STATUS_TRANSITIONS,
    ROLE_SCENARIO_ADMIN,
    ROLE_SUPER_ADMIN,
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

    def _require_manageable_model(self, current_user, model: ModelVersion) -> None:
        """Lifecycle operations follow the same dataset ownership boundary."""
        dataset = self.db.get(Dataset, model.dataset_id)
        if dataset is None:
            raise ServiceError(404, "模型绑定的数据集不存在")
        role = getattr(current_user, "role", None)
        if role == ROLE_SUPER_ADMIN:
            if dataset.visibility != DATASET_VISIBILITY_PLATFORM:
                raise ServiceError(403, "系统管理员只能管理平台数据集派生模型")
        elif role == ROLE_SCENARIO_ADMIN:
            if (
                model.scenario_id != getattr(current_user, "scenario_id", None)
                or dataset.visibility not in (DATASET_VISIBILITY_PLATFORM, "company")
            ):
                raise ServiceError(403, "无权限操作")
        else:
            raise ServiceError(403, "无权限操作")

    def _require_trainer(self, current_user, model: ModelVersion) -> None:
        """模型只能由发起训练的管理员发布。"""
        if getattr(current_user, "id", None) != model.trained_by:
            raise ServiceError(403, "只有训练该模型的管理员可以发布")

    def _to_dict(self, model: ModelVersion) -> dict:
        """Serialize a model with the display fields needed by the real model center."""
        data = row_to_dict(model)
        data.update(
            {
                "model_version_id": model.id,
                "scenario_code": model.scenario.code if model.scenario else None,
                "scenario_name": model.scenario.name if model.scenario else None,
                "dataset_logical_id": model.dataset.logical_id if model.dataset else None,
                "dataset_version": model.dataset.version if model.dataset else None,
                "algorithm_code": model.algorithm.code if model.algorithm else None,
                "algorithm_name": model.algorithm.display_name if model.algorithm else None,
                "trained_by_name": model.trainer.username if model.trainer else None,
                "published_by_name": model.publisher.username if model.publisher else None,
            }
        )
        return data

    def _validate_dataset_file(self, dataset: Dataset) -> Optional[str]:
        """校验训练数据文件与注册字段结构一致（需求 3.1.1 / 3.1.2）。

        检查项（任一失败 → 返回错误信息，禁止训练）：
        - 字段重名：实际文件出现同名两列
        - 标签字段缺失：label_field 不在实际文件中
        - 字段缺失：注册 schema 定义的字段必须全部存在于实际文件
        - 类型不匹配：注册类型（numeric/enum/string）与实际文件类型不一致
        只读 ARFF 头部（1 行），对大文件开销可忽略。
        """
        from app.services.training_executor import resolve_dataset_path
        from app.utils.arff_reader import read_arff

        path = resolve_dataset_path(dataset.file_path)
        if not os.path.exists(path):
            return f"数据集文件不存在: {path}"
        try:
            actual_fields, _ = read_arff(path, max_rows=1)
        except Exception as exc:  # noqa: BLE001
            return f"数据集文件解析失败: {exc}"

        actual_names = [f["name"] for f in actual_fields]
        seen: set = set()
        for name in actual_names:
            if name in seen:
                return f"数据集文件字段重名: {name}，禁止训练"
            seen.add(name)

        if dataset.label_field not in actual_names:
            return f"标签字段 {dataset.label_field} 缺失，缺少标签无法监督训练，禁止训练"

        schema = dataset.fields_schema or []
        schema_names = [f["name"] for f in schema]
        missing = [name for name in schema_names if name not in actual_names]
        if missing:
            shown = "、".join(missing[:5])
            suffix = " 等" if len(missing) > 5 else ""
            return f"数据集缺少注册字段: {shown}{suffix}，禁止训练"

        actual_type = {f["name"]: f["type"] for f in actual_fields}
        for field in schema:
            expect = field.get("type")
            got = actual_type.get(field["name"])
            if expect == "numeric" and got != "numeric":
                return f"字段 {field['name']} 类型不匹配：注册为 {expect}，实际为 {got}，禁止训练"
            if expect == "enum" and got != "enum":
                return f"字段 {field['name']} 类型不匹配：注册为 {expect}，实际为 {got}，禁止训练"
            if expect == "string" and got != "string":
                return f"字段 {field['name']} 类型不匹配：注册为 {expect}，实际为 {got}，禁止训练"
        return None

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
        """启动训练：生成 TRAINING 状态的模型版本（管理级角色，场景管理员仅自己场景）。

        校验：场景存在；数据集属于所选场景（需求 1.1.3/2.2.3 禁止跨场景混合训练）；
        数据集 ACTIVE；算法 AVAILABLE；training_parameters 必须完整（需求 6.6.3.4）。
        """
        self.require_scenario_admin_of(current_user, scenario_id)

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
        if dataset.visibility != DATASET_VISIBILITY_PLATFORM and getattr(current_user, "role", None) == ROLE_SUPER_ADMIN:
            raise ServiceError(403, "系统管理员只能使用平台数据集训练模型")
        if (
            getattr(current_user, "role", None) == ROLE_SCENARIO_ADMIN
            and dataset.visibility not in (DATASET_VISIBILITY_PLATFORM, "company")
        ):
            raise ServiceError(403, "场景管理员不能使用个人数据集训练模型")

        algorithm = self.db.get(Algorithm, algorithm_id)
        if algorithm is None:
            raise ServiceError(404, "算法不存在")
        if algorithm.status != ALGORITHM_STATUS_AVAILABLE:
            raise ServiceError(400, "算法不可用，不能用于训练")

        if not isinstance(training_parameters, dict):
            raise ServiceError(400, "training_parameters 必须是 JSON 对象")
        # 按算法注册的 param_schema 校验必填项、类型与范围（需求 6.6.3.2/6.6.3.4）。
        # 对 param_schema 为空的算法（如 PMWNB 不暴露超参数，使用服务内置默认参数），
        # 允许传入空对象 {}。
        err = validate_params_schema(algorithm.param_schema, training_parameters)
        if err:
            raise ServiceError(400, err)

        # 训练数据与注册字段结构一致性校验（需求 3.1.1/3.1.2）：
        # 字段缺失 / 重名 / 类型不匹配 / 标签字段缺失 → 禁止训练。
        file_err = self._validate_dataset_file(dataset)
        if file_err:
            raise ServiceError(400, file_err)

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
    def train_and_save(
        self,
        current_user,
        scenario_id: int,
        dataset_id: int,
        algorithm_id: int,
        training_parameters: Dict[str, Any],
    ):
        """训练并落库（需求 6.7.1 训练执行接口，单次调用完成真实训练）。

        复用 create() 完成场景/数据集/算法/参数校验并创建 TRAINING 版本，随后：
        所有算法均调用对应 Java/Weka 真实服务，成功 → TRAINING → DRAFT；
        服务异常 → TRAINING → FAILED。
        """
        created = self.create(
            current_user, scenario_id, dataset_id, algorithm_id, training_parameters
        )
        if created.code != 0:
            # create() 内部把 ServiceError 转成了 fail 响应（不抛出），此处重新抛出让本
            # 方法的 @service_call 按统一语义返回 HTTP 状态码。
            raise ServiceError(created.code, created.message)

        model = self._get(created.data["id"])
        algorithm = self.db.get(Algorithm, algorithm_id)
        try:
            metrics = self._run_algorithm_training(
                model, algorithm.code, model.training_parameters or {}
            )
            self._transition(model, MODEL_STATUS_DRAFT)
            model.evaluation_metrics = metrics
            self.commit()
        except Exception as exc:
            self._transition(model, MODEL_STATUS_FAILED)
            model.evaluation_metrics = {"source": "error", "error": str(exc)}
            self.commit()
            raise ServiceError(500, f"训练失败：{exc}")
        return ok(data=self._to_dict(model), message="训练完成，模型进入 DRAFT 待发布")

    def _run_algorithm_training(
        self, model: ModelVersion, algorithm_code: str, training_parameters: dict
    ) -> dict:
        """调用对应 Java 算法服务，并把注册 schema 校验后的参数传入 /train。"""
        from app.services.training_executor import (
            build_model_save_path,
            execute_algorithm_training,
            resolve_dataset_path,
        )

        dataset = self.db.get(Dataset, model.dataset_id)
        if dataset is None:
            raise ServiceError(404, "数据集不存在")
        dataset_path = resolve_dataset_path(dataset.file_path)
        model_save_path = build_model_save_path(model.id, algorithm_code)
        return execute_algorithm_training(
            algorithm_code, dataset_path, model_save_path, training_parameters
        )

    @service_call
    def complete_training(
        self, current_user, model_id: int, evaluation_metrics: Dict[str, Any]
    ):
        """训练成功：TRAINING → DRAFT，保存评估指标（需求 6.7.2 转换条件）。"""
        if not isinstance(evaluation_metrics, dict):
            raise ServiceError(400, "evaluation_metrics 必须是 JSON 对象")
        model = self._get(model_id)
        self.require_scenario_admin_of(current_user, model.scenario_id)
        self._require_manageable_model(current_user, model)
        self._transition(model, MODEL_STATUS_DRAFT)
        model.evaluation_metrics = evaluation_metrics
        self.commit()
        return ok(data=self._to_dict(model), message="训练完成，模型进入 DRAFT 待发布")

    @service_call
    def fail_training(
        self, current_user, model_id: int, error_message: Optional[str] = None
    ):
        """训练失败：TRAINING → FAILED。"""
        model = self._get(model_id)
        self.require_scenario_admin_of(current_user, model.scenario_id)
        self._require_manageable_model(current_user, model)
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
        """发布模型：仅训练人可将 DRAFT 模型发布。"""
        model = self._get(model_id)
        self.require_scenario_admin_of(current_user, model.scenario_id)
        self._require_manageable_model(current_user, model)
        self._require_trainer(current_user, model)
        self._transition(model, MODEL_STATUS_PUBLISHED, operator_id=current_user.id)
        self.commit()
        return ok(data=self._to_dict(model), message="模型已发布")

    @service_call
    def offline(self, current_user, model_id: int):
        """兼容旧接口：将已发布模型禁用。

        需求 6.7.4.5：默认模型被下线时，系统必须同时取消其默认状态（is_default=False）。
        """
        model = self._get(model_id)
        self.require_scenario_admin_of(current_user, model.scenario_id)
        self._require_manageable_model(current_user, model)
        self._transition(model, MODEL_STATUS_DISABLED)
        if model.is_default:
            model.is_default = False
        self.commit()
        return ok(data=self._to_dict(model), message="模型已禁用，默认推荐状态已清除")

    @service_call
    def disable(self, current_user, model_id: int):
        """禁用模型：PUBLISHED → DISABLED，保留模型记录。"""
        model = self._get(model_id)
        self.require_scenario_admin_of(current_user, model.scenario_id)
        self._require_manageable_model(current_user, model)
        self._transition(model, MODEL_STATUS_DISABLED)
        if model.is_default:
            model.is_default = False
        self.commit()
        return ok(data=self._to_dict(model), message="模型已禁用，默认推荐状态已清除")

    @service_call
    def enable(self, current_user, model_id: int):
        """重新启用模型：DISABLED → PUBLISHED。

禁用时已清除默认推荐标记，重新启用后不自动恢复，需管理员根据当前场景单独设置。
        """
        model = self._get(model_id)
        self.require_scenario_admin_of(current_user, model.scenario_id)
        self._require_manageable_model(current_user, model)
        self._transition(model, MODEL_STATUS_PUBLISHED, operator_id=current_user.id)
        self.commit()
        return ok(data=self._to_dict(model), message="模型已重新启用")

    @service_call
    def set_default(self, current_user, model_id: int):
        """设置默认推荐模型（需求 6.7.4）。

        约束：必须 PUBLISHED；每个"场景＋数据集"最多一个默认模型（先清除同范围旧默认，
        与 uk_mv_default 部分唯一索引保持一致）。
        """
        model = self._get(model_id)
        self.require_scenario_admin_of(current_user, model.scenario_id)
        self._require_manageable_model(current_user, model)
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
        """取消默认推荐状态（管理级角色，仅场景内）。"""
        model = self._get(model_id)
        self.require_scenario_admin_of(current_user, model.scenario_id)
        self._require_manageable_model(current_user, model)
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

        - 最外层管理员：仅自己训练的模型，可按状态过滤。
        - 场景管理员：自己场景内全部模型版本（管理视角）。
        - 场景用户：仅已发布模型（需求 6.7.3.4 / 6.7.5.1）。
        """
        self.require_login(current_user)
        role = getattr(current_user, "role", None)
        stmt = select(ModelVersion)
        if role == ROLE_SUPER_ADMIN:
            # 系统管理员不能看到场景管理员训练的模型，避免跨管理员泄露模型资产。
            stmt = stmt.where(ModelVersion.trained_by == current_user.id)
            if status:
                stmt = stmt.where(ModelVersion.status == status)
        elif role == ROLE_SCENARIO_ADMIN:
            # 普通管理员可以管理本场景模型，但不展示系统管理员尚未发布的模型。
            # 系统管理员已发布的模型仍可作为本场景可用模型展示。
            stmt = (
                stmt.join(Dataset, Dataset.id == ModelVersion.dataset_id)
                .join(AppUser, AppUser.id == ModelVersion.trained_by)
                .where(
                    ModelVersion.scenario_id == getattr(current_user, "scenario_id", None),
                    Dataset.visibility.in_((DATASET_VISIBILITY_PLATFORM, "company")),
                    or_(
                        AppUser.role != ROLE_SUPER_ADMIN,
                        ModelVersion.status == MODEL_STATUS_PUBLISHED,
                    ),
                )
            )
            if status:
                stmt = stmt.where(ModelVersion.status == status)
        else:
            # 场景用户：仅看到绑定场景中可用的已发布模型；个人模型仅限本人。
            stmt = stmt.join(Dataset, Dataset.id == ModelVersion.dataset_id).where(
                ModelVersion.status.in_(USER_VISIBLE_MODEL_STATUSES)
            )
            bound = getattr(current_user, "scenario_id", None)
            if bound is None:
                return ok(data={"items": [], "total": 0, "page": page, "page_size": page_size})
            stmt = stmt.where(
                ModelVersion.scenario_id == bound,
                (Dataset.visibility.in_((DATASET_VISIBILITY_PLATFORM, "company")))
                | ((Dataset.visibility == "personal") & (Dataset.uploaded_by == current_user.id)),
            )
        if scenario_id is not None:
            if role != ROLE_SUPER_ADMIN:
                self.require_scenario_access(current_user, scenario_id)
            stmt = stmt.where(ModelVersion.scenario_id == scenario_id)
        if dataset_id is not None:
            stmt = stmt.where(ModelVersion.dataset_id == dataset_id)
        stmt = stmt.order_by(ModelVersion.id.desc())
        result = paginate(self.db, stmt, page, page_size)
        result["items"] = [self._to_dict(m) for m in result["items"]]
        return ok(data=result)

    def _can_view_model(self, current_user, model: ModelVersion) -> bool:
        """模型可见性（需求 0.2 / 6.7）。

        - SUPER_ADMIN：仅自己训练的模型
        - SCENARIO_ADMIN：自己场景全部
        - SCENARIO_USER：仅已发布
        """
        role = getattr(current_user, "role", None)
        if role == ROLE_SUPER_ADMIN:
            return model.trained_by == getattr(current_user, "id", None)
        if role == ROLE_SCENARIO_ADMIN:
            dataset = self.db.get(Dataset, model.dataset_id)
            trainer = self.db.get(AppUser, model.trained_by)
            return (
                model.scenario_id == getattr(current_user, "scenario_id", None)
                and bool(dataset)
                and dataset.visibility in (DATASET_VISIBILITY_PLATFORM, "company")
                and not (
                    trainer
                    and trainer.role == ROLE_SUPER_ADMIN
                    and model.status != MODEL_STATUS_PUBLISHED
                )
            )
        dataset = self.db.get(Dataset, model.dataset_id)
        return (
            model.scenario_id == getattr(current_user, "scenario_id", None)
            and model.status in USER_VISIBLE_MODEL_STATUSES
            and bool(dataset)
            and (
                dataset.visibility in (DATASET_VISIBILITY_PLATFORM, "company")
                or (
                    dataset.visibility == "personal"
                    and dataset.uploaded_by == getattr(current_user, "id", None)
                )
            )
        )

    @service_call
    def get(self, current_user, model_id: int):
        """模型版本详情（含评估指标）。"""
        self.require_login(current_user)
        model = self._get(model_id)
        if not self._can_view_model(current_user, model):
            raise ServiceError(403, "无权限操作")
        return ok(data=self._to_dict(model))

    @service_call
    def get_default(
        self, current_user, scenario_id: int, dataset_id: int
    ):
        """获取某"场景＋数据集"的默认推荐模型（需求 6.7.4：无默认则返回 null）。"""
        self.require_scenario_access(current_user, scenario_id)
        model = self.db.scalar(
            select(ModelVersion).where(
                ModelVersion.scenario_id == scenario_id,
                ModelVersion.dataset_id == dataset_id,
                ModelVersion.is_default.is_(True),
            )
        )
        if model is None:
            return ok(data=None, message="当前范围暂无默认推荐模型")
        if not self._can_view_model(current_user, model):
            return ok(data=None, message="当前范围暂无可用默认推荐模型")
        return ok(data=self._to_dict(model))

    @service_call
    def compare(self, current_user, model_ids: List[int]):
        """模型版本对比（需求 6.2 P1）：场景用户只比较已发布模型。

        返回每个模型的评估指标（evaluation_metrics），供前端横向对比。
        """
        self.require_login(current_user)
        if not model_ids:
            raise ServiceError(400, "缺少模型版本 ID 列表")
        results: List[dict] = []
        for model_id in model_ids:
            model = self._get(model_id)
            if not self._can_view_model(current_user, model):
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
        """删除模型版本（管理级角色，仅场景内）。

        已被推理记录或风险事件引用的模型禁止删除，保持历史可追溯
        （需求 6.7.3.5 / 5.2.4）。
        """
        model = self._get(model_id)
        self.require_scenario_admin_of(current_user, model.scenario_id)
        self._require_manageable_model(current_user, model)
        if model.status != MODEL_STATUS_DISABLED:
            raise ServiceError(400, "只有禁用中的模型才能删除")
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
