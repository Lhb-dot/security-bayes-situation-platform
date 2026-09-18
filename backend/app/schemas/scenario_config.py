"""Validation helpers for scenario explanation dictionaries.

The validator is intentionally pure so it can run in unit tests and deployment
checks without requiring a database. It validates configured fields rather than
guessing metadata for fields that have not been registered yet.
"""
from __future__ import annotations

from typing import Any


REQUIRED_SCENARIO_FIELDS = (
    "scenario_name",
    "analysis_goal",
    "risk_types",
    "recommended_actions",
    "manual_review_advice",
    "risk_expression_template",
    "feature_dictionary",
)
REQUIRED_FEATURE_FIELDS = (
    "display_name",
    "meaning",
    "high_value_meaning",
    "low_value_meaning",
    "abnormal_value_meaning",
    "recommended_action",
)


def validate_scenario_config(code: str, config: Any) -> list[str]:
    """Return human-readable configuration errors for one scenario."""
    errors: list[str] = []
    if not isinstance(config, dict):
        return [f"{code}: 配置必须是 JSON 对象"]

    for key in REQUIRED_SCENARIO_FIELDS:
        if key not in config:
            errors.append(f"{code}: 缺少字段 {key}")

    for key in ("scenario_name", "analysis_goal", "manual_review_advice", "risk_expression_template"):
        if key in config and not isinstance(config[key], str):
            errors.append(f"{code}: {key} 必须是非空字符串")
        elif key in config and not config[key].strip():
            errors.append(f"{code}: {key} 不能为空")

    for key in ("risk_types", "recommended_actions"):
        value = config.get(key)
        if not isinstance(value, list) or not value or any(not str(item).strip() for item in value):
            errors.append(f"{code}: {key} 必须是非空字符串数组")

    dictionary = config.get("feature_dictionary")
    if not isinstance(dictionary, dict):
        errors.append(f"{code}: feature_dictionary 必须是对象")
    else:
        for feature_name, metadata in dictionary.items():
            if not isinstance(metadata, dict):
                errors.append(f"{code}.{feature_name}: 字段说明必须是对象")
                continue
            for key in REQUIRED_FEATURE_FIELDS:
                value = metadata.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{code}.{feature_name}: 缺少非空字段 {key}")
    required_names = config.get("required_feature_names")
    if required_names is not None:
        if not isinstance(required_names, list) or not required_names or any(not isinstance(name, str) or not name.strip() for name in required_names):
            errors.append(f"{code}: required_feature_names 必须是非空字符串数组")
        else:
            missing = [name for name in required_names if name not in dictionary]
            if missing:
                errors.append(f"{code}: 字段字典缺少 {', '.join(missing)}")
    return errors


def validate_scenario_configs(configs: Any) -> list[str]:
    """Validate every scenario in a configuration mapping."""
    if not isinstance(configs, dict):
        return ["场景配置根节点必须是 JSON 对象"]
    errors: list[str] = []
    for code, config in configs.items():
        errors.extend(validate_scenario_config(str(code), config))
    return errors
