"""Service 层业务常量与数据字典（硬编码校验基准）。

对应需求文档章节：
- 6.5.1 角色定义（ADMIN / USER）
- 6.5.2 权限矩阵
- 6.7.2 模型版本生命周期状态机
- 5.3  风险类型映射（数据集 → risk_type）
- 5.4  风险等级生成规则（可配置阈值，此处仅提供兜底值）
- 6.4.1 分类类别统一约定（风险样本 = 正类，显式映射，禁止自动推断）

⚠️ 重要：本模块的编码清单（SCENARIO_CODES / ALGORITHM_CODES /
DATASET_POSITIVE_LABELS / DATASET_RISK_TYPES）是需求文档的业务数据字典，
作为 Service 层校验基准硬编码。新增场景/数据集/算法时必须同步更新本文档
与数据库种子数据。
"""

# ---------------------------------------------------------------------------
# 用户与角色（数据库设计文档v2 2.1；需求文档 6.5.1）
#
# 三级角色（多场景复杂系统：最外层管理员 / 场景管理员 / 场景用户）：
# - SUPER_ADMIN（最外层管理员）：平台方，管所有场景运行、平台数据/模型、创建场景管理员
# - SCENARIO_ADMIN（场景管理员）：绑定一个场景，场景内最高权限（数据集/模型/训练/阈值/创建场景用户）
# - SCENARIO_USER（场景用户）：绑定一个场景，使用已发布模型推理、看本人数据
# ---------------------------------------------------------------------------
ROLE_SUPER_ADMIN = "SUPER_ADMIN"
ROLE_SCENARIO_ADMIN = "SCENARIO_ADMIN"
ROLE_SCENARIO_USER = "SCENARIO_USER"
ROLES = (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN, ROLE_SCENARIO_USER)

# 兼容别名（旧两级模型）：旧"管理员"=最外层管理员，旧"普通用户"=场景用户
ROLE_ADMIN = ROLE_SUPER_ADMIN
ROLE_USER = ROLE_SCENARIO_USER

# 管理级角色集合（能做管理操作的角色）
ADMIN_ROLES = (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN)

USER_STATUS_ENABLED = "ENABLED"
USER_STATUS_DISABLED = "DISABLED"
USER_STATUSES = (USER_STATUS_ENABLED, USER_STATUS_DISABLED)

# 账号字段长度约束（与 ORM 列定义一致）
USERNAME_MAX_LEN = 64
PASSWORD_HASH_MAX_LEN = 128
PASSWORD_MIN_LEN = 6  # 需求将"复杂密码策略"列为 P2，第一阶段仅做基本长度校验

# 数据可见性分级（三级角色数据所有权：平台/公司/个人）
DATASET_VISIBILITY_PLATFORM = "platform"   # 平台数据：最外层管理员管理，各场景基线
DATASET_VISIBILITY_COMPANY = "company"     # 公司数据：场景管理员上传，最外层不可见
DATASET_VISIBILITY_PERSONAL = "personal"   # 个人数据：场景用户上传，上级都不可见
DATASET_VISIBILITIES = (
    DATASET_VISIBILITY_PLATFORM,
    DATASET_VISIBILITY_COMPANY,
    DATASET_VISIBILITY_PERSONAL,
)

# ---------------------------------------------------------------------------
# 场景（数据库设计文档v2 2.2；需求文档 1/2）
# ---------------------------------------------------------------------------
SCENARIO_ACCESS_ACTUAL = "ACTUAL"      # 实际接入
SCENARIO_ACCESS_RESERVED = "RESERVED"  # 仅预留接口
SCENARIO_ACCESS_STATUSES = (SCENARIO_ACCESS_ACTUAL, SCENARIO_ACCESS_RESERVED)

# 需求文档 §1：第一阶段正式场景编码（数据字典，硬编码校验基准）
SCENARIO_CODES = (
    "network_security",     # 网络安全
    "power_system",         # 电力系统
    "geological_risk",      # 地质风险（⚠️ 当前 seed 迁移 d6adba5112b8 未覆盖，需补充）
    "flightdeck_operation", # 航母甲板作业
)

SCENARIO_CODE_MAX_LEN = 32
SCENARIO_NAME_MAX_LEN = 64

# ---------------------------------------------------------------------------
# 数据集（数据库设计文档v2 2.3；需求文档 2.3）
# ---------------------------------------------------------------------------
DATASET_STATUS_ACTIVE = "ACTIVE"      # 可用
DATASET_STATUS_INACTIVE = "INACTIVE"  # 停用（被模型引用时不得物理删除，只能停用）
DATASET_STATUSES = (DATASET_STATUS_ACTIVE, DATASET_STATUS_INACTIVE)

DATASET_LOGICAL_ID_MAX_LEN = 64
DATASET_FILE_PATH_MAX_LEN = 255
DATASET_LABEL_FIELD_MAX_LEN = 64

# 需求文档 §2 第一阶段数据集编码清单（用于风险规则映射与展示，不作为"禁止新增"约束——
# 需求文档主题即为"接入新的数据集"，管理员可上传新数据集；未登记的数据集默认不生成风险事件，
# 需在 DATASET_RISK_TYPES 中补充映射）
DATASET_LOGICAL_IDS = (
    "kdd_train_20_percent",
    "nf_unsw_nb15_v2",
    "powergrid_knowledgebase",
    "dis_raw_data",
    "dis_landslides",
    "dis_causative_factors",
    "dis_global_catalog",
    "dis_guaruja_random",
    "carrier_feature2_biaoqian",
    "carrier_feature2_lisan",
    "carrier_paired_trail",
)

# ---------------------------------------------------------------------------
# 算法（数据库设计文档v2 2.4；需求文档 6.6.1）
# ---------------------------------------------------------------------------
ALGORITHM_STATUS_AVAILABLE = "AVAILABLE"
ALGORITHM_STATUS_DEPRECATED = "DEPRECATED"
ALGORITHM_STATUSES = (ALGORITHM_STATUS_AVAILABLE, ALGORITHM_STATUS_DEPRECATED)

# 需求文档 §6.6.1 第一阶段五种算法编码（数据字典，硬编码校验基准）
ALGORITHM_CODES = ("A2WNB", "MAWNB", "EMAWNB", "DIWNB", "PMWNB")
ALGORITHM_CODE_MAX_LEN = 32
ALGORITHM_NAME_MAX_LEN = 64

# ---------------------------------------------------------------------------
# 模型版本生命周期（数据库设计文档v2 2.5；需求文档 6.7.2）
# ---------------------------------------------------------------------------
MODEL_STATUS_TRAINING = "TRAINING"   # 训练中
MODEL_STATUS_FAILED = "FAILED"       # 训练失败
MODEL_STATUS_DRAFT = "DRAFT"         # 训练成功，待管理员审核发布
MODEL_STATUS_PUBLISHED = "PUBLISHED" # 已发布，可供普通用户选择
MODEL_STATUS_OFFLINE = "OFFLINE"     # 已下线，不再接受新的推理请求
MODEL_STATUS_DISABLED = "DISABLED"   # 已禁用，对普通用户不可见，保留记录

MODEL_STATUSES = (
    MODEL_STATUS_TRAINING,
    MODEL_STATUS_FAILED,
    MODEL_STATUS_DRAFT,
    MODEL_STATUS_PUBLISHED,
    MODEL_STATUS_OFFLINE,
    MODEL_STATUS_DISABLED,
)

# 需求文档 §6.7.2 状态转换规则（Service 层强制校验）
# TRAINING → FAILED / DRAFT；DRAFT → PUBLISHED；PUBLISHED → DISABLED。
# OFFLINE 仅为历史兼容状态，迁移后统一使用 DISABLED。
MODEL_STATUS_TRANSITIONS = {
    MODEL_STATUS_TRAINING: (MODEL_STATUS_FAILED, MODEL_STATUS_DRAFT),
    MODEL_STATUS_FAILED: (),
    MODEL_STATUS_DRAFT: (MODEL_STATUS_PUBLISHED,),
    MODEL_STATUS_PUBLISHED: (MODEL_STATUS_DISABLED,),
    MODEL_STATUS_OFFLINE: (),
    MODEL_STATUS_DISABLED: (),
}

# 普通用户可见的模型状态（需求文档 §6.7.3.3 / §6.7.5.1）
USER_VISIBLE_MODEL_STATUSES = (MODEL_STATUS_PUBLISHED,)

# 可执行新推理的模型状态（需求文档 §6.7.3.3 / §6.7.5.6）
INFERENCE_ALLOWED_MODEL_STATUSES = (MODEL_STATUS_PUBLISHED,)

# ---------------------------------------------------------------------------
# 风险事件（数据库设计文档v2 2.7；需求文档 5.2 / 5.3 / 5.4）
# ---------------------------------------------------------------------------
RISK_LEVEL_HIGH = "HIGH"
RISK_LEVEL_MEDIUM = "MEDIUM"
RISK_LEVEL_LOW = "LOW"
RISK_LEVELS = (RISK_LEVEL_HIGH, RISK_LEVEL_MEDIUM, RISK_LEVEL_LOW)

RISK_EVENT_STATUS_PENDING = "PENDING"        # 待处置
RISK_EVENT_STATUS_PROCESSING = "PROCESSING"  # 处理中
RISK_EVENT_STATUS_RESOLVED = "RESOLVED"      # 已处置
RISK_EVENT_STATUSES = (
    RISK_EVENT_STATUS_PENDING,
    RISK_EVENT_STATUS_PROCESSING,
    RISK_EVENT_STATUS_RESOLVED,
)

# 处置状态转换规则（需求文档 §5.2：新事件默认"待处置"，后续可变为"处理中"或"已处置"，
# 即 PENDING 可直接转 PROCESSING 或 RESOLVED；PROCESSING → RESOLVED）
RISK_EVENT_STATUS_TRANSITIONS = {
    RISK_EVENT_STATUS_PENDING: (RISK_EVENT_STATUS_PROCESSING, RISK_EVENT_STATUS_RESOLVED),
    RISK_EVENT_STATUS_PROCESSING: (RISK_EVENT_STATUS_RESOLVED,),
    RISK_EVENT_STATUS_RESOLVED: (),
}

# 统一风险类型（需求文档 §5.3）
RISK_TYPE_NETWORK = "NETWORK_SECURITY_RISK"
RISK_TYPE_POWER = "POWER_SYSTEM_RISK"
RISK_TYPE_GEOLOGICAL = "GEOLOGICAL_RISK"
RISK_TYPE_FLIGHT_DECK = "FLIGHT_DECK_OPERATION_RISK"

# ---------------------------------------------------------------------------
# 风险事件生成规则（需求文档 §5.3 风险类型映射 + §6.4.1 正负类显式映射）
# ---------------------------------------------------------------------------
# 每个数据集"风险（正类）"标签的显式映射 —— 需求文档 §6.4.1 明确：
# 开发人员不得按标签字符串、数值大小或文件排列顺序自动推断正类，必须使用显式映射。
DATASET_POSITIVE_LABELS = {
    "kdd_train_20_percent": {"anomaly"},                       # 正类=anomaly / 负类=normal
    "nf_unsw_nb15_v2": {"1"},                                  # 正类=1 / 负类=0
    "powergrid_knowledgebase": {"1"},                          # 正类=Target_Event 1 / 0
    "dis_raw_data": {"1"},                                     # Label=1 风险 / 0 正常
    "dis_landslides": {"1"},                                   # LS=1 风险 / 0 正常
    "dis_causative_factors": {"1"},                            # landslides>0 即风险（另见 DATASET_RISK_GT_ZERO）
    "dis_guaruja_random": {"1"},                               # class=1 风险 / 0 正常
    "carrier_feature2_biaoqian": {"1"},                        # Collision=1 风险 / 0 正常
    "carrier_feature2_lisan": {"1"},
    "carrier_paired_trail": {"1"},
}
# dis_global_catalog：多分类编目数据，不参与二分类训练与风险事件生成（§4.4.3），未列入映射。

# 需求 §5.3 特殊规则：DIS_Landslide_Causative_Factors 的标签 landslides 为数值，
# "landslides>0"（有滑坡记录）即风险；当模型输出为数值标签时按 >0 判定。
DATASET_RISK_GT_ZERO = ("dis_causative_factors",)


def is_risk_label(logical_id: str, prediction_label: object) -> bool:
    """判断预测标签是否属于该数据集的风险类（正类）。

    对应需求文档：6.4.1（正负类显式映射，禁止自动推断）、5.3（风险类型映射）。
    优先精确匹配 DATASET_POSITIVE_LABELS；对 DATASET_RISK_GT_ZERO 数据集，
    数值标签大于 0 也判定为风险（如 DIS_Causative 的 landslides>0）。
    """
    label = str(prediction_label).strip()
    if label in DATASET_POSITIVE_LABELS.get(logical_id, set()):
        return True
    if logical_id in DATASET_RISK_GT_ZERO:
        try:
            return float(label) > 0
        except (TypeError, ValueError):
            return False
    return False

# 数据集 → 统一风险类型（需求文档 §5.3）
DATASET_RISK_TYPES = {
    "kdd_train_20_percent": RISK_TYPE_NETWORK,
    "nf_unsw_nb15_v2": RISK_TYPE_NETWORK,
    "powergrid_knowledgebase": RISK_TYPE_POWER,
    "dis_raw_data": RISK_TYPE_GEOLOGICAL,
    "dis_landslides": RISK_TYPE_GEOLOGICAL,
    "dis_causative_factors": RISK_TYPE_GEOLOGICAL,
    "dis_guaruja_random": RISK_TYPE_GEOLOGICAL,
    "carrier_feature2_biaoqian": RISK_TYPE_FLIGHT_DECK,
    "carrier_feature2_lisan": RISK_TYPE_FLIGHT_DECK,
    "carrier_paired_trail": RISK_TYPE_FLIGHT_DECK,
}

# 阈值兜底（需求文档 §5.4.1 第 6 条：正式阈值应通过 risk_threshold 表配置提供，
# 本文不写死"正式默认阈值"。此处仅为场景尚未配置阈值时的兜底值，并记录 warning 日志。）
DEFAULT_MEDIUM_THRESHOLD = 0.5
DEFAULT_HIGH_THRESHOLD = 0.8

# ---------------------------------------------------------------------------
# 处置记录（数据库设计文档v2 2.8；需求文档 4）
# ---------------------------------------------------------------------------
HANDLING_ACTIONS = ("ASSIGN", "UPDATE_STATUS", "ADD_COMMENT")
HANDLING_ACTION_MAX_LEN = 32

# ---------------------------------------------------------------------------
# 报告（数据库设计文档v2 2.10；需求文档 6.2 报告生成 P1）
# ---------------------------------------------------------------------------
REPORT_TYPES = ("SCENE_SNAPSHOT", "USER_SNAPSHOT")
REPORT_FORMATS = ("markdown", "html", "pdf")
REPORT_TYPE_MAX_LEN = 16
