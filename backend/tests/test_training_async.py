"""训练异步化测试：状态流转、失败指标形状、僵尸 TRAINING 兜底。

改动前 tests/ 没有覆盖训练状态流转与失败路径，而这两块正是异步化要碰的地方：
- 失败时 evaluation_metrics 必须带 source="error"（前端 isRealTrain 读它）；
- 进程重启后停在 TRAINING 的版本必须能被兜底清理。

不连真实数据库：用最小会话桩，与 test_report_content.py 的做法一致。
"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services import training_runner  # noqa: E402
from app.services.model_version_service import ModelVersionService  # noqa: E402


class FakeDb:
    """最小会话桩：只实现训练路径用到的 get / scalars / commit / rollback / close。"""

    def __init__(self, model=None, algorithm=None, stale=()):
        self.model = model
        self.algorithm = algorithm
        self.stale = list(stale)
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def get(self, model_type, _identifier):
        name = getattr(model_type, "__name__", "")
        if name == "ModelVersion":
            return self.model
        if name == "Algorithm":
            return self.algorithm
        return None

    def scalars(self, _stmt):
        return SimpleNamespace(all=lambda: list(self.stale))

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def make_model(**overrides):
    data = {
        "id": 7,
        "status": "TRAINING",
        "dataset_id": 1,
        "algorithm_id": 2,
        "training_parameters": {"alpha": 1},
        "evaluation_metrics": {},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_service(model):
    return ModelVersionService(FakeDb(model=model, algorithm=SimpleNamespace(code="PMWNB")))


CREATED = SimpleNamespace(code=0, message="训练启动", data={"id": 7, "status": "TRAINING"})


class SyncTrainingRegressionTests(unittest.TestCase):
    """train_and_save 抽公共方法后行为必须与改动前一致。"""

    def test_success_still_marks_draft_with_metrics(self):
        model = make_model()
        service = make_service(model)
        with patch.object(ModelVersionService, "create", return_value=CREATED), \
                patch.object(ModelVersionService, "_run_algorithm_training", return_value={"accuracy": 0.9}), \
                patch.object(ModelVersionService, "_to_dict", return_value={"id": 7}), \
                patch("app.services.model_evaluation_service.build_model_attributes", return_value={"k": "v"}):
            resp = service.train_and_save(SimpleNamespace(id=1), 1, 1, 2, {})

        self.assertEqual(resp.code, 0)
        self.assertEqual(resp.message, "训练完成，模型进入 DRAFT 待发布")
        self.assertEqual(model.status, "DRAFT")
        self.assertEqual(model.evaluation_metrics, {"accuracy": 0.9})
        self.assertEqual(model.model_attributes, {"k": "v"})

    def test_failure_still_returns_500_and_writes_error_source(self):
        model = make_model()
        service = make_service(model)
        with patch.object(ModelVersionService, "create", return_value=CREATED), \
                patch.object(ModelVersionService, "_run_algorithm_training",
                             side_effect=RuntimeError("java 不可达")):
            resp = service.train_and_save(SimpleNamespace(id=1), 1, 1, 2, {})

        self.assertEqual(resp.code, 500)
        self.assertEqual(resp.message, "训练失败：java 不可达")
        self.assertEqual(model.status, "FAILED")
        self.assertEqual(model.evaluation_metrics, {"source": "error", "error": "java 不可达"})


class AsyncSubmissionTests(unittest.TestCase):
    def test_returns_training_immediately_without_running_training(self):
        model = make_model()
        service = make_service(model)
        submitted = []
        with patch.object(ModelVersionService, "create", return_value=CREATED), \
                patch.object(ModelVersionService, "_run_algorithm_training",
                             side_effect=AssertionError("异步路径不应在请求线程里训练")), \
                patch("app.services.training_runner.is_running", return_value=True), \
                patch("app.services.training_runner.submit",
                      side_effect=lambda model_id: submitted.append(model_id) is None):
            resp = service.train_and_save_async(SimpleNamespace(id=1), 1, 1, 2, {})

        self.assertEqual(resp.code, 0)
        self.assertEqual(resp.message, "训练已提交，模型版本进入 TRAINING")
        self.assertEqual(resp.data["status"], "TRAINING")
        self.assertEqual(submitted, [7])

    def test_rejected_with_503_when_runner_disabled(self):
        model = make_model()
        service = make_service(model)
        with patch.object(ModelVersionService, "create",
                          side_effect=AssertionError("执行器未启用时不应建版本")), \
                patch("app.services.training_runner.is_running", return_value=False):
            resp = service.train_and_save_async(SimpleNamespace(id=1), 1, 1, 2, {})

        self.assertEqual(resp.code, 503)
        self.assertEqual(resp.message, "训练执行器未启用，无法提交后台训练")

    def test_validation_error_is_forwarded_with_its_own_code(self):
        model = make_model()
        service = make_service(model)
        rejected = SimpleNamespace(code=400, message="数据集不属于所选场景，禁止跨场景混合训练", data=None)
        with patch.object(ModelVersionService, "create", return_value=rejected), \
                patch("app.services.training_runner.is_running", return_value=True):
            resp = service.train_and_save_async(SimpleNamespace(id=1), 1, 1, 2, {})

        self.assertEqual(resp.code, 400)
        self.assertEqual(resp.message, "数据集不属于所选场景，禁止跨场景混合训练")


class BackgroundJobTests(unittest.TestCase):
    def test_success_marks_draft_and_keeps_metrics(self):
        model = make_model()
        service = make_service(model)
        with patch.object(ModelVersionService, "_run_algorithm_training", return_value={"accuracy": 0.88}), \
                patch("app.services.model_evaluation_service.build_model_attributes", return_value={"k": "v"}):
            service.run_training_job(model)

        self.assertEqual(model.status, "DRAFT")
        self.assertEqual(model.evaluation_metrics, {"accuracy": 0.88})
        self.assertEqual(model.model_attributes, {"k": "v"})

    def test_failure_does_not_raise_and_writes_error_source(self):
        model = make_model()
        service = make_service(model)
        with patch.object(ModelVersionService, "_run_algorithm_training",
                          side_effect=RuntimeError("java 不可达")):
            service.run_training_job(model)

        self.assertEqual(model.status, "FAILED")
        self.assertEqual(model.evaluation_metrics, {"source": "error", "error": "java 不可达"})

    def test_failure_with_unreachable_state_is_swallowed(self):
        model = make_model(status="DRAFT")
        service = make_service(model)
        with patch.object(ModelVersionService, "_run_algorithm_training",
                          side_effect=RuntimeError("java 不可达")):
            service.run_training_job(model)

        self.assertEqual(model.status, "DRAFT")
        self.assertEqual(service.db.rollbacks, 1)


class StaleTrainingReaperTests(unittest.TestCase):
    def _reap(self, model, stale, minutes=60):
        db = FakeDb(model=model, stale=stale)
        with patch("app.services.training_runner.SessionLocal", return_value=db):
            reaped = training_runner.reap_stale(minutes)
        self.assertTrue(db.closed)
        return reaped

    def test_old_training_row_is_marked_failed(self):
        stale = make_model(id=42, trained_at=datetime.now(timezone.utc) - timedelta(hours=3))
        self.assertEqual(self._reap(stale, [stale]), 1)
        self.assertEqual(stale.status, "FAILED")
        self.assertEqual(stale.evaluation_metrics["source"], "error")

    def test_nothing_stale_is_a_noop(self):
        db = FakeDb(stale=[])
        with patch("app.services.training_runner.SessionLocal", return_value=db):
            self.assertEqual(training_runner.reap_stale(60), 0)
        self.assertEqual(db.commits, 0)

    def test_disabled_by_zero_minutes(self):
        stale = make_model(id=42, trained_at=datetime.now(timezone.utc) - timedelta(days=1))
        db = FakeDb(model=stale, stale=[stale])
        with patch("app.services.training_runner.SessionLocal", return_value=db):
            self.assertEqual(training_runner.reap_stale(0), 0)
        self.assertEqual(stale.status, "TRAINING")
        # 关闭兜底时不连库
        self.assertFalse(db.closed)


class RunnerWiringTests(unittest.TestCase):
    def test_submit_is_rejected_before_start(self):
        self.assertFalse(training_runner.is_running())
        self.assertFalse(training_runner.submit(1))

    def test_worker_count_is_clamped_to_one_and_four(self):
        self.assertEqual(training_runner._worker_count(0), 1)
        self.assertEqual(training_runner._worker_count(2), 2)
        self.assertEqual(training_runner._worker_count(99), 4)

    def test_async_route_registered_alongside_sync_route(self):
        from app.main import app

        paths = app.openapi()["paths"]
        self.assertIn("/api/v1/model-versions/train-async", paths)
        self.assertIn("/api/v1/model-versions/train", paths)


if __name__ == "__main__":
    unittest.main()
