"""报告内容组装测试：不包含模型版本评价，章节编号连续。

模型评价改由模型中心单独查看/导出（见 ModelCenter 的"导出"按钮），
报告只保留统计、多视图研判、特征、趋势与 NL 结论。

另含三类"口径必须说清"的回归：
- 重点风险事件的**总起数**不能拿截断后的列表长度顶替；
- 风险等级按**生成账号的阈值**判定，必须在数据说明里声明；
- 手动创建（POST /reports）不支持定时 —— 它没法在到期时按真实数据重生成。
"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services.report_nl import build_analysis_nl  # noqa: E402
from app.services.report_service import ReportService  # noqa: E402


class FakeDb:
    def __init__(self, scenario=None):
        self.scenario = scenario
        self.added = []

    def get(self, model_type, identifier):
        if getattr(model_type, "__name__", "") == "Scenario":
            return self.scenario
        return None

    def scalars(self, _stmt):
        return SimpleNamespace(all=lambda: [])

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def rollback(self):
        pass


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


def make_event(record_id, score=0.9, status="PENDING"):
    return SimpleNamespace(
        inference_record_id=record_id,
        occurred_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        risk_score=score,
        risk_level="HIGH",
        risk_type="port_scan",
        status=status,
        raw_features={"src_bytes": 1, "dst_port": 2},
        scenario_id=1,
    )


def make_records(count):
    out = []
    for i in range(1, count + 1):
        record = make_record()
        record.id = i
        out.append((record, make_model()))
    return out


def base_report_data(**overrides):
    data = {
        "report_info": {"title": "测试报告", "data_scope": "全平台数据"},
        "overview": {},
        "prediction": {},
        "model_analysis": [],
        "feature_analysis": {},
        "trend": [],
        "key_events": [],
        "key_events_total": 0,
    }
    data.update(overrides)
    return data


class KeyEventsTotalTests(unittest.TestCase):
    """重点风险事件：截断列表 + 真实总起数，两个都要给。"""

    def test_total_is_returned_alongside_the_truncated_list(self):
        records = make_records(12)
        events = [make_event(i, score=0.9 - i / 100) for i in range(1, 13)]

        items, total = ReportService._key_events(events, records, limit=10, thresholds={})

        self.assertEqual(len(items), 10)
        self.assertEqual(total, 12)
        self.assertGreaterEqual(items[0]["probability"], items[-1]["probability"])

    def test_total_equals_list_when_everything_fits(self):
        records = make_records(3)
        events = [make_event(i) for i in range(1, 4)]

        items, total = ReportService._key_events(events, records, limit=10, thresholds={})

        self.assertEqual((len(items), total), (3, 3))

    def test_markdown_says_the_real_total(self):
        records = make_records(12)
        events = [make_event(i) for i in range(1, 13)]
        items, total = ReportService._key_events(events, records, limit=10, thresholds={})

        content = ReportService._render_content(
            base_report_data(key_events=items, key_events_total=total)
        )

        self.assertIn("重点风险事件（共 12 起，下列为概率最高的 10 起）", content)
        self.assertNotIn("重点风险事件（共 10 起", content)

    def test_markdown_drops_the_breakdown_when_all_events_are_listed(self):
        records = make_records(3)
        events = [make_event(i) for i in range(1, 4)]
        items, total = ReportService._key_events(events, records, limit=10, thresholds={})

        content = ReportService._render_content(
            base_report_data(key_events=items, key_events_total=total)
        )

        self.assertIn("重点风险事件（共 3 起）：", content)

    def test_narrative_uses_total_not_the_truncated_length(self):
        text = build_analysis_nl(
            base_report_data(
                overview={"total_inferences": 100, "risk_count": 50},
                key_events=[{"risk_level": "高危", "probability": 1.0}] * 10,
                key_events_total=666,
            )
        )

        self.assertIn("共 666 起", text)
        self.assertIn("列出概率最高的 10 起", text)
        self.assertNotIn("重点风险事件 10 起", text)

    def test_narrative_stays_plain_when_all_events_are_listed(self):
        text = build_analysis_nl(
            base_report_data(
                overview={"total_inferences": 10, "risk_count": 5},
                key_events=[{"risk_level": "中危", "probability": 0.7}] * 3,
                key_events_total=3,
            )
        )

        self.assertIn("重点风险事件 3 起", text)
        self.assertNotIn("列出概率最高的", text)

    def test_legacy_report_data_claims_no_count(self):
        """修复前生成的报告没有 key_events_total：不能拿列表长度冒充总数。"""
        stub = {
            "time": "2026-09-01 12:00",
            "risk_level": "高危",
            "probability": 1.0,
            "status": "待处置",
        }
        data = base_report_data(
            overview={"total_inferences": 10, "risk_count": 5},
            key_events=[dict(stub) for _ in range(10)],
        )
        del data["key_events_total"]

        content = ReportService._render_content(data)
        text = build_analysis_nl(data)

        self.assertIn("重点风险事件：", content)
        self.assertNotIn("重点风险事件（共", content)
        self.assertNotIn("10 起", content)
        self.assertNotIn("10 起", text)


class RiskProbabilityWordingTests(unittest.TestCase):
    def test_avg_risk_prob_is_named_as_risk_sample_average(self):
        """这个均值只统计风险样本，不能写成像全样本的平均。"""
        data = base_report_data(
            overview={"total_inferences": 10, "risk_count": 4, "avg_risk_prob": 0.948}
        )

        content = ReportService._render_content(data)
        text = build_analysis_nl(data)

        self.assertIn("风险样本平均概率：0.948", content)
        self.assertIn("风险样本的平均概率为 0.948", text)
        self.assertNotIn("平均风险概率：", content)


class DataNotesThresholdTests(unittest.TestCase):
    """等级是「按你的尺子量的」，必须在数据说明里说清。"""

    def test_declares_the_account_threshold(self):
        notes = ReportService._data_notes(
            {"data_scope": "全平台数据"},
            {"total_inferences": 10},
            [],
            thresholds={1: (0.6, 0.9)},
            scenario_id=1,
        )

        self.assertIn("中危 ≥ 0.6", notes)
        self.assertIn("高危 ≥ 0.9", notes)
        self.assertIn("不同账号的阈值下", notes)
        self.assertNotIn("系统默认值", notes)

    def test_declares_the_fallback_when_unconfigured(self):
        notes = ReportService._data_notes(
            {"data_scope": "全平台数据"},
            {"total_inferences": 10},
            [],
            thresholds={},
            scenario_id=None,
        )

        self.assertIn("中危 ≥ 0.5", notes)
        self.assertIn("高危 ≥ 0.8", notes)
        self.assertIn("系统默认值", notes)


class ManualCreateTests(unittest.TestCase):
    """POST /reports 的 content 是外部给的，到期无法重生成，所以不支持定时。"""

    def setUp(self):
        self.service = ReportService(FakeDb())
        self.user = SimpleNamespace(id=1, role="SUPER_ADMIN", status="ENABLED", scenario_id=None)

    def test_scheduled_is_rejected_instead_of_silently_never_running(self):
        resp = self.service.create(
            current_user=self.user,
            title="手动报告",
            report_type="USER_SNAPSHOT",
            content="# 正文",
            scheduled=True,
            interval_days=7,
        )

        self.assertEqual(resp.code, 400)
        self.assertIn("定时报告", resp.message)

    def test_without_scheduled_it_still_works(self):
        resp = self.service.create(
            current_user=self.user,
            title="手动报告",
            report_type="USER_SNAPSHOT",
            content="# 正文",
        )

        self.assertEqual(resp.code, 0)
        self.assertFalse(resp.data["scheduled"])
        self.assertIsNone(resp.data["next_run_at"])


if __name__ == "__main__":
    unittest.main()
