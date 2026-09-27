"""批量研判后台执行器（进程内任务表 + 守护线程队列）。

批量研判是逐条串行调 Java 预测服务并落库的，200 条上限最坏可跑十几分钟，
超过 nginx 的 proxy_read_timeout（600 秒）：同步返回会让前端拿到 504，
但后端还在继续跑、且已经落了一半记录 —— 用户看到「失败」、实际成功了一半。
改成「提交 → 轮询」后前端拿到的是真实汇总。

- 提交接口只做校验与登记（样本在提交前已解析好），毫秒级返回 job_id；
- 后台线程执行既有的逐条链路，进度写回任务表；
- 单条失败不影响整批（沿用原语义），失败条目带 error 文案。

任务表刻意放在进程内：批量研判的产物是 InferenceRecord，已经落在数据库里，
任务表只承载「进度 + 汇总」这份临时状态，进程重启后丢失不会造成数据不一致
（前端拿到 404 时提示去看推理记录列表即可）。若将来需要跨重启存活，再建
inference_batch_job 表并用 SELECT ... FOR UPDATE SKIP LOCKED 抢占。

环境变量：
- BATCH_RUNNER_ENABLED    默认 1；置 0 关闭（异步入口返回 503）
- BATCH_JOB_TTL_SECONDS   默认 1800，终态任务在表里保留多久（供前端取结果）
- BATCH_JOB_MAX           默认 100，在册任务上限，超了先清最旧的终态任务
"""
import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.utils.common import get_logger, running_under_test_runner

logger = get_logger("batch_inference_runner")

STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
TERMINAL_STATUSES = (STATUS_DONE, STATUS_FAILED)

DEFAULT_TTL_SECONDS = 1800
DEFAULT_MAX_JOBS = 100
POLL_SECONDS = 1.0

_jobs: Dict[str, "BatchJob"] = {}
_jobs_lock = threading.Lock()
_queue: queue.Queue[str] = queue.Queue()
_stop = threading.Event()
_lock = threading.Lock()
_thread: Optional[threading.Thread] = None
_started = False


@dataclass
class BatchJob:
    """一次批量研判任务的进度与汇总。samples 只在进程内流转，不对外下发。"""

    id: str
    user_id: int
    model_version_id: int
    total: int
    samples: List[Dict[str, Any]]
    truncated: bool = False
    status: str = STATUS_PENDING
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    risk_count: int = 0
    items: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def to_dict(self) -> dict:
        """对外视图：终态时才带逐条明细，进行中只给计数。

        created_at 是 epoch 秒，前端据此算已用时间（前端自己记的话刷新会归零）。
        """
        return {
            "job_id": self.id,
            "status": self.status,
            "model_version_id": self.model_version_id,
            "total": self.total,
            "processed": self.processed,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "risk_count": self.risk_count,
            "truncated": self.truncated,
            "error": self.error,
            "created_at": self.created_at,
            "result": (
                {
                    "total": self.total,
                    "succeeded": self.succeeded,
                    "failed": self.failed,
                    "risk_count": self.risk_count,
                    "items": self.items,
                    "truncated": self.truncated,
                }
                if self.status in TERMINAL_STATUSES
                else None
            ),
        }

    def to_brief(self) -> dict:
        """列表视图：不带逐条明细。

        明细最多 200 条，一份任务就是几十 KB；列表接口只用来恢复「还在跑」的状态，
        明细仍走单任务接口取。
        """
        view = self.to_dict()
        view.pop("result", None)
        return view


def is_running() -> bool:
    """执行器是否已启动（未启动时不应接受异步提交）。"""
    return _started


def create_job(
    user_id: int,
    model_version_id: int,
    samples: List[Dict[str, Any]],
    truncated: bool = False,
) -> str:
    """登记任务并返回 job_id（不阻塞，执行交给后台线程）。"""
    job = BatchJob(
        id=uuid.uuid4().hex,
        user_id=int(user_id),
        model_version_id=int(model_version_id),
        total=len(samples),
        samples=list(samples),
        truncated=truncated,
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
    """当前用户的批量研判任务列表，最近的在前（刷新 / 切页回来能恢复在途状态）。"""
    with _jobs_lock:
        mine = [job for job in _jobs.values() if job.user_id == int(user_id)]
        mine.sort(key=lambda job: job.created_at, reverse=True)
        return [job.to_brief() for job in mine]


def _ttl_seconds() -> int:
    try:
        return int(os.getenv("BATCH_JOB_TTL_SECONDS", DEFAULT_TTL_SECONDS))
    except ValueError:
        return DEFAULT_TTL_SECONDS


def _max_jobs() -> int:
    try:
        return max(1, int(os.getenv("BATCH_JOB_MAX", DEFAULT_MAX_JOBS)))
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
    """在工作线程里独立开一个会话执行批量研判（请求会话已随响应关闭）。"""
    from app.db import SessionLocal
    from app.models.app_user import AppUser
    from app.services.inference_record_service import InferenceRecordService

    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return
    job.status = STATUS_RUNNING

    def on_progress(processed: int, succeeded: int, failed: int, risk_count: int) -> None:
        job.processed = processed
        job.succeeded = succeeded
        job.failed = failed
        job.risk_count = risk_count

    db = SessionLocal()
    try:
        user = db.get(AppUser, job.user_id)
        if user is None:
            raise RuntimeError("发起批量研判的用户不存在")
        summary = InferenceRecordService(db).run_batch_job(
            current_user=user,
            model_version_id=job.model_version_id,
            samples=job.samples,
            on_progress=on_progress,
        )
    except Exception as exc:  # noqa: BLE001 - 后台任务：失败写进任务表
        db.rollback()
        job.status = STATUS_FAILED
        job.error = str(exc)
        logger.exception("批量研判任务 %s 失败", job_id)
    else:
        job.items = summary["items"]
        job.succeeded = summary["succeeded"]
        job.failed = summary["failed"]
        job.risk_count = summary["risk_count"]
        job.processed = job.total
        job.status = STATUS_DONE
        logger.info(
            "批量研判任务 %s 完成：成功 %s 条、风险 %s 条、失败 %s 条",
            job_id,
            job.succeeded,
            job.risk_count,
            job.failed,
        )
    finally:
        job.finished_at = time.time()
        # 明细不再需要，及时释放
        job.samples = []
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
            logger.exception("批量研判任务 %s 执行异常", job_id)
        finally:
            _queue.task_done()


def start() -> None:
    """启动执行器线程（幂等：重复调用只保留一个线程）。"""
    global _thread, _started
    if os.getenv("BATCH_RUNNER_ENABLED", "1") != "1":
        logger.info("批量研判执行器已按 BATCH_RUNNER_ENABLED=0 关闭")
        return
    if running_under_test_runner():
        return
    with _lock:
        if _started:
            return
        _stop.clear()
        _thread = threading.Thread(target=_loop, name="batch-inference-runner", daemon=True)
        _thread.start()
        _started = True
    logger.info("批量研判执行器已启动")


def stop() -> None:
    """停止执行器（优雅退出 / 测试用）。"""
    global _started
    _stop.set()
    with _lock:
        _started = False
