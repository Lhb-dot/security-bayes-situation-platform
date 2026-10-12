"""数据集 Service（Dataset，含"数据集版本"管理）。

对应需求文档章节：2.2（数据集绑定规则）、2.3（数据集管理、版本与删除规则）、
3.1（固定字段统一要求）、6.5.2（权限矩阵）。

模型：app.models.dataset.Dataset。说明：ORM 中没有独立的 DatasetVersion 表，
"数据集版本"由 dataset.logical_id + dataset.version 联合唯一表示（uk_dataset_logical_version），
版本管理逻辑（自动递增版本号、引用保护、停用/删除规则）在本 Service 内实现。

关键业务规则（需求 2.3）：
1. 管理级角色可修改/停用/删除；新建数据集还允许 SCENARIO_USER 上传本人场景的个人数据。
2. 上传必须指定场景，并完成格式、固定字段、字段类型、标签字段校验。
3. 已产生模型版本的数据集不得直接覆盖——"修改"必须创建新版本并保留旧版本。
4. 已被模型版本引用的数据集版本不得物理删除，只能停用；未引用的可物理删除。
5. 停用数据集不得用于新的模型训练（model_version service 侧校验）。
6. 普通用户只能查看与已发布模型有关的数据集（需求 2.3.1）。

迭代模型（app/services/dataset_iteration.py）：
所有数据/结构/元数据变更统一走 ``_revise`` —— **迭代**与**版本**分离：
每次迭代都落一条 dataset_revision 记录，是否新开版本快照由
``resolve_iteration_policy(change_type, referenced)`` 决定。于是"修改字段"与
"追加数据条数"不需要两套逻辑：追加是兼容迭代（未引用时原地更新，不涨版本），
改字段是破坏性迭代（必然新开版本留痕）。
"""
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload
from app.paths import PROJECT_ROOT
from app.models.dataset import Dataset
from app.models.dataset_revision import DatasetRevision
from app.models.model_version import ModelVersion
from app.models.scenario import Scenario
from app.schemas.common import ok
from app.security.policy import default_dataset_visibility
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.dataset_iteration import (
    CHANGE_TYPE_APPEND_ROWS,
    CHANGE_TYPE_CREATE,
    CHANGE_TYPE_REPLACE_FILE,
    CHANGE_TYPE_SCHEMA_CHANGE,
    CHANGE_TYPES,
    MODE_IN_PLACE,
    MODE_NEW_VERSION,
    change_type_label,
    resolve_iteration_policy,
)
from app.services.constants import (
    DATASET_FILE_PATH_MAX_LEN,
    DATASET_LABEL_FIELD_MAX_LEN,
    DATASET_LOGICAL_ID_MAX_LEN,
    DATASET_STATUS_ACTIVE,
    DATASET_STATUS_INACTIVE,
    dataset_display_name_of,
    ROLE_SCENARIO_USER,
)
from app.utils.common import (
    get_logger,
    paginate,
    row_to_dict,
    validate_fields_schema,
    validate_length,
    validate_required,
)

logger = get_logger("dataset")


def _invalidate_dashboard_cache() -> None:
    """数据集登记 / 修改 / 删除后清掉首页聚合的进程级缓存。

    首页与场景中心的数据集统计（有效样本量、风险占比等）在 dashboard_service 里
    按 dataset_id 做了进程级缓存，数据集元数据变更后必须清掉，否则页面会显示旧值。
    """
    from app.services.dashboard_service import clear_dataset_caches

    clear_dataset_caches()


class DatasetService(ServiceBase):
    @staticmethod
    def _validate_file_path(file_path: str) -> Optional[str]:
        """Keep registered dataset paths inside the repository data directory."""
        if not file_path or Path(file_path).is_absolute():
            return "file_path 必须是 data/ 目录下的相对路径"
        candidate = Path(file_path)
        if ".." in candidate.parts or candidate.parts[:1] != ("data",):
            return "file_path 必须位于 data/ 目录内"
        return None

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

    def _record_revision(
        self,
        *,
        dataset: Dataset,
        change_type: str,
        is_breaking: bool,
        mode: str,
        reason: str,
        summary: Optional[str],
        detail: Optional[Dict],
        current_user,
        result_dataset_id: Optional[int],
        created_at: datetime,
    ) -> None:
        """写一条迭代记录（原地更新也留痕，保证「迭代 = 全部记录」）。

        dataset_id 指向被迭代的目标版本行；result_dataset_id 仅在新建版本时给出。
        """
        self.db.add(
            DatasetRevision(
                logical_id=dataset.logical_id,
                dataset_id=dataset.id,
                change_type=change_type,
                is_breaking=is_breaking,
                mode=mode,
                result_dataset_id=result_dataset_id,
                reason=reason,
                summary=summary,
                detail=detail,
                created_by=current_user.id,
                created_at=created_at,
            )
        )

    def _iteration_target_path(self, dataset: Dataset, fmt: str) -> str:
        """为一次「带文件」的迭代生成新的物理文件相对路径。

        统一写到新文件而不是就地覆盖：旧版本行可能仍指向原文件（例如只改字段时
        沿用同一份数据文件），就地覆盖会污染历史版本。文件名带时间戳保证唯一。
        """
        normalized = dataset.file_path.replace("\\", "/")
        # Path.parent 在 Windows 上会给出反斜杠，统一成正斜杠，避免同一逻辑在不同
        # 平台/历史数据上生成两种写法（读取侧 resolve_dataset_path 两者都认）。
        parent = str(Path(normalized).parent).replace("\\", "/")
        stem = Path(normalized).stem
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        return f"{parent}/{stem}__rev{stamp}.{fmt}"

    _record_count_cache: dict = {}

    def _count_records(self, file_path: str) -> int:
        """统计 ARFF 样本数（按 path+mtime 缓存，避免列表接口重复扫盘）。"""
        from app.services.training_executor import resolve_dataset_path
        from app.utils.arff_reader import count_arff_rows

        try:
            path = resolve_dataset_path(file_path)
            if not os.path.exists(path):
                return 0
            mtime = os.path.getmtime(path)
            cached = DatasetService._record_count_cache.get(path)
            if cached and cached[0] == mtime:
                return cached[1]
            total = count_arff_rows(path)
            DatasetService._record_count_cache[path] = (mtime, total)
            return total
        except Exception:
            logger.exception("统计数据集样本数失败: %s", file_path)
            return 0

    def _to_dict(self, dataset: Dataset) -> dict:
        """序列化数据集，并补充前端列表/详情常用展示字段。"""
        data = row_to_dict(dataset)
        data["name"] = dataset_display_name_of(dataset)
        data["field_count"] = len(dataset.fields_schema or [])
        normalized = dataset.file_path.replace("\\", "/")
        suffix = Path(normalized).suffix.lstrip(".").lower()
        data["data_format"] = suffix if suffix in ("csv", "arff", "json") else "arff"
        # 原始文件名（登记时的源文件名，如 DIS_raw_data.arff）。仅作源文件溯源，
        # 不参与展示 —— 展示名统一由 dataset_display_name_of() 给出（= logical_id）。
        data["file_name"] = Path(normalized).name
        data["record_count"] = self._count_records(dataset.file_path)
        data["referenced"] = self._is_referenced(dataset.id)
        data["enabled"] = dataset.status == DATASET_STATUS_ACTIVE
        # 迭代元数据：版本是怎么来的、是否破坏兼容、血缘上一版（前端展示变更标签）。
        data["change_type"] = dataset.change_type
        data["change_type_label"] = (
            change_type_label(dataset.change_type) if dataset.change_type else None
        )
        data["is_breaking"] = bool(dataset.is_breaking)
        data["base_version_id"] = dataset.base_version_id
        # 上传人展示名：前端列表/版本管理只认名字，不再显示 uploaded_by 编号
        # （与 model_version_service 的 trained_by_name / published_by_name 同款做法）。
        data["uploader_name"] = dataset.uploader.username if dataset.uploader else None
        if getattr(dataset, "scenario", None) is not None:
            data["scenario_code"] = dataset.scenario.code
            data["scenario_name"] = dataset.scenario.name
        return data

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

        可见性一律由 :meth:`Authz.scope_datasets` 追加条件：
        - SUPER_ADMIN：仅 platform；
        - SCENARIO_ADMIN：本场景全部（含 personal）；
        - SCENARIO_USER：本场景 platform + company + 本人 personal。
        """
        self.require_login(current_user)
        stmt = select(Dataset).options(joinedload(Dataset.uploader))
        stmt = self.authz.scope_datasets(stmt, current_user)
        if scenario_id is not None:
            stmt = stmt.where(Dataset.scenario_id == scenario_id)
        stmt = stmt.order_by(Dataset.logical_id, Dataset.version)
        result = paginate(self.db, stmt, page, page_size)
        result["items"] = [self._to_dict(d) for d in result["items"]]
        return ok(data=result)

    @service_call
    def get(self, current_user, dataset_id: int):
        """数据集详情（含字段结构 fields_schema）。

        与列表一致，可见性统一由 :meth:`Authz.can_view_dataset` 判定（需求 0.2 / 2.4）。
        """
        self.require_login(current_user)
        dataset = self._get(dataset_id)
        if not self.authz.can_view_dataset(current_user, dataset):
            raise ServiceError(403, "无权限操作")
        return ok(data=self._to_dict(dataset))

    # ------------------------------------------------------------------
    # 上传 / 版本 / 停用 / 删除（数据级别由上传者角色决定，创建后不可变）
    # ------------------------------------------------------------------
    def _authorize_upload(self, current_user, scenario_id: int) -> Optional[str]:
        """上传授权（create 与 upload_from_file 共用），返回调用者角色。

        - SCENARIO_ADMIN：仅自己绑定的场景（上传即 company 数据）；
        - SCENARIO_USER：仅自己绑定的场景（上传即 personal 数据）；
        - SUPER_ADMIN：平台方，任意场景（仍要求账号可用）。

        抽成独立方法是为了让 upload_from_file 能在**落盘之前**完成鉴权
        （原先先写文件再进 create 校验，未授权请求也会在 data/<场景编码>/ 下留下文件）。
        """
        role = getattr(current_user, "role", None)
        if not self.authz.can_upload_dataset(current_user, scenario_id):
            if role == ROLE_SCENARIO_USER:
                raise ServiceError(403, "场景用户只能在自己场景上传个人数据")
            raise ServiceError(403, "无权限操作")
        return role

    @service_call
    def create(
        self,
        current_user,
        logical_id: str,
        scenario_id: int,
        file_path: str,
        fields_schema: List[Dict],
        label_field: str,
        name: Optional[str] = None,
    ):
        """上传数据集，版本号自动取最大值 + 1。

        数据级别由**上传者角色**决定，调用方不可自选、创建后不可变（2026-10 定稿）：
        - SUPER_ADMIN → platform（平台数据），任意场景；
        - SCENARIO_ADMIN → company（公司数据），仅自己场景；
        - SCENARIO_USER → personal（个人数据），仅自己场景。
        """
        role = self._authorize_upload(current_user, scenario_id)
        visibility = default_dataset_visibility(role)

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
        path_err = self._validate_file_path(file_path)
        if path_err:
            raise ServiceError(400, path_err)
        err = validate_length(label_field, "label_field", DATASET_LABEL_FIELD_MAX_LEN)
        if err:
            raise ServiceError(400, err)

        scenario = self.db.get(Scenario, scenario_id)
        if scenario is None:
            raise ServiceError(404, "场景不存在")
        err = validate_fields_schema(fields_schema, label_field)
        if err:
            raise ServiceError(400, err)

        # 初次登记也走同一套策略：change_type=create → 直接生成首个版本
        decision = resolve_iteration_policy(CHANGE_TYPE_CREATE, referenced=False)

        now = datetime.now(timezone.utc)
        dataset = Dataset(
            logical_id=logical_id,
            name=(name or None),
            version=self._next_version(logical_id),
            scenario_id=scenario_id,
            file_path=file_path,
            fields_schema=fields_schema,
            label_field=label_field,
            visibility=visibility,
            uploader_role=role,
            uploaded_by=current_user.id,
            uploaded_at=now,
            status=DATASET_STATUS_ACTIVE,
            change_type=CHANGE_TYPE_CREATE,
            base_version_id=None,
            is_breaking=decision.is_breaking,
        )
        self.db.add(dataset)
        self.db.flush()
        self._record_revision(
            dataset=dataset,
            change_type=CHANGE_TYPE_CREATE,
            is_breaking=decision.is_breaking,
            mode=decision.mode,
            reason=decision.reason,
            summary=f"登记数据集 {logical_id} v{dataset.version}",
            detail=None,
            current_user=current_user,
            result_dataset_id=dataset.id,
            created_at=now,
        )
        self.commit()
        _invalidate_dashboard_cache()
        return ok(data=self._to_dict(dataset), message="数据集上传成功")

    @service_call
    def upload_from_file(
        self,
        current_user,
        logical_id: str,
        scenario_id: int,
        label_field: str,
        filename: str,
        file_bytes: bytes,
        name: Optional[str] = None,
    ):
        """上传数据集文件（multipart）：保存到 data/<场景编码>/<文件名>，自动识别
        ARFF/CSV 格式并解析字段结构，最后复用 create() 登记落库。

        - 自动推断字段类型与枚举值域、样本数；
        - label_field 必须存在于文件字段中（否则报错，前端可据此提示修正）。
        """
        from app.utils.dataset_file_reader import (
            build_fields_schema,
            detect_format,
            read_dataset_file,
        )

        # 先鉴权再落盘：未授权请求不得在 data/<场景编码>/ 下留下任何文件
        self._authorize_upload(current_user, scenario_id)

        scenario = self.db.get(Scenario, scenario_id)
        if scenario is None:
            raise ServiceError(404, "场景不存在")

        fmt = detect_format(filename)
        if fmt == "unknown":
            raise ServiceError(400, "仅支持 .arff / .csv 格式文件")

        # 保存到 data/<场景编码>/<安全文件名>（basename 防路径穿越）
        # 统一按 "/" 切分再取 basename：Windows 上 os.path.basename 会把 "\" 当分隔符，
        # 而 Linux 上不会——不统一就会让同名文件在两个平台上落到不同文件名。
        safe_name = os.path.basename(filename.replace("\\", "/")).strip()
        if not safe_name or safe_name in (".", ".."):
            raise ServiceError(400, "文件名不合法")
        target_dir = PROJECT_ROOT / "data" / scenario.code / safe_name
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        with open(target_dir, "wb") as f:
            f.write(file_bytes)
        relative_path = f"data/{scenario.code}/{safe_name}"

        # 自动解析
        try:
            _, fields, _ = read_dataset_file(target_dir)
        except Exception as exc:  # noqa: BLE001
            raise ServiceError(400, f"文件解析失败: {exc}")

        if not fields:
            raise ServiceError(400, "文件没有解析出任何字段")

        names = [f["name"] for f in fields]
        if label_field not in names:
            raise ServiceError(
                400,
                f"标签字段 {label_field} 不存在于文件字段中（可用字段: {', '.join(names[:10])}...）",
            )

        fields_schema = build_fields_schema(fields, label_field)
        return self.create(
            current_user,
            logical_id=logical_id,
            name=name,
            scenario_id=scenario_id,
            file_path=relative_path,
            fields_schema=fields_schema,
            label_field=label_field,
        )

    @service_call
    def revise(
        self,
        current_user,
        dataset_id: int,
        change_type: str,
        file_path: Optional[str] = None,
        fields_schema: Optional[List[Dict]] = None,
        label_field: Optional[str] = None,
        name: Optional[str] = None,
        summary: Optional[str] = None,
        detail: Optional[Dict] = None,
    ):
        """数据集迭代统一入口（管理级角色，场景管理员仅自己场景）。

        change_type 取 dataset_iteration.CHANGE_TYPES；是否新开版本由策略决定：
        破坏结构兼容（字段/标签变更）必然新建版本；兼容迭代（追加/修正样本）在
        已被模型引用时新建版本，未被引用时原地更新当前版本行（版本号不变）。
        """
        dataset, decision = self._revise(
            current_user,
            dataset_id,
            change_type,
            file_path=file_path,
            fields_schema=fields_schema,
            label_field=label_field,
            name=name,
            summary=summary,
            detail=detail,
        )
        label = change_type_label(change_type)
        if decision.mode == MODE_NEW_VERSION:
            message = f"{label}：已新建版本 v{dataset.version}（旧版本保留）"
        else:
            message = f"{label}：已原地更新当前版本"
        return ok(data=self._to_dict(dataset), message=message)

    @service_call
    def update(
        self,
        current_user,
        dataset_id: int,
        file_path: Optional[str] = None,
        fields_schema: Optional[List[Dict]] = None,
        label_field: Optional[str] = None,
    ):
        """旧接口（PUT /datasets/{id}）：等价于一次「字段变更 / 文件替换」迭代。

        保留给已有前端调用方；内部统一走 _revise，不再单独维护一套版本逻辑。
        """
        change_type = (
            CHANGE_TYPE_SCHEMA_CHANGE
            if (fields_schema is not None or label_field is not None)
            else CHANGE_TYPE_REPLACE_FILE
        )
        dataset, decision = self._revise(
            current_user,
            dataset_id,
            change_type,
            file_path=file_path,
            fields_schema=fields_schema,
            label_field=label_field,
        )
        if decision.mode == MODE_NEW_VERSION:
            message = "原数据集已被模型引用，已创建新版本（旧版本保留）"
        else:
            message = "数据集修改成功"
        return ok(data=self._to_dict(dataset), message=message)

    def _revise(
        self,
        current_user,
        dataset_id: int,
        change_type: str,
        *,
        file_path: Optional[str] = None,
        fields_schema: Optional[List[Dict]] = None,
        label_field: Optional[str] = None,
        name: Optional[str] = None,
        summary: Optional[str] = None,
        detail: Optional[Dict] = None,
    ):
        """执行一次迭代，返回 (目标版本行, 决策)。

        策略见 dataset_iteration.resolve_iteration_policy：
        - 破坏结构兼容 → 必新建版本（即使未被引用也留痕）；
        - 兼容 + 已被引用 → 新建版本，冻结旧文件；
        - 兼容 + 未被引用 → 原地更新当前版本行（不涨版本号，仍记迭代记录）。
        """
        if change_type not in CHANGE_TYPES:
            raise ServiceError(400, f"未知的数据集迭代类型: {change_type}")

        dataset = self._get(dataset_id)
        if not self.authz.can_manage_dataset(current_user, dataset):
            raise ServiceError(403, "无权限操作")

        previous_file_path = dataset.file_path

        target_file_path = dataset.file_path
        target_schema = dataset.fields_schema
        target_label = dataset.label_field

        if file_path is not None:
            err = validate_length(file_path, "file_path", DATASET_FILE_PATH_MAX_LEN)
            if err:
                raise ServiceError(400, err)
            path_err = self._validate_file_path(file_path)
            if path_err:
                raise ServiceError(400, path_err)
            target_file_path = file_path

        if fields_schema is not None:
            target_schema = fields_schema
        if label_field is not None:
            target_label = label_field
        if fields_schema is not None or label_field is not None:
            err = validate_fields_schema(target_schema, target_label)
            if err:
                raise ServiceError(400, err)

        # 数据级别由上传者角色决定、创建后不可变：迭代不得改写 visibility。
        target_visibility = dataset.visibility
        target_name = name if name is not None else dataset.name

        schema_unchanged = (
            list(target_schema) == list(dataset.fields_schema)
            and target_label == dataset.label_field
        )
        referenced = self._is_referenced(dataset.id)
        decision = resolve_iteration_policy(
            change_type, referenced=referenced, schema_unchanged=schema_unchanged
        )

        now = datetime.now(timezone.utc)

        if decision.mode == MODE_IN_PLACE:
            dataset.file_path = target_file_path
            dataset.fields_schema = target_schema
            dataset.label_field = target_label
            dataset.visibility = target_visibility
            dataset.name = target_name
            self._record_revision(
                dataset=dataset,
                change_type=change_type,
                is_breaking=decision.is_breaking,
                mode=decision.mode,
                reason=decision.reason,
                summary=summary,
                detail=detail,
                current_user=current_user,
                result_dataset_id=None,
                created_at=now,
            )
            self.commit()
            if target_file_path != previous_file_path:
                self._cleanup_replaced_file(previous_file_path)
            _invalidate_dashboard_cache()
            return dataset, decision

        new_dataset = Dataset(
            logical_id=dataset.logical_id,
            name=target_name,
            version=self._next_version(dataset.logical_id),
            scenario_id=dataset.scenario_id,
            file_path=target_file_path,
            fields_schema=target_schema,
            label_field=target_label,
            visibility=target_visibility,
            uploader_role=dataset.uploader_role,
            uploaded_by=dataset.uploaded_by,
            uploaded_at=now,
            status=DATASET_STATUS_ACTIVE,
            change_type=change_type,
            base_version_id=dataset.id,
            is_breaking=decision.is_breaking,
        )
        self.db.add(new_dataset)
        self.db.flush()
        self._record_revision(
            dataset=dataset,
            change_type=change_type,
            is_breaking=decision.is_breaking,
            mode=decision.mode,
            reason=decision.reason,
            summary=summary,
            detail=detail,
            current_user=current_user,
            result_dataset_id=new_dataset.id,
            created_at=now,
        )
        self.commit()
        if target_file_path != previous_file_path:
            self._cleanup_replaced_file(previous_file_path)
        _invalidate_dashboard_cache()
        return new_dataset, decision

    def _cleanup_replaced_file(self, old_file_path: str) -> None:
        """迭代换文件后清理不再被任何版本引用的旧物理文件（best-effort）。

        只在没有任何 dataset 行仍指向它时删除：只改字段的旧路径可能被多个版本共用，
        贸然删除会让历史版本读不到文件。删除失败只记日志，不影响迭代结果。
        """
        if not old_file_path:
            return
        still_used = self.db.scalar(
            select(func.count())
            .select_from(Dataset)
            .where(Dataset.file_path == old_file_path)
        )
        if still_used:
            return
        try:
            from app.services.training_executor import resolve_dataset_path

            path = resolve_dataset_path(old_file_path)
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            logger.warning("清理被替换的数据集文件失败: %s", old_file_path)

    @service_call
    def append_rows(
        self,
        current_user,
        dataset_id: int,
        filename: str,
        file_bytes: bytes,
    ):
        """追加样本（管理级角色，场景管理员仅自己场景）。

        把「增量文件」并入当前数据集：增量必须是同结构（字段名同名同序）的
        ARFF / CSV。合并后写到新物理文件，再交给 _revise 按迭代策略决定
        原地更新还是新建版本 —— 未被引用时版本号不变（只增数据），已被引用时
        自动新开版本冻结旧文件。

        需要改变字段结构请改用「字段变更」迭代，本方法只负责增加数据条数。
        """
        from app.services.training_executor import resolve_dataset_path
        from app.utils.dataset_file_reader import (
            detect_format,
            read_all_rows,
            write_dataset_file,
        )

        dataset = self._get(dataset_id)
        if not self.authz.can_manage_dataset(current_user, dataset):
            raise ServiceError(403, "无权限操作")

        fmt = detect_format(filename)
        if fmt == "unknown":
            raise ServiceError(400, "仅支持 .arff / .csv 格式的增量文件")
        if detect_format(dataset.file_path) != fmt:
            raise ServiceError(400, "增量文件格式必须与当前数据集一致")

        increment_rows, increment_fields = self._parse_increment(file_bytes, fmt)
        if not increment_rows:
            raise ServiceError(400, "增量文件没有数据行")

        expected_names = [str(f.get("name")) for f in (dataset.fields_schema or [])]
        actual_names = [str(f.get("name")) for f in increment_fields]
        if actual_names != expected_names:
            raise ServiceError(
                400,
                "增量文件字段与当前数据集不一致（追加要求同名同序）；"
                "如需变更字段请使用「字段变更」迭代",
            )

        current_path = resolve_dataset_path(dataset.file_path)
        if not os.path.exists(current_path):
            raise ServiceError(404, f"数据集文件不存在: {current_path}")
        _, current_rows = read_all_rows(current_path)
        merged_rows = list(current_rows) + list(increment_rows)

        new_rel_path = self._iteration_target_path(dataset, fmt)
        write_dataset_file(
            resolve_dataset_path(new_rel_path), dataset.fields_schema, merged_rows, fmt
        )

        added = len(increment_rows)
        dataset_after, decision = self._revise(
            current_user,
            dataset_id,
            CHANGE_TYPE_APPEND_ROWS,
            file_path=new_rel_path,
            summary=f"追加 {added} 条样本（{len(current_rows)} → {len(merged_rows)}）",
            detail={
                "added_rows": added,
                "rows_before": len(current_rows),
                "rows_after": len(merged_rows),
                "increment_file": filename,
            },
        )
        if decision.mode == MODE_NEW_VERSION:
            message = f"追加样本：已新建版本 v{dataset_after.version}，新增 {added} 条"
        else:
            message = f"追加样本：当前版本新增 {added} 条（版本号不变）"
        return ok(data=self._to_dict(dataset_after), message=message)

    @staticmethod
    def _parse_increment(file_bytes: bytes, fmt: str):
        """把增量文件字节解析为 (rows, fields)，用临时文件承载解析器。"""
        import tempfile

        from app.utils.dataset_file_reader import read_all_rows

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            fields, rows = read_all_rows(tmp_path)
            return rows, fields
        except ServiceError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ServiceError(400, f"增量文件解析失败: {exc}")
        finally:
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    @service_call
    def get_revisions(self, current_user, dataset_id: int):
        """迭代历史（登录用户，按数据集可见性）：每次迭代一条，含原地更新。"""
        self.require_login(current_user)
        dataset = self._get(dataset_id)
        if not self.authz.can_view_dataset(current_user, dataset):
            raise ServiceError(403, "无权限操作")
        revisions = self.db.scalars(
            select(DatasetRevision)
            .where(DatasetRevision.logical_id == dataset.logical_id)
            .order_by(DatasetRevision.created_at.desc())
        ).all()
        return ok(
            data={
                "dataset_id": dataset.id,
                "logical_id": dataset.logical_id,
                "items": [
                    {
                        "id": r.id,
                        "dataset_id": r.dataset_id,
                        "change_type": r.change_type,
                        "change_type_label": change_type_label(r.change_type),
                        "is_breaking": bool(r.is_breaking),
                        "mode": r.mode,
                        "result_dataset_id": r.result_dataset_id,
                        "reason": r.reason,
                        "summary": r.summary,
                        "detail": r.detail,
                        "created_at": (
                            r.created_at.isoformat() if r.created_at else None
                        ),
                    }
                    for r in revisions
                ],
            }
        )

    @service_call
    def disable(self, current_user, dataset_id: int):
        """停用数据集（管理级角色，场景管理员仅自己场景）。

        需求 2.3.5/2.3.7：停用后不得用于新的模型训练，但历史模型、训练记录、
        评估结果、推理记录和风险事件仍保持可追溯（本方法不触碰历史数据）。
        """
        dataset = self._get(dataset_id)
        if not self.authz.can_manage_dataset(current_user, dataset):
            raise ServiceError(403, "无权限操作")
        dataset.status = DATASET_STATUS_INACTIVE
        self.commit()
        return ok(data=self._to_dict(dataset), message="数据集已停用")

    @service_call
    def delete(self, current_user, dataset_id: int):
        """物理删除数据集（管理级角色，场景管理员仅自己场景）。

        需求 2.3.5/2.3.6：被任何模型版本引用的数据集版本只能停用，不能物理删除；
        未被引用的可以物理删除。
        """
        dataset = self._get(dataset_id)
        if not self.authz.can_manage_dataset(current_user, dataset):
            raise ServiceError(403, "无权限操作")
        if self._is_referenced(dataset_id):
            raise ServiceError(400, "数据集已被模型版本引用，禁止物理删除，只能停用")
        self.db.delete(dataset)
        self.commit()
        _invalidate_dashboard_cache()
        return ok(message="数据集已删除")

    @service_call
    def get_fields_schema(self, current_user, dataset_id: int):
        """字段预览（需求 3.1.4：字段名、字段类型、字段角色、样例值由上层提供）。"""
        self.require_login(current_user)
        dataset = self._get(dataset_id)
        if not self.authz.can_view_dataset(current_user, dataset):
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
        if not self.authz.can_view_dataset(current_user, dataset):
            raise ServiceError(403, "无权限操作")

        from app.services.training_executor import resolve_dataset_path
        from app.utils.dataset_file_reader import read_sample_rows

        path = resolve_dataset_path(dataset.file_path)
        if not os.path.exists(path):
            raise ServiceError(404, f"数据集文件不存在: {path}")

        offset = (page - 1) * page_size
        # 取样本的统一入口（ARFF / CSV 都支持，字段名取登记的 fields_schema），
        # 与「批量研判」共用，避免两处口径漂移。
        page_rows = read_sample_rows(path, dataset.fields_schema, offset, page_size)
        total = self._count_records(dataset.file_path)
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
                "total": total,
            }
        )
