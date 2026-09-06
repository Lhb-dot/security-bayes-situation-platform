"""report_nl.py — 态势报告自然语言生成（6.10.4：规则+场景模板，LLM 仅 P2 可选润色）。

输入统一为 report_data dict（由 report_service._build_report_data 生成），关键键：
- report_info：报告期 / 数据范围 / 场景 / 涉及算法
- overview：态势概况（推理总量、风险/正常占比、风险等级、平均风险概率、变化方向）
- prediction：预测标签分布、类别概率、风险概率区间、低置信度样本数
- model_analysis：逐模型的多视图预测与一致性
- feature_analysis：特征加权条件概率（Top-K + 全量）
- trend / key_events：风险趋势与重点事件

规则（6.10.4）：
1. 每条关键分析必须引用对应数值，不输出无依据的通用文本；
2. 风险规避指导按场景（network_security / power_system / geological_risk /
   flightdeck_operation）给出对应建议，含优先级、触发概率/特征、动作、人工复核项；
3. 样本不足、概率接近阈值、视图分歧、解释缺失时说明不确定性；
4. LLM（本地 vLLM）仅作为 P2 可选润色，失败/不可达一律回退模板原文。
"""
from __future__ import annotations

import os

import requests

from app.config import DEEPSEEK_CONFIG
from app.utils.common import get_logger

logger = get_logger("report_nl")

LLM_TIMEOUT = float(os.getenv("REPORT_LLM_TIMEOUT", "15"))


def _pct(value) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def build_analysis_nl(report_data: dict) -> str:
    """自然语言态势分析（6.10.4 第 2 条：逐项引用真实数值）。"""
    info = report_data.get("report_info") or {}
    ov = report_data.get("overview") or {}
    pred = report_data.get("prediction") or {}
    feats = (report_data.get("feature_analysis") or {}).get("top_features") or []
    models = report_data.get("model_analysis") or []
    key_events = report_data.get("key_events") or []

    sentences = []

    sentences.append(
        f"本报告覆盖{info.get('data_scope', '')}，报告期{info.get('report_period') or '—'}，"
        f"涉及推理记录 {ov.get('total_inferences', 0)} 条。"
    )

    total = ov.get("total_inferences", 0)
    risk = ov.get("risk_count", 0)
    if total == 0:
        sentences.append("报告期内无推理记录，暂无法评估风险态势。")
    else:
        if ov.get("high_count", 0) > 0:
            level = "较高"
        elif ov.get("medium_count", 0) > 0:
            level = "中等"
        else:
            level = "较低"
        sentences.append(
            f"整体风险水平{level}：{total} 条推理中判定为风险 {risk} 条（占比 {_pct(ov.get('risk_ratio'))}），"
            f"其中高危 {ov.get('high_count', 0)} 起、中危 {ov.get('medium_count', 0)} 起、低危 {ov.get('low_count', 0)} 起，"
            f"风险变化方向为{ov.get('risk_trend', '无法判断')}。"
        )

    if ov.get("avg_risk_prob") is not None:
        sentences.append(f"平均风险概率为 {ov['avg_risk_prob']:.3f}。")

    buckets = pred.get("risk_prob_buckets") or []
    if buckets:
        main = max(buckets, key=lambda b: b.get("count", 0))
        if main.get("count", 0) > 0:
            sentences.append(f"风险概率主要分布在 {main['range']} 区间（{main['count']} 条）。")

    if pred.get("low_confidence_count", 0) > 0:
        sentences.append(
            f"存在 {pred['low_confidence_count']} 条低置信度/接近阈值的样本，建议人工复核。"
        )

    disagree = []
    for m in models:
        if not m.get("has_views"):
            continue
        for v in m.get("views", []):
            if not v.get("consistent_with_final"):
                disagree.append(f"{m['algorithm_name'] or m['algorithm_code']} 的 {v['name']}")
    if disagree:
        sentences.append("以下视图与最终预测存在分歧：" + "、".join(disagree) + "，建议人工复核。")
    else:
        has_views_models = [m for m in models if m.get("has_views")]
        if has_views_models:
            sentences.append("各模型的多视图预测与最终预测整体一致。")

    if feats:
        top_txt = "、".join(
            f"「{f['attribute']}={f['value']}」（{f['support_direction']}）" for f in feats[:5]
        )
        sentences.append(f"对风险判断贡献较大的特征依次为：{top_txt}。")

    if key_events:
        top = key_events[0]
        sentences.append(
            f"报告期内重点风险事件 {len(key_events)} 起，等级最高为[{top.get('risk_level')}]"
            f"（概率 {top.get('probability')}）。"
        )

    return "".join(sentences)


def build_guidance_nl(report_data: dict) -> str:
    """风险规避指导（6.10.4 第 4/5/6 条：按场景 + 优先级 + 人工复核 + 不确定性）。"""
    info = report_data.get("report_info") or {}
    ov = report_data.get("overview") or {}
    pred = report_data.get("prediction") or {}
    feats = (report_data.get("feature_analysis") or {}).get("top_features") or []
    scenario = info.get("scenario_code") or info.get("scenario_name") or ""

    lines = []

    scenario_advice = {
        "network_security": "对异常端口、协议、主机与流量日志进行核查，必要时隔离可疑主机、封禁异常端口并加强边界防护。",
        "power_system": "对受影响设备与 PMU/SCADA 数据进行核验，安排巡检并核查保护装置与告警联动。",
        "geological_risk": "对重点区域开展现场核查，加强降雨量、位移与地下水位监测，做好避险转移准备。",
        "flightdeck_operation": "复核双机间距、接近率与方向角，必要时调整调度顺序与避让航线。",
    }
    matched = next((adv for key, adv in scenario_advice.items() if key in scenario), None)
    lines.append(f"1. 【场景处置建议】{matched or '结合本场景风险类型对高风险样本进行专项核查与处置。'}")

    idx = 2
    if ov.get("high_count", 0) > 0:
        lines.append(f"{idx}. 【高优先级】存在 {ov['high_count']} 起高危事件，建议立即处置，并由专人复核后闭环。")
        idx += 1
    if ov.get("medium_count", 0) > 0:
        lines.append(f"{idx}. 【中优先级】存在 {ov['medium_count']} 起中危事件，建议 24 小时内复核，防止升级。")
        idx += 1
    if ov.get("low_count", 0) > 0:
        lines.append(f"{idx}. 【低优先级】存在 {ov['low_count']} 起低危事件，纳入例行观察。")
        idx += 1

    for f in feats[:3]:
        lines.append(
            f"{idx}. 【特征核查】关键特征「{f['attribute']}={f['value']}」（{f['support_direction']}），"
            f"建议加强该维度监控并复核相关阈值配置。"
        )
        idx += 1

    manual = []
    if ov.get("risk_trend") == "样本不足，无法判断":
        manual.append("样本量不足，建议补充数据后再评估风险变化方向")
    if pred.get("low_confidence_count", 0) > 0:
        manual.append("存在低置信度/接近阈值样本需人工复核")
    view_disagree = any(
        any(not v.get("consistent_with_final") for v in m.get("views", []))
        for m in report_data.get("model_analysis", [])
        if m.get("has_views")
    )
    if view_disagree:
        manual.append("多视图预测存在分歧，建议人工复核")
    no_explain = all(not m.get("has_views") for m in report_data.get("model_analysis", []))
    if no_explain and report_data.get("model_analysis"):
        manual.append("算法解释数据缺失，结论适用边界受限")
    if manual:
        lines.append(f"{idx}. 【人工复核】以下事项需人工确认：" + "；".join(manual) + "。")
        idx += 1

    lines.append(
        f"{idx}. 本报告仅提供辅助研判与规避指导，不直接执行封禁、停机、撤离或调度等业务操作。"
    )
    return "\n".join(lines)


def polish_with_llm(text: str) -> str:
    """用本地 vLLM 对模板文本做措辞润色（P2 可选）；失败时回退返回原文。"""
    if not text or not text.strip():
        return text
    try:
        url = DEEPSEEK_CONFIG.get("api_url")
        model = DEEPSEEK_CONFIG.get("model")
        if not url or not model:
            return text
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是安全态势报告润色助手。只润色措辞、使表达更专业流畅，"
                        "不得增删或改动任何事实数字与结论，直接输出润色后的文本。"
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,
            "max_tokens": int(DEEPSEEK_CONFIG.get("max_tokens", 1024)),
        }
        resp = requests.post(url, json=payload, timeout=LLM_TIMEOUT)
        resp.raise_for_status()
        content = (resp.json().get("choices") or [{}])[0].get("message", {}).get("content", "")
        if content and content.strip():
            return content.strip()
    except Exception as exc:  # noqa: BLE001 连接失败/超时/模型未加载等一律回退模板
        logger.warning("LLM 润色失败，回退模板文本：%s", exc)
    return text


def generate_report_narrative(report_data: dict) -> dict:
    """生成并润色态势分析 + 风险规避指导，返回 {analysis_nl, guidance_nl}。"""
    analysis = polish_with_llm(build_analysis_nl(report_data))
    guidance = polish_with_llm(build_guidance_nl(report_data))
    return {"analysis_nl": analysis, "guidance_nl": guidance}
