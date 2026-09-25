"""批量研判异步化测试：任务表、进度、单条失败不影响整批、CSV 解析口径不变。

改动前 tests/ 没有覆盖批量研判的失败路径，而这正是异步化要碰的地方：
- 单条失败必须继续跑后面的（沿用原语义）；
- 任务表只在终态下发逐条明细，进行中只给计数；
- 任务表不持有 samples（终态即释放）。
"""
import os
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.schemas.common import fail, ok  # noqa: E402
from app.services import batch_inference_runner  # noqa: E402
from app.services.base import ServiceError  # noqa: E402
from app.services.inference_record_service import InferenceRecordService  # noqa: E402


class FakeDb:
    def __init__(self, user=None):
        self.user = user
        self.rollbacks = 0
        self.closed = False

    def get(self, _model_type, _identifier):
        return self.user

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


DATASET = SimpleNamespace(
    label_field="label",
    fields_schema=[
        {"name": "a", "role": "feature", "type": "numeric"},
        {"name": "label", "role": "label", "type": "enum"},
    ],
)


def make_service():
    return InferenceRecordService(FakeDb())


def target_patch():
    return patch.object(
        InferenceRecordService, "_resolve_target", return_value=(SimpleNamespace(id=1), DATASET)
    )


def hit(record_id, label="risk", probability=0.9, event_id=5):
    return ok(
        data={
            "id": record_id,
            "prediction_label": label,
            "risk_level": "高",
            "is_risk_event": event_id is not None,
            "explain_data": {"risk_probability": probability},
            "risk_event": {"id": event_id} if event_id else None,
        }
    )


class BatchLoopTests(unittest.TestCase):
    """create_batch_inference / _run_batch 的既有语义。"""

    def setUp(self):
        self.service = make_service()

    def test_single_failure_does_not_stop_the_batch(self):
        responses = [hit(11), fail(code=500, message="预测服务不可用"), hit(13, "normal", 0.1, None)]
        with target_patch(), patch.object(
            InferenceRecordService, "create_inference", side_effect=responses
        ):
            resp = self.service.create_batch_inference(
                SimpleNamespace(id=1), 1, [{"a": 1}, {"a": 2}, {"a": 3}]
            )

        self.assertEqual(resp.code, 0)
        self.assertEqual(resp.data["total"], 3)
        self.assertEqual(resp.data["succeeded"], 2)
        self.assertEqual(resp.data["failed"], 1)
        self.assertEqual(resp.data["risk_count"], 1)
        self.assertEqual([i["index"] for i in resp.data["items"]], [0, 1, 2])
        self.assertEqual(
            [i["error"] for i in resp.data["items"]], [None, "预测服务不可用", None]
        )

    def test_label_column_is_stripped_before_inference(self):
        with target_patch(), patch.object(
            InferenceRecordService, "create_inference", return_value=hit(11)
        ) as call:
            self.service.create_batch_inference(
                SimpleNamespace(id=1), 1, [{"a": 1, "label": "x"}]
            )

        self.assertEqual(call.call_args.kwargs["input_features"], {"a": 1})

    def test_progress_callback_fires_for_every_row(self):
        seen = []
        with target_patch(), patch.object(
            InferenceRecordService, "create_inference", side_effect=[hit(11), hit(12, "normal", 0.1, None)]
        ):
            self.service._run_batch(
                SimpleNamespace(id=1),
                1,
                DATASET,
                [{"a": 1}, {"a": 2}],
                on_progress=lambda p, s, f, r: seen.append((p, s, f, r)),
            )

        self.assertEqual([item[0] for item in seen], [1, 2])
        self.assertEqual(seen[-1][1], 2)

    def test_run_batch_job_returns_summary_without_response_model(self):
        with target_patch(), patch.object(
            InferenceRecordService, "create_inference", return_value=hit(11)
        ):
            summary = self.service.run_batch_job(SimpleNamespace(id=1), 1, [{"a": 1}])

        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["succeeded"], 1)
        self.assertEqual(summary["risk_count"], 1)
        self.assertEqual(len(summary["items"]), 1)

    def test_empty_samples_is_rejected(self):
        with target_patch():
            resp = self.service.create_batch_inference(SimpleNamespace(id=1), 1, [])
        self.assertEqual(resp.code, 400)
        self.assertEqual(resp.message, "没有可研判的样本")


class CsvParsingTests(unittest.TestCase):
    """CSV 解析抽成 _parse_csv_samples 后口径必须不变。"""

    def setUp(self):
        self.service = make_service()

    def test_missing_columns_message_is_unchanged(self):
        two_features = SimpleNamespace(
            label_field="label",
            fields_schema=[
                {"name": "a", "role": "feature", "type": "numeric"},
                {"name": "b", "role": "feature", "type": "numeric"},
            ],
        )
        with self.assertRaises(ServiceError) as ctx:
            self.service._parse_csv_samples(two_features, "x.csv", b"a\n1\n", 200)
        self.assertEqual(ctx.exception.code, 400)
        self.assertEqual(ctx.exception.message, "CSV 缺少字段：b")

    def test_non_csv_is_rejected(self):
        with self.assertRaises(ServiceError) as ctx:
            self.service._parse_csv_samples(DATASET, "x.xlsx", b"", 200)
        self.assertEqual(ctx.exception.message, "仅支持 .csv 文件")

    def test_truncates_to_limit_and_drops_label(self):
        samples = self.service._parse_csv_samples(
            DATASET, "x.csv", "a,label\n1,x\n2,y\n3,z\n".encode("utf-8"), 2
        )
        self.assertEqual(len(samples), 2)
        self.assertEqual(list(samples[0].keys()), ["a"])

    def test_empty_body_is_rejected(self):
        with self.assertRaises(ServiceError) as ctx:
            self.service._parse_csv_samples(DATASET, "x.csv", b"a,label\n", 200)
        self.assertEqual(ctx.exception.message, "CSV 中没有数据行")


class SubmitTests(unittest.TestCase):
    def setUp(self):
        self.service = make_service()

    def test_rejected_with_503_when_runner_disabled(self):
        with target_patch(), patch(
            "app.services.batch_inference_runner.is_running", return_value=False
        ):
            resp = self.service.submit_batch_inference(SimpleNamespace(id=9), 1, [{"a": 1}])
        self.assertEqual(resp.code, 503)

    def test_returns_job_id_when_runner_running(self):
        with target_patch(), patch(
            "app.services.batch_inference_runner.is_running", return_value=True
        ), patch("app.services.batch_inference_runner.create_job", return_value="job-1") as created:
            resp = self.service.submit_batch_inference(
                SimpleNamespace(id=9), 1, [{"a": 1}, {"a": 2}], truncated=True
            )

        self.assertEqual(resp.code, 0)
        self.assertEqual(resp.data["job_id"], "job-1")
        self.assertEqual(resp.data["total"], 2)
        self.assertTrue(resp.data["truncated"])
        self.assertEqual(created.call_args.kwargs["user_id"], 9)
        self.assertEqual(created.call_args.kwargs["model_version_id"], 1)

    def test_unknown_job_is_404(self):
        resp = self.service.get_batch_job(SimpleNamespace(id=9, status="ENABLED"), "nope")
        self.assertEqual(resp.code, 404)


class JobStoreTests(unittest.TestCase):
    def setUp(self):
        with batch_inference_runner._jobs_lock:
            batch_inference_runner._jobs.clear()

    def tearDown(self):
        with batch_inference_runner._jobs_lock:
            batch_inference_runner._jobs.clear()

    def test_job_view_hides_samples_and_detail_until_terminal(self):
        job_id = batch_inference_runner.create_job(9, 1, [{"a": 1}, {"a": 2}])
        view = batch_inference_runner.get_job(job_id, 9)

        self.assertEqual(view["status"], batch_inference_runner.STATUS_PENDING)
        self.assertEqual(view["total"], 2)
        self.assertEqual(view["processed"], 0)
        self.assertIsNone(view["result"])
        self.assertNotIn("samples", view)

    def test_job_is_not_visible_to_other_users(self):
        job_id = batch_inference_runner.create_job(9, 1, [{"a": 1}])
        self.assertIsNone(batch_inference_runner.get_job(job_id, 10))

    def test_execute_marks_done_and_releases_samples(self):
        job_id = batch_inference_runner.create_job(9, 1, [{"a": 1}, {"a": 2}])
        summary = {"total": 2, "succeeded": 2, "failed": 0, "risk_count": 1, "items": [{"index": 0}]}
        db = FakeDb(user=SimpleNamespace(id=9))
        with patch("app.db.SessionLocal", return_value=db), patch.object(
            InferenceRecordService, "run_batch_job", return_value=summary
        ) as run:
            batch_inference_runner._execute(job_id)

        view = batch_inference_runner.get_job(job_id, 9)
        self.assertEqual(view["status"], batch_inference_runner.STATUS_DONE)
        self.assertEqual(view["processed"], 2)
        self.assertEqual(view["risk_count"], 1)
        self.assertEqual(view["result"]["items"], [{"index": 0}])
        self.assertTrue(callable(run.call_args.kwargs["on_progress"]))
        self.assertTrue(db.closed)
        self.assertEqual(batch_inference_runner._jobs[job_id].samples, [])

    def test_execute_marks_failed_on_error(self):
        job_id = batch_inference_runner.create_job(9, 1, [{"a": 1}])
        db = FakeDb(user=SimpleNamespace(id=9))
        with patch("app.db.SessionLocal", return_value=db), patch.object(
            InferenceRecordService, "run_batch_job", side_effect=RuntimeError("模型不可用")
        ):
            batch_inference_runner._execute(job_id)

        view = batch_inference_runner.get_job(job_id, 9)
        self.assertEqual(view["status"], batch_inference_runner.STATUS_FAILED)
        self.assertEqual(view["error"], "模型不可用")
        self.assertEqual(db.rollbacks, 1)
        self.assertTrue(db.closed)

    def test_execute_fails_when_issuing_user_is_gone(self):
        job_id = batch_inference_runner.create_job(9, 1, [{"a": 1}])
        db = FakeDb(user=None)
        with patch("app.db.SessionLocal", return_value=db), patch.object(
            InferenceRecordService, "run_batch_job"
        ) as run:
            batch_inference_runner._execute(job_id)

        self.assertEqual(
            batch_inference_runner.get_job(job_id, 9)["status"],
            batch_inference_runner.STATUS_FAILED,
        )
        run.assert_not_called()

    def test_expired_terminal_job_is_purged_on_next_submit(self):
        stale_id = batch_inference_runner.create_job(9, 1, [{"a": 1}])
        stale = batch_inference_runner._jobs[stale_id]
        stale.status = batch_inference_runner.STATUS_DONE
        stale.finished_at = time.time() - 99999

        with patch.dict(os.environ, {"BATCH_JOB_TTL_SECONDS": "10"}):
            batch_inference_runner.create_job(9, 1, [{"a": 1}])

        self.assertIsNone(batch_inference_runner.get_job(stale_id, 9))

    def test_running_job_is_never_purged(self):
        live_id = batch_inference_runner.create_job(9, 1, [{"a": 1}])
        batch_inference_runner._jobs[live_id].created_at = time.time() - 99999

        with patch.dict(os.environ, {"BATCH_JOB_TTL_SECONDS": "10", "BATCH_JOB_MAX": "1"}):
            batch_inference_runner.create_job(9, 1, [{"a": 1}])

        self.assertIsNotNone(batch_inference_runner.get_job(live_id, 9))

    def test_submit_is_rejected_before_start(self):
        self.assertFalse(batch_inference_runner.is_running())
        self.assertIsNone(batch_inference_runner.get_job("x", 9))


class RouteWiringTests(unittest.TestCase):
    def test_async_routes_registered_alongside_sync_ones(self):
        from app.main import app

        paths = app.openapi()["paths"]
        self.assertIn("/api/v1/inference-records/predict-batch/jobs", paths)
        self.assertIn("/api/v1/inference-records/predict-batch/jobs/{job_id}", paths)
        self.assertIn("/api/v1/inference-records/predict-batch/upload/jobs", paths)
        self.assertIn("/api/v1/inference-records/predict-batch", paths)
        self.assertIn("/api/v1/inference-records/predict-batch/upload", paths)


if __name__ == "__main__":
    unittest.main()
