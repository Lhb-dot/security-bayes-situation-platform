"""Legacy PMWNB HTTP endpoints kept for older clients.

The current frontend uses ``/api/v1``. These endpoints remain available because
older integrations may still call them, but they are isolated from application
startup and the database-backed API.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.algorithms.pmwnb_demo import (
    append_exp_record,
    del_exp_by_id,
    get_all_exp,
    save_threshold_sim,
)
from app.api.deps import get_current_user, require_scenario_admin
from app.paths import OUTPUT_ROOT
from app.services.model_sim import get_dataset_list, infer_bayes_sim, train_bayes_sim


router = APIRouter(tags=["兼容接口"])

# The old training endpoint is process-local by design. Keep its original
# behavior while preventing the state from leaking into the v1 model APIs.
_legacy_training_state = {
    "is_trained": False,
    "current_dataset": "",
}


@router.get("/china-map.json")
async def get_map_json():
    map_file = OUTPUT_ROOT / "china-map.json"
    if not map_file.exists():
        raise HTTPException(status_code=404, detail="地图数据文件缺失")
    return FileResponse(map_file, media_type="application/json")


@router.get("/api/model/dataset-list")
async def get_legacy_datasets(current_user=Depends(get_current_user)):  # noqa: ARG001
    return {"code": 200, "data": get_dataset_list()}


@router.post("/api/model/save-threshold")
async def save_legacy_threshold(
    high: float,
    mid: float,
    low: float,
    current_user=Depends(require_scenario_admin),  # noqa: ARG001
):
    if not save_threshold_sim(high, mid, low):
        raise HTTPException(status_code=400, detail="阈值规则错误，必须满足 高>中>低")
    return {"code": 200, "msg": "全局告警阈值保存成功"}


@router.post("/api/model/train")
def train_legacy_model(
    dataset_name: str,
    algo_type: str = "",
    discrete_method: str = "",
    current_user=Depends(require_scenario_admin),  # noqa: ARG001
):
    train_result = train_bayes_sim(dataset_name, algo_type, discrete_method)
    _legacy_training_state["is_trained"] = True
    _legacy_training_state["current_dataset"] = dataset_name

    append_exp_record(
        {
            "dataset_name": dataset_name,
            "algo_type": algo_type or "PMWNB",
            "discrete_method": discrete_method or "EWD+MDLP",
            "accuracy": train_result["accuracy"],
            "f1": train_result["f1"],
            "recall": train_result["recall"],
            "train_time_s": train_result["train_time_s"],
            "train_time": train_result["train_time_s"],
        }
    )

    return {"code": 200, "msg": f"{dataset_name} PMWNB训练完成", "data": train_result}


@router.post("/api/model/infer")
def infer_legacy_model(
    flowLength: float,
    duration: float,
    accessFreq: float,
    current_user=Depends(get_current_user),  # noqa: ARG001
):
    if not _legacy_training_state["is_trained"]:
        raise HTTPException(status_code=400, detail="禁止预测：请先选择数据集执行模型训练")
    result = infer_bayes_sim(
        {"flowLength": flowLength, "duration": duration, "accessFreq": accessFreq}
    )
    return {"code": 200, "msg": "AI研判完成", "data": result}


@router.get("/api/model/exp-records")
async def get_legacy_experiment_records(current_user=Depends(get_current_user)):  # noqa: ARG001
    return {"code": 200, "data": get_all_exp()}


@router.delete("/api/model/exp/{record_id}")
async def delete_legacy_experiment_record(
    record_id: int,
    current_user=Depends(require_scenario_admin),  # noqa: ARG001
):
    del_exp_by_id(record_id)
    return {"code": 200, "msg": "实验记录删除完成"}


@router.get("/api/model/risk_statistics")
def get_legacy_risk_statistics(current_user=Depends(get_current_user)):  # noqa: ARG001
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
