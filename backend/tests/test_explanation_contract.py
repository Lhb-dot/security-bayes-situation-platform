import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.schemas.explanation_contract import (
    ALGORITHM_CODES,
    EXPLANATION_CONTRACT_VERSION,
    algorithm_specific_template,
    explanation_for_role,
    normalize_explanation,
    prediction_snapshot,
    validate_explanation_contract,
)


class ExplanationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = Path(__file__).parent / "fixtures" / "unified_explanation_samples.json"
        cls.samples = json.loads(fixture.read_text(encoding="utf-8"))

    def test_all_six_algorithms_have_standard_samples(self):
        self.assertEqual(
            {case["algorithm_code"] for case in self.samples["cases"]},
            {"A2WNB", "MAWNB", "EMAWNB", "CAVWNB", "PMWNB", "DIWNB"},
        )
        self.assertEqual(self.samples["contract_version"], EXPLANATION_CONTRACT_VERSION)

    def test_all_six_algorithm_specific_shapes_are_frozen(self):
        self.assertEqual(
            set(ALGORITHM_CODES),
            {case["algorithm_code"] for case in self.samples["cases"]},
        )
        required = {
            "A2WNB": {"original_attributes", "enhanced_attributes", "probability_change", "rode"},
            "MAWNB": {"original_view", "spode_view", "random_forest_view"},
            "EMAWNB": {"dynamic_view_weights", "before_fusion", "after_fusion", "view_conflict"},
            "CAVWNB": {"feature_evidence"},
            "PMWNB": {"submodels", "risk_support_count", "disagreement"},
            "DIWNB": {"original_view", "knn_view", "k", "neighbor_risk_ratio", "neighbor_class_ratios", "consistency"},
        }
        for code, fields in required.items():
            self.assertTrue(fields.issubset(algorithm_specific_template(code)))

    def test_prediction_snapshot_is_unchanged_by_explanation_contract(self):
        for case in self.samples["cases"]:
            with self.subTest(algorithm=case["algorithm_code"]):
                self.assertEqual(
                    prediction_snapshot(case["prediction_before"]),
                    prediction_snapshot(case["prediction_after"]),
                )

    def test_normalized_explanation_has_fixed_fields_and_missing_shape(self):
        explanation = normalize_explanation({
            "prediction": "anomaly",
            "prediction_is_risk": True,
            "algorithm_details": {"specific": {"available": False, "reason": "not wired"}},
        })
        self.assertEqual(validate_explanation_contract(explanation), [])
        self.assertEqual(explanation["model_quality"]["availability"]["cv_mean"], {
            "available": False,
            "reason": "训练结果未提供交叉验证均值",
        })

    def test_java_details_envelope_is_unwrapped_without_losing_shape(self):
        explanation = normalize_explanation({
            "prediction": "anomaly",
            "algorithm_details": {
                "algorithm_code": "PMWNB",
                "availability": {"available": True, "reason": None},
                "specific": {
                    "submodels": [{"predicted_label": "anomaly"}],
                    "risk_support_count": 1,
                    "disagreement": {"has_conflict": False},
                    "available": True,
                },
            },
        })
        specific = explanation["algorithm_details"]["specific"]
        self.assertEqual(specific["submodels"], [{"predicted_label": "anomaly"}])
        self.assertEqual(explanation["algorithm_details"]["algorithm_code"], "PMWNB")
        self.assertTrue(explanation["algorithm_details"]["availability"]["available"])

    def test_role_visibility_is_explicit(self):
        explanation = normalize_explanation({
            "prediction": "anomaly",
            "top_features": [{"feature_name": str(i)} for i in range(5)],
            "model_quality": {"risk_f1": 0.8},
            "input_snapshot": {"secret": "value"},
        })
        user = explanation_for_role(explanation, "SCENARIO_USER")
        admin = explanation_for_role(explanation, "SCENARIO_ADMIN")
        self.assertEqual(len(user["top_features"]), 3)
        self.assertNotIn("model_quality", user)
        self.assertNotIn("input_snapshot", user)
        self.assertIn("model_quality", admin)
        self.assertIn("input_snapshot", admin)


if __name__ == "__main__":
    unittest.main()
