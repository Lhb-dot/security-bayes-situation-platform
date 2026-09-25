"""报告生成异步化测试：任务表隔离、终态流转、提交前置校验、路由注册。

生成一份报告要做数据聚合 + 多视图研判 + NL 分析，同步返回会把请求线程和界面一起钉住。
改成「提交 → 轮询 → 通知」后要锁住的不变量：任务只对发起人可见、失败要写进任务表
（而不是把异常吞掉）、参数不对必须在 POST 时就拒掉（不能丢进队列等后台才发现）。
"""
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.schemas.common import fail, ok  # noqa: E402
from app.services import report_generate_runner  # noqa: E402
from app.services.report_service import ReportService  # noqa: E402

SUPER_ADMIN = SimpleNamespace(id=1, role="SUPER_ADMIN", status="ENABLED")


class FakeDb:
    def __init__(self, user=None):
        self.rollbacks = 0
        self.closed = False
        self._user = user if user is not None else SUPER_ADMIN

    def get(self, _model, _pk):
        return self._user

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class JobStoreCase(unittest.TestCase):
    def setUp(self):
        with report_generate_runner._jobs_lock:
            report_generate_runner._jobs.clear()
        while not report_generate_runner._queue.empty():
            report_generate_runner._queue.get_nowait()

    def tearDown(self):
        with report_generate_runner._jobs_lock:
            report_generate_runner._jobs.clear()


class JobStoreTests(JobStoreCase):
    def test_view_carries_title_but_not_params(self):
        job_id = report_generate_runner.create_job(
            1, "网络安全月度态势报告", {"scope": "self", "format": "markdown"}
        )
        view = report_generate_runner.get_job(job_id, 1)

        self.assertEqual(view["status"], report_generate_runner.STATUS_PENDING)
        self.assertFalse(view["ready"])
        self.assertEqual(view["title"], "网络安全月度态势报告")
        self.assertNotIn("params", view)

    def test_job_is_not_visible_to_other_users(self):
        job_id = report_generate_runner.create_job(1, "测试报告", {})
        self.assertIsNone(report_generate_runner.get_job(job_id, 2))
        self.assertEqual(report_generate_runner.list_jobs(2), [])

    def test_submit_is_rejected_before_start(self):
        self.assertFalse(report_generate_runner.is_running())

    def test_execute_marks_done_with_report_id(self):
        job_id = report_generate_runner.create_job(1, "测试报告", {"scope": "self"})
        db = FakeDb()
        with patch("app.db.SessionLocal", return_value=db), patch.object(
            ReportService, "generate", return_value=ok(data={"report_id": "42"})
        ) as generate:
            report_generate_runner._execute(job_id)

        view = report_generate_runner.get_job(job_id, 1)
        self.assertEqual(view["status"], report_generate_runner.STATUS_DONE)
        self.assertTrue(view["ready"])
        self.assertEqual(view["report_id"], "42")
        self.assertTrue(db.closed)
        # 后台线程要按发起人的身份生成，数据范围才不会被放大
        self.assertEqual(generate.call_args.kwargs["current_user"].id, 1)
        self.assertEqual(generate.call_args.kwargs["title"], "测试报告")

    def test_service_failure_is_recorded_not_swallowed(self):
        """generate 带 @service_call，业务失败回非 0 code 而不抛 —— 必须转成 FAILED。"""
        job_id = report_generate_runner.create_job(1, "测试报告", {})
        db = FakeDb()
        with patch("app.db.SessionLocal", return_value=db), patch.object(
            ReportService, "generate", return_value=fail(code=400, message="定时生成需指定有效周期")
        ):
            report_generate_runner._execute(job_id)

        view = report_generate_runner.get_job(job_id, 1)
        self.assertEqual(view["status"], report_generate_runner.STATUS_FAILED)
        self.assertEqual(view["error"], "定时生成需指定有效周期")
        self.assertEqual(db.rollbacks, 1)
        self.assertTrue(db.closed)

    def test_exception_is_recorded(self):
        job_id = report_generate_runner.create_job(1, "测试报告", {})
        db = FakeDb()
        with patch("app.db.SessionLocal", return_value=db), patch.object(
            ReportService, "generate", side_effect=RuntimeError("数据库炸了")
        ):
            report_generate_runner._execute(job_id)

        view = report_generate_runner.get_job(job_id, 1)
        self.assertEqual(view["status"], report_generate_runner.STATUS_FAILED)
        self.assertEqual(view["error"], "数据库炸了")
        self.assertTrue(db.closed)

    def test_missing_owner_fails_the_job(self):
        job_id = report_generate_runner.create_job(1, "测试报告", {})
        db = FakeDb(user=None)
        with patch("app.db.SessionLocal", return_value=db):
            report_generate_runner._execute(job_id)

        self.assertEqual(
            report_generate_runner.get_job(job_id, 1)["status"],
            report_generate_runner.STATUS_FAILED,
        )

    def test_expired_terminal_job_is_purged_on_next_submit(self):
        stale_id = report_generate_runner.create_job(1, "旧报告", {})
        stale = report_generate_runner._jobs[stale_id]
        stale.status = report_generate_runner.STATUS_DONE
        stale.finished_at = time.time() - 99999

        with patch.dict("os.environ", {"REPORT_GEN_JOB_TTL_SECONDS": "10"}):
            report_generate_runner.create_job(1, "新报告", {})

        self.assertIsNone(report_generate_runner.get_job(stale_id, 1))

    def test_pending_job_is_never_purged(self):
        live_id = report_generate_runner.create_job(1, "在跑的报告", {})
        report_generate_runner._jobs[live_id].created_at = time.time() - 99999

        with patch.dict(
            "os.environ", {"REPORT_GEN_JOB_TTL_SECONDS": "10", "REPORT_GEN_JOB_MAX": "1"}
        ):
            report_generate_runner.create_job(1, "新报告", {})

        self.assertIsNotNone(report_generate_runner.get_job(live_id, 1))


class SubmitGenerateTests(JobStoreCase):
    def setUp(self):
        super().setUp()
        self.service = ReportService(FakeDb())

    def test_valid_submit_is_queued_with_pending_status(self):
        with patch("app.services.report_generate_runner.is_running", return_value=True):
            resp = self.service.submit_generate(
                SUPER_ADMIN, title="  网络安全月度态势报告  ", scope="self", format="markdown"
            )

        self.assertEqual(resp.code, 0)
        self.assertEqual(resp.message, "生成任务已提交")
        self.assertEqual(report_generate_runner._queue.qsize(), 1)
        view = report_generate_runner.get_job(resp.data["job_id"], 1)
        self.assertEqual(view["status"], report_generate_runner.STATUS_PENDING)
        self.assertEqual(view["title"], "网络安全月度态势报告", "标题应已 strip")

    def test_bad_format_is_rejected_before_queueing(self):
        resp = self.service.submit_generate(SUPER_ADMIN, title="测试报告", format="docx")

        self.assertEqual(resp.code, 400)
        self.assertEqual(report_generate_runner._queue.qsize(), 0, "参数不对不该入队")

    def test_blank_title_is_rejected_before_queueing(self):
        resp = self.service.submit_generate(SUPER_ADMIN, title="   ")

        self.assertEqual(resp.code, 400)
        self.assertEqual(report_generate_runner._queue.qsize(), 0)

    def test_scheduled_without_interval_is_rejected(self):
        resp = self.service.submit_generate(
            SUPER_ADMIN, title="测试报告", scheduled=True, interval_days=None
        )

        self.assertEqual(resp.code, 400)
        self.assertEqual(report_generate_runner._queue.qsize(), 0)

    def test_anonymous_is_rejected(self):
        resp = self.service.submit_generate(None, title="测试报告")

        self.assertEqual(resp.code, 403)
        self.assertEqual(report_generate_runner._queue.qsize(), 0)

    def test_runner_disabled_returns_503(self):
        with patch("app.services.report_generate_runner.is_running", return_value=False):
            resp = self.service.submit_generate(SUPER_ADMIN, title="测试报告")

        self.assertEqual(resp.code, 503)
        self.assertEqual(report_generate_runner._queue.qsize(), 0, "未启动时不该入队")

    def test_unknown_job_is_404(self):
        self.assertEqual(self.service.get_generate_job(SUPER_ADMIN, "nope").code, 404)

    def test_other_users_job_is_404(self):
        job_id = report_generate_runner.create_job(1, "测试报告", {})
        other = SimpleNamespace(id=2, role="SUPER_ADMIN", status="ENABLED")

        self.assertEqual(self.service.get_generate_job(other, job_id).code, 404)
        self.assertEqual(self.service.list_generate_jobs(other).data, [])


class RouteWiringTests(unittest.TestCase):
    def test_async_routes_registered_alongside_the_old_generate_route(self):
        from app.main import app

        paths = app.openapi()["paths"]
        self.assertIn("/api/v1/reports/generate/jobs", paths)
        self.assertIn("/api/v1/reports/generate/jobs/{job_id}", paths)
        self.assertIn("/api/v1/reports/generate", paths, "老同步接口必须留着做回退")
        self.assertIn("post", paths["/api/v1/reports/generate/jobs"])
        self.assertIn("get", paths["/api/v1/reports/generate/jobs"])


if __name__ == "__main__":
    unittest.main()
