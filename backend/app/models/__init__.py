"""ORM 模型注册入口。

导入本包即可把全部 12 张表注册到 Base.metadata 上（Alembic autogenerate /
metadata.create_all 依赖这一点）。模型与《数据库设计文档v2》2.1 ~ 2.12 一一对应：

    app_user            用户表
    scenario            场景表
    dataset             数据集表
    algorithm           算法表
    model_version       模型版本表
    inference_record    推理记录表
    risk_event          风险事件表
    handling_record     处置记录表
    situation_snapshot  态势快照表
    report              报告表
    risk_threshold      风险阈值配置表
    threshold_audit_log 阈值变更日志表
"""
from app.models.app_user import AppUser
from app.models.scenario import Scenario
from app.models.dataset import Dataset
from app.models.algorithm import Algorithm
from app.models.model_version import ModelVersion
from app.models.inference_record import InferenceRecord
from app.models.risk_event import RiskEvent
from app.models.handling_record import HandlingRecord
from app.models.situation_snapshot import SituationSnapshot
from app.models.report import Report
from app.models.risk_threshold import RiskThreshold
from app.models.threshold_audit_log import ThresholdAuditLog

__all__ = [
    "AppUser",
    "Scenario",
    "Dataset",
    "Algorithm",
    "ModelVersion",
    "InferenceRecord",
    "RiskEvent",
    "HandlingRecord",
    "SituationSnapshot",
    "Report",
    "RiskThreshold",
    "ThresholdAuditLog",
]
