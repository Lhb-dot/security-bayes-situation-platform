"""报告生成后台任务（进程内任务表 + 守护线程）。

生成一份态势报告要在服务端做一串重活：RiskEvent / 推理记录聚合 → 算法多视图研判 →
NL 态势分析与风险规避指导 → 落库 content 与 report_data。慢的时候十几秒起步，
走同步接口会把请求线程和用户界面一起钉住 —— 前端点完「生成报告」只能干等，
既关不掉弹窗也做不了别的事，误以为没点上还会连点。

改成「提交 → 轮询 → 通知」后：

- POST 立刻返回 job_id，前端关掉弹窗，用户可以继续干别的（甚至离开页面）；
- 后台线程用既有的 ReportService.generate 生成，落库行为与老接口完全一致；
- GET .../jobs 列出本账号的任务，刷新 / 切页回来能恢复「还在跑」的状态。

任务表放在进程内是有意的：产物就是一条 report 记录，已经落在数据库里，
任务表只承载「进度 + 结果 id」这份临时状态，进程重启后丢失不会造成数据不一致
（前端拿到 404 时提示去看报告列表即可）。若将来需要跨重启存活，再建表。

单线程串行：生成要读大量事件与推理记录并调 Java 算法服务，并发跑几个会把单机内存
和 CPU 吃满，排队反而更稳。任务状态里的 PENDING 就是「排队中」。

环境变量：
- REPORT_GEN_RUNNER_ENABLED    默认 1；置 0 关闭（异步入口返回 503）
- REPORT_GEN_JOB_TTL_SECONDS   默认 900，终态任务保留多久（供前端取结果）
- REPORT_GEN_JOB_MAX           默认 50，在册任务上限，超了先清最旧的终态任务
"""
import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.utils.common import get_logger, running_under_test_runner

logger = get_logger("report_generate")

STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
TERMINAL_STATUSES = (STATUS_DONE, STATUS_FAILED)

DEFAULT_TTL_SECONDS = 900
DEFAULT_MAX_JOBS = 50
POLL_SECONDS = 1.0

_jobs: Dict[str, "GenerateJob"] = {}
_jobs_lock = threading.Lock()
_queue: queue.Queue[str] = queue.Queue()
_stop = threading.Event()
_lock = threading.Lock()
_thread: Optional[threading.Thread] = None
_started = False


@dataclass
class GenerateJob:
    """一次报告生成任务的进度与结果。params 是 generate() 的原样入参。"""

    id: str
    user_id: int
    title: str
    params: dict
    status: str = STATUS_PENDING
    error: Optional[str] = None
    report_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def to_dict(self) -> dict:
        """对外视图：不下发入参，只给前端渲染任务卡与通知所需的字段。

        created_at 是 epoch 秒：前端用它算「已进行多少秒」。前端自己记开始时刻的话
        刷新就归零，而这个任务表本来就在服务端、时间以它为准才对。
        """
        return {
            "job_id": self.id,
            "title": self.title,
            "status": self.status,
            "error": self.error,
            "report_id": self.report_id,
            "ready": self.status == STATUS_DONE,
            "created_at": self.created_at,
        }


def is_running() -> bool:
    """执行器是否已启动（未启动时不应接受异步生成提交）。"""
    return _started


def create_job(user_id: int, title: str, params: dict) -> str:
    """登记任务并入队，返回 job_id。"""
    job = GenerateJob(
        id=uuid.uuid4().hex,
        user_id=int(user_id),
        title=title,
        params=dict(params),
    )
    with _jobs_lock:
        _purge_locked()
        _jobs[job.id] = job
    _queue.put(job.id)
    return job.id


def get_job(job_id: str, user_id: int) -> Optional[dict]:
    """取任务视图；任务不存在或不属于该用户时返回 None。"""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None or job.user_id != int(user_id):
            return None
        return job.to_dict()


def list_jobs(user_id: int) -> List[dict]:
    """当前用户的任务列表，最近的在前。"""
    with _jobs_lock:
        mine = [job for job in _jobs.values() if job.user_id == int(user_id)]
        mine.sort(key=lambda job: job.created_at, reverse=True)
        return [job.to_dict() for job in mine]


def _ttl_seconds() -> int:
    try:
        return int(os.getenv("REPORT_GEN_JOB_TTL_SECONDS", DEFAULT_TTL_SECONDS))
    except ValueError:
        return DEFAULT_TTL_SECONDS


def _max_jobs() -> int:
    try:
        return max(1, int(os.getenv("REPORT_GEN_JOB_MAX", DEFAULT_MAX_JOBS)))
    except ValueError:
        return DEFAULT_MAX_JOBS


def _purge_locked() -> None:
    """清掉过期与超量的终态任务（调用方必须已持 _jobs_lock）。"""
    now = time.time()
    ttl = _ttl_seconds()
    for job_id, job in list(_jobs.items()):
        if job.status in TERMINAL_STATUSES and job.finished_at is not None:
            if now - job.finished_at > ttl:
                _jobs.pop(job_id, None)
    overflow = len(_jobs) - _max_jobs()
    if overflow <= 0:
        return
    finished = sorted(
        (job for job in _jobs.values() if job.status in TERMINAL_STATUSES),
        key=lambda job: job.finished_at or job.created_at,
    )
    for job in finished[:overflow]:
        _jobs.pop(job.id, None)


def _execute(job_id: str) -> None:
    """在工作线程里独立开一个会话生成报告（请求会话已随响应关闭）。"""
    from app.db import SessionLocal
    from app.models.app_user import AppUser
    from app.services.report_service import ReportService

    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return
    job.status = STATUS_RUNNING

    db = SessionLocal()
    try:
        # 权限在提交时已按发起人校验过；这里重新取一次用户行，generate() 要按它的角色定数据范围。
        owner = db.get(AppUser, job.user_id)
        if owner is None:
            raise RuntimeError("发起人不存在")
        params = job.params
        result = ReportService(db).generate(
            current_user=owner,
            title=job.title,
            scenario_id=params.get("scenario_id"),
            scope=params.get("scope", "self"),
            format=params.get("format", "markdown"),
            scheduled=bool(params.get("scheduled")),
            interval_days=params.get("interval_days"),
        )
        # generate 带 @service_call：业务失败不会抛，而是回一个非 0 的 code
        if result.code != 0:
            raise RuntimeError(result.message or "报告生成失败")
        job.report_id = (result.data or {}).get("report_id")
    except Exception as exc:  # noqa: BLE001 - 后台任务：失败写进任务表
        db.rollback()
        job.status = STATUS_FAILED
        job.error = str(exc)
        logger.exception("报告生成任务 %s 失败", job_id)
    else:
        job.status = STATUS_DONE
        logger.info("报告生成任务 %s 完成：report_id=%s", job_id, job.report_id)
    finally:
        job.finished_at = time.time()
        db.close()


def _loop() -> None:
    while not _stop.is_set():
        try:
            job_id = _queue.get(timeout=POLL_SECONDS)
        except queue.Empty:
            continue
        try:
            _execute(job_id)
        except Exception:  # noqa: BLE001 - 单条任务失败不能拖垮执行器
            logger.exception("报告生成任务 %s 执行异常", job_id)
        finally:
            _queue.task_done()


def start() -> None:
    """启动执行器线程（幂等：重复调用只保留一个线程）。"""
    global _thread, _started
    if os.getenv("REPORT_GEN_RUNNER_ENABLED", "1") != "1":
        logger.info("报告生成执行器已按 REPORT_GEN_RUNNER_ENABLED=0 关闭")
        return
    if running_under_test_runner():
        return
    with _lock:
        if _started:
            return
        _stop.clear()
        _thread = threading.Thread(target=_loop, name="report-generate-runner", daemon=True)
        _thread.start()
        _started = True
    logger.info("报告生成执行器已启动")


def stop() -> None:
    """停止执行器（优雅退出 / 测试用）。"""
    global _started
    _stop.set()
    with _lock:
        _started = False
