"""API v1 路由注册入口（统一前缀 /api/v1）。

在 main.py 中引入（见任务说明）：
    from app.api.v1 import api_router
    app.include_router(api_router)

各端点路由文件位于 app/api/v1/endpoints/，使用相对前缀（如 /users），
由本文件统一挂载到 /api/v1 之下。
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    algorithm_routes,
    dataset_routes,
    inference_record_routes,
    model_version_routes,
    report_routes,
    risk_event_routes,
    risk_threshold_routes,
    scenario_routes,
    user_routes,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(user_routes.router)
api_router.include_router(scenario_routes.router)
api_router.include_router(dataset_routes.router)
api_router.include_router(algorithm_routes.router)
api_router.include_router(model_version_routes.router)
api_router.include_router(inference_record_routes.router)
api_router.include_router(risk_event_routes.router)
api_router.include_router(risk_threshold_routes.router)
api_router.include_router(report_routes.router)
