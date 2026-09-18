"""Application bootstrap for the security situation platform."""

import logging
import os
import sys
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Support both ``python app/main.py`` and ``python -m app.main`` from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.legacy_model_routes import router as legacy_model_router
from app.api.v1 import api_router
from app.paths import BACKEND_ROOT, PROJECT_ROOT


logger = logging.getLogger(__name__)

WEB_ROOT = PROJECT_ROOT / "frontend"
DIST_ROOT = WEB_ROOT / "dist"
SITE_ROOT = DIST_ROOT if (DIST_ROOT / "index.html").exists() else WEB_ROOT


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
    app.mount("/", StaticFiles(directory=str(SITE_ROOT), html=True), name="web")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=12312)
