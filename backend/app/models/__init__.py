"""ORM 模型注册入口。

导入本包即把全部业务表注册到 Base.metadata 上（Alembic autogenerate /
metadata.create_all 都依赖这一点）。基线迁移 85b25ac03ba5 直接调用
Base.metadata.create_all()，漏导入任何一个模型，全新环境的库就会缺表，
因此本文件必须与 app/models/ 下的模块一一对应 —— 现在共 15 张表，
比《数据库设计文档v2》2.1~2.12 多出三张文档之后新增的：
auth_session（服务端登录会话，只存 HMAC 摘要不存明文令牌）、
user_ai_setting（用户级 AI 供应商配置，api_key 加密落库）、
dataset_revision（每次数据集迭代一条，见 dataset_iteration.py）。

relationship 的目标一律写成字符串（"Dataset" 等），由 SQLAlchemy 在 mapper
配置阶段从 registry 解析，所以下面的导入顺序只为可读性，不会造成循环导入：
models 包内的模块之间没有任何互相 import，每个模块只依赖 app.db.Base。
"""
from app.models.app_user import AppUser
from app.models.scenario import Scenario
from app.models.dataset import Dataset
from app.models.dataset_revision import DatasetRevision
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
    "DatasetRevision",
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
