"""dataset_file_reader.py — 数据集文件格式识别与解析（ARFF / CSV）。

服务「上传数据集」功能：自动识别文件格式（按扩展名），解析出统一字段结构
fields（[{name, type, enum_values, sample_values}]）与样本数，供 DatasetService
登记为 fields_schema（角色 role 由调用方按 label_field 标记）。

字段类型约定（与 app/utils/arff_reader.py 一致）：
- numeric：数值列（含 real/integer/date）
- enum：枚举列（有界值域，CSV 按去重值推断）
- string：自由文本列
"""
import csv
from pathlib import Path

from app.utils.arff_reader import count_arff_rows, read_arff

# CSV 枚举推断阈值：去重值数量 <= 该值视为枚举（类别型），否则视为自由文本
_ENUM_MAX_DISTINCT = 50
# 类型推断采样上限：超大 CSV 只扫前 N 行推断类型，避免拖慢上传
_TYPE_SAMPLE_LIMIT = 5000


def detect_format(filename: str) -> str:
    """按扩展名识别格式，返回 "arff" / "csv"，未知返回 "unknown"。"""
    suffix = Path(filename).suffix.lstrip(".").lower()
    if suffix == "arff":
        return "arff"
    if suffix == "csv":
        return "csv"
    return "unknown"


def _is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def read_csv(path: str, sample_limit: int = _TYPE_SAMPLE_LIMIT):
    """解析 CSV，返回 (fields, rows)。

    - fields: [{name, type, enum_values, sample_values}]，类型按前 sample_limit 行推断
    - rows: list[list[str]]（最多 sample_limit 行）
    """
    fields: list[dict] = []
    rows: list[list[str]] = []
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return fields, rows
        header = [str(h).strip() for h in header]
        for row in reader:
            rows.append(row)
            if len(rows) >= sample_limit:
                break

    n = len(header)
    for i in range(n):
        name = header[i] or f"col_{i}"
        col = [r[i] for r in rows if i < len(r)]
        nonempty = [v for v in col if v is not None and str(v).strip() != ""]
        distinct = set(nonempty)
        if nonempty and all(_is_float(str(v)) for v in nonempty):
            ftype, enum = "numeric", []
        elif 0 < len(distinct) <= _ENUM_MAX_DISTINCT:
            ftype, enum = "enum", sorted(distinct)
        else:
            ftype, enum = "string", []
        fields.append(
            {
                "name": name,
                "type": ftype,
                "enum_values": enum,
                "sample_values": list(distinct)[:2],
            }
        )
    return fields, rows


def count_csv_rows(path: str) -> int:
    """统计 CSV 数据行数（不含表头）。"""
    count = 0
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            return 0
        for _ in reader:
            count += 1
    return count


def read_dataset_file(path: str):
    """按格式解析数据集文件，返回 (format, fields, record_count)。

    - ARFF：用 @attribute 声明拿精确类型与枚举值域，样本数统计 @DATA 行
    - CSV：表头取字段名，类型按数据推断
    """
    fmt = detect_format(path)
    if fmt == "arff":
        fields, _ = read_arff(path, max_rows=100)
        record_count = count_arff_rows(path)
    elif fmt == "csv":
        fields, _ = read_csv(path)
        record_count = count_csv_rows(path)
    else:
        raise ValueError("不支持的文件格式：仅支持 .arff / .csv")
    return fmt, fields, record_count


def build_fields_schema(fields: list[dict], label_field: str) -> list[dict]:
    """把解析出的 fields 加上角色 role，转为可入库的 fields_schema。

    - name == label_field 的字段标记为 label，其余为 feature
    - 保留 type / enum_values / sample_values
    """
    schema = []
    for f in fields:
        schema.append(
            {
                "name": f["name"],
                "role": "label" if f["name"] == label_field else "feature",
                "type": f["type"],
                "enum_values": f.get("enum_values", []),
                "sample_values": f.get("sample_values", []),
            }
        )
    return schema
