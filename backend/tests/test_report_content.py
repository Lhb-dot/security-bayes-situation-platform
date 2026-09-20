"""报告内容组装测试：不包含模型版本评价，章节编号连续。

模型评价改由模型中心单独查看/导出（见 ModelCenter 的"导出"按钮），
报告只保留统计、多视图研判、特征、趋势与 NL 结论。
"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services.report_service import ReportService  # noqa: E402


class FakeDb:
    def __init__(self, scenario=None):
        self.scenario = scenario

    def get(self, model_type, identifier):
        if getattr(model_type, "__name__", "") == "Scenario":
            return self.scenario
        return None

    def scalars(self, _stmt):
        return SimpleNamespace(all=lambda: [])


def make_record():
    return SimpleNamespace(
        # _key_events 用 record.id 去 event_map 里找事件，桩数据必须带上该字段
        id=1,
        executed_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        is_risk_event=True,
        risk_score=0.91,
        prediction_label="risk",
        explain_data={
            "probability": 0.91,
            "prediction_label": "risk",
            "views": [],
            "feature_evidence": [],
            "class_distribution": [],
        },
    )


def make_model():
    return SimpleNamespace(
        id=34,
        status="PUBLISHED",
        dataset=SimpleNamespace(logical_id="network-demo", version=1),
        algorithm=SimpleNamespace(code="DIWNB", display_name="双视图示例加权朴素贝叶斯"),
        ai_evaluation={"management": {"source": "ai", "markdown": "旧的管理员评价"}},
    )


class ReportContentTests(unittest.TestCase):
    def setUp(self):
        self.service = ReportService(FakeDb(SimpleNamespace(name="网络安全", code="network_security")))
        self.user = SimpleNamespace(id=1, role="SUPER_ADMIN", username="admin")
        self.records = [(make_record(), make_model())]

    def test_report_data_has_no_model_evaluation_section(self):
        report_data = self.service._build_report_data(
            title="测试报告",
            scenario_id=1,
            scope="all",
            role="SUPER_ADMIN",
            current_user=self.user,
            events=[],
            records=self.records,
        )
        self.assertNotIn("model_evaluations", report_data)
        self.assertIn("model_analysis", report_data)

    def test_rendered_markdown_drops_model_evaluation_and_keeps_numbering(self):
        report_data = self.service._build_report_data(
            title="测试报告",
            scenario_id=1,
            scope="all",
            role="SUPER_ADMIN",
            current_user=self.user,
            events=[],
            records=self.records,
        )
        report_data.update({"analysis_nl": "分析", "guidance_nl": "指导"})
        content = ReportService._render_content(report_data)
        self.assertNotIn("模型版本评价", content)
        self.assertNotIn("旧的管理员评价", content)
        self.assertIn("## 七、态势分析", content)
        self.assertIn("## 八、风险规避指导", content)
        self.assertIn("## 九、数据说明", content)


if __name__ == "__main__":
    unittest.main()
