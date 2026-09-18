"""Unified model facts, scenario context, and OpenAI-compatible wording.

This module deliberately keeps model decisions outside the LLM. The LLM receives
the already-calculated facts and can only express them in Markdown. The rule
fallback is always available so explanation generation cannot block inference.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from cryptography.fernet import Fernet
import openai
from openai import OpenAI

from app.data.scenario_feature_catalog import expand_scenario_feature_catalog
from app.models.user_ai_setting import UserAISetting
from app.services.base import ServiceError, ServiceBase, service_call
from app.schemas.explanation_contract import (
    EXPLANATION_CONTRACT_VERSION,
    availability,
    explanation_for_role,
    normalize_explanation,
    unavailable,
)
from app.schemas.scenario_config import validate_scenario_config, validate_scenario_configs
from app.schemas.common import ok
from app.utils.common import get_logger, row_to_dict

logger = get_logger("explanation")
CONFIG_PATH = Path(__file__).resolve().parents[1] / "data" / "scenario_configs.json"


def _env_float(name: str, default: float, minimum: float) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


AI_REQUEST_TIMEOUT_SECONDS = _env_float("AI_EXPLANATION_TIMEOUT_SECONDS", 60.0, 5.0)
# Some OpenAI-compatible gateways need several seconds to warm up a model.
# Keep connectivity checks strict, but allow a normal remote first response.
AI_CONNECTIVITY_TIMEOUT_SECONDS = _env_float("AI_CONNECTIVITY_TIMEOUT_SECONDS", 30.0, 3.0)
AI_MAX_OUTPUT_TOKENS = _env_int("AI_EXPLANATION_MAX_TOKENS", 1200, 64)
AI_MAX_OUTPUT_CHARS = _env_int("AI_EXPLANATION_MAX_CHARS", 12000, 512)


def _configs() -> dict[str, dict[str, Any]]:
    try:
        configs = expand_scenario_feature_catalog(
            json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        )
        errors = validate_scenario_configs(configs)
        if errors:
            logger.error("场景解释配置校验失败: %s", "；".join(errors[:10]))
        return configs if isinstance(configs, dict) else {}
    except (OSError, json.JSONDecodeError):
        logger.exception("场景解释配置加载失败")
        return {}


def get_scenario_config(code: str | None) -> dict[str, Any]:
    code = str(code or "").strip()
    config = _configs().get(code)
    if config is None:
        return {
            "scenario_code": code,
            "scenario_name": code or "未指定场景",
            "analysis_goal": "基于模型结果识别风险",
            "risk_types": [],
            "recommended_actions": [],
            "manual_review_advice": "信息不足时请结合原始数据进行人工复核。",
            "feature_dictionary": {},
        }
    errors = validate_scenario_config(code, config)
    if errors:
        logger.error("场景 %s 解释配置不可用: %s", code, "；".join(errors[:10]))
        return {
            "scenario_code": code,
            "scenario_name": config.get("scenario_name") or code or "未指定场景",
            "analysis_goal": "基于模型结果识别风险",
            "risk_types": [],
            "recommended_actions": [],
            "manual_review_advice": "场景配置不完整，请结合原始数据进行人工复核。",
            "risk_expression_template": None,
            "feature_dictionary": {},
            "configuration_available": False,
            "configuration_errors": errors,
        }
    return {**config, "scenario_code": code, "configuration_available": True}


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _availability(reason: str) -> dict[str, Any]:
    return unavailable(reason)


def _raw_value(sample: dict[str, Any], name: str) -> Any:
    return sample.get(name)


def _top_features(
    sample: dict[str, Any],
    result: dict[str, Any],
    is_prediction_risk: bool,
    scenario_config: dict[str, Any],
) -> list[dict[str, Any]]:
    source = result.get("top_features") or result.get("feature_attribution") or []
    if not source:
        source = result.get("feature_evidence") or []
    if not isinstance(source, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in source:
        if not isinstance(item, dict):
            continue
        name = item.get("feature_name") or item.get("attribute") or item.get("feature")
        if not name:
            continue
        value = item.get("raw_value", _raw_value(sample, str(name)))
        processed = item.get("processed_value", item.get("value", value))
        contribution = _finite_number(
            item.get("contribution", item.get("salience", item.get("importance")))
        )
        if contribution is None and isinstance(item.get("class_contributions"), list):
            contributions = item["class_contributions"]
            values = [
                _finite_number(c.get("contribution"))
                for c in contributions
                if isinstance(c, dict)
            ]
            values = [v for v in values if v is not None]
            contribution = max((abs(v) for v in values), default=None)
        if contribution is None:
            continue
        supports_predicted = item.get("supports_predicted")
        if supports_predicted is None:
            signed = _finite_number(item.get("signed_contribution"))
            supports_predicted = signed is None or signed >= 0
        direction = "支持风险" if bool(supports_predicted) == is_prediction_risk else "支持正常"
        feature_name = str(name)
        metadata = (scenario_config.get("feature_dictionary") or {}).get(feature_name) or {}
        feature = {
            "feature_name": feature_name,
            "raw_value": value,
            "processed_value": processed,
            "contribution": round(abs(contribution), 6),
            "direction": direction,
            "rank": 0,
        }
        for key in ("display_name", "meaning", "risk_description", "recommended_action"):
            if metadata.get(key) is not None:
                feature[key] = metadata[key]
        normalized.append(feature)
    normalized.sort(key=lambda x: x["contribution"], reverse=True)
    for rank, item in enumerate(normalized, start=1):
        item["rank"] = rank
    return normalized[:10]


def _views(result: dict[str, Any]) -> list[dict[str, Any]]:
    views = result.get("views")
    return views if isinstance(views, list) else []


def build_unified_explanation(
    *,
    scenario_code: str | None,
    sample: dict[str, Any],
    model_result: dict[str, Any],
    algorithm_code: str,
    is_prediction_risk: bool,
    model_metrics: dict[str, Any] | None = None,
    risk_threshold: float = 0.5,
) -> dict[str, Any]:
    """Normalize Java output without changing the model's prediction."""
    result = model_result or {}
    prediction = str(result.get("prediction_label", "")).strip()
    class_distribution = result.get("class_distribution") or []
    risk_probability = _finite_number(result.get("risk_probability"))
    if risk_probability is None:
        risk_probability = _finite_number(result.get("probability")) if is_prediction_risk else None
        if isinstance(class_distribution, list):
            risk_probability = next(
                (
                    _finite_number(row.get("probability"))
                    for row in class_distribution
                    if isinstance(row, dict)
                    and str(row.get("class", "")).strip() == prediction
                    and is_prediction_risk
                ),
                risk_probability,
            )
    quality = model_metrics or {}
    cv_mean = _finite_number(quality.get("cv_mean"))
    cv_std = _finite_number(quality.get("cv_std"))
    views = _views(result)
    conflict_labels = {
        str(view.get("predicted_label"))
        for view in views
        if isinstance(view, dict) and view.get("predicted_label") is not None
    }
    has_conflict = len(conflict_labels | ({prediction} if prediction else set())) > 1
    config = get_scenario_config(scenario_code)
    scenario_data = {
        "scenario_code": scenario_code,
        "scenario_name": config.get("scenario_name"),
        "analysis_goal": config.get("analysis_goal"),
        "risk_types": config.get("risk_types", []),
        "feature_dictionary": config.get("feature_dictionary", {}),
        "recommended_actions": config.get("recommended_actions", []),
        "manual_review_advice": config.get("manual_review_advice"),
        "risk_expression_template": config.get("risk_expression_template"),
        "configuration_available": config.get("configuration_available", True),
    }
    confidence_gap = abs((risk_probability if risk_probability is not None else 0.5) - risk_threshold)
    confidence = "高" if confidence_gap >= 0.25 else "中" if confidence_gap >= 0.1 else "低"
    raw_algorithm_details = result.get("algorithm_details")
    specific = (
        raw_algorithm_details.get("specific")
        if isinstance(raw_algorithm_details, dict) and "specific" in raw_algorithm_details
        else raw_algorithm_details
    )
    if not specific:
        specific = {
            "MAWNB": {"views": views} if algorithm_code == "MAWNB" and views else _availability("MAWNB 未提供视图明细"),
            "EMAWNB": {"views": views, "dynamic_view_weights": result.get("view_weights") or []}
            if algorithm_code == "EMAWNB" and (views or result.get("view_weights"))
            else _availability("EMAWNB 未提供动态视图权重"),
            "CAVWNB": {"feature_evidence": result.get("feature_evidence") or []}
            if algorithm_code == "CAVWNB" and result.get("feature_evidence")
            else _availability("CAVWNB 未提供条件概率或特征权重明细"),
            "PMWNB": {"views": views} if algorithm_code == "PMWNB" and views else _availability("PMWNB 未提供 10 个子模型明细"),
            "DIWNB": {"views": views, "view_weights": result.get("view_weights") or []}
            if algorithm_code == "DIWNB" and (views or result.get("view_weights"))
            else _availability("DIWNB 未提供 KNN/K 值明细"),
            "A2WNB": _availability("A2WNB 未提供原始属性、增强属性和概率变化明细"),
        }.get(algorithm_code, _availability("当前算法未提供专属解释数据"))
    algorithm_details = {
        "algorithm_code": algorithm_code,
        "class_distribution": class_distribution,
        "views": views,
        "view_weights": result.get("view_weights") or [],
        "feature_evidence": result.get("feature_evidence") or [],
        "calculation_method": result.get("calculation_method"),
        "specific": specific,
    }
    if not views and not result.get("feature_evidence") and not result.get("feature_attribution"):
        algorithm_details["availability"] = _availability("当前算法未提供视图或特征解释数据")
    return normalize_explanation({
        "contract_version": EXPLANATION_CONTRACT_VERSION,
        "prediction": prediction,
        "prediction_is_risk": is_prediction_risk,
        "risk_probability": risk_probability,
        "risk_threshold": risk_threshold,
        "confidence": confidence,
        "top_features": _top_features(sample, result, is_prediction_risk, config),
        "model_quality": {
            "risk_recall": _finite_number(quality.get("risk_recall", quality.get("recall"))),
            "risk_f1": _finite_number(quality.get("risk_f1", quality.get("f1"))),
            "cv_mean": cv_mean,
            "cv_std": cv_std,
            "availability": {
                "cv_mean": availability(cv_mean is not None, "训练结果未提供交叉验证均值"),
                "cv_std": availability(cv_std is not None, "训练结果未提供交叉验证标准差"),
            },
        },
        "conflict": {
            "has_conflict": has_conflict,
            "description": "视图或子模型判断存在差异" if has_conflict else "各模块判断基本一致",
        },
        "scenario": scenario_data,
        "recommended_actions": config.get("recommended_actions", []),
        "algorithm_details": algorithm_details,
        "input_snapshot": sample,
    })


def public_explanation(explanation: dict[str, Any] | None) -> dict[str, Any]:
    """Return the ordinary-user view while retaining the common contract."""
    return explanation_for_role(explanation, "SCENARIO_USER")


def fallback_markdown(explanation: dict[str, Any]) -> str:
    prediction = explanation.get("prediction") or "未知"
    probability = explanation.get("risk_probability")
    probability_text = "信息不足"
    if probability is not None:
        probability_text = f"{float(probability) * 100:.1f}%"
    conclusion = "风险" if explanation.get("prediction_is_risk") else "正常"
    lines = [
        "### 研判结论",
        f"当前样本被判断为{conclusion}，风险概率为 {probability_text}。",
        "",
        "### 主要依据",
    ]
    features = explanation.get("top_features") or []
    if features:
        for idx, item in enumerate(features[:3], start=1):
            name = item.get("display_name") or item.get("feature_name")
            sentence = f"{idx}. {name} 当前值为 `{item.get('raw_value')}`，{item['direction']}。"
            if item.get("risk_description"):
                sentence += f"场景配置说明：{item['risk_description']}。"
            lines.append(sentence)
    else:
        lines.append("暂未获得可用的特征贡献数据。")
    if explanation.get("conflict", {}).get("has_conflict"):
        lines.append("多视图或子模型存在差异，建议人工复核。")
    else:
        lines.append("各分析模块对当前结果基本一致。")
    lines.extend(["", "### 场景分析"])
    scenario = explanation.get("scenario") or {}
    risk_types = scenario.get("risk_types") or []
    if risk_types:
        lines.append(
            f"当前场景为{scenario.get('scenario_name') or '未指定场景'}，关注的风险类型包括：{'、'.join(map(str, risk_types))}。"
        )
    else:
        lines.append("当前场景暂未配置风险类型，无法进一步展开场景分析。")
    lines.extend(["", "### 风险规避建议"])
    actions = explanation.get("recommended_actions") or []
    lines.extend(f"{idx}. {action}" for idx, action in enumerate(actions, start=1))
    if not actions:
        lines.append("当前场景未配置具体处置措施，请结合原始数据人工复核。")
    manual = ((explanation.get("scenario") or {}).get("manual_review_advice")
              or "建议结合原始数据和人工经验进行复核。")
    lines.extend(["", "### 注意事项", manual, "该结果为模型辅助研判，建议结合原始日志和人工经验确认。"])
    return "\n".join(lines)


def _fernet() -> Fernet:
    seed = os.getenv("AI_SETTINGS_ENCRYPTION_KEY", "").strip()
    if not seed:
        seed = os.getenv("AUTH_SESSION_PEPPER", "").strip()
    if len(seed) < 32:
        raise RuntimeError("AI_SETTINGS_ENCRYPTION_KEY 或 AUTH_SESSION_PEPPER 至少需要 32 个字符")
    key = base64.urlsafe_b64encode(hashlib.sha256(seed.encode("utf-8")).digest())
    return Fernet(key)


def _mask_key(value: str | None) -> str | None:
    if not value:
        return None
    return f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "********"


class AISettingService(ServiceBase):
    @service_call
    def get(self, current_user) -> dict:
        self.require_login(current_user)
        setting = self.db.get(UserAISetting, current_user.id)
        if setting is None:
            return ok(data={"configured": False, "provider": "openai-compatible"})
        key = _fernet().decrypt(setting.api_key_encrypted.encode("utf-8")).decode("utf-8")
        return ok(data={
                "configured": True,
                "provider": setting.provider,
                "base_url": setting.base_url,
                "model": setting.model,
                "enabled": setting.enabled,
                "api_key_masked": _mask_key(key),
                "updated_at": getattr(setting, "updated_at", None),
            })

    @service_call
    def update(self, current_user, payload: dict) -> dict:
        self.require_login(current_user)
        base_url = str(payload.get("base_url", "")).strip().rstrip("/")
        if base_url.endswith("/chat/completions"):
            base_url = base_url[: -len("/chat/completions")].rstrip("/")
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ServiceError(400, "base_url 必须是完整的 http/https 地址")
        model = str(payload.get("model", "")).strip()
        if not model:
            raise ServiceError(400, "model 不能为空")
        setting = self.db.get(UserAISetting, current_user.id)
        api_key = str(payload.get("api_key") or "").strip()
        if setting is None and not api_key:
            raise ServiceError(400, "首次保存必须提供 API key")
        if setting is None:
            setting = UserAISetting(
                user_id=current_user.id,
                provider=str(payload.get("provider") or "openai-compatible"),
                base_url=base_url,
                model=model,
                api_key_encrypted="",
                enabled=bool(payload.get("enabled", True)),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.db.add(setting)
        else:
            setting.provider = str(payload.get("provider") or setting.provider)
            setting.base_url = base_url
            setting.model = model
            setting.enabled = bool(payload.get("enabled", True))
            setting.updated_at = datetime.now(timezone.utc)
        if api_key:
            setting.api_key_encrypted = _fernet().encrypt(api_key.encode("utf-8")).decode("utf-8")
        self.commit()
        return self.get(current_user)

    @service_call
    def test_connection(self, current_user) -> dict:
        """Test the saved provider without returning a key or model response."""
        self.require_login(current_user)
        setting = self.db.get(UserAISetting, current_user.id)
        if setting is None or not setting.enabled:
            return ok(data={
                "connected": False,
                "reason_code": "not_configured",
                "message": "当前账号未配置或未启用 AI 服务",
            })
        try:
            key = _fernet().decrypt(setting.api_key_encrypted.encode("utf-8")).decode("utf-8")
            client = OpenAI(
                api_key=key,
                base_url=setting.base_url,
                timeout=AI_CONNECTIVITY_TIMEOUT_SECONDS,
            )
            response = client.chat.completions.create(
                model=setting.model,
                messages=[{"role": "user", "content": "Reply with OK."}],
                temperature=0,
                max_tokens=1,
                stream=False,
            )
            if not response or not getattr(response, "choices", None):
                return ok(data={
                    "connected": False,
                    "reason_code": "empty_response",
                    "message": "AI 服务返回空响应",
                })
            return ok(data={
                "connected": True,
                "reason_code": "ok",
                "message": "AI 服务连接正常",
            })
        except Exception as exc:  # noqa: BLE001
            reason_code, message = _classify_ai_error(exc)
            logger.warning(
                "AI connectivity test failed user_id=%s model=%s reason=%s",
                current_user.id,
                setting.model,
                reason_code,
            )
            return ok(data={
                "connected": False,
                "reason_code": reason_code,
                "message": message,
            })


def _openai_stream(setting: UserAISetting, messages: list[dict[str, str]]) -> Iterable[str]:
    key = _fernet().decrypt(setting.api_key_encrypted.encode("utf-8")).decode("utf-8")
    client = OpenAI(api_key=key, base_url=setting.base_url, timeout=AI_REQUEST_TIMEOUT_SECONDS)
    stream = client.chat.completions.create(
        model=setting.model,
        messages=messages,
        temperature=0.1,
        max_tokens=AI_MAX_OUTPUT_TOKENS,
        stream=True,
    )
    emitted = 0
    for chunk in stream:
        choices = getattr(chunk, "choices", None) or []
        if choices:
            content = getattr(getattr(choices[0], "delta", None), "content", None)
            if content:
                remaining = AI_MAX_OUTPUT_CHARS - emitted
                if remaining <= 0:
                    break
                content = str(content)[:remaining]
                emitted += len(content)
                if content:
                    yield content


def _classify_ai_error(exc: Exception) -> tuple[str, str]:
    """Map provider failures to stable, non-sensitive API messages."""
    if isinstance(exc, openai.APITimeoutError):
        return "timeout", "AI 服务请求超时"
    if isinstance(exc, openai.RateLimitError):
        return "rate_limited", "AI 服务请求过于频繁，请稍后重试"
    if isinstance(exc, openai.AuthenticationError):
        return "authentication_failed", "AI 服务认证失败，请检查 API key"
    if isinstance(exc, openai.NotFoundError):
        return "model_not_found", "AI 服务或模型不存在，请检查地址和模型名称"
    if isinstance(exc, openai.APIConnectionError):
        return "connection_failed", "无法连接 AI 服务，请检查地址和网络"
    return "provider_error", "AI 服务暂时不可用"


def build_prompt(explanation: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "你是模型结果表达助手。只能使用用户消息中的事实数据和场景配置，输出 Markdown。"
        "不得重新计算或改变 prediction、risk_probability、risk_threshold、confidence。"
        "所有数字必须直接来自输入；不得编造字段、因果关系或处置措施。信息不足时明确写出。"
        "固定输出：### 研判结论、### 主要依据、### 场景分析、### 风险规避建议、### 注意事项。"
        "风险规避建议只能引用 recommended_actions；统计关联不得写成确定因果。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(explanation, ensure_ascii=False, sort_keys=True)},
    ]


def build_explanation_facts(explanation: dict[str, Any]) -> dict[str, Any]:
    """Flatten the request envelope into the immutable facts sent to the AI."""
    return {
        **(explanation.get("model_result") or {}),
        "scenario": explanation.get("scenario") or {},
        "sample": explanation.get("sample") or {},
        "algorithm_details": explanation.get("algorithm_details") or {},
        "recommended_actions": explanation.get("recommended_actions") or [],
    }


def stream_explanation(db, current_user, explanation: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    facts = build_explanation_facts(explanation)
    setting = db.get(UserAISetting, current_user.id)
    yield "start", {"status": "开始分析"}
    if setting is None or not setting.enabled:
        yield "error", {"message": "当前账号未配置可用的 AI 服务"}
        for chunk in _chunk_text(fallback_markdown(facts)):
            yield "delta", {"content": chunk}
        yield "done", {"status": "已使用规则模板完成", "source": "fallback"}
        return
    try:
        logger.info(
            "AI explanation started user_id=%s model=%s",
            current_user.id,
            setting.model,
        )
        emitted = False
        for chunk in _openai_stream(setting, build_prompt(facts)):
            emitted = True
            yield "delta", {"content": chunk}
        if not emitted:
            raise RuntimeError("empty AI response")
        yield "done", {"status": "完成", "source": "ai"}
    except Exception as exc:  # noqa: BLE001
        reason_code, _ = _classify_ai_error(exc)
        logger.warning(
            "AI explanation failed user_id=%s model=%s reason=%s",
            current_user.id,
            setting.model,
            reason_code,
        )
        yield "error", {"message": "AI 服务不可用，已回退规则模板", "reason_code": reason_code}
        for chunk in _chunk_text(fallback_markdown(facts)):
            yield "delta", {"content": chunk}
        yield "done", {"status": "已使用规则模板完成", "source": "fallback"}


def _chunk_text(value: str, size: int = 24) -> Iterable[str]:
    for index in range(0, len(value), size):
        yield value[index:index + size]
