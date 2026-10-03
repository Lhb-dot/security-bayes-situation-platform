"""ORM 模型注册入口。

导入本包即可把全部业务表注册到 Base.metadata 上（Alembic autogenerate /
metadata.create_all 依赖这一点）。基线迁移 85b25ac03ba5 直接调用
``Base.metadata.create_all()``，**漏导入任何一个模型都会让全新环境的库缺表**，
因此本文件必须与 app/models/ 下的模块一一对应。

模型与《数据库设计文档v2》2.1 ~ 2.12 对应，另有 2 张文档之后新增的表
（auth_session / user_ai_setting），共 14 张：

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
    auth_session        服务端登录会话表（不存明文令牌，只存 HMAC 摘要）
    user_ai_setting     用户级 AI 供应商配置（api_key 加密落库）

relationship 的目标一律写成字符串（``"Dataset"`` 等），由 SQLAlchemy 在 mapper
配置阶段从 registry 解析，所以下面的导入顺序只是为了可读性，**不会造成循环导入**：
models 包内的模块之间没有任何互相 import，每个模块只依赖 app.db.Base。
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
from app.models.auth_session import AuthSession
from app.models.user_ai_setting import UserAISetting

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
    "AuthSession",
    "UserAISetting",
]
