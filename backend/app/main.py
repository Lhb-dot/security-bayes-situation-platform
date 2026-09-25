"""Application bootstrap for the security situation platform."""

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

# Support both ``python app/main.py`` and ``python -m app.main`` from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.legacy_model_routes import router as legacy_model_router
from app.api.v1 import api_router
from app.paths import BACKEND_ROOT, PROJECT_ROOT


logger = logging.getLogger(__name__)

WEB_ROOT = PROJECT_ROOT / "frontend"
DIST_ROOT = WEB_ROOT / "dist"
SITE_ROOT = DIST_ROOT if (DIST_ROOT / "index.html").exists() else WEB_ROOT


class SPAStaticFiles(StaticFiles):
    """Static files plus an SPA fallback for client-side routes.

    ``StaticFiles(html=True)`` only serves ``index.html`` for *directory*
    requests (``/``). A deep link such as ``/reports`` is neither a file nor a
    directory, so it 404s — which is why the frontend historically ran in hash
    mode. Now that vue-router uses history mode, the shell must answer those
    paths and let the router resolve them.

    Two exclusions keep genuine 404s intact:
    * ``/api/`` — an unknown endpoint must stay a JSON 404, never become HTML.
    * last path segment containing ``.`` — a missing asset must stay 404.
    """

    def __init__(self, *, api_prefixes: tuple[str, ...] = ("/api/",), **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._api_prefixes = api_prefixes

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # Starlette's HTTPException, not FastAPI's — the latter subclasses it,
            # so catching the FastAPI one here would never fire.
            if exc.status_code != 404:
                raise
            if scope.get("path", "").startswith(self._api_prefixes):
                raise
            if "." in path.rsplit("/", 1)[-1]:
                raise
            return await super().get_response("index.html", scope)


def _warm_dataset_caches_async() -> None:
    """Warm ARFF caches after startup without delaying the first response."""
    if os.getenv("WARM_DATASET_CACHES", "1") != "1" or "pytest" in sys.modules:
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
    """Start the background scheduler that refreshes due scheduled reports."""
    from app.services.report_scheduler import start

    start()


def _start_training_runner() -> None:
    """Start the background runner that executes submitted training jobs."""
    from app.services.training_runner import start

    start()


def _start_batch_inference_runner() -> None:
    """Start the background runner that executes submitted batch inference jobs."""
    from app.services.batch_inference_runner import start

    start()


def _start_export_job_runner() -> None:
    """Start the background runner that renders submitted report export jobs."""
    from app.services.export_job_service import start

    start()


def _start_report_generate_runner() -> None:
    """Start the background runner that generates submitted reports."""
    from app.services.report_generate_runner import start

    start()


def create_app() -> FastAPI:
    """Create the HTTP application and register routes in one place."""
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    app.include_router(legacy_model_router)
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
