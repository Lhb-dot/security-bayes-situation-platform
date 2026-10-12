import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services.constants import ROLE_SCENARIO_ADMIN
from app.services.dataset_analysis_service import (
    DatasetAnalysisService,
    build_algorithm_catalog,
    build_dataset_profile,
    fallback_dataset_analysis,
)


NUMERIC_FIELDS = [
    {"name": "slope", "role": "feature", "type": "numeric", "enum_values": [], "sample_values": ["1.2"]},
    {"name": "rain", "role": "feature", "type": "numeric", "enum_values": [], "sample_values": ["5"]},
    {"name": "label", "role": "label", "type": "enum", "enum_values": ["0", "1"], "sample_values": ["0"]},
]

DISCRETE_FIELDS = [
    {"name": "lithology", "role": "feature", "type": "enum", "enum_values": ["a", "b"], "sample_values": ["a"]},
    {"name": "label", "role": "label", "type": "enum", "enum_values": ["0", "1"], "sample_values": ["0"]},
]


def _dataset(fields):
    return SimpleNamespace(
        id=11,
        logical_id="dis_demo",
        version=1,
        label_field="label",
        fields_schema=fields,
        scenario_id=3,
        visibility="platform",
        file_path="data/geological_risk/dis_demo.arff",
        scenario=SimpleNamespace(code="geological_risk", name="地质风险"),
    )


def _algorithms():
    rows = []
    for index, code in enumerate(("A2WNB", "MAWNB", "EMAWNB", "CAVWNB", "PMWNB", "DIWNB"), start=1):
        rows.append(
            SimpleNamespace(
                id=index,
                code=code,
                display_name=f"{code} 名称",
                description=f"{code} 说明",
                param_schema=[{"name": "discrete_bins", "type": "int"}],
                status="AVAILABLE",
            )
        )
    return rows


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeDb:
    def __init__(self, dataset, setting=None, algorithms=None):
        self.dataset = dataset
        self.setting = setting
        self.algorithms = algorithms or []

    def get(self, model, _key):
        name = getattr(model, "__name__", "")
        if name == "Dataset":
            return self.dataset
        if name == "UserAISetting":
            return self.setting
        return None

    def scalars(self, _stmt):
        return _Scalars(self.algorithms)

    def refresh(self, _obj, **_kwargs):
        return None

    def commit(self):
        return None


class DatasetAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=7, role=ROLE_SCENARIO_ADMIN, scenario_id=3, status="ENABLED")

    def test_profile_counts_numeric_and_discrete_features(self):
        profile = build_dataset_profile(_dataset(NUMERIC_FIELDS), record_count=100)
        self.assertTrue(profile["has_numeric_features"])
        self.assertEqual(profile["numeric_feature_count"], 2)
        self.assertEqual(profile["discrete_feature_count"], 0)
        self.assertEqual(profile["feature_count"], 2)
        self.assertEqual(profile["record_count"], 100)

    def test_pmwnb_excluded_when_dataset_is_all_discrete(self):
        catalog = build_algorithm_catalog(FakeDb(_dataset(DISCRETE_FIELDS), algorithms=_algorithms()), has_numeric=False)
        by_code = {item["code"]: item for item in catalog}
        self.assertFalse(by_code["PMWNB"]["applicable"])
        self.assertTrue(by_code["A2WNB"]["applicable"])
        self.assertTrue(by_code["DIWNB"]["applicable"])

    def test_string_feature_produces_caveat(self):
        fields = [
            {"name": "note", "role": "feature", "type": "string", "enum_values": [], "sample_values": ["x"]},
            {"name": "label", "role": "label", "type": "enum", "enum_values": ["0", "1"], "sample_values": ["0"]},
        ]
        profile = build_dataset_profile(_dataset(fields), record_count=5)
        self.assertEqual(profile["string_feature_count"], 1)
        self.assertTrue(any("字符串型" in item for item in profile["caveats"]))

    def test_pmwnb_applicable_when_numeric_features_present(self):
        catalog = build_algorithm_catalog(FakeDb(_dataset(NUMERIC_FIELDS), algorithms=_algorithms()), has_numeric=True)
        by_code = {item["code"]: item for item in catalog}
        self.assertTrue(by_code["PMWNB"]["applicable"])

    def test_unconfigured_ai_falls_back_to_rule_template(self):
        db = FakeDb(_dataset(NUMERIC_FIELDS), algorithms=_algorithms())
        with patch("app.services.dataset_service.DatasetService._count_records", return_value=0):
            events = list(DatasetAnalysisService(db).stream(self.user, 11))
        self.assertEqual(events[0], ("start", {"status": "开始解析数据集"}))
        self.assertEqual(events[1][0], "error")
        self.assertTrue(any(event == "delta" for event, _ in events))
        self.assertEqual(events[-1][1]["source"], "fallback")

    def test_get_analysis_reports_unavailable_before_first_run(self):
        db = FakeDb(_dataset(NUMERIC_FIELDS), algorithms=_algorithms())
        response = DatasetAnalysisService(db).get_analysis(self.user, 11)
        self.assertEqual(response.code, 0)
        self.assertFalse(response.data["available"])
        self.assertIsNone(response.data["markdown"])

    def test_second_stream_reuses_saved_analysis_without_ai(self):
        dataset = _dataset(NUMERIC_FIELDS)
        db = FakeDb(dataset, algorithms=_algorithms())
        with patch("app.services.dataset_service.DatasetService._count_records", return_value=0):
            first = list(DatasetAnalysisService(db).stream(self.user, 11))
        self.assertEqual(first[-1][1]["source"], "fallback")
        # 未要求重算且事实未变：第二次应直接下发缓存，不再走 AI/规则模板。
        with patch(
            "app.services.dataset_analysis_service._openai_stream",
            side_effect=AssertionError("cached path must not call the provider"),
        ):
            second = list(DatasetAnalysisService(db).stream(self.user, 11))
        self.assertEqual(second[-1], ("done", {"status": "已读取已保存的解析结果", "source": "cached"}))
        self.assertTrue(all(event != "error" for event, _ in second))

    def test_ai_stream_marks_source_ai(self):
        setting = SimpleNamespace(enabled=True, model="mock-model")
        db = FakeDb(_dataset(NUMERIC_FIELDS), setting=setting, algorithms=_algorithms())
        with patch("app.services.dataset_service.DatasetService._count_records", return_value=0), patch(
            "app.services.dataset_analysis_service._openai_stream",
            return_value=[("content", "### 数据集特征概览\n\n结论")],
        ):
            events = list(DatasetAnalysisService(db).stream(self.user, 11))
        self.assertEqual(events[-1], ("done", {"status": "数据集解析完成", "source": "ai"}))
        self.assertNotIn("error", [event for event, _ in events])

    def test_fallback_markdown_lists_recommendation_and_exclusion(self):
        facts = {
            "dataset": {
                "name": "dis_demo",
                "logical_id": "dis_demo",
                "version": 1,
                "scenario": {"name": "地质风险"},
                "record_count": 10,
                "field_count": 2,
                "feature_count": 1,
                "label_field": "label",
                "numeric_feature_count": 0,
                "discrete_feature_count": 1,
                "string_feature_count": 0,
            },
            "algorithms": [
                {"code": "A2WNB", "name": "A2WNB 名称", "applicable": True, "applicability_reason": "可用"},
                {"code": "PMWNB", "name": "PMWNB 名称", "applicable": False, "applicability_reason": "不适用"},
            ],
        }
        markdown = fallback_dataset_analysis(facts)
        self.assertIn("### 推荐算法", markdown)
        self.assertIn("### 不适用算法", markdown)
        self.assertIn("PMWNB", markdown)


if __name__ == "__main__":
    unittest.main()
