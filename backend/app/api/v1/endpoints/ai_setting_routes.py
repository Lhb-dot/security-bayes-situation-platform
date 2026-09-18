"""User-bound AI provider settings. Raw keys never leave the backend."""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.ai_setting import AISettingUpdate
from app.services.explanation_service import AISettingService

router = APIRouter(prefix="/settings/ai", tags=["AI 设置"])


@router.get("", summary="读取当前用户 AI 设置（API key 仅返回掩码）")
def get_ai_setting(current_user: AppUser = Depends(get_current_user), db=Depends(get_db)):
    return unwrap(AISettingService(db).get(current_user))


@router.put("", summary="保存当前用户 OpenAI 兼容 AI 设置")
def update_ai_setting(
    payload: AISettingUpdate,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return unwrap(AISettingService(db).update(current_user, payload.model_dump()))


@router.post("/test", summary="测试当前用户 AI 服务连通性")
def test_ai_setting(current_user: AppUser = Depends(get_current_user), db=Depends(get_db)):
    return unwrap(AISettingService(db).test_connection(current_user))
