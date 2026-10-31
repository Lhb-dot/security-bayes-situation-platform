"""服务层的惰性导出。

保持惰性是为了避免只用到一个小工具（比如 risk_view）时把整个服务层都加载起来。
老代码里那些包级导入仍可通过 __getattr__ 用。
"""

from importlib import import_module


_EXPORTS = {
    "ServiceBase": ("base", "ServiceBase"),
    "ServiceError": ("base", "ServiceError"),
    "service_call": ("base", "service_call"),
    "UserService": ("user_service", "UserService"),
    "ScenarioService": ("scenario_service", "ScenarioService"),
    "DatasetService": ("dataset_service", "DatasetService"),
    "AlgorithmService": ("algorithm_service", "AlgorithmService"),
    "ModelVersionService": ("model_version_service", "ModelVersionService"),
    "InferenceRecordService": ("inference_record_service", "InferenceRecordService"),
    "RiskEventService": ("risk_event_service", "RiskEventService"),
    "HandlingRecordService": ("handling_record_service", "HandlingRecordService"),
    "SituationSnapshotService": ("situation_snapshot_service", "SituationSnapshotService"),
    "ReportService": ("report_service", "ReportService"),
    "RiskThresholdService": ("risk_threshold_service", "RiskThresholdService"),
    "ThresholdAuditLogService": ("threshold_audit_log_service", "ThresholdAuditLogService"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute_name)
    globals()[name] = value
    return value
