"""数据集 Service（Dataset，含"数据集版本"管理）。

对应需求文档章节：2.2（数据集绑定规则）、2.3（数据集管理、版本与删除规则）、
3.1（固定字段统一要求）、6.5.2（权限矩阵）。

模型：app.models.dataset.Dataset。说明：ORM 中没有独立的 DatasetVersion 表，
"数据集版本"由 dataset.logical_id + dataset.version 联合唯一表示（uk_dataset_logical_version），
版本管理逻辑（自动递增版本号、引用保护、停用/删除规则）在本 Service 内实现。

关键业务规则（需求 2.3）：
1. 仅 ADMIN 可上传/修改/停用/删除；ADMIN 之间共享权限，不按上传人隔离。
2. 上传必须指定场景，并完成格式、固定字段、字段类型、标签字段校验。
3. 已产生模型版本的数据集不得直接覆盖——"修改"必须创建新版本并保留旧版本。
4. 已被模型版本引用的数据集版本不得物理删除，只能停用；未引用的可物理删除。
5. 停用数据集不得用于新的模型训练（model_version service 侧校验）。
6. 普通用户只能查看与已发布模型有关的数据集（需求 2.3.1）。
"""
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, select

from app.models.dataset import Dataset
from app.models.model_version import ModelVersion
from app.models.scenario import Scenario
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    DATASET_FILE_PATH_MAX_LEN,
    DATASET_LABEL_FIELD_MAX_LEN,
    DATASET_LOGICAL_ID_MAX_LEN,
    DATASET_STATUS_ACTIVE,
    DATASET_STATUS_INACTIVE,
    DATASET_STATUSES,
    MODEL_STATUS_PUBLISHED,
    ROLE_ADMIN,
)
from app.utils.common import (
    get_logger,
    paginate,
    row_to_dict,
    validate_enum,
    validate_fields_schema,
    validate_length,
    validate_required,
)

logger = get_logger("dataset")


class DatasetService(ServiceBase):
    """数据集管理（上传/版本/停用/删除）+ 字段结构校验。"""

    def _get(self, dataset_id: int) -> Dataset:
        dataset = self.db.get(Dataset, dataset_id)
        if dataset is None:
            raise ServiceError(404, "数据集不存在")
        return dataset

    def _next_version(self, logical_id: str) -> int:
        max_version = self.db.scalar(
            select(func.max(Dataset.version)).where(Dataset.logical_id == logical_id)
        ) or 0
        return int(max_version) + 1

    def _is_referenced(self, dataset_id: int) -> bool:
        count = self.db.scalar(
            select(func.count()).select_from(ModelVersion).where(
                ModelVersion.dataset_id == dataset_id
            )
        )
        return bool(count)

    @staticmethod
    def _to_dict(dataset: Dataset) -> dict:
        return row_to_dict(dataset)

    # ------------------------------------------------------------------
    # 查询（需求 2.3.1 / 6.5.2：查看列表与字段预览 → 允许/允许）
    # ------------------------------------------------------------------
    @service_call
    def get_list(
        self,
        current_user,
        scenario_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 10,
    ):
        """数据集列表（按场景过滤可选）。

        普通用户仅能看到与已发布模型有关的数据集（需求 2.3.1）。
        """
        self.require_login(current_user)
        stmt = select(Dataset)
        if scenario_id is not None:
            stmt = stmt.where(Dataset.scenario_id == scenario_id)
        if getattr(current_user, "role", None) != ROLE_ADMIN:
            # 需求 V3.0 §1.1.6：普通用户仅看到被分配场景的数据集
            bound = getattr(current_user, "scenario_id", None)
            if bound is None:
                return ok(data={"items": [], "total": 0, "page": page, "page_size": page_size})
            stmt = stmt.where(Dataset.scenario_id == bound)
            stmt = stmt.where(
                Dataset.id.in_(
                    select(ModelVersion.dataset_id).where(
                        ModelVersion.status == MODEL_STATUS_PUBLISHED
                    )
                )
            )
        stmt = stmt.order_by(Dataset.logical_id, Dataset.version)
        result = paginate(self.db, stmt, page, page_size)
        result["items"] = [self._to_dict(d) for d in result["items"]]
        return ok(data=result)

    @service_call
    def get(self, current_user, dataset_id: int):
        """数据集详情（含字段结构 fields_schema）。"""
        self.require_login(current_user)
        dataset = self._get(dataset_id)
        if getattr(current_user, "role", None) != ROLE_ADMIN:
            published = self.db.scalar(
                select(func.count()).select_from(ModelVersion).where(
                    ModelVersion.dataset_id == dataset_id,
                    ModelVersion.status == MODEL_STATUS_PUBLISHED,
                )
            )
            if not published:
                raise ServiceError(403, "无权限操作")
        return ok(data=self._to_dict(dataset))

    # ------------------------------------------------------------------
    # 上传 / 版本 / 停用 / 删除（需求 2.3：仅 ADMIN）
    # ------------------------------------------------------------------
    @service_call
    def create(
        self,
        current_user,
        logical_id: str,
        scenario_id: int,
        file_path: str,
        fields_schema: List[Dict],
        label_field: str,
    ):
        """上传数据集（仅 ADMIN），版本号自动取该 logical_id 的最大版本 + 1。"""
        self.require_admin(current_user)
        err = validate_required(
            {"logical_id": logical_id, "file_path": file_path, "label_field": label_field},
            ("logical_id", "file_path", "label_field"),
        )
        if err:
            raise ServiceError(400, err)
        err = validate_length(logical_id, "logical_id", DATASET_LOGICAL_ID_MAX_LEN)
        if err:
            raise ServiceError(400, err)
        err = validate_length(file_path, "file_path", DATASET_FILE_PATH_MAX_LEN)
        if err:
            raise ServiceError(400, err)
        err = validate_length(label_field, "label_field", DATASET_LABEL_FIELD_MAX_LEN)
        if err:
            raise ServiceError(400, err)

        scenario = self.db.get(Scenario, scenario_id)
        if scenario is None:
            raise ServiceError(404, "场景不存在")
        err = validate_fields_schema(fields_schema, label_field)
        if err:
            raise ServiceError(400, err)

        now = datetime.now(timezone.utc)
        dataset = Dataset(
            logical_id=logical_id,
            version=self._next_version(logical_id),
            scenario_id=scenario_id,
            file_path=file_path,
            fields_schema=fields_schema,
            label_field=label_field,
            uploaded_by=current_user.id,
            uploaded_at=now,
            status=DATASET_STATUS_ACTIVE,
        )
        self.db.add(dataset)
        self.commit()
        return ok(data=self._to_dict(dataset), message="数据集上传成功")

    @service_call
    def update(
        self,
        current_user,
        dataset_id: int,
        file_path: Optional[str] = None,
        fields_schema: Optional[List[Dict]] = None,
        label_field: Optional[str] = None,
    ):
        """修改数据集（仅 ADMIN）。

        需求 2.3.3：已产生模型版本的数据集不得直接覆盖——自动创建新版本
        （version+1）并保留旧版本；未被任何模型版本引用的可直接更新当前行。
        """
        self.require_admin(current_user)
        dataset = self._get(dataset_id)

        if self._is_referenced(dataset_id):
            # 创建新版本：继承 logical_id / scenario，version+1
            now = datetime.now(timezone.utc)
            new_dataset = Dataset(
                logical_id=dataset.logical_id,
                version=self._next_version(dataset.logical_id),
                scenario_id=dataset.scenario_id,
                file_path=file_path if file_path is not None else dataset.file_path,
                fields_schema=fields_schema if fields_schema is not None else dataset.fields_schema,
                label_field=label_field if label_field is not None else dataset.label_field,
                uploaded_by=current_user.id,
                uploaded_at=now,
                status=DATASET_STATUS_ACTIVE,
            )
            err = validate_fields_schema(
                new_dataset.fields_schema, new_dataset.label_field
            )
            if err:
                raise ServiceError(400, err)
            self.db.add(new_dataset)
            self.commit()
            return ok(
                data=self._to_dict(new_dataset),
                message="原数据集已被模型引用，已创建新版本（旧版本保留）",
            )

        # 未被引用：直接更新当前行
        if file_path is not None:
            err = validate_length(file_path, "file_path", DATASET_FILE_PATH_MAX_LEN)
            if err:
                raise ServiceError(400, err)
            dataset.file_path = file_path
        if label_field is not None or fields_schema is not None:
            new_label = label_field if label_field is not None else dataset.label_field
            new_schema = fields_schema if fields_schema is not None else dataset.fields_schema
            err = validate_fields_schema(new_schema, new_label)
            if err:
                raise ServiceError(400, err)
            dataset.label_field = new_label
            dataset.fields_schema = new_schema
        self.commit()
        return ok(data=self._to_dict(dataset), message="数据集修改成功")

    @service_call
    def disable(self, current_user, dataset_id: int):
        """停用数据集（仅 ADMIN）。

        需求 2.3.5/2.3.7：停用后不得用于新的模型训练，但历史模型、训练记录、
        评估结果、推理记录和风险事件仍保持可追溯（本方法不触碰历史数据）。
        """
        self.require_admin(current_user)
        dataset = self._get(dataset_id)
        dataset.status = DATASET_STATUS_INACTIVE
        self.commit()
        return ok(data=self._to_dict(dataset), message="数据集已停用")

    @service_call
    def delete(self, current_user, dataset_id: int):
        """物理删除数据集（仅 ADMIN）。

        需求 2.3.5/2.3.6：被任何模型版本引用的数据集版本只能停用，不能物理删除；
        未被引用的可以物理删除。
        """
        self.require_admin(current_user)
        dataset = self._get(dataset_id)
        if self._is_referenced(dataset_id):
            raise ServiceError(400, "数据集已被模型版本引用，禁止物理删除，只能停用")
        self.db.delete(dataset)
        self.commit()
        return ok(message="数据集已删除")

    @service_call
    def get_fields_schema(self, current_user, dataset_id: int):
        """字段预览（需求 3.1.4：字段名、字段类型、字段角色、样例值由上层提供）。"""
        self.require_login(current_user)
        dataset = self._get(dataset_id)
        if getattr(current_user, "role", None) != ROLE_ADMIN:
            published = self.db.scalar(
                select(func.count()).select_from(ModelVersion).where(
                    ModelVersion.dataset_id == dataset_id,
                    ModelVersion.status == MODEL_STATUS_PUBLISHED,
                )
            )
            if not published:
                raise ServiceError(403, "无权限操作")
        return ok(
            data={
                "dataset_id": dataset.id,
                "logical_id": dataset.logical_id,
                "version": dataset.version,
                "label_field": dataset.label_field,
                "fields_schema": dataset.fields_schema,
            }
        )

    @service_call
    def get_preview(
        self,
        current_user,
        dataset_id: int,
        page: int = 1,
        page_size: int = 50,
    ):
        """数据内容预览（需求 2.4：前 N 条数据、标签列高亮、分页）。

        - 权限：管理员全部数据集；普通用户仅与已发布模型关联的数据集（2.4.4）
        - 性能：单次最多返回 50 条（2.4.5），后端从 ARFF 直接读取，读多少算多少
        """
        self.require_login(current_user)
        if page_size > 50:
            page_size = 50  # 2.4.5 每页最多 50 条
        dataset = self._get(dataset_id)
        if getattr(current_user, "role", None) != ROLE_ADMIN:
            published = self.db.scalar(
                select(func.count()).select_from(ModelVersion).where(
                    ModelVersion.dataset_id == dataset_id,
                    ModelVersion.status == MODEL_STATUS_PUBLISHED,
                )
            )
            if not published:
                raise ServiceError(403, "无权限操作")

        from app.services.training_executor import resolve_dataset_path
        from app.utils.arff_reader import count_arff_rows, read_arff

        path = resolve_dataset_path(dataset.file_path)
        if not os.path.exists(path):
            raise ServiceError(404, f"数据集文件不存在: {path}")

        offset = (page - 1) * page_size
        _, rows = read_arff(path, max_rows=offset + page_size)  # 读够本页即可
        page_rows = rows[offset: offset + page_size]
        return ok(
            data={
                "dataset_id": dataset.id,
                "logical_id": dataset.logical_id,
                "version": dataset.version,
                "label_field": dataset.label_field,
                "fields_schema": dataset.fields_schema,
                "rows": page_rows,
                "page": page,
                "page_size": len(page_rows),
                "total": count_arff_rows(path),
            }
        )
