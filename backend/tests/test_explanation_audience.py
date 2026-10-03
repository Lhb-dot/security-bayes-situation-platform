"""AI 研判产物按受众分格：管理员版不会被场景用户重新生成时覆盖。

改造前 ``ai_explanation`` 是单格，任何有权限看这条记录的人生成都会覆盖它。
现在按 management / user 分格，且老的单格结构读时兼容、写时展开。
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.constants import (  # noqa: E402
    EVALUATION_AUDIENCE_MANAGEMENT,
    EVALUATION_AUDIENCE_USER,
)
from app.services.inference_record_service import (  # noqa: E402
    InferenceRecordService,
    _explanation_artifact_for,
    _explanation_artifacts,
)

ADMIN = SimpleNamespace(id=1, role="SUPER_ADMIN", status="ENABLED")
OWNER = SimpleNamespace(id=9, role="SCENARIO_USER", status="ENABLED")
OTHER = SimpleNamespace(id=10, role="SCENARIO_USER", status="ENABLED")

FULL_EXPLANATION = {
    "contract_version": "1.0",
    "prediction": "anomaly",
    "prediction_is_risk": True,
    "risk_probability": 0.91,
    "risk_threshold": 0.5,
    "confidence": "高",
    "top_features": [
        {"feature_name": f"f{i}", "contribution": 0.4 - i / 100, "direction": "支持风险", "rank": i + 1}
        for i in range(5)
    ],
    "conflict": {"has_conflict": False, "description": "各模块判断基本一致"},
    "scenario": {"scenario_code": "network_security", "scenario_name": "网络安全"},
    "recommended_actions": ["核查异常端口"],
    "model_quality": {"cv_mean": 0.95, "cv_std": 0.01},
    "algorithm_details": {"algorithm_code": "DIWNB", "views": [{"name": "v1"}]},
    "input_snapshot": {"src_ip": "1.2.3.4"},
}


class AudienceDb:
    """最小假 Session：够 _require_record_access 与保存链路走通。"""

    def __init__(self, record, model, dataset, setting=None):
        self.record = record
        self.model = model
        self.dataset = dataset
        self.setting = setting
        self.commits = 0

    def get(self, model_type, identifier):
        name = getattr(model_type, "__name__", "")
        if name == "InferenceRecord":
            return self.record if identifier == self.record.id else None
        if name == "ModelVersion":
            return self.model if identifier == self.model.id else None
        if name == "Dataset":
            return self.dataset if identifier == self.dataset.id else None
        if name == "UserAISetting":
            return self.setting
        return None

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def make_world(explain_data=None):
    dataset = SimpleNamespace(id=7, visibility="platform", logical_id="net", version=1)
    model = SimpleNamespace(
        id=34,
        dataset_id=7,
        scenario_id=1,
        scenario=SimpleNamespace(code="network_security"),
    )
    record = SimpleNamespace(
        id=101,
        user_id=9,
        model_version_id=34,
        explain_data=dict(explain_data or {}),
        input_features={"src_ip": "1.2.3.4"},
        prediction_label="anomaly",
        is_risk_event=True,
        risk_score=0.91,
    )
    return record, model, dataset


class LegacyStructureTests(unittest.TestCase):
    """改造前落库的单格产物必须还能读出来，否则历史评价会凭空消失。"""

    LEGACY = {"ai_explanation": {"markdown": "老正文", "source": "ai", "generated_at": "t"}}

    def test_legacy_slot_is_visible_to_both_audiences(self):
        for role in ("SUPER_ADMIN", "SCENARIO_ADMIN", "SCENARIO_USER"):
            self.assertEqual(_explanation_artifact_for(self.LEGACY, role)["markdown"], "老正文")

    def test_legacy_slot_expands_into_two_slots_on_write(self):
        artifacts = _explanation_artifacts(self.LEGACY)
        self.assertEqual(
            set(artifacts), {EVALUATION_AUDIENCE_MANAGEMENT, EVALUATION_AUDIENCE_USER}
        )
        self.assertEqual(artifacts[EVALUATION_AUDIENCE_USER]["markdown"], "老正文")


class AudienceIsolationTests(unittest.TestCase):
    def _service(self, explain_data=None):
        record, model, dataset = make_world(explain_data)
        return InferenceRecordService(AudienceDb(record, model, dataset)), record

    def test_slots_do_not_overwrite_each_other(self):
        service, record = self._service()
        service.save_generated_explanation(ADMIN, 101, "管理员正文", "ai", {"facts": "admin"})
        service.save_generated_explanation(OWNER, 101, "用户正文", "ai", {"facts": "user"})

        artifacts = record.explain_data["ai_explanation"]
        self.assertEqual(artifacts[EVALUATION_AUDIENCE_MANAGEMENT]["markdown"], "管理员正文")
        self.assertEqual(artifacts[EVALUATION_AUDIENCE_USER]["markdown"], "用户正文")

    def test_saved_artifact_is_scoped_by_role(self):
        service, record = self._service()
        service.save_generated_explanation(ADMIN, 101, "管理员正文", "ai", {})

        self.assertTrue(service._saved_explanation_for_role(record, "SUPER_ADMIN")["available"])
        self.assertFalse(service._saved_explanation_for_role(record, "SCENARIO_USER")["available"])

    def test_facts_snapshot_stays_manager_only(self):
        service, record = self._service()
        service.save_generated_explanation(ADMIN, 101, "管理员正文", "ai", {"facts": 1})

        self.assertIn("data_snapshot", service._saved_explanation_for_role(record, "SUPER_ADMIN"))
        self.assertNotIn("data_snapshot", service._saved_explanation_for_role(record, "SCENARIO_USER"))

    def test_metadata_records_who_generated_it(self):
        service, record = self._service()
        service.save_generated_explanation(OWNER, 101, "用户正文", "ai", {})

        artifact = record.explain_data["ai_explanation"][EVALUATION_AUDIENCE_USER]
        self.assertEqual(artifact["generated_by"], OWNER.id)
        self.assertEqual(artifact["prompt_version"], "1.0")

    def test_other_user_cannot_write(self):
        service, record = self._service()
        response = service.save_generated_explanation(OTHER, 101, "越权正文", "ai", {})

        self.assertEqual(response.code, 403)
        self.assertNotIn("ai_explanation", record.explain_data or {})


class ExplanationSourceAudienceTests(unittest.TestCase):
    """喂给 AI 的事实也要按受众裁剪，否则正文会把算法内部明细写给普通用户。"""

    def _sources(self):
        record, model, dataset = make_world({"ai_explanation": {}, **FULL_EXPLANATION})
        service = InferenceRecordService(AudienceDb(record, model, dataset))
        return (
            service.get_explanation_source(ADMIN, 101).data,
            service.get_explanation_source(OWNER, 101).data,
        )

    def test_algorithm_details_are_admin_only(self):
        admin, user = self._sources()
        self.assertTrue(admin["algorithm_details"])
        self.assertEqual(user["algorithm_details"], {})
        self.assertNotIn("algorithm_details", user["model_result"])

    def test_quality_metrics_and_input_snapshot_are_admin_only(self):
        admin, user = self._sources()
        self.assertIn("model_quality", admin["model_result"])
        self.assertIn("input_snapshot", admin["model_result"])
        self.assertNotIn("model_quality", user["model_result"])
        self.assertNotIn("input_snapshot", user["model_result"])

    def test_top_features_are_trimmed_for_users(self):
        admin, user = self._sources()
        self.assertEqual(len(admin["model_result"]["top_features"]), 5)
        self.assertEqual(len(user["model_result"]["top_features"]), 3)


if __name__ == "__main__":
    unittest.main()
