"""Service 层公共工具函数。

对应需求文档章节：6.2（P0 功能）、6.4.4（结果一致性）、6.8（数据访问与态势统计）。

提供：
- paginate：SQLAlchemy 2.0 风格（select()）分页
- row_to_dict：ORM 行转 JSON 友好 dict（DateTime → ISO 字符串）
- validate_required / validate_enum：字段校验辅助
- hash_password / verify_password：标准库 PBKDF2 密码哈希（无新增依赖）
- get_logger：统一日志记录器
"""
import hashlib
import hmac
import logging
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger("app.services")


def get_logger(name: str) -> logging.Logger:
    """获取带统一前缀的日志记录器。"""
    return logging.getLogger(f"app.services.{name}")


# ---------------------------------------------------------------------------
# 分页（SQLAlchemy 2.0 风格）
# ---------------------------------------------------------------------------

def paginate(
    db: Session,
    stmt,
    page: int = 1,
    page_size: int = 10,
) -> Dict[str, Any]:
    """对 select() 语句执行分页，返回 {"items", "total", "page", "page_size"}。

    - 强制 page >= 1、1 <= page_size <= 200，防止非法参数。
    - total 通过子查询 COUNT 计算，避免额外加载全部数据。
    """
    page = max(1, int(page or 1))
    page_size = min(max(1, int(page_size or 10)), 200)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(
        db.scalars(
            stmt.offset((page - 1) * page_size).limit(page_size)
        ).all()
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ---------------------------------------------------------------------------
# ORM 行序列化
# ---------------------------------------------------------------------------

def row_to_dict(obj: Any, exclude: Sequence[str] = ()) -> Dict[str, Any]:
    """把 ORM 行转换为 JSON 友好 dict。

    - DateTime → ISO 8601 字符串
    - JSONB / dict / list 原样保留
    - exclude 用于隐藏敏感字段（如 password_hash）
    """
    result: Dict[str, Any] = {}
    for column in obj.__table__.columns:
        name = column.name
        if name in exclude:
            continue
        value = getattr(obj, name)
        if isinstance(value, datetime):
            value = value.isoformat()
        result[name] = value
    return result


# ---------------------------------------------------------------------------
# 字段校验辅助
# ---------------------------------------------------------------------------

def validate_required(data: Dict[str, Any], fields: Sequence[str]) -> Optional[str]:
    """校验必填字段：缺失 / None / 空字符串视为非法，返回错误文案或 None。"""
    for field in fields:
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            return f"缺少必填字段: {field}"
    return None


def validate_enum(value: Any, allowed: Sequence[str], field_name: str) -> Optional[str]:
    """校验枚举值域，非法时返回错误文案。"""
    if value not in allowed:
        return f"{field_name} 取值非法: {value}，允许值: {sorted(allowed)}"
    return None


def validate_length(
    value: str, field_name: str, max_len: int, min_len: int = 1
) -> Optional[str]:
    """校验字符串长度（按字符数）。"""
    length = len(value or "")
    if length < min_len or length > max_len:
        return f"{field_name} 长度必须在 [{min_len}, {max_len}] 之间"
    return None


# ---------------------------------------------------------------------------
# 数据集字段结构校验（需求文档 3.1 固定字段统一要求）
# ---------------------------------------------------------------------------

def validate_fields_schema(
    fields_schema: Any, label_field: str
) -> Optional[str]:
    """校验 fields_schema 结构（需求 3.1.2 / 3.1.5）。

    规则：必须是列表；label_field 必须存在且 role == "label"；至少含一个
    role == "feature" 的字段；枚举字段必须带 enum_values。
    """
    if not isinstance(fields_schema, list) or not fields_schema:
        return "fields_schema 必须是非空字段列表"
    feature_count = 0
    label_found = False
    for idx, field in enumerate(fields_schema):
        if not isinstance(field, dict) or not field.get("name"):
            return f"fields_schema 第 {idx + 1} 项缺少 name"
        role = field.get("role")
        if role == "feature":
            feature_count += 1
        elif role == "label":
            if field["name"] == label_field:
                label_found = True
        else:
            return f"字段 {field.get('name')} 的 role 必须为 feature 或 label"
        if field.get("type") == "enum" and not field.get("enum_values"):
            return f"枚举字段 {field.get('name')} 缺少 enum_values 值域定义"
    if not feature_count:
        return "fields_schema 至少需要一个输入特征（role=feature）字段"
    if not label_found:
        return f"label_field '{label_field}' 必须在 fields_schema 中且 role=label"
    return None


def validate_input_features(fields_schema: List[Dict], input_features: Any) -> Optional[str]:
    """校验单条推理输入（需求 3.1.3 / 3.1.5）。

    - 所有 role=feature 的字段必填；
    - 枚举字段必须按 enum_values 值域校验；
    - 标签字段不要求用户填写。
    """
    if not isinstance(input_features, dict):
        return "input_features 必须是 JSON 对象"
    for field in fields_schema:
        name = field.get("name")
        role = field.get("role")
        if role == "label":
            continue  # 推理输入不要求标签（需求 3.1.3）
        if name not in input_features or input_features.get(name) is None:
            return f"缺少必填输入特征: {name}"
        if field.get("type") == "enum":
            enum_values = field.get("enum_values") or []
            value = input_features.get(name)
            if str(value) not in {str(v) for v in enum_values}:
                return f"字段 {name} 取值 {value} 不在枚举值域内: {enum_values}"
    return None


def validate_params_schema(
    param_schema: Any, params: Any
) -> Optional[str]:
    """校验训练参数（需求 6.6.3：参数必须提供默认值，管理员修改须通过类型和范围校验）。

    参数项结构（与算法注册的 param_schema 对齐）：
        {"name": str, "type": "int|float|bool|enum|str", "required": bool,
         "default": Any, "min": Number, "max": Number, "enum_values": [...]}
    - required 且缺失 → 报错；
    - enum 按 enum_values 值域校验；
    - int/float 做类型转换与 min/max 范围校验；
    - bool 校验类型；str 仅做非空。
    """
    if not isinstance(params, dict):
        return "training_parameters 必须是 JSON 对象"
    schema = param_schema or []
    if not isinstance(schema, list):
        return "param_schema 配置非法（必须是列表）"
    for item in schema:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        name = item["name"]
        required = bool(item.get("required", False))
        if name not in params:
            if required:
                return f"缺少必填训练参数: {name}"
            continue
        value = params[name]
        ptype = str(item.get("type", "")).lower()
        if ptype == "enum":
            allowed = item.get("enum_values") or []
            if str(value) not in {str(v) for v in allowed}:
                return f"训练参数 {name} 取值 {value} 不在枚举值域内: {allowed}"
        elif ptype in ("int", "integer", "float", "number"):
            try:
                numeric = float(value) if ptype in ("float", "number") else int(value)
            except (TypeError, ValueError):
                return f"训练参数 {name} 必须是{'数值' if ptype in ('float', 'number') else '整数'}"
            lo, hi = item.get("min"), item.get("max")
            if lo is not None and numeric < lo:
                return f"训练参数 {name} 不能小于 {lo}"
            if hi is not None and numeric > hi:
                return f"训练参数 {name} 不能大于 {hi}"
        elif ptype == "bool":
            if not isinstance(value, bool):
                return f"训练参数 {name} 必须是布尔值"
    return None


# ---------------------------------------------------------------------------
# 密码哈希（标准库 PBKDF2，无新增第三方依赖）
# ---------------------------------------------------------------------------
# 说明：需求文档 6.2 将"复杂密码策略"列为 P2，第一阶段仅要求可登录/改密；
# 此处采用 PBKDF2-SHA256（10 万次迭代）+ 随机盐，满足基本的落库安全要求。

_PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    """生成密码哈希，格式: pbkdf2_sha256$<iterations>$<salt>$<digest>。"""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    """校验密码与存储哈希是否一致（恒定时间比较）。"""
    try:
        _algo, iterations, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
        ).hex()
        return hmac.compare_digest(calc, digest)
    except (ValueError, TypeError):
        return False
