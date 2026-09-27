"""推理记录路由（/api/v1/inference-records）。

对应 Service：InferenceRecordService（backend/app/services/inference_record_service.py）。
权限（需求 6.8/6.7.3）：执行推理 → 登录用户（仅 PUBLISHED 模型）；
查看记录 → 登录用户（USER 仅本人）；删除 → 仅 ADMIN。
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.schemas.inference_record import InferenceBatchPredict, InferencePredict
from app.services.inference_record_service import InferenceRecordService

router = APIRouter(prefix="/inference-records", tags=["推理记录"])


@router.post(
    "/predict",
    response_model=ResponseModel,
    summary="执行单条推理（登录用户；风险类结果自动生成 RiskEvent）",
)
def predict(
    payload: InferencePredict,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """执行推理并落库推理记录；预测为风险类时生成 RiskEvent（需求 5.2/5.3）。

    说明：任务原路径 `/inference-records/{id}/predict` 中的 id 与
    InferenceRecordService.create_inference 的语义（创建新记录，入参为
    model_version_id）不符，故采用无 id 的 POST /predict 形式。

    预测结果由服务端统一预测入口（独立 Java 预测服务）根据
    model_version_id + input_features 计算，客户端不再提交 prediction_label/risk_score。
    """
    return unwrap(
        InferenceRecordService(db).create_inference(
            current_user=current_user,
            model_version_id=payload.model_version_id,
            input_features=payload.input_features,
        )
    )


@router.post(
    "/predict-batch",
    response_model=ResponseModel,
    summary="批量推理（登录用户；逐条落库，风险类自动生成 RiskEvent）",
)
def predict_batch(
    payload: InferenceBatchPredict,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """批量研判：与单条推理行为一致，风险类样本照常生成 RiskEvent。

    必须注册在 ``/{record_id}`` 之前 —— 否则 "predict-batch" 会被当成
    路径参数解析而返回 422。
    """
    service = InferenceRecordService(db)
    if payload.source == "dataset":
        return service.create_batch_from_dataset(
            current_user=current_user,
            model_version_id=payload.model_version_id,
            offset=payload.offset,
            limit=payload.limit,
        )
    return service.create_batch_inference(
        current_user=current_user,
        model_version_id=payload.model_version_id,
        samples=payload.samples or [],
    )


@router.post(
    "/predict-batch/upload",
    response_model=ResponseModel,
    summary="上传 CSV 批量研判（表头需覆盖数据集全部输入特征）",
)
async def predict_batch_upload(
    file: UploadFile = File(..., description="CSV 文件"),
    model_version_id: int = Form(..., description="模型版本 ID"),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """用上传的 CSV 做批量研判；列名对不上会明确告知缺哪几列。"""
    file_bytes = await file.read()
    return unwrap(
        InferenceRecordService(db).create_batch_from_csv(
            current_user=current_user,
            model_version_id=model_version_id,
            filename=file.filename or "",
            file_bytes=file_bytes,
        )
    )


@router.post(
    "/predict-batch/jobs",
    response_model=ResponseModel,
    summary="提交异步批量研判（登录用户）：立刻返回 job_id，后台逐条执行",
)
def predict_batch_submit(
    payload: InferenceBatchPredict,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """异步批量研判：校验与同步 /predict-batch 一致，只是不在请求线程里跑。

    200 条最坏可跑十几分钟，超过 nginx 的 proxy_read_timeout（600 秒）；
    同步返回会让前端拿到 504 而实际已经落了一半记录，所以页面走这条。

    必须注册在 ``/{record_id}`` 之前 —— 否则 "predict-batch" 会被当成
    路径参数解析而返回 422。
    """
    service = InferenceRecordService(db)
    if payload.source == "dataset":
        return service.submit_batch_from_dataset(
            current_user=current_user,
            model_version_id=payload.model_version_id,
            offset=payload.offset,
            limit=payload.limit,
        )
    return service.submit_batch_inference(
        current_user=current_user,
        model_version_id=payload.model_version_id,
        samples=payload.samples or [],
    )


@router.post(
    "/predict-batch/upload/jobs",
    response_model=ResponseModel,
    summary="上传 CSV 并提交异步批量研判（表头需覆盖数据集全部输入特征）",
)
async def predict_batch_upload_submit(
    file: UploadFile = File(..., description="CSV 文件"),
    model_version_id: int = Form(..., description="模型版本 ID"),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """上传 CSV 后立刻返回 job_id；解析/列名错误仍同步返回，便于前端即时提示。"""
    file_bytes = await file.read()
    return unwrap(
        InferenceRecordService(db).submit_batch_from_csv(
            current_user=current_user,
            model_version_id=model_version_id,
            filename=file.filename or "",
            file_bytes=file_bytes,
        )
    )


@router.get(
    "/predict-batch/jobs",
    response_model=ResponseModel,
    summary="我的批量研判任务列表（刷新/切页回来能恢复「还在跑」的状态）",
)
def list_predict_batch_jobs(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(InferenceRecordService(db).list_batch_jobs(current_user))


@router.get(
    "/predict-batch/jobs/{job_id}",
    response_model=ResponseModel,
    summary="查询批量研判任务进度（仅发起人）",
)
def get_predict_batch_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(InferenceRecordService(db).get_batch_job(current_user, job_id))


@router.get(
    "",
    response_model=ResponseModel,
    summary="推理记录列表（普通用户仅本人；管理员全部）",
)
def list_inference_records(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    model_version_id: Optional[int] = Query(None, description="按模型版本过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页条数"),
):
    return unwrap(
        InferenceRecordService(db).get_list(
            current_user=current_user,
            model_version_id=model_version_id,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/{record_id}",
    response_model=ResponseModel,
    summary="推理记录详情（普通用户仅本人）",
)
def get_inference_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        InferenceRecordService(db).get(
            current_user=current_user, record_id=record_id
        )
    )


@router.get(
    "/{record_id}/explain",
    response_model=ResponseModel,
    summary="推理记录可解释性信息（多视图预测 / 特征加权条件概率）",
)
def get_inference_explain(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        InferenceRecordService(db).get_explain(
            current_user=current_user, record_id=record_id
        )
    )


@router.delete(
    "/{record_id}",
    response_model=ResponseModel,
    summary="删除推理记录（仅管理员；已生成风险事件的记录禁止删除）",
)
def delete_inference_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        InferenceRecordService(db).delete(
            current_user=current_user, record_id=record_id
        )
    )
