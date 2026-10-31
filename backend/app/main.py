"""安全态势平台的后端启动入口。"""

import logging
import os
import sys
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

# 兼容从 backend/ 目录直接跑 `python app/main.py` 和 `python -m app.main` 两种启动方式。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.v1 import api_router
from app.paths import PROJECT_ROOT


logger = logging.getLogger(__name__)

WEB_ROOT = PROJECT_ROOT / "frontend"
DIST_ROOT = WEB_ROOT / "dist"
SITE_ROOT = DIST_ROOT if (DIST_ROOT / "index.html").exists() else WEB_ROOT


class SPAStaticFiles(StaticFiles):
    """静态文件服务，外加一层 SPA 回退。

    StaticFiles(html=True) 只在请求目录（/）时返回 index.html；像 /reports
    这种深链既不是文件也不是目录，直接 404——前端早年就是因为这个才用 hash
    模式。vue-router 改成 history 模式之后，这些路径得由这里返回外壳，
    交给前端路由自己解析。

    两个例外保证真正的 404 不被吞掉：
    - /api/ 开头的路径：未知接口必须继续返回 JSON 404，不能变成 HTML。
    - 末段带 . 的路径：缺失的静态资源仍然 404。
    """

    def __init__(self, *, api_prefixes: tuple[str, ...] = ("/api/",), **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._api_prefixes = api_prefixes

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # 这里要的是 Starlette 的 HTTPException，不是 FastAPI 的 —— 后者是它的子类，
            # 只捕 FastAPI 那个的话，这里永远不会命中。
            if exc.status_code != 404:
                raise
            if scope.get("path", "").startswith(self._api_prefixes):
                raise
            if "." in path.rsplit("/", 1)[-1]:
                raise
            return await super().get_response("index.html", scope)


def _warm_dataset_caches_async() -> None:
    """启动后在后台预热 ARFF 缓存，不拖慢第一个请求。"""
    # 测试进程不预热：`running_under_test_runner()` 覆盖 `python -m unittest`
    # （`"pytest" in sys.modules` 覆盖不到它），与其余 5 个 runner 的判定口径一致。
    from app.utils.common import running_under_test_runner

    if (
        os.getenv("WARM_DATASET_CACHES", "1") != "1"
        or "pytest" in sys.modules
        or running_under_test_runner()
    ):
        return

    def warm() -> None:
        from app.db import SessionLocal
        from app.services.dashboard_service import warm_dataset_caches

        db = SessionLocal()
        try:
            stats = warm_dataset_caches(db)
            logger.info(
                "数据集缓存预热完成: %s/%s 份, 跳过 %s 份, 耗时 %sms, 行缓存 %.1f MB",
                stats["warmed"],
                stats["total"],
                stats["skipped"],
                stats["elapsed_ms"],
                stats["row_cache_bytes"] / 1024 / 1024,
            )
        except Exception:  # noqa: BLE001 - cache warmup must not block startup
            logger.exception("数据集缓存预热失败（不影响服务）")
        finally:
            db.close()

    threading.Thread(target=warm, name="dataset-cache-warmup", daemon=True).start()


def _start_report_scheduler() -> None:
    """拉起定时报告的后台调度线程。"""
    from app.services.report_scheduler import start

    start()


def _start_training_runner() -> None:
    """拉起训练任务的后台执行线程。"""
    from app.services.training_runner import start

    start()


def _start_batch_inference_runner() -> None:
    """拉起批量推理任务的后台执行线程。"""
    from app.services.batch_inference_runner import start

    start()


def _start_export_job_runner() -> None:
    """拉起报告导出任务的后台执行线程。"""
    from app.services.export_job_service import start

    start()


def _start_report_generate_runner() -> None:
    """拉起报告生成任务的后台执行线程。"""
    from app.services.report_generate_runner import start

    start()


def create_app() -> FastAPI:
    """建 HTTP 应用，路由统一在这里注册。"""
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    _warm_dataset_caches_async()
    _start_report_scheduler()
    _start_training_runner()
    _start_batch_inference_runner()
    _start_export_job_runner()
    _start_report_generate_runner()
    app.mount("/", SPAStaticFiles(directory=str(SITE_ROOT), html=True), name="web")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=12312)
