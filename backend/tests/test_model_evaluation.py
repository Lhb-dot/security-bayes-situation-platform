import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services.model_evaluation_service import (  # noqa: E402
    ADMIN_ROLE,
    ModelEvaluationService,
    build_model_attributes,
    build_model_evaluation_facts,
    fallback_model_evaluation,
    public_model_attributes,
)
from app.services.model_version_service import ModelVersionService  # noqa: E402
from app.services.report_service import ReportService  # noqa: E402


class EvaluationDb:
    def __init__(self, model, setting=None):
        self.model = model
        self.setting = setting
        self.commits = 0

    def get(self, model_type, identifier):
        name = getattr(model_type, "__name__", "")
        if name == "ModelVersion":
            return self.model if identifier == self.model.id else None
        if name == "Dataset":
            return self.model.dataset
        if name == "UserAISetting":
            return self.setting
        if name == "AppUser":
            return self.model.trainer
        return None

    def commit(self):
        self.commits += 1


def make_model(status="PUBLISHED"):
    dataset = SimpleNamespace(
        logical_id="network-demo",
        version=1,
        label_field="risk",
        visibility="platform",
        fields_schema=[
            {"name": "src_ip", "type": "string", "role": "feature"},
            {"name": "packet_rate", "type": "numeric", "role": "feature"},
            {"name": "risk", "type": "enum", "role": "label"},
        ],
    )
    scenario = SimpleNamespace(code="network_security", name="网络安全")
    algorithm = SimpleNamespace(
        code="DIWNB", display_name="动态交互加权朴素贝叶斯", description="test", param_schema=[]
    )
    trainer = SimpleNamespace(role="SUPER_ADMIN", username="admin")
    return SimpleNamespace(
        id=34,
        status=status,
        scenario_id=1,
        dataset_id=20,
        trained_by=1,
        scenario=scenario,
        dataset=dataset,
        algorithm=algorithm,
        trainer=trainer,
        publisher=None,
        training_parameters={"k": 5},
        evaluation_metrics={
            "accuracy": 0.9,
            "precision": 0.8,
            "recall": 0.85,
            "f1": 0.82,
            "risk_recall": 0.88,
            "risk_f1": 0.81,
            "cv_mean": 0.86,
            "cv_std": 0.03,
        },
        model_attributes=None,
        ai_evaluation=None,
    )


class ModelEvaluationTests(unittest.TestCase):
    def test_attributes_are_model_facts_and_do_not_claim_feature_importance(self):
        attributes = build_model_attributes(make_model())
        self.assertEqual(attributes["model_version_id"], 34)
        self.assertEqual(attributes["algorithm"]["code"], "DIWNB")
        self.assertFalse(attributes["feature_importance"]["available"])
        self.assertEqual(len(attributes["feature_profile"]), 2)

    def test_public_view_removes_internal_model_details(self):
        public = public_model_attributes(build_model_attributes(make_model()))
        self.assertNotIn("training_parameters", public)
        self.assertNotIn("feature_importance", public)
        self.assertNotIn("cv_mean", public["quality_metrics"])
        self.assertEqual(public["algorithm"]["code"], "DIWNB")

    def test_facts_and_fallback_are_role_specific(self):
        attributes = build_model_attributes(make_model())
        admin_facts = build_model_evaluation_facts(attributes, ADMIN_ROLE)
        user_facts = build_model_evaluation_facts(attributes, "user")
        self.assertIn("training_parameters", admin_facts["model"])
        self.assertNotIn("training_parameters", user_facts["model"])
        self.assertIn("管理员", fallback_model_evaluation(admin_facts, ADMIN_ROLE))
        self.assertNotIn("CV Std", fallback_model_evaluation(user_facts, "user"))

    def test_unconfigured_stream_falls_back_and_saves_without_inference_record(self):
        model = make_model()
        db = EvaluationDb(model)
        user = SimpleNamespace(id=1, role="SUPER_ADMIN", status="ENABLED")
        events = list(ModelEvaluationService(db).stream(user, 34))
        self.assertEqual(events[0][0], "start")
        self.assertEqual(next(data for event, data in events if event == "error")["reason_code"], "not_configured")
        self.assertEqual(events[-1][1]["source"], "fallback")
        self.assertEqual((model.ai_evaluation or {}).get("management", {}).get("source"), "fallback")
        self.assertEqual(db.commits, 2)  # model attributes + evaluation; no inference record is touched

    def test_cached_stream_does_not_call_ai_again(self):
        model = make_model()
        model.model_attributes = build_model_attributes(model)
        model.ai_evaluation = {"management": {"markdown": "cached", "source": "ai"}}
        db = EvaluationDb(model)
        user = SimpleNamespace(id=1, role="SUPER_ADMIN", status="ENABLED")
        with patch("app.services.model_evaluation_service._openai_stream") as mocked:
            events = list(ModelEvaluationService(db).stream(user, 34, False))
        mocked.assert_not_called()
        self.assertEqual(events[-1], ("done", {"status": "已读取已保存模型评价", "source": "cached"}))

    def test_management_can_prepare_a_sanitized_user_evaluation(self):
        model = make_model()
        db = EvaluationDb(model, setting=SimpleNamespace(enabled=True))
        user = SimpleNamespace(id=1, role="SUPER_ADMIN", status="ENABLED")
        with patch(
            "app.services.model_evaluation_service._openai_stream",
            return_value=["### 模型能做什么\n场景提示"],
        ):
            events = list(ModelEvaluationService(db).stream(user, 34, True, "user"))
        self.assertEqual(events[-1][1]["source"], "ai")
        saved = (model.ai_evaluation or {}).get("user") or {}
        self.assertEqual(saved.get("source"), "ai")
        self.assertNotIn("training_parameters", saved.get("facts_snapshot", {}).get("model", {}))

    def test_model_version_serialization_hides_training_parameters_from_users(self):
        model = make_model()
        db = EvaluationDb(model)
        service = ModelVersionService(db)
        admin = SimpleNamespace(id=1, role="SUPER_ADMIN", status="ENABLED")
        user = SimpleNamespace(id=2, role="SCENARIO_USER", status="ENABLED")
        with patch("app.services.model_version_service.row_to_dict", side_effect=lambda *args, **kwargs: {}):
            admin_data = service._to_dict(model, admin)
            user_data = service._to_dict(model, user)
        self.assertEqual(admin_data["training_parameters"], {"k": 5})
        self.assertEqual(user_data["training_parameters"], {})

    def test_report_reuses_role_scoped_evaluation_text_only(self):
        model = make_model()
        model.ai_evaluation = {
            "management": {
                "source": "ai",
                "markdown": "管理员诊断",
                "generated_at": "2026-09-14T00:00:00+00:00",
                "facts_snapshot": {"model": {"training_parameters": {"k": 5}}},
            },
            "user": {
                "source": "ai",
                "markdown": "用户提示",
                "generated_at": "2026-09-14T00:00:00+00:00",
                "facts_snapshot": {"model": {"quality_metrics": {"f1": 0.8}}},
            },
        }
        admin = SimpleNamespace(id=1, role="SUPER_ADMIN")
        user = SimpleNamespace(id=2, role="SCENARIO_USER")
        admin_result = ReportService._model_evaluations(admin, [(None, model)])
        user_result = ReportService._model_evaluations(user, [(None, model)])
        self.assertEqual(admin_result[0]["markdown"], "管理员诊断")
        self.assertEqual(user_result[0]["markdown"], "用户提示")
        self.assertNotIn("facts_snapshot", admin_result[0])
        self.assertNotIn("facts_snapshot", user_result[0])

    def test_user_report_omits_non_published_model_evaluation(self):
        model = make_model(status="DISABLED")
        model.ai_evaluation = {"user": {"source": "ai", "markdown": "旧评价"}}
        user = SimpleNamespace(id=2, role="SCENARIO_USER")
        self.assertEqual(ReportService._model_evaluations(user, [(None, model)]), [])


if __name__ == "__main__":
    unittest.main()
