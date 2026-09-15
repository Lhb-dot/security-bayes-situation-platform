import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services.training_executor import _request_train
from app.services.model_version_service import ModelVersionService


class TrainingMetricsContractTests(unittest.TestCase):
    def _response(self, metrics):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"success": True, "metrics": metrics}
        return response

    def test_quality_metrics_are_forwarded_as_numbers(self):
        metrics = {
            "accuracy": 0.91,
            "precision": 0.9,
            "recall": 0.88,
            "f1": 0.89,
            "specificity": 0.94,
            "g_mean": 0.91,
            "risk_recall": 0.86,
            "risk_f1": 0.84,
            "cv_mean": 0.87,
            "cv_std": 0.03,
            "quality_availability": {
                "risk_recall": {"available": True, "reason": None},
                "risk_f1": {"available": True, "reason": None},
                "cv_mean": {"available": True, "reason": None},
                "cv_std": {"available": True, "reason": None},
            },
        }
        with patch("app.services.training_executor.os.path.exists", return_value=True), \
                patch("app.services.training_executor.requests.post", return_value=self._response(metrics)):
            result = _request_train("http://java", "PMWNB", "dataset.arff", "model.bin", risk_labels=["risk"])

        self.assertEqual(result["risk_recall"], 0.86)
        self.assertEqual(result["risk_f1"], 0.84)
        self.assertEqual(result["cv_mean"], 0.87)
        self.assertEqual(result["cv_std"], 0.03)
        self.assertTrue(result["quality_availability"]["cv_mean"]["available"])

    def test_missing_quality_metrics_remain_null_instead_of_zero(self):
        metrics = {
            "accuracy": 0.5,
            "precision": 0.5,
            "recall": 0.5,
            "f1": 0.5,
        }
        with patch("app.services.training_executor.os.path.exists", return_value=True), \
                patch("app.services.training_executor.requests.post", return_value=self._response(metrics)):
            result = _request_train("http://java", "A2WNB", "dataset.arff", "model.bin")

        self.assertIsNone(result["specificity"])
        self.assertIsNone(result["g_mean"])
        self.assertIsNone(result["risk_recall"])
        self.assertIsNone(result["risk_f1"])
        self.assertIsNone(result["cv_mean"])
        self.assertIsNone(result["cv_std"])
        self.assertEqual(result["quality_availability"], {})
        for key in ("specificity", "g_mean", "risk_recall", "risk_f1", "cv_mean", "cv_std"):
            self.assertNotEqual(result[key], 0.0)

    def test_model_comparison_hides_internal_metrics_for_scenario_user(self):
        service = ModelVersionService.__new__(ModelVersionService)
        model = SimpleNamespace(evaluation_metrics={
            "accuracy": 0.8,
            "risk_recall": 0.7,
            "risk_f1": 0.6,
            "cv_mean": 0.75,
            "cv_std": 0.04,
        })
        user = SimpleNamespace(role="SCENARIO_USER")
        admin = SimpleNamespace(role="SCENARIO_ADMIN")

        self.assertNotIn("risk_f1", service._visible_metrics(model, user))
        self.assertNotIn("cv_std", service._visible_metrics(model, user))
        self.assertEqual(service._visible_metrics(model, admin)["risk_f1"], 0.6)


if __name__ == "__main__":
    unittest.main()
