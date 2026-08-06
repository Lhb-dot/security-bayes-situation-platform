"""Service 层统一导出。

覆盖 ORM 全部 12 张表（backend/app/models/）：
- 用户 AppUser（含 Role 常量）       → UserService
- 场景 Scenario                       → ScenarioService
- 数据集 Dataset（含版本管理）        → DatasetService
- 算法 Algorithm                      → AlgorithmService
- 模型版本 ModelVersion（状态机）     → ModelVersionService
- 推理记录 InferenceRecord            → InferenceRecordService
- 风险事件 RiskEvent                  → RiskEventService
- 处置记录 HandlingRecord             → HandlingRecordService
- 态势快照 SituationSnapshot          → SituationSnapshotService
- 报告 Report（实验记录/报表）        → ReportService
- 风险阈值 RiskThreshold              → RiskThresholdService
- 阈值变更日志 ThresholdAuditLog      → ThresholdAuditLogService

公共设施：ServiceBase / ServiceError / service_call（app.services.base）、
ok / fail（app.schemas.common）、分页与校验（app.utils.common）。

用法（FastAPI 依赖注入）：
    from app.db import get_db
    from app.services import UserService

    @router.get("/users")
    def list_users(db: Session = Depends(get_db)):
        return UserService(db).get_list(current_user=...)
"""
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.algorithm_service import AlgorithmService
from app.services.dataset_service import DatasetService
from app.services.handling_record_service import HandlingRecordService
from app.services.inference_record_service import InferenceRecordService
from app.services.model_version_service import ModelVersionService
from app.services.report_service import ReportService
from app.services.risk_event_service import RiskEventService
from app.services.risk_threshold_service import RiskThresholdService
from app.services.scenario_service import ScenarioService
from app.services.situation_snapshot_service import SituationSnapshotService
from app.services.threshold_audit_log_service import ThresholdAuditLogService
from app.services.user_service import UserService

__all__ = [
    "ServiceBase",
    "ServiceError",
    "service_call",
    "UserService",
    "ScenarioService",
    "DatasetService",
    "AlgorithmService",
    "ModelVersionService",
    "InferenceRecordService",
    "RiskEventService",
    "HandlingRecordService",
    "SituationSnapshotService",
    "ReportService",
    "RiskThresholdService",
    "ThresholdAuditLogService",
]
