import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.data.scenario_feature_catalog import expand_scenario_feature_catalog
from app.schemas.scenario_config import validate_scenario_config, validate_scenario_configs
from app.services.explanation_service import CONFIG_PATH, get_scenario_config


class ScenarioConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.configs = expand_scenario_feature_catalog(
            json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        )

    def test_registered_scenario_configs_are_complete(self):
        self.assertEqual(validate_scenario_configs(self.configs), [])
        network = self.configs["network_security"]
        self.assertEqual(len(network["required_feature_names"]), 80)
        self.assertTrue(set(network["required_feature_names"]).issubset(network["feature_dictionary"]))
        for code, config in self.configs.items():
            self.assertTrue(get_scenario_config(code)["configuration_available"])
            self.assertTrue(get_scenario_config(code)["recommended_actions"])

    def test_all_non_network_scenario_catalogs_are_expanded(self):
        self.assertEqual(len(self.configs["power_system"]["required_feature_names"]), 8)
        self.assertEqual(len(self.configs["geological_risk"]["required_feature_names"]), 51)
        self.assertEqual(len(self.configs["flightdeck_operation"]["required_feature_names"]), 280)
        for code in ("power_system", "geological_risk", "flightdeck_operation"):
            config = self.configs[code]
            self.assertEqual(
                set(config["required_feature_names"]),
                set(config["feature_dictionary"]),
            )

    def test_explanation_service_exposes_expanded_catalog(self):
        expected = {"power_system": 8, "geological_risk": 51, "flightdeck_operation": 280}
        for code, count in expected.items():
            config = get_scenario_config(code)
            self.assertEqual(len(config["required_feature_names"]), count)
            self.assertEqual(len(config["feature_dictionary"]), count)

    def test_feature_metadata_requires_all_explanation_dimensions(self):
        errors = validate_scenario_config("demo", {
            "scenario_name": "演示",
            "analysis_goal": "测试",
            "risk_types": ["测试风险"],
            "recommended_actions": ["人工复核"],
            "manual_review_advice": "请复核",
            "risk_expression_template": "风险概率 {risk_probability}",
            "feature_dictionary": {"feature": {"display_name": "字段"}},
        })
        self.assertIn("demo.feature: 缺少非空字段 meaning", errors)
        self.assertIn("demo.feature: 缺少非空字段 abnormal_value_meaning", errors)

    def test_empty_actions_are_rejected(self):
        errors = validate_scenario_config("demo", {
            "scenario_name": "演示",
            "analysis_goal": "测试",
            "risk_types": ["测试风险"],
            "recommended_actions": [],
            "manual_review_advice": "请复核",
            "risk_expression_template": "风险概率 {risk_probability}",
            "feature_dictionary": {},
        })
        self.assertIn("demo: recommended_actions 必须是非空字符串数组", errors)


if __name__ == "__main__":
    unittest.main()
