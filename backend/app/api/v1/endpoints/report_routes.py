"""报告路由（/api/v1/reports）。

对应 Service：ReportService（backend/app/services/report_service.py）。
权限（需求 6.8.5/6.2 P1）：生成/查看 → 登录用户（场景用户仅本人数据；
管理员可全平台/本场景聚合或本人数据，不再支持指定单个用户）；删除 → 生成者本人或管理员。
定时报告：创建时带 scheduled=true 登记，GET /reports/scheduled 只看本账号配置的定时报告，
到期由后台调度器（app/services/report_scheduler.py）原地重新生成。
"""
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.schemas.report import ReportCreate, ReportGenerate, ReportScheduleUpdate
from app.services.report_export import content_disposition
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["报告管理"])


def _file_download_response(resp, report_id: int | None = None):
    """把 Service 的导出结果转成文件流。

    导出接口不走 unwrap 的统一 JSON 结构：成功时直接回文件流，失败时 unwrap
    已经给出 JSONResponse，这里原样透传。

    文件名里的 report_id 以 payload 为准（``read_export_file`` 的任务记录里存了报告
    ID），路径参数只在 payload 没带时兜底（``export`` 的 payload 就不带）。
    """
    if isinstance(resp, JSONResponse):
        return resp
    payload = resp.data
    return Response(
        content=payload["content"],
        media_type=payload["media_type"],
        headers={
            "Content-Disposition": content_disposition(
                payload["filename"],
                payload.get("report_id") or report_id,
                payload["format"],
            )
        },
    )


@router.get(
    "",
    response_model=ResponseModel,
    summary="报告列表（普通用户：本人生成或定向给自己的报告；管理员全部）",
)
def list_reports(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页条数"),
):
    return unwrap(
        ReportService(db).get_list(
            current_user=current_user,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/scheduled",
    response_model=ResponseModel,
    summary="当前账号配置的定时报告（跟随账号，仅本人生成的）",
)
def list_scheduled_reports(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    # 必须声明在 /{report_id} 之前：否则 "scheduled" 会被当成 report_id 去做整型校验
    return unwrap(ReportService(db).list_scheduled(current_user=current_user))


@router.post(
    "/{report_id}/export/jobs",
    response_model=ResponseModel,
    summary="提交报告导出任务（pdf 后台渲染；markdown / html 立即完成）",
)
def submit_export_job(
    report_id: int,
    format: str | None = Query(
        None, description="导出格式，缺省用报告自身记录的格式"
    ),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """导出改为「提交 → 轮询 → 取文件」：PDF 渲染不再占住请求线程。

    老接口 GET /reports/{report_id}/export 一行未改，行为不变，出问题可一键回退。
    """
    return unwrap(
        ReportService(db).submit_export(
            current_user=current_user, report_id=report_id, fmt=format
        )
    )


@router.get(
    "/export/jobs",
    response_model=ResponseModel,
    summary="我的导出任务列表（刷新/切页回来能恢复「已经好了」的状态）",
)
def list_export_jobs(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    # 必须声明在 /{report_id} 之前：否则 "export" 会被当成 report_id 去做整型校验
    return unwrap(ReportService(db).list_export_jobs(current_user=current_user))


@router.get(
    "/export/jobs/{job_id}",
    response_model=ResponseModel,
    summary="导出任务进度（仅发起人）",
)
def get_export_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        ReportService(db).get_export_job(current_user=current_user, job_id=job_id)
    )


@router.get(
    "/export/jobs/{job_id}/file",
    response_class=Response,
    summary="下载导出任务产出的文件（与老接口同一套文件名编码）",
)
def download_export_job_file(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    # 这里不走 unwrap 的统一 JSON 结构：成功时直接回文件流，失败时 unwrap 给出 JSONResponse
    return _file_download_response(
        unwrap(
            ReportService(db).read_export_file(current_user=current_user, job_id=job_id)
        )
    )


@router.post(
    "/generate/jobs",
    response_model=ResponseModel,
    summary="提交报告生成任务（后台线程生成，完成后前端收通知）",
)
def submit_generate_job(
    payload: ReportGenerate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """生成改为「提交 → 轮询 → 通知」：POST 立刻返回 job_id，用户不必干等在弹窗里。

    生成一份报告要做数据聚合 + 多视图研判 + NL 分析，慢的时候十几秒起步，同步返回会把
    请求线程和界面一起钉住。老接口 POST /reports/generate 一行未改，出问题可一键回退。
    """
    return unwrap(
        ReportService(db).submit_generate(
            current_user=current_user,
            title=payload.title,
            scenario_id=payload.scenario_id,
            scope=payload.scope,
            format=payload.format,
            scheduled=payload.scheduled,
            interval_days=payload.interval_days,
        )
    )


@router.get(
    "/generate/jobs",
    response_model=ResponseModel,
    summary="我的生成任务列表（刷新/切页回来能恢复「还在跑」的状态）",
)
def list_generate_jobs(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    # 必须声明在 /{report_id} 之前：否则 "generate" 会被当成 report_id 去做整型校验
    return unwrap(ReportService(db).list_generate_jobs(current_user=current_user))


@router.get(
    "/generate/jobs/{job_id}",
    response_model=ResponseModel,
    summary="生成任务进度（仅发起人）",
)
def get_generate_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        ReportService(db).get_generate_job(current_user=current_user, job_id=job_id)
    )


@router.get(
    "/{report_id}", response_model=ResponseModel, summary="报告详情"
)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        ReportService(db).get(current_user=current_user, report_id=report_id)
    )


@router.get(
    "/{report_id}/export",
    response_class=Response,
    summary="导出报告文件（markdown / html / pdf）",
)
def export_report(
    report_id: int,
    format: str | None = Query(
        None, description="导出格式，缺省用报告自身记录的格式"
    ),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    # 这里不走 unwrap 的统一 JSON 结构：成功时直接回文件流，失败时 unwrap 给出 JSONResponse
    return _file_download_response(
        unwrap(
            ReportService(db).export(
                current_user=current_user, report_id=report_id, fmt=format
            )
        ),
        report_id,
    )


@router.post(
    "", response_model=ResponseModel, summary="生成态势报告（普通用户仅本人数据）"
)
def create_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        ReportService(db).create(
            current_user=current_user,
            title=payload.title,
            report_type=payload.report_type,
            content=payload.content,
            file_path=payload.file_path,
            scenario_id=payload.scenario_id,
            format=payload.format,
            scheduled=payload.scheduled,
            interval_days=payload.interval_days,
        )
    )


@router.post(
    "/generate",
    response_model=ResponseModel,
    summary="自动生成态势报告（真实数据 + 算法多视图研判 + NL 分析）",
)
def generate_report(
    payload: ReportGenerate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        ReportService(db).generate(
            current_user=current_user,
            title=payload.title,
            scenario_id=payload.scenario_id,
            scope=payload.scope,
            format=payload.format,
            scheduled=payload.scheduled,
            interval_days=payload.interval_days,
        )
    )


@router.put(
    "/{report_id}/schedule",
    response_model=ResponseModel,
    summary="保存报告定时配置（到期由后台调度器重新生成）",
)
def update_report_schedule(
    report_id: int,
    payload: ReportScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        ReportService(db).update_schedule(
            current_user=current_user,
            report_id=report_id,
            scheduled=payload.scheduled,
            interval_days=payload.interval_days,
        )
    )


@router.delete(
    "/{report_id}",
    response_model=ResponseModel,
    summary="删除报告（生成者本人或管理员）",
)
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        ReportService(db).delete(current_user=current_user, report_id=report_id)
    )
