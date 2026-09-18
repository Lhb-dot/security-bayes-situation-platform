"""Lazy public exports for the service layer.

Keeping imports lazy avoids loading every service when a module only needs one
small shared helper such as ``risk_view``. The old package-level imports remain
available through ``__getattr__`` for callers that use the public exports.
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
