"""AI evaluation endpoints for model versions, independent of inference."""
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.schemas.model_evaluation import ModelEvaluationRequest
from app.services.base import ServiceError
from app.services.model_evaluation_service import ModelEvaluationService

router = APIRouter(prefix="/model-versions", tags=["模型评价"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/{model_id}/evaluation", summary="读取模型版本的角色化 AI 评价")
def get_model_evaluation(
    model_id: int,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return unwrap(ModelEvaluationService(db).get_evaluation(current_user, model_id))


@router.post("/{model_id}/evaluation/stream", summary="流式生成模型版本的角色化 AI 评价")
def stream_model_evaluation(
    model_id: int,
    payload: ModelEvaluationRequest,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    service = ModelEvaluationService(db)
    access = service.get_evaluation(current_user, model_id)
    if access.code != 0:
        return unwrap(access)
    try:
        evaluation_role = service.requested_role(current_user, payload.audience)
        if evaluation_role == "user" and access.data.get("status") != "PUBLISHED":
            return unwrap(ResponseModel(code=403, data=None, message="未发布模型不能生成普通用户评价"))
    except ServiceError as exc:
        return unwrap(ResponseModel(code=exc.code, data=None, message=exc.message))

    def generate():
        for event, data in service.stream(
            current_user, model_id, payload.regenerate, evaluation_role
        ):
            yield _sse(event, data)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
