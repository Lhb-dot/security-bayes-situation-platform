"""报告导出后台任务（进程内任务表 + 守护线程）。

PDF 渲染走 Chromium，单次 1–2 秒、等待上限 120 秒；同步接口会让请求线程一直等。
改成「提交 → 轮询 → 取文件」后：

- POST 立刻返回 job_id；
- 后台线程用既有的 build_export 产出文件，字节与老接口完全一致；
- GET .../file 复用老接口同一段 Content-Disposition 逻辑，下载文件名不变。

只有 pdf 需要排队：markdown 是 str.encode()、html 是模板套壳，都是毫秒级，
异步化只会增加复杂度，所以提交时直接同步完成（任务登记即为 DONE）。

任务表放在进程内是有意的：产物只是一次性的下载文件，进程重启后重新导一次即可，
不值得为它建表。若将来需要跨重启存活，再建 export_job 表并落文件。

环境变量：
- EXPORT_RUNNER_ENABLED   默认 1；置 0 关闭（异步导出入口返回 503）
- EXPORT_JOB_TTL_SECONDS  默认 900，终态任务保留多久（供前端取结果）
- EXPORT_JOB_MAX          默认 50，在册任务上限，超了先清最旧的终态任务
"""
import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.utils.common import get_logger, running_under_test_runner

logger = get_logger("export_job")

STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
TERMINAL_STATUSES = (STATUS_DONE, STATUS_FAILED)

DEFAULT_TTL_SECONDS = 900
DEFAULT_MAX_JOBS = 50
POLL_SECONDS = 1.0

_jobs: Dict[str, "ExportJob"] = {}
_jobs_lock = threading.Lock()
_queue: queue.Queue[str] = queue.Queue()
_stop = threading.Event()
_lock = threading.Lock()
_thread: Optional[threading.Thread] = None
_started = False


@dataclass
class ExportJob:
    """一次导出任务的进度与产物。content 只在进程内流转。"""

    id: str
    user_id: int
    report_id: int
    fmt: str
    title: str
    status: str = STATUS_PENDING
    error: Optional[str] = None
    content: Optional[bytes] = None
    filename: Optional[str] = None
    media_type: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def to_dict(self) -> dict:
        """对外视图：不下发文件内容。"""
        return {
            "job_id": self.id,
            "report_id": self.report_id,
            "format": self.fmt,
            "status": self.status,
            "error": self.error,
            "filename": self.filename,
            "ready": self.status == STATUS_DONE,
        }


def is_running() -> bool:
    """执行器是否已启动（未启动时不应接受异步导出提交）。"""
    return _started


def create_job(user_id: int, report_id: int, fmt: str, title: str) -> str:
    """登记任务并入队，返回 job_id。"""
    job = _register(user_id, report_id, fmt, title)
    _queue.put(job.id)
    return job.id


def create_finished_job(user_id: int, report_id: int, fmt: str, title: str, exported) -> str:
    """登记一个已经产出好的任务（markdown / html 走这条）。"""
    job = _register(user_id, report_id, fmt, title)
    _fill(job, exported)
    return job.id


def _register(user_id: int, report_id: int, fmt: str, title: str) -> "ExportJob":
    job = ExportJob(
        id=uuid.uuid4().hex,
        user_id=int(user_id),
        report_id=int(report_id),
        fmt=fmt,
        title=title,
    )
    with _jobs_lock:
        _purge_locked()
        _jobs[job.id] = job
    return job


def _fill(job: "ExportJob", exported) -> None:
    job.content = exported.content
    job.filename = exported.filename
    job.media_type = exported.media_type
    job.status = STATUS_DONE
    job.finished_at = time.time()


def get_job(job_id: str, user_id: int) -> Optional[dict]:
    """取任务视图；任务不存在或不属于该用户时返回 None。"""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None or job.user_id != int(user_id):
            return None
        return job.to_dict()


def get_job_record(job_id: str, user_id: int) -> Optional["ExportJob"]:
    """取任务对象（含产物），供下载接口使用。"""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None or job.user_id != int(user_id):
            return None
        return job


def list_jobs(user_id: int) -> List[dict]:
    """当前用户的任务列表，最近的在前。"""
    with _jobs_lock:
        mine = [job for job in _jobs.values() if job.user_id == int(user_id)]
        mine.sort(key=lambda job: job.created_at, reverse=True)
        return [job.to_dict() for job in mine]


def _ttl_seconds() -> int:
    try:
        return int(os.getenv("EXPORT_JOB_TTL_SECONDS", DEFAULT_TTL_SECONDS))
    except ValueError:
        return DEFAULT_TTL_SECONDS


def _max_jobs() -> int:
    try:
        return max(1, int(os.getenv("EXPORT_JOB_MAX", DEFAULT_MAX_JOBS)))
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
    """在工作线程里独立开一个会话渲染 PDF（请求会话已随响应关闭）。"""
    from app.db import SessionLocal
    from app.services.report_export import build_export
    from app.services.report_service import ReportService

    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return
    job.status = STATUS_RUNNING

    db = SessionLocal()
    try:
        # 权限已在提交时校验过；这里只取标题与正文，正文体积大，放在渲染前才读。
        title, content = ReportService(db).load_export_source(job.report_id)
        exported = build_export(title, content, job.report_id, job.fmt)
    except Exception as exc:  # noqa: BLE001 - 后台任务：失败写进任务表
        db.rollback()
        job.status = STATUS_FAILED
        job.error = str(exc)
        logger.exception("报告导出任务 %s 失败", job_id)
    else:
        _fill(job, exported)
        logger.info("报告导出任务 %s 完成：%s", job_id, job.filename)
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
            logger.exception("报告导出任务 %s 执行异常", job_id)
        finally:
            _queue.task_done()


def start() -> None:
    """启动执行器线程（幂等：重复调用只保留一个线程）。"""
    global _thread, _started
    if os.getenv("EXPORT_RUNNER_ENABLED", "1") != "1":
        logger.info("报告导出执行器已按 EXPORT_RUNNER_ENABLED=0 关闭")
        return
    if running_under_test_runner():
        return
    with _lock:
        if _started:
            return
        _stop.clear()
        _thread = threading.Thread(target=_loop, name="export-job-runner", daemon=True)
        _thread.start()
        _started = True
    logger.info("报告导出执行器已启动")


def stop() -> None:
    """停止执行器（优雅退出 / 测试用）。"""
    global _started
    _stop.set()
    with _lock:
        _started = False
