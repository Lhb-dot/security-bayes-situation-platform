"""Security Bayes Platform — FastAPI 应用入口。

整合：
- 统一 CORS 中间件
- 鉴权依赖（X-User-Id 请求头 → get_current_user）
- v2.0 API 路由（场景/数据集/算法/模型/推理/风险事件/阈值/报告/态势/处置记录/用户管理）
- PMWNB 贝叶斯模型接口（/api/model/*，兼容旧版前端）
- 静态文件服务（Vue 前端）

启动方式：
    python -m app.main
    uvicorn app.main:app --host 0.0.0.0 --port 12312
"""
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# 确保 backend/ 在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
root_logger = logging.getLogger()
root_logger.handlers.clear()
root_logger.setLevel(LOG_LEVEL)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(LOG_LEVEL)
stream_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
stream_handler.terminator = "\n"
root_logger.addHandler(stream_handler)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent     # backend/
PROJECT_ROOT = BASE_DIR.parent                         # security-bayes-platform/
OUTPUT_DIR = BASE_DIR / "storage" / "output"           # backend/storage/output/
WEB_DIR = PROJECT_ROOT / "frontend"                    # frontend/ at project root

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Security Bayes Platform API",
    description="多场景安全风险智能感知与预测平台",
    version="2.0.0",
)

# ---------------------------------------------------------------------------
# CORS — 允许 Vite dev server + 生产环境
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:12312",  # 生产静态文件同源
        "http://127.0.0.1:12312",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 注册 v2.0 API 路由（Service 层 CRUD）
# ---------------------------------------------------------------------------
from app.auth import router as auth_router
from app.api.users import router as users_router
from app.api.scenarios import router as scenarios_router
from app.api.datasets import router as datasets_router
from app.api.algorithms import router as algorithms_router
from app.api.models import router as models_router
from app.api.inference import router as inference_router
from app.api.risk_events import router as risk_events_router
from app.api.thresholds import router as thresholds_router
from app.api.reports import router as reports_router
from app.api.situation import router as situation_router
from app.api.handling_records import router as handling_records_router

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(scenarios_router)
app.include_router(datasets_router)
app.include_router(algorithms_router)
app.include_router(models_router)
app.include_router(inference_router)
app.include_router(risk_events_router)
app.include_router(thresholds_router)
app.include_router(reports_router)
app.include_router(situation_router)
app.include_router(handling_records_router)

# ---------------------------------------------------------------------------
# 兼容旧版 PMWNB 贝叶斯模型接口（/api/model/*）
# ---------------------------------------------------------------------------
import app.algorithms.pmwnb_demo as pmwnb_demo
from app.algorithms.pmwnb_demo import (
    save_threshold_sim, get_all_exp, del_exp_by_id, append_exp_record,
)
from app.services.model_sim import get_dataset_list, train_bayes_sim, infer_bayes_sim

# 全局训练状态管控（兼容旧版前端）
train_global_status = {
    "is_trained": False,
    "current_dataset": "",
    "model_path": "",
}


@app.get("/api/model/dataset-list", tags=["PMWNB 贝叶斯模型"])
async def get_ds():
    return {"code": 200, "data": get_dataset_list()}


@app.post("/api/model/save-threshold", tags=["PMWNB 贝叶斯模型"])
async def save_thr(high: float, mid: float, low: float):
    ok = save_threshold_sim(high, mid, low)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="阈值规则错误，必须满足 高>中>低")
    return {"code": 200, "msg": "全局告警阈值保存成功"}


@app.post("/api/model/train", tags=["PMWNB 贝叶斯模型"])
def api_train_bayes_model(dataset_name: str, algo_type: str = "", discrete_method: str = ""):
    global train_global_status
    train_result = train_bayes_sim(dataset_name, algo_type, discrete_method)
    train_global_status["is_trained"] = True
    train_global_status["current_dataset"] = dataset_name
    append_exp_record({
        "dataset_name": dataset_name,
        "algo_type": algo_type or "PMWNB",
        "discrete_method": discrete_method or "EWD+MDLP",
        "accuracy": train_result["accuracy"],
        "f1": train_result["f1"],
        "recall": train_result["recall"],
        "train_time_s": train_result["train_time_s"],
        "train_time": train_result["train_time_s"],
    })
    return {"code": 200, "msg": f"{dataset_name} PMWNB训练完成", "data": train_result}


@app.post("/api/model/infer", tags=["PMWNB 贝叶斯模型"])
def api_bayes_infer(flowLength: float, duration: float, accessFreq: float):
    global train_global_status
    if not train_global_status["is_trained"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="禁止预测：请先选择数据集执行模型训练")
    infer_result = infer_bayes_sim({"flowLength": flowLength, "duration": duration, "accessFreq": accessFreq})
    return {"code": 200, "msg": "AI研判完成", "data": infer_result}


@app.get("/api/model/exp-records", tags=["PMWNB 贝叶斯模型"])
async def get_exp():
    return {"code": 200, "data": get_all_exp()}


@app.delete("/api/model/exp/{record_id}", tags=["PMWNB 贝叶斯模型"])
async def del_exp(record_id: int):
    del_exp_by_id(record_id)
    return {"code": 200, "msg": "实验记录删除完成"}


@app.get("/api/model/risk_statistics", tags=["PMWNB 贝叶斯模型"])
def get_bayes_risk_stat():
    """大屏贝叶斯批量统计接口（兼容旧版前端）。"""
    return {
        "topSourceIps": [
            {"name": "110.25.33.12", "score": 96},
            {"name": "45.89.12.56", "score": 88},
            {"name": "192.168.1.33", "score": 84},
        ],
        "attackTrend": [
            {"label": "00点", "value": 8, "blocked": 3, "sources": 2, "primaryType": "暴力破解"},
            {"label": "02点", "value": 15, "blocked": 6, "sources": 4, "primaryType": "DDoS攻击"},
        ],
        "attackTypes": [
            {"label": "暴力破解", "value": 35, "color": "#ff7b72"},
            {"label": "DDoS攻击", "value": 45, "color": "#5ba6ff"},
            {"label": "异常访问", "value": 20, "color": "#53e5c8"},
        ],
        "sourceMap": {
            "china": {
                "points": [
                    {"label": "北京", "x": 12, "y": -14, "value": "44次", "delay": 0.6},
                    {"label": "上海", "x": 12, "y": -12, "value": "38次", "delay": 1.2},
                ]
            }
        },
        "model_metric": {"accuracy": 0.86, "f1": 0.84, "recall": 0.82},
    }


# ---------------------------------------------------------------------------
# 静态资源
# ---------------------------------------------------------------------------
@app.get("/china-map.json", include_in_schema=False)
async def get_map_json():
    map_file = OUTPUT_DIR / "china-map.json"
    if not map_file.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="地图数据文件缺失")
    return FileResponse(map_file, media_type="application/json")


# ---------------------------------------------------------------------------
# 挂载前端静态文件（必须在所有 API 路由之后）
# ---------------------------------------------------------------------------
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

# ---------------------------------------------------------------------------
# 启动事件：首次启动自动建表 + 种子数据
# ---------------------------------------------------------------------------
@app.on_event("startup")
def seed_default_data():
    """首次启动自动建表（SQLite）并写入种子数据。

    - 默认管理员: admin / admin123
    - 4 个场景: network_security / power_system / geological_risk / flightdeck_operation
    - 5 个算法: A2WNB / MAWNB / EMAWNB / DIWNB / PMWNB
    """

    from app.db import Base, engine, SessionLocal
    from app.models.app_user import AppUser
    from app.models.scenario import Scenario
    from app.models.algorithm import Algorithm
    from app.utils.common import hash_password

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        from sqlalchemy import select

        # ── 种子：管理员账号 ──
        if db.scalar(select(AppUser).where(AppUser.username == "admin")) is None:
            now = datetime.now(timezone.utc)
            db.add(AppUser(
                username="admin",
                password_hash=hash_password("admin123"),
                role="ADMIN",
                status="ENABLED",
                created_at=now,
                updated_at=now,
            ))
            db.commit()
            logger.info("已创建默认管理员账号: admin / admin123")

        # ── 种子：4 个场景 ──
        if db.scalar(select(Scenario).limit(1)) is None:
            now = datetime.now(timezone.utc)
            db.add_all([
                Scenario(code="network_security", name="网络安全态势",
                         description="网络入侵流量分类", access_status="ACTUAL",
                         created_at=now, updated_at=now),
                Scenario(code="power_system", name="电力系统态势",
                         description="电力停电风险", access_status="ACTUAL",
                         created_at=now, updated_at=now),
                Scenario(code="geological_risk", name="地质风险态势",
                         description="滑坡易发性地质风险分类", access_status="ACTUAL",
                         created_at=now, updated_at=now),
                Scenario(code="flightdeck_operation", name="舰面调度态势",
                         description="航母舰面调度风险", access_status="ACTUAL",
                         created_at=now, updated_at=now),
            ])
            db.commit()
            logger.info("已写入 4 个场景种子数据")

        # ── 种子：5 个算法 ──
        if db.scalar(select(Algorithm).limit(1)) is None:
            now = datetime.now(timezone.utc)
            codes = ["A2WNB", "MAWNB", "EMAWNB", "DIWNB", "PMWNB"]
            db.add_all([
                Algorithm(
                    code=c,
                    display_name="PMWNB 矩阵加权贝叶斯" if c == "PMWNB" else "矩阵加权贝叶斯系",
                    description="当前项目已接入算法" if c == "PMWNB" else "矩阵加权贝叶斯系",
                    param_schema=[],
                    status="AVAILABLE",
                    created_at=now,
                ) for c in codes
            ])
            db.commit()
            logger.info("已写入 5 个算法种子数据")

    except Exception:
        db.rollback()
        logger.exception("种子数据写入失败")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=12312)
