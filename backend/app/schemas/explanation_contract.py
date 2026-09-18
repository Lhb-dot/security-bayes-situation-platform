"""Versioned contract for model explanations.

The contract is deliberately independent from Weka, SQLAlchemy and the AI
client. Prediction facts are copied into an explanation after prediction and
are never used to calculate the prediction itself.
"""
from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any


EXPLANATION_CONTRACT_VERSION = "1.0"
EXPLANATION_ROLES = ("SCENARIO_USER", "SCENARIO_ADMIN", "SUPER_ADMIN")
ALGORITHM_CODES = ("A2WNB", "MAWNB", "EMAWNB", "CAVWNB", "PMWNB", "DIWNB")

PUBLIC_FIELDS = (
    "contract_version",
    "prediction",
    "prediction_is_risk",
    "risk_probability",
    "risk_threshold",
    "confidence",
    "top_features",
    "conflict",
    "scenario",
    "recommended_actions",
)

ADMIN_FIELDS = PUBLIC_FIELDS + (
    "model_quality",
    "algorithm_details",
    "input_snapshot",
)


def unavailable(reason: str) -> dict[str, Any]:
    """Represent an unavailable structured value consistently."""
    return {"available": False, "reason": str(reason)}


def availability(is_available: bool, reason: str | None = None) -> dict[str, Any]:
    """Return the fixed shape used by every availability marker."""
    return {
        "available": bool(is_available),
        "reason": None if is_available else str(reason or "数据不可用"),
    }


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def prediction_snapshot(result: dict[str, Any] | None) -> dict[str, Any]:
    """Extract only prediction facts for before/after regression comparison."""
    source = result or {}
    distribution = source.get("class_distribution")
    normalized_distribution = []
    if isinstance(distribution, list):
        for item in distribution:
            if not isinstance(item, dict) or item.get("class") is None:
                continue
            normalized_distribution.append({
                "class": str(item["class"]),
                "probability": finite_number(item.get("probability")),
            })
    return {
        "prediction_label": str(source.get("prediction_label", "")).strip(),
        "probability": finite_number(source.get("probability")),
        "class_distribution": normalized_distribution,
    }


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def algorithm_specific_template(algorithm_code: str) -> dict[str, Any]:
    """Return the fixed shape for one algorithm's read-only details."""
    code = str(algorithm_code or "").upper()
    templates = {
        "A2WNB": {
            "original_attributes": [],
            "enhanced_attributes": [],
            "probability_change": None,
            "rode": unavailable("A2WNB 专属数据尚未接入"),
        },
        "MAWNB": {
            "original_view": {},
            "spode_view": {},
            "random_forest_view": {},
        },
        "EMAWNB": {
            "dynamic_view_weights": [],
            "before_fusion": [],
            "after_fusion": [],
            "view_conflict": {},
        },
        "CAVWNB": {"feature_evidence": []},
        "PMWNB": {
            "submodels": [],
            "risk_support_count": None,
            "disagreement": None,
        },
        "DIWNB": {
            "original_view": {},
            "knn_view": {},
            "k": None,
            "neighbor_risk_ratio": None,
            "neighbor_class_ratios": [],
            "consistency": None,
        },
    }
    return deepcopy(templates.get(code, {"available": False, "reason": "当前算法未提供专属解释数据"}))


def merge_algorithm_specific(algorithm_code: str, value: Any) -> dict[str, Any]:
    """Merge actual read-only data into its fixed algorithm template."""
    template = algorithm_specific_template(algorithm_code)
    if isinstance(value, dict):
        template.update(deepcopy(value))
        if value.get("available") is False:
            template["available"] = False
            template["reason"] = str(value.get("reason") or "算法专属数据不可用")
        elif value:
            template["available"] = bool(value.get("available", True))
            template["reason"] = None if template["available"] else str(value.get("reason") or "算法专属数据不可用")
    return template


def normalize_explanation(explanation: dict[str, Any] | None) -> dict[str, Any]:
    """Fill and type-normalize the v1 envelope without changing model facts."""
    data = deepcopy(explanation or {})
    data["contract_version"] = EXPLANATION_CONTRACT_VERSION
    data["prediction"] = str(data.get("prediction", data.get("prediction_label", ""))).strip()
    data["prediction_is_risk"] = bool(data.get("prediction_is_risk", False))
    data["risk_probability"] = finite_number(data.get("risk_probability"))
    data["risk_threshold"] = finite_number(data.get("risk_threshold"))
    data["confidence"] = str(data.get("confidence", "低"))
    data["top_features"] = _list(data.get("top_features"))
    data["recommended_actions"] = [str(item) for item in _list(data.get("recommended_actions"))]

    conflict = _dict(data.get("conflict"))
    data["conflict"] = {
        "has_conflict": bool(conflict.get("has_conflict", False)),
        "description": str(conflict.get("description", "未提供一致性判断")),
    }

    scenario = _dict(data.get("scenario"))
    data["scenario"] = {
        "scenario_code": scenario.get("scenario_code"),
        "scenario_name": scenario.get("scenario_name"),
        "analysis_goal": scenario.get("analysis_goal"),
        "risk_types": [str(item) for item in _list(scenario.get("risk_types"))],
        "feature_dictionary": _dict(scenario.get("feature_dictionary")),
        "recommended_actions": [str(item) for item in _list(scenario.get("recommended_actions"))],
        "manual_review_advice": scenario.get("manual_review_advice"),
        "risk_expression_template": scenario.get("risk_expression_template"),
        "configuration_available": bool(scenario.get("configuration_available", True)),
    }

    quality = _dict(data.get("model_quality"))
    data["model_quality"] = {
        "risk_recall": finite_number(quality.get("risk_recall")),
        "risk_f1": finite_number(quality.get("risk_f1")),
        "cv_mean": finite_number(quality.get("cv_mean")),
        "cv_std": finite_number(quality.get("cv_std")),
        "availability": {
            "risk_recall": availability(
                finite_number(quality.get("risk_recall")) is not None,
                "训练结果未提供风险召回率",
            ),
            "risk_f1": availability(
                finite_number(quality.get("risk_f1")) is not None,
                "训练结果未提供风险 F1",
            ),
            "cv_mean": availability(
                finite_number(quality.get("cv_mean")) is not None,
                "训练结果未提供交叉验证均值",
            ),
            "cv_std": availability(
                finite_number(quality.get("cv_std")) is not None,
                "训练结果未提供交叉验证标准差",
            ),
        },
    }

    details = _dict(data.get("algorithm_details"))
    algorithm_code = str(details.get("algorithm_code", "")).upper()
    specific = details.get("specific")
    specific = merge_algorithm_specific(algorithm_code, specific)
    details["algorithm_code"] = algorithm_code
    details["class_distribution"] = _list(details.get("class_distribution"))
    details["views"] = _list(details.get("views"))
    details["view_weights"] = _list(details.get("view_weights"))
    details["feature_evidence"] = _list(details.get("feature_evidence"))
    details["specific"] = specific
    details["availability"] = availability(
        bool(details.get("availability", {}).get("available", True))
        if isinstance(details.get("availability"), dict)
        else bool(details["views"] or details["feature_evidence"] or specific.get("available", True)),
        (details.get("availability") or {}).get("reason")
        if isinstance(details.get("availability"), dict)
        else None,
    )
    data["algorithm_details"] = details
    data["input_snapshot"] = _dict(data.get("input_snapshot"))

    # Keep legacy prediction fields when present, while making their types stable.
    if "prediction_label" in data:
        data["prediction_label"] = str(data["prediction_label"]).strip()
    if "probability" in data:
        data["probability"] = finite_number(data.get("probability"))
    if "class_distribution" in data:
        data["class_distribution"] = _list(data.get("class_distribution"))
    return data


def explanation_for_role(explanation: dict[str, Any] | None, role: str | None) -> dict[str, Any]:
    """Apply the three-level explanation visibility policy."""
    data = normalize_explanation(explanation)
    if role in ("SUPER_ADMIN", "SCENARIO_ADMIN"):
        return data

    public = {key: data[key] for key in PUBLIC_FIELDS}
    public["top_features"] = data["top_features"][:3]
    public["scenario"] = {
        key: data["scenario"].get(key)
        for key in (
            "scenario_code",
            "scenario_name",
            "analysis_goal",
            "risk_types",
            "manual_review_advice",
            "risk_expression_template",
            "configuration_available",
        )
    }
    return public


def validate_explanation_contract(explanation: dict[str, Any]) -> list[str]:
    """Return contract violations; intended for tests and boundary checks."""
    errors = []
    if not isinstance(explanation, dict):
        return ["explanation must be an object"]
    for field in PUBLIC_FIELDS:
        if field not in explanation:
            errors.append(f"missing field: {field}")
    if explanation.get("contract_version") != EXPLANATION_CONTRACT_VERSION:
        errors.append("contract_version must be 1.0")
    if not isinstance(explanation.get("top_features"), list):
        errors.append("top_features must be an array")
    if not isinstance(explanation.get("recommended_actions"), list):
        errors.append("recommended_actions must be an array")
    conflict = explanation.get("conflict")
    if not isinstance(conflict, dict) or not isinstance(conflict.get("has_conflict"), bool):
        errors.append("conflict.has_conflict must be boolean")
    return errors
