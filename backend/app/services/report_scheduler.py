"""定时报告调度器（后台守护线程）。

部署形态是单进程 FastAPI（uvicorn app.main:app），所以不引入 celery / APScheduler
这类外部调度组件 —— 多一个中间件就多一处运维面。报告以「天」为周期，用一条常驻
线程按分钟级间隔扫描数据库里到期的定时报告足够，且不依赖任何外部状态。

多进程 / 多副本部署：抢占由 ReportService.run_due_scheduled_reports 里的
SELECT ... FOR UPDATE SKIP LOCKED 保证，同一条记录只会被一个进程处理，不会重复生成。

环境变量：
- REPORT_SCHEDULER_ENABLED   默认 1；置 0 关闭（例如只让某一个副本跑调度）
- REPORT_SCHEDULER_INTERVAL  默认 60，轮询间隔（秒），下限 5
"""
import os
import threading

from app.db import SessionLocal
from app.services.report_service import ReportService
from app.utils.common import get_logger, running_under_test_runner

logger = get_logger("report_scheduler")

DEFAULT_INTERVAL_SECONDS = 60
MIN_INTERVAL_SECONDS = 5

_stop = threading.Event()
_thread: threading.Thread | None = None
_lock = threading.Lock()


def run_once() -> int:
    """扫一轮到期报告并重新生成，返回成功刷新的条数。"""
    db = SessionLocal()
    try:
        return ReportService(db).run_due_scheduled_reports()
    finally:
        db.close()


def _loop(interval_seconds: int) -> None:
    logger.info("定时报告调度器已启动，轮询间隔 %s 秒", interval_seconds)
    # 先扫一轮再等：服务重启后能立刻补上停机期间到期的报告，不用白等一个间隔
    while not _stop.is_set():
        try:
            refreshed = run_once()
            if refreshed:
                logger.info("本轮定时报告处理完成，共 %s 份", refreshed)
        except Exception:  # noqa: BLE001 - 调度失败不能影响主服务
            logger.exception("定时报告调度轮询失败")
        _stop.wait(interval_seconds)
    logger.info("定时报告调度器已停止")


def start(interval_seconds: int | None = None) -> None:
    """启动调度线程（幂等：重复调用只保留一个线程）。"""
    global _thread
    if os.getenv("REPORT_SCHEDULER_ENABLED", "1") != "1":
        logger.info("定时报告调度器已按 REPORT_SCHEDULER_ENABLED=0 关闭")
        return
    # 与其余四个后台执行器（training / batch_inference / export / report_generate）同一判定：
    # 只认 __main__ 的 spec。原来只看 sys.modules 里有没有 pytest，`python -m unittest`
    # 跑测试时判定为 False，调度线程会真的起来连数据库扫到期报告。
    if running_under_test_runner():
        return
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        interval = interval_seconds
        if interval is None:
            try:
                interval = int(os.getenv("REPORT_SCHEDULER_INTERVAL", DEFAULT_INTERVAL_SECONDS))
            except ValueError:
                interval = DEFAULT_INTERVAL_SECONDS
        interval = max(MIN_INTERVAL_SECONDS, interval)
        _stop.clear()
        _thread = threading.Thread(
            target=_loop, args=(interval,), name="report-scheduler", daemon=True
        )
        _thread.start()


def stop() -> None:
    """停止调度线程（优雅退出 / 测试用）。"""
    _stop.set()
