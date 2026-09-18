"""Unified streaming explanation API."""
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.explanation import ExplanationStreamRequest
from app.services.explanation_service import (
    build_explanation_facts,
    get_scenario_config,
    stream_explanation,
)
from app.services.inference_record_service import InferenceRecordService

router = APIRouter(tags=["模型解释"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/inference/explanation/stream", summary="流式生成模型结果解释")
def stream_model_explanation(
    payload: ExplanationStreamRequest,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    if payload.inference_record_id is not None:
        source_response = InferenceRecordService(db).get_explanation_source(
            current_user=current_user,
            record_id=payload.inference_record_id,
        )
        if source_response.code != 0:
            return unwrap(source_response)
        explanation = source_response.data
    else:
        scenario_code = (payload.scenario or {}).get("scenario_code") or (payload.scenario or {}).get("code")
        scenario = get_scenario_config(scenario_code)
        explanation = {
            "scenario": scenario,
            "sample": payload.sample,
            "model_result": payload.model_result,
            "algorithm_details": payload.algorithm_details,
            "recommended_actions": scenario.get("recommended_actions") or [],
        }
    facts = build_explanation_facts(explanation)

    def generate():
        markdown_parts = []
        source = "fallback"
        done_data = None
        for event, data in stream_explanation(db, current_user, explanation):
            if event == "delta":
                markdown_parts.append(str(data.get("content") or ""))
            elif event == "done":
                done_data = data
                source = str(data.get("source") or source)
                continue
            yield _sse(event, data)
        if payload.inference_record_id is not None and markdown_parts:
            save_response = InferenceRecordService(db).save_generated_explanation(
                current_user=current_user,
                record_id=payload.inference_record_id,
                markdown="".join(markdown_parts),
                source=source,
                data_snapshot=facts,
            )
            if save_response.code != 0:
                yield _sse("error", {"message": "解释文本未能保存到推理记录"})
        if done_data is not None:
            yield _sse("done", done_data)

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })
