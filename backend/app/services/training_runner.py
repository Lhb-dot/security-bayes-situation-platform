"""训练任务后台执行器（守护线程 + 队列）。

部署形态是单进程 FastAPI（uvicorn app.main:app），所以与 report_scheduler 一致，
不引入 celery / APScheduler —— 多一个中间件就多一处运维面。

分工：
- 请求线程：只做 create()（建 TRAINING 版本）后立刻返回，不再被 TRAIN_TIMEOUT 卡住；
- 后台线程：从队列取模型 ID，调 Java 算法服务真实训练，成功 / 失败分别流转状态。

状态流转复用 ModelVersionService 里与同步路径同一套实现，保证写入
evaluation_metrics / model_attributes 的字段形状完全一致。

多副本部署：队列在进程内，不做跨进程分发。若将来上多副本，需要给 model_version
加一个「已被某副本认领」的标记并用 SELECT ... FOR UPDATE SKIP LOCKED 抢占，
与 ReportService.run_due_scheduled_reports 的做法一致。

环境变量：
- TRAINING_RUNNER_ENABLED  默认 1；置 0 关闭（此时 /train-async 返回 503）
- TRAINING_RUNNER_WORKERS  默认 1，并发训练数，上限 4
- TRAINING_STALE_MINUTES   默认 60；启动时以及每 REAP_INTERVAL_SECONDS 把超过该
                           时长仍停在 TRAINING 的版本标记为 FAILED（进程重启后
                           无人推进的在途任务兜底）
"""
import os
import queue
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models.model_version import ModelVersion
from app.services.constants import MODEL_STATUS_FAILED, MODEL_STATUS_TRAINING
from app.services.model_version_service import ModelVersionService
from app.utils.common import get_logger, running_under_test_runner

logger = get_logger("training_runner")

DEFAULT_WORKERS = 1
MAX_WORKERS = 4
DEFAULT_STALE_MINUTES = 60
POLL_SECONDS = 1.0
REAP_INTERVAL_SECONDS = 300.0
INTERRUPTED_ERROR = "训练任务中断（服务重启或执行器停止），未能完成"

_queue: queue.Queue[int] = queue.Queue()
_stop = threading.Event()
_lock = threading.Lock()
_threads: list[threading.Thread] = []
_started = False


def is_running() -> bool:
    """执行器是否已启动（未启动时不应接受异步训练提交）。"""
    return _started


def submit(model_id: int) -> bool:
    """把模型版本加入训练队列；执行器未启动时返回 False。"""
    if not _started:
        return False
    _queue.put(int(model_id))
    return True


def _execute(model_id: int) -> None:
    """在工作线程里独立开一个会话执行训练（请求会话已随响应关闭）。"""
    db = SessionLocal()
    try:
        model = db.get(ModelVersion, model_id)
        if model is None:
            logger.warning("训练任务 #%s 对应的模型版本不存在，跳过", model_id)
            return
        if model.status != MODEL_STATUS_TRAINING:
            logger.warning(
                "训练任务 #%s 当前状态为 %s，非 TRAINING，跳过", model_id, model.status
            )
            return
        ModelVersionService(db).run_training_job(model)
    finally:
        db.close()


def reap_stale(stale_minutes: int | None = None) -> int:
    """把超过 stale_minutes 仍停在 TRAINING 的版本标记为 FAILED，返回处理条数。

    治的是「进程重启导致在途任务无人推进」：状态机里 TRAINING 只能转 FAILED / DRAFT，
    没有别的角色会去推进它，不兜底就会永远显示「训练中」。
    """
    minutes = _stale_minutes(stale_minutes)
    if minutes <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

    db = SessionLocal()
    try:
        stale_ids = [
            model.id
            for model in db.scalars(
                select(ModelVersion).where(
                    ModelVersion.status == MODEL_STATUS_TRAINING,
                    ModelVersion.trained_at < cutoff,
                )
            ).all()
        ]
        if not stale_ids:
            return 0

        service = ModelVersionService(db)
        reaped = 0
        for model_id in stale_ids:
            model = db.get(ModelVersion, model_id)
            if model is None or model.status != MODEL_STATUS_TRAINING:
                continue
            try:
                service.apply_training_failure(model, INTERRUPTED_ERROR)
            except Exception:  # noqa: BLE001 - 单条清理失败不影响其余
                db.rollback()
                logger.exception("清理超时训练任务 #%s 失败", model_id)
                continue
            reaped += 1
            logger.warning("训练任务 #%s 超过 %s 分钟未完成，已标记为 FAILED", model_id, minutes)
        return reaped
    finally:
        db.close()


def _stale_minutes(override: int | None) -> int:
    if override is not None:
        return int(override)
    try:
        return int(os.getenv("TRAINING_STALE_MINUTES", DEFAULT_STALE_MINUTES))
    except ValueError:
        return DEFAULT_STALE_MINUTES


def _worker_count(override: int | None) -> int:
    if override is None:
        try:
            override = int(os.getenv("TRAINING_RUNNER_WORKERS", DEFAULT_WORKERS))
        except ValueError:
            override = DEFAULT_WORKERS
    return min(MAX_WORKERS, max(1, int(override)))


def _reap_safely() -> None:
    try:
        reap_stale()
    except Exception:  # noqa: BLE001 - 兜底失败不能拖垮执行器
        logger.exception("清理超时训练任务失败")


def _worker(index: int) -> None:
    if index == 0:
        # 启动先兜底一轮：进程重启后残留在 TRAINING 的版本立刻被清理
        _reap_safely()
    last_reap = time.monotonic()
    while not _stop.is_set():
        try:
            model_id = _queue.get(timeout=POLL_SECONDS)
        except queue.Empty:
            model_id = None
        if model_id is not None:
            try:
                _execute(model_id)
            except Exception:  # noqa: BLE001 - 单条任务失败不能拖垮执行器
                logger.exception("训练任务 #%s 执行异常", model_id)
            finally:
                _queue.task_done()
        if index == 0 and time.monotonic() - last_reap >= REAP_INTERVAL_SECONDS:
            last_reap = time.monotonic()
            _reap_safely()


def start(workers: int | None = None) -> None:
    """启动执行器线程（幂等：重复调用只保留一组线程）。"""
    global _started
    if os.getenv("TRAINING_RUNNER_ENABLED", "1") != "1":
        logger.info("训练执行器已按 TRAINING_RUNNER_ENABLED=0 关闭")
        return
    if running_under_test_runner():
        return
    with _lock:
        if _started:
            return
        count = _worker_count(workers)
        _stop.clear()
        _threads.clear()
        for index in range(count):
            thread = threading.Thread(
                target=_worker, args=(index,), name=f"training-runner-{index}", daemon=True
            )
            thread.start()
            _threads.append(thread)
        _started = True
    logger.info("训练执行器已启动，并发数 %s", count)


def stop() -> None:
    """停止执行器（优雅退出 / 测试用）。"""
    global _started
    _stop.set()
    with _lock:
        _started = False
