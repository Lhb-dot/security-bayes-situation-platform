"""数据集级 AI 解析：判断该数据集适合使用哪些已注册算法。

沿用 explanation_service 里已经跑通的 OpenAI 兼容流式内核（_openai_stream /
_classify_ai_error / _chunk_text）。设计原则与模型评价一致：**适用性判断留在
Python 里**，LLM 只负责对已算好的事实做排序与措辞，不允许自行发明算法能力。

算法适用性知识来自仓库根目录 ``nb_alg_summary.md``。算法只能由开发人员通过代码
接入（见 AlgorithmService：页面增删改一律 403），所以这份与实现强耦合的知识也
留在代码里，按 ``code`` 与库中算法行合并，避免引入新的可编辑来源造成口径漂移。
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Iterable

from sqlalchemy import select

from app.models.algorithm import Algorithm
from app.models.dataset import Dataset
from app.models.user_ai_setting import UserAISetting
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import ALGORITHM_STATUS_AVAILABLE, dataset_display_name_of
from app.services.dataset_service import DatasetService
from app.services.explanation_service import (
    _chunk_text,
    _classify_ai_error,
    _openai_stream,
    get_scenario_config,
)
from app.utils.common import (
    NUMERIC_FIELD_TYPES,
    dataset_has_numeric_features,
    get_logger,
)

logger = get_logger("dataset_analysis")

#: 契约版本，随产物一起返回，便于回溯「这份解析是按哪版口径生成的」。
DATASET_ANALYSIS_VERSION = "1.0"
DATASET_ANALYSIS_PROMPT_VERSION = "1.0"

#: 算法适用性知识，键为 algorithm.code。
#:
#: - ``requires_raw_numeric``：算法内部自行离散、必须吃原始数值特征（PMWNB）。
#:   数据集若已全部离散，它的多视图扰动会退化成同一份输入，性能大幅下降。
#: - ``needs_discrete_input``：基分类器只接受离散属性，数值特征需前置离散；
#:   平台在训练时通过 Weka Discretize 自动完成，所以含数值特征也不影响可用性。
ALGORITHM_APPLICABILITY: dict[str, dict[str, Any]] = {
    "PMWNB": {
        "requires_raw_numeric": True,
        "notes": [
            "内部用等宽(EWD)与监督(MDLP)两套离散生成矩阵视图，不需要平台层离散参数",
            "必须喂原始数值特征；若数据集已预先离散，两套视图输入完全一致，核心机制失效",
        ],
    },
    "A2WNB": {
        "needs_discrete_input": True,
        "notes": [
            "RODE 基分类器只接受离散输入，数值特征需前置离散（平台自动完成）",
            "潜在属性数量 s 建议不小于属性数的一半",
        ],
    },
    "MAWNB": {
        "needs_discrete_input": True,
        "notes": [
            "SPODE / RandomTree 基分类器要求离散输入",
            "训练集同时用于生成标签视图，存在标签泄露、易过拟合",
        ],
    },
    "EMAWNB": {
        "needs_discrete_input": True,
        "notes": [
            "MAWNB 的增强版，用交叉验证消除标签泄露并学习视图权重",
            "交叉验证折数不宜过小，否则缓解泄露的效果很差",
        ],
    },
    "CAVWNB": {
        "needs_discrete_input": True,
        "notes": [
            "按类×属性值加权，负条件对数似然 + L2 正则",
            "正则系数 λ 不能设为 0，否则权重爆炸过拟合",
        ],
    },
    "DIWNB": {
        "notes": [
            "用一组 KNN 基分类器生成标签/概率视图后做实例加权",
            "原生支持连续特征；复现论文结果时数据集会先做全局离散",
        ],
    },
}

_FALLBACK_ALGORITHM_NOTE = "暂无该算法的补充适用性说明。"


def _field_type(field: dict[str, Any]) -> str:
    return str(field.get("type") or "").strip().lower()


def build_dataset_profile(dataset: Dataset, record_count: int | None = None) -> dict[str, Any]:
    """从已登记的 fields_schema 汇总数据集特征画像（只统计样本数，不解析原始文件）。"""
    fields_schema = getattr(dataset, "fields_schema", None) or []
    fields: list[dict[str, Any]] = []
    numeric = discrete = string = 0
    for raw in fields_schema:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        role = "label" if raw.get("role") == "label" else "feature"
        ftype = _field_type(raw)
        enum_values = raw.get("enum_values") or []
        samples = [str(v) for v in (raw.get("sample_values") or [])][:2]
        if role == "feature":
            if ftype in NUMERIC_FIELD_TYPES:
                numeric += 1
            elif ftype == "enum":
                discrete += 1
            else:
                string += 1
        fields.append(
            {
                "name": name,
                "role": role,
                "type": ftype or "unknown",
                "distinct_value_count": len(enum_values) if enum_values else None,
                "sample_values": samples,
            }
        )

    scenario = getattr(dataset, "scenario", None)
    scenario_code = getattr(scenario, "code", None)
    scenario_config = get_scenario_config(scenario_code)
    feature_count = numeric + discrete + string
    has_numeric = dataset_has_numeric_features(fields_schema)
    caveats: list[str] = []
    if string > 0:
        caveats.append(f"存在 {string} 个字符串型输入特征，训练前通常需要编码为枚举或数值类型")
    if not has_numeric and feature_count == 0:
        caveats.append("没有可用的输入特征（role=feature），当前无法训练")
    return {
        "logical_id": getattr(dataset, "logical_id", None),
        "name": dataset_display_name_of(dataset),
        "version": getattr(dataset, "version", None),
        "scenario": {
            "code": scenario_code,
            "name": getattr(scenario, "name", None)
            or scenario_config.get("scenario_name"),
            "analysis_goal": scenario_config.get("analysis_goal"),
        },
        "label_field": getattr(dataset, "label_field", None),
        "record_count": record_count,
        "field_count": len(fields),
        "feature_count": feature_count,
        "numeric_feature_count": numeric,
        "discrete_feature_count": discrete,
        "string_feature_count": string,
        "has_numeric_features": has_numeric,
        "caveats": caveats,
        "field_profile": fields,
    }


def _applicability(knowledge: dict[str, Any], has_numeric: bool) -> tuple[bool, str]:
    """确定性适用性筛选：返回 (是否适用, 理由)。"""
    if knowledge.get("requires_raw_numeric"):
        if has_numeric:
            return True, "数据集保留原始数值特征，符合该算法内部离散化对输入的要求，匹配度最高"
        return False, (
            "数据集不含数值特征（已全部离散），该算法的多套离散视图会退化为同一份输入，"
            "核心机制失效，不适合使用"
        )
    if knowledge.get("needs_discrete_input"):
        if has_numeric:
            return True, "基分类器要求离散输入，数值特征会由平台在训练前自动离散化"
        return True, "数据集本身已是离散属性，可直接满足该算法的输入要求"
    if has_numeric:
        return True, "算法原生支持连续与离散特征，与当前数据集兼容"
    return True, "数据集为离散属性，与当前数据集兼容"


def build_algorithm_catalog(db, has_numeric: bool) -> list[dict[str, Any]]:
    """已注册可用算法目录 + 面向本数据集的适用性结论。"""
    rows = db.scalars(
        select(Algorithm)
        .where(Algorithm.status == ALGORITHM_STATUS_AVAILABLE)
        .order_by(Algorithm.id)
    ).all()
    catalog: list[dict[str, Any]] = []
    for row in rows:
        knowledge = ALGORITHM_APPLICABILITY.get(row.code) or {}
        applicable, reason = _applicability(knowledge, has_numeric)
        public_params = [
            str(item.get("name"))
            for item in (row.param_schema or [])
            if isinstance(item, dict) and item.get("name")
        ]
        catalog.append(
            {
                "code": row.code,
                "name": row.display_name,
                "description": row.description,
                "applicable": applicable,
                "applicability_reason": reason,
                "notes": knowledge.get("notes") or [_FALLBACK_ALGORITHM_NOTE],
                "public_parameters": public_params,
            }
        )
    return catalog


def build_dataset_analysis_facts(db, dataset: Dataset) -> dict[str, Any]:
    # 样本数不在 dataset 行上，复用数据集服务的按 path+mtime 缓存统计。
    record_count = DatasetService(db)._count_records(dataset.file_path)
    profile = build_dataset_profile(dataset, record_count=record_count)
    return {
        "contract_version": DATASET_ANALYSIS_VERSION,
        "analysis_type": "dataset_algorithm_fit",
        "dataset": profile,
        "algorithms": build_algorithm_catalog(db, bool(profile["has_numeric_features"])),
    }


def fallback_dataset_analysis(facts: dict[str, Any]) -> str:
    """规则模板降级：按确定性适用性结论直接给出推荐，不依赖 AI。"""
    dataset = facts.get("dataset") or {}
    algorithms = facts.get("algorithms") or []
    suitable = [a for a in algorithms if a.get("applicable")]
    unsuitable = [a for a in algorithms if not a.get("applicable")]
    scenario = dataset.get("scenario") or {}
    lines = [
        "### 数据集特征概览",
        f"- 数据集：{dataset.get('name')}（{dataset.get('logical_id')}，版本 {dataset.get('version')}）",
        f"- 所属场景：{scenario.get('name') or '未指定'}",
        (
            f"- 规模：{dataset.get('record_count')} 条样本 / {dataset.get('field_count')} 个字段"
            f"（输入特征 {dataset.get('feature_count')} 个，分类标签 {dataset.get('label_field')}）"
        ),
        (
            f"- 特征形态：数值 {dataset.get('numeric_feature_count')} 个、"
            f"离散 {dataset.get('discrete_feature_count')} 个、"
            f"字符串 {dataset.get('string_feature_count')} 个"
        ),
        "",
        "### 推荐算法",
    ]
    if suitable:
        for index, item in enumerate(suitable, start=1):
            lines.append(
                f"{index}. **{item.get('name')}（{item.get('code')}）**：{item.get('applicability_reason')}"
            )
    else:
        lines.append("当前数据集没有匹配的可用算法，请检查字段结构或标签设置。")
    if unsuitable:
        lines.extend(["", "### 不适用算法"])
        for item in unsuitable:
            lines.append(
                f"- **{item.get('name')}（{item.get('code')}）**：{item.get('applicability_reason')}"
            )
    lines.extend(
        [
            "",
            "### 选择建议",
            "以上为基于数据集字段形态的规则判断；配置 AI 服务后可获得更细的取舍说明与参数提示。",
            "",
            "### 注意事项",
        ]
    )
    for caveat in dataset.get("caveats") or []:
        lines.append(f"- {caveat}")
    lines.append("该结论只依据数据集的字段结构推断，不代表实际训练效果，仍需训练后结合评估指标验证。")
    return "\n".join(lines)


def build_dataset_analysis_prompt(facts: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "你是数据集与算法的匹配分析助手。只能使用用户消息中给出的事实，"
        "不得编造字段业务含义、算法能力、训练结果或数据分布。"
        "algorithms 里 applicable=false 的算法一律不得列入推荐。"
        "推荐排序只能依据 applicable、applicability_reason 与 notes。"
        "请输出 Markdown，固定包含：### 数据集特征概览、### 推荐算法、### 选择建议、### 注意事项。"
        "推荐算法用有序列表，每条写清算法名（编码）与推荐理由，理由必须来自给定事实。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(facts, ensure_ascii=False, sort_keys=True)},
    ]


class DatasetAnalysisService(ServiceBase):
    """数据集算法适配解析（登录用户可读，与数据集可见性一致）。"""

    def _authorized_dataset(self, current_user, dataset_id: int) -> Dataset:
        self.require_login(current_user)
        dataset = self.db.get(Dataset, dataset_id)
        if dataset is None:
            raise ServiceError(404, "数据集不存在")
        # 复用集中式可见性规则，避免两处口径漂移。
        if not self.authz.can_view_dataset(current_user, dataset):
            raise ServiceError(403, "无权限操作")
        return dataset

    @staticmethod
    def _cached(dataset: Dataset) -> dict[str, Any]:
        artifact = (getattr(dataset, "ai_analysis", None) or {}).get("latest")
        return artifact if isinstance(artifact, dict) else {}

    @staticmethod
    def _is_current(artifact: dict[str, Any], facts: dict[str, Any]) -> bool:
        """缓存只在事实未变时有效：字段结构或算法目录变了就重新生成。"""
        return bool(artifact.get("markdown")) and artifact.get("facts_snapshot") == facts

    def _save(
        self,
        dataset: Dataset,
        markdown: str,
        source: str,
        facts: dict[str, Any],
        ai_model: str | None = None,
    ) -> None:
        """整块 JSONB 读改写：先锁行再回写，避免并发解析互相覆盖。"""
        self.db.refresh(dataset, with_for_update=True)
        payload = dict(getattr(dataset, "ai_analysis", None) or {})
        payload["latest"] = {
            "available": True,
            "markdown": markdown[:100_000],
            "source": source if source in {"ai", "fallback"} else "fallback",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": ai_model,
            "prompt_version": DATASET_ANALYSIS_PROMPT_VERSION,
            "facts_snapshot": facts,
        }
        dataset.ai_analysis = payload
        self.commit()

    @service_call
    def check_access(self, current_user, dataset_id: int):
        """流式接口的前置鉴权：失败时以普通响应返回，便于前端拿到正确的 HTTP 状态。"""
        dataset = self._authorized_dataset(current_user, dataset_id)
        return ok(
            data={
                "dataset_id": dataset.id,
                "name": dataset_display_name_of(dataset),
                "prompt_version": DATASET_ANALYSIS_PROMPT_VERSION,
            }
        )

    @service_call
    def get_analysis(self, current_user, dataset_id: int):
        """读取已保存的解析结果；没有则 available=false（前端据此显示空状态）。"""
        dataset = self._authorized_dataset(current_user, dataset_id)
        artifact = self._cached(dataset)
        markdown = artifact.get("markdown")
        return ok(
            data={
                "dataset_id": dataset.id,
                "name": dataset_display_name_of(dataset),
                "available": bool(markdown),
                "markdown": markdown or None,
                "source": artifact.get("source"),
                "generated_at": artifact.get("generated_at"),
            }
        )

    def stream(
        self, current_user, dataset_id: int, regenerate: bool = False
    ) -> Iterable[tuple[str, dict[str, Any]]]:
        """产出 SSE 事件：start → (reasoning | delta)* → done，error 表示已降级。"""
        dataset = self._authorized_dataset(current_user, dataset_id)
        facts = build_dataset_analysis_facts(self.db, dataset)
        yield "start", {"status": "开始解析数据集"}
        cached = self._cached(dataset)
        # 事实未变且未要求重算时直接下发缓存，不再调用 AI。
        if not regenerate and self._is_current(cached, facts):
            for chunk in _chunk_text(str(cached["markdown"])):
                yield "delta", {"content": chunk}
            yield "done", {"status": "已读取已保存的解析结果", "source": "cached"}
            return
        setting = self.db.get(UserAISetting, current_user.id)
        if setting is None or not setting.enabled:
            markdown = fallback_dataset_analysis(facts)
            self._save(dataset, markdown, "fallback", facts)
            yield "error", {"message": "当前账号未配置可用的 AI 服务", "reason_code": "not_configured"}
            for chunk in _chunk_text(markdown):
                yield "delta", {"content": chunk}
            yield "done", {"status": "已使用规则模板完成解析", "source": "fallback"}
            return
        try:
            parts: list[str] = []
            for kind, text in _openai_stream(setting, build_dataset_analysis_prompt(facts)):
                if kind == "reasoning":
                    # 思维链只用于前端「正在生成」的反馈，不并入正文。
                    yield "reasoning", {"content": text}
                    continue
                parts.append(text)
                yield "delta", {"content": text}
            markdown = "".join(parts).strip()
            if not markdown:
                raise RuntimeError("empty AI response")
            self._save(dataset, markdown, "ai", facts, ai_model=getattr(setting, "model", None))
            yield "done", {"status": "数据集解析完成", "source": "ai"}
        except Exception as exc:  # noqa: BLE001
            reason_code, reason_message = _classify_ai_error(exc)
            logger.warning(
                "dataset analysis fell back to rules dataset_id=%s model=%s reason=%s",
                dataset_id,
                getattr(setting, "model", None),
                reason_code,
                exc_info=(reason_code == "provider_error"),
            )
            markdown = fallback_dataset_analysis(facts)
            self._save(dataset, markdown, "fallback", facts, ai_model=getattr(setting, "model", None))
            yield "error", {
                "message": f"AI 解析未完成，已回退规则模板：{reason_message}",
                "reason_code": reason_code,
            }
            for chunk in _chunk_text(markdown):
                yield "delta", {"content": chunk}
            yield "done", {"status": "已使用规则模板完成解析", "source": "fallback"}
