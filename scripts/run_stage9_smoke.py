"""Run the real API explanation smoke flow against a running local stack.

The script is intentionally opt-in for the AI settings write. Without
``--configure-mock`` it uses the account's existing AI setting. It never starts
or stops Docker, Java, or FastAPI processes.

Example:
    python scripts/run_stage9_smoke.py --configure-mock
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests


def _api(session: requests.Session, base_url: str, method: str, path: str, **kwargs: Any) -> Any:
    response = session.request(method, f"{base_url}{path}", timeout=kwargs.pop("timeout", 30), **kwargs)
    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{method} {path} 返回非 JSON（HTTP {response.status_code}）") from exc
    if response.status_code >= 400 or body.get("code") != 0:
        message = body.get("message") or body.get("detail") or f"HTTP {response.status_code}"
        raise RuntimeError(f"{method} {path} 失败: {message}")
    return body.get("data")


def _sample_value(field: dict[str, Any]) -> Any:
    samples = field.get("sample_values") or []
    if samples:
        value = samples[0]
    else:
        enum_values = field.get("enum_values") or []
        value = enum_values[0] if enum_values else "0"
    field_type = str(field.get("type") or "").lower()
    if field_type == "numeric":
        try:
            number = float(value)
            return int(number) if number.is_integer() else number
        except (TypeError, ValueError):
            return 0
    return value


def _build_features(fields_schema: list[dict[str, Any]]) -> dict[str, Any]:
    features = {}
    for field in fields_schema:
        if field.get("role") != "label":
            features[str(field["name"])] = _sample_value(field)
    if not features:
        raise RuntimeError("数据集没有可用于推理的 feature 字段")
    return features


def _consume_sse(response: requests.Response) -> tuple[list[str], dict[str, Any]]:
    events: list[str] = []
    done: dict[str, Any] = {}
    event_name: str | None = None
    data_line: str | None = None
    for raw_line in response.iter_lines(decode_unicode=True):
        line = raw_line if isinstance(raw_line, str) else raw_line.decode("utf-8", "replace")
        if not line:
            if event_name and data_line:
                payload = json.loads(data_line)
                events.append(event_name)
                if event_name == "done":
                    done = payload
            event_name = None
            data_line = None
        elif line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_line = line.split(":", 1)[1].strip()
    if event_name and data_line:
        events.append(event_name)
        if event_name == "done":
            done = json.loads(data_line)
    return events, done


def main() -> int:
    parser = argparse.ArgumentParser(description="Run stage 9 API/SSE explanation smoke test")
    parser.add_argument("--base-url", default=os.getenv("SMOKE_API_BASE_URL", "http://127.0.0.1:12312"))
    parser.add_argument("--username", default=os.getenv("SMOKE_USERNAME", "alice"))
    parser.add_argument("--password", default=os.getenv("SMOKE_PASSWORD", "alice123"))
    parser.add_argument("--mock-base-url", default=os.getenv("SMOKE_MOCK_AI_URL", "http://127.0.0.1:8765/v1"))
    parser.add_argument("--configure-mock", action="store_true", help="write the current account's AI setting to the local Mock")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    session = requests.Session()
    login = _api(session, base_url, "POST", "/api/v1/auth/login", json={"username": args.username, "password": args.password})
    csrf = login.get("csrf_token") if isinstance(login, dict) else None
    if not csrf:
        csrf = session.cookies.get("bayes_csrf")
    if not csrf:
        raise RuntimeError("登录成功但没有获得 CSRF token")
    headers = {"X-CSRF-Token": csrf}
    print(f"登录成功: {args.username}")

    if args.configure_mock:
        _api(
            session,
            base_url,
            "PUT",
            "/api/v1/settings/ai",
            headers=headers,
            json={
                "provider": "openai-compatible",
                "base_url": args.mock_base_url.rstrip("/"),
                "model": "mock-model",
                "api_key": "local-smoke-key",
                "enabled": True,
            },
        )
        print(f"AI 配置已切换到 Mock: {args.mock_base_url}")

    models = _api(session, base_url, "GET", "/api/v1/model-versions?page=1&page_size=200")
    items = models.get("items", []) if isinstance(models, dict) else []
    published = [item for item in items if item.get("status") == "PUBLISHED"]
    if not published:
        raise RuntimeError("当前账号没有可用的 PUBLISHED 模型")
    model = published[0]
    model_id = model.get("model_version_id") or model.get("id")
    dataset_id = model.get("dataset_id")
    if not model_id or not dataset_id:
        raise RuntimeError("模型列表缺少 model_version_id 或 dataset_id")
    print(f"选择模型: model={model_id}, algorithm={model.get('algorithm_code')}, dataset={dataset_id}")

    dataset = _api(session, base_url, "GET", f"/api/v1/datasets/{dataset_id}")
    fields_schema = dataset.get("fields_schema") or []
    features = _build_features(fields_schema)
    print(f"生成合法输入: {len(features)} 个 feature 字段")

    prediction = _api(
        session,
        base_url,
        "POST",
        "/api/v1/inference-records/predict",
        headers=headers,
        json={"model_version_id": model_id, "input_features": features},
        timeout=120,
    )
    record_id = prediction.get("id")
    label = prediction.get("prediction_label")
    if not record_id or not label:
        raise RuntimeError("预测响应缺少记录 ID 或预测标签")
    explain_data = prediction.get("explain_data") or {}
    if explain_data.get("prediction_label") not in (None, label):
        raise RuntimeError("预测标签与解释快照不一致")
    print(f"预测完成: record={record_id}, label={label}, risk_score={prediction.get('risk_score')}")

    response = session.post(
        f"{base_url}/api/v1/inference/explanation/stream",
        headers={**headers, "Content-Type": "application/json"},
        json={"inference_record_id": record_id},
        stream=True,
        timeout=(10, 180),
    )
    if response.status_code >= 400:
        raise RuntimeError(f"SSE 请求失败: HTTP {response.status_code} {response.text[:200]}")
    events, done = _consume_sse(response)
    if "start" not in events or "delta" not in events or "done" not in events:
        raise RuntimeError(f"SSE 事件不完整: {events}")
    print(f"SSE 完成: events={events}, source={done.get('source')}")

    detail = _api(session, base_url, "GET", f"/api/v1/inference-records/{record_id}/explain")
    saved = detail.get("generated_explanation") or {}
    if not saved.get("available") or not saved.get("markdown"):
        raise RuntimeError("SSE 完成后没有读取到已保存解释文本")
    if args.configure_mock and saved.get("source") != "ai":
        raise RuntimeError(f"已配置 Mock 但解释来源不是 ai: {saved.get('source')}")
    print(f"历史复用成功: source={saved.get('source')}, markdown_chars={len(saved['markdown'])}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (requests.RequestException, RuntimeError) as exc:
        print(f"联调未通过: {exc}", file=sys.stderr)
        raise SystemExit(1)
