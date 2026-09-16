"""Model-level AI evaluation.

This service evaluates a trained model version from persisted model facts. It
does not require an input sample, execute prediction, or create an inference
record. The stored wording is separated by role because an administrator and
an ordinary scenario user have different information needs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Iterable

from app.models.dataset import Dataset
from app.models.app_user import AppUser
from app.models.model_version import ModelVersion
from app.models.user_ai_setting import UserAISetting
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    DATASET_VISIBILITY_PLATFORM,
    dataset_display_name,
    ROLE_SCENARIO_ADMIN,
    ROLE_SUPER_ADMIN,
    USER_VISIBLE_MODEL_STATUSES,
)
from app.services.explanation_service import (
    _chunk_text,
    _classify_ai_error,
    _openai_stream,
    get_scenario_config,
)


MODEL_EVALUATION_VERSION = "1.0"
ADMIN_ROLE = "management"
USER_ROLE = "user"


def _role_key(user: Any) -> str:
    return ADMIN_ROLE if getattr(user, "role", None) in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN) else USER_ROLE


def _quality_metrics(metrics: dict[str, Any] | None) -> dict[str, Any]:
    source = metrics if isinstance(metrics, dict) else {}
    keys = (
        "accuracy", "precision", "recall", "specificity", "f1", "g_mean",
        "risk_recall", "risk_f1", "cv_mean", "cv_std", "quality_availability",
        "num_instances", "num_attributes", "num_classes", "class_distribution",
    )
    return {key: source.get(key) for key in keys if key in source}


def build_model_attributes(model: ModelVersion) -> dict[str, Any]:
    """Build immutable, non-secret facts attached to a model version."""
    dataset = getattr(model, "dataset", None)
    algorithm = getattr(model, "algorithm", None)
    scenario = getattr(model, "scenario", None)
    scenario_code = getattr(scenario, "code", None)
    scenario_config = get_scenario_config(scenario_code)
    fields = getattr(dataset, "fields_schema", None) or []
    dictionary = scenario_config.get("feature_dictionary") or {}
    feature_profile: list[dict[str, Any]] = []
    for field in fields:
        if not isinstance(field, dict) or field.get("role") == "label":
            continue
        name = str(field.get("name") or "")
        metadata = dictionary.get(name) or {}
        feature_profile.append({
            "name": name,
            "type": field.get("type"),
            "display_name": metadata.get("display_name") or name,
            "meaning": metadata.get("meaning"),
            "high_value_meaning": metadata.get("high_value_meaning"),
            "low_value_meaning": metadata.get("low_value_meaning"),
            "abnormal_value_meaning": metadata.get("abnormal_value_meaning"),
            "recommended_action": metadata.get("recommended_action"),
        })
    return {
        "contract_version": MODEL_EVALUATION_VERSION,
        "model_version_id": getattr(model, "id", None),
        "status": getattr(model, "status", None),
        "scenario": {
            "code": scenario_code,
            "name": scenario_config.get("scenario_name"),
            "risk_types": scenario_config.get("risk_types") or [],
            "analysis_goal": scenario_config.get("analysis_goal"),
            "manual_review_advice": scenario_config.get("manual_review_advice"),
        },
        "dataset": {
            "logical_id": getattr(dataset, "logical_id", None),
            "name": dataset_display_name(getattr(dataset, "logical_id", None)),
            "version": getattr(dataset, "version", None),
            "label_field": getattr(dataset, "label_field", None),
            "field_count": len(feature_profile),
            "visibility": getattr(dataset, "visibility", None),
        },
        "algorithm": {
            "code": getattr(algorithm, "code", None),
            "name": getattr(algorithm, "display_name", None),
            "description": getattr(algorithm, "description", None),
            "parameter_schema": getattr(algorithm, "param_schema", None) or [],
        },
        "training_parameters": getattr(model, "training_parameters", None) or {},
        "quality_metrics": _quality_metrics(getattr(model, "evaluation_metrics", None)),
        "feature_profile": feature_profile,
        "feature_importance": {
            "available": False,
            "reason": "当前版本保存的是模型训练参数和场景字段画像，未保存可证明因果的全局特征重要性",
        },
        "evaluation_scope": "这是模型版本评价，不是某条样本的风险推理；评价不得改变模型预测结果。",
    }


def public_model_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    """Remove internal quality and algorithm tuning details for users."""
    data = dict(attributes or {})
    data["algorithm"] = {
        key: (data.get("algorithm") or {}).get(key)
        for key in ("code", "name", "description")
    }
    data["quality_metrics"] = {
        key: (data.get("quality_metrics") or {}).get(key)
        for key in ("accuracy", "precision", "recall", "specificity", "f1", "g_mean")
        if key in (data.get("quality_metrics") or {})
    }
    data.pop("training_parameters", None)
    data.pop("feature_importance", None)
    # Keep field semantics useful to the scenario user but omit internal data.
    data["feature_profile"] = [
        {
            key: item.get(key)
            for key in (
                "name", "type", "display_name", "meaning", "high_value_meaning",
                "low_value_meaning", "abnormal_value_meaning", "recommended_action",
            )
        }
        for item in data.get("feature_profile", [])
    ]
    return data


def build_model_evaluation_facts(attributes: dict[str, Any], role: str) -> dict[str, Any]:
    facts = attributes if role == ADMIN_ROLE else public_model_attributes(attributes)
    return {
        "evaluation_type": "model_version_evaluation",
        "audience": "管理员" if role == ADMIN_ROLE else "场景普通用户",
        "model": facts,
    }


def fallback_model_evaluation(facts: dict[str, Any], role: str) -> str:
    model = facts.get("model") or {}
    algorithm = model.get("algorithm") or {}
    dataset = model.get("dataset") or {}
    quality = model.get("quality_metrics") or {}
    fields = model.get("feature_profile") or []
    title = "### 模型评价（管理员）" if role == ADMIN_ROLE else "### 模型使用提示"
    lines = [title, f"模型版本 `{model.get('model_version_id')}` 使用算法 **{algorithm.get('name') or algorithm.get('code') or '未命名算法'}**。"]
    lines.extend(["", "### 模型结论"])
    if quality.get("f1") is not None:
        lines.append(
            f"当前模型 F1 为 `{quality['f1']}`，基于数据集 "
            f"`{dataset.get('name') or dataset.get('logical_id')}` 的训练结果进行评价。"
        )
    else:
        lines.append("当前模型缺少完整质量指标，使用时需要结合实际效果持续复核。")
    lines.extend(["", "### 场景重点字段"])
    if fields:
        for item in fields[:5]:
            lines.append(f"- **{item.get('display_name') or item.get('name')}**：{item.get('meaning') or '请结合该字段在当前场景中的业务含义判断。'}")
    else:
        lines.append("当前模型没有可展示的场景字段画像。")
    if role == ADMIN_ROLE:
        lines.extend(["", "### 管理员诊断", "模型评价只能依据已保存的训练参数、质量指标和字段画像；当前未保存全局特征重要性，因此不能把某个字段描述为确定的因果来源。", "", "### 优化建议"])
        if quality.get("cv_std") is not None:
            lines.append(f"- 关注交叉验证波动：当前 CV Std 为 `{quality['cv_std']}`，建议结合不同时间段或场景子集复核稳定性。")
        lines.append("- 建议补充全局特征重要性或分层验证结果后再进行更强的字段影响排序。")
        lines.append("- 上线后持续观察风险召回率、风险 F1 和误报漏报，并按场景数据漂移重新训练。")
    else:
        lines.extend(["", "### 使用注意", "这些提示用于理解模型关注的场景字段，不代表对某一条具体数据的风险判定；具体结果以实际推理页面为准。"])
    return "\n".join(lines)


def build_model_evaluation_prompt(facts: dict[str, Any], role: str) -> list[dict[str, str]]:
    if role == ADMIN_ROLE:
        system = (
            "你是机器学习模型质量审查员。请评价模型版本本身，而不是评价某条风险样本。"
            "只能使用用户消息中的事实，不得编造指标、特征重要性、因果关系或训练过程。"
            "如果 feature_importance.available=false，不得声称某列是模型实际影响最大的列，只能称为场景重点关注字段。"
            "请输出 Markdown，固定包含：### 模型结论、### 关键风险信号、### 质量诊断、### 算法结构评价、### 优化建议、### 上线监控建议。"
            "优化建议要能帮助管理员改进数据、参数、验证方案或监控，不得改变正式预测逻辑。"
        )
    else:
        system = (
            "你是场景模型使用提示助手。请评价已发布模型能帮助普通用户关注什么，而不是评价某条风险样本。"
            "只能使用用户消息中的事实，不得展示内部训练参数、交叉验证指标、原始路径或管理员优化建议。"
            "不得把字段语义写成确定因果；应使用场景重点关注、可能提示、建议留意等表达。"
            "请输出 Markdown，固定包含：### 模型能做什么、### 场景重点字段、### 风险提示、### 使用注意。"
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(facts, ensure_ascii=False, sort_keys=True)},
    ]


class ModelEvaluationService(ServiceBase):
    def requested_role(self, current_user, audience: str = "current") -> str:
        """Resolve the audience while preventing role escalation."""
        current_role = _role_key(current_user)
        if audience in (None, "current"):
            return current_role
        if audience not in (ADMIN_ROLE, USER_ROLE):
            raise ServiceError(400, "评价受众不合法")
        if audience != current_role:
            self.require_scenario_admin(current_user)
        return audience

    def _get_authorized(self, current_user, model_id: int) -> ModelVersion:
        self.require_login(current_user)
        model = self.db.get(ModelVersion, model_id)
        if model is None:
            raise ServiceError(404, "模型版本不存在")
        role = getattr(current_user, "role", None)
        dataset = self.db.get(Dataset, model.dataset_id)
        if role == ROLE_SUPER_ADMIN:
            allowed = model.trained_by == getattr(current_user, "id", None) and dataset is not None and dataset.visibility == DATASET_VISIBILITY_PLATFORM
        elif role == ROLE_SCENARIO_ADMIN:
            trainer = self.db.get(AppUser, model.trained_by)
            allowed = (
                model.scenario_id == getattr(current_user, "scenario_id", None)
                and dataset is not None
                and dataset.visibility in ("platform", "company")
                and not (
                    trainer is not None
                    and trainer.role == ROLE_SUPER_ADMIN
                    and model.status != "PUBLISHED"
                )
            )
        else:
            allowed = model.status in USER_VISIBLE_MODEL_STATUSES and model.scenario_id == getattr(current_user, "scenario_id", None) and dataset is not None and (dataset.visibility in ("platform", "company") or dataset.uploaded_by == getattr(current_user, "id", None))
        if not allowed:
            raise ServiceError(403, "无权限查看该模型评价")
        return model

    def _attributes(self, model: ModelVersion) -> dict[str, Any]:
        current = getattr(model, "model_attributes", None)
        if not isinstance(current, dict) or current.get("contract_version") != MODEL_EVALUATION_VERSION:
            current = build_model_attributes(model)
            model.model_attributes = current
            self.commit()
        elif current.get("status") != model.status:
            # Status is the only lifecycle fact that changes after training.
            # Keep the model-owned snapshot aligned without rebuilding other facts.
            current = {**current, "status": model.status}
            model.model_attributes = current
            self.commit()
        return current

    @service_call
    def get_evaluation(self, current_user, model_id: int) -> dict:
        model = self._get_authorized(current_user, model_id)
        attributes = self._attributes(model)
        role = _role_key(current_user)
        artifact = (getattr(model, "ai_evaluation", None) or {}).get(role) or {}
        return ok(data={
            "model_version_id": model.id,
            "status": model.status,
            "role": role,
            "model_attributes": attributes if role == ADMIN_ROLE else public_model_attributes(attributes),
            "evaluation": {
                "available": bool(artifact.get("markdown")),
                "source": artifact.get("source"),
                "markdown": artifact.get("markdown"),
                "generated_at": artifact.get("generated_at"),
            },
        })

    def _save(self, model: ModelVersion, role: str, markdown: str, source: str, facts: dict[str, Any]) -> None:
        evaluations = dict(getattr(model, "ai_evaluation", None) or {})
        evaluations[role] = {
            "available": True,
            "markdown": markdown[:100_000],
            "source": source if source in {"ai", "fallback"} else "fallback",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "facts_snapshot": facts,
        }
        model.ai_evaluation = evaluations
        self.commit()

    def stream(
        self,
        current_user,
        model_id: int,
        regenerate: bool = False,
        evaluation_role: str | None = None,
    ) -> Iterable[tuple[str, dict[str, Any]]]:
        model = self._get_authorized(current_user, model_id)
        attributes = self._attributes(model)
        role = evaluation_role or _role_key(current_user)
        if role == USER_ROLE and model.status not in USER_VISIBLE_MODEL_STATUSES:
            raise ServiceError(403, "未发布模型不能生成普通用户评价")
        evaluations = getattr(model, "ai_evaluation", None) or {}
        cached = evaluations.get(role) or {}
        yield "start", {"status": "开始读取模型评价"}
        if cached.get("markdown") and not regenerate:
            for chunk in _chunk_text(str(cached["markdown"])):
                yield "delta", {"content": chunk}
            yield "done", {"status": "已读取已保存模型评价", "source": "cached"}
            return
        facts = build_model_evaluation_facts(attributes, role)
        setting = self.db.get(UserAISetting, current_user.id)
        if setting is None or not setting.enabled:
            markdown = fallback_model_evaluation(facts, role)
            self._save(model, role, markdown, "fallback", facts)
            yield "error", {"message": "当前账号未配置可用的 AI 服务", "reason_code": "not_configured"}
            for chunk in _chunk_text(markdown):
                yield "delta", {"content": chunk}
            yield "done", {"status": "已使用规则模板完成模型评价", "source": "fallback"}
            return
        try:
            parts: list[str] = []
            for chunk in _openai_stream(setting, build_model_evaluation_prompt(facts, role)):
                parts.append(chunk)
                yield "delta", {"content": chunk}
            markdown = "".join(parts).strip()
            if not markdown:
                raise RuntimeError("empty AI response")
            self._save(model, role, markdown, "ai", facts)
            yield "done", {"status": "模型评价完成", "source": "ai"}
        except Exception as exc:  # noqa: BLE001
            reason_code, _ = _classify_ai_error(exc)
            markdown = fallback_model_evaluation(facts, role)
            self._save(model, role, markdown, "fallback", facts)
            yield "error", {"message": "AI 服务不可用，已回退规则模型评价", "reason_code": reason_code}
            for chunk in _chunk_text(markdown):
                yield "delta", {"content": chunk}
            yield "done", {"status": "已使用规则模板完成模型评价", "source": "fallback"}
