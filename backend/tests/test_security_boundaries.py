import sys
import unittest
import os
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services.base import ServiceError
from app.services.inference_record_service import InferenceRecordService
from app.api.deps import get_current_session
from app.utils.auth import digest_token
from app.services.explanation_service import AISettingService, _fernet


class AccessDb:
    def __init__(self, model, dataset):
        self.model = model
        self.dataset = dataset

    def get(self, model_type, _identifier):
        name = getattr(model_type, "__name__", "")
        if name == "ModelVersion":
            return self.model
        if name == "Dataset":
            return self.dataset
        return None


def user(user_id, role, scenario_id=None):
    return SimpleNamespace(
        id=user_id,
        role=role,
        scenario_id=scenario_id,
        status="ENABLED",
    )


class SecurityBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.model = SimpleNamespace(scenario_id=10, dataset_id=20)
        self.platform_dataset = SimpleNamespace(visibility="platform")
        self.company_dataset = SimpleNamespace(visibility="company")
        self.record = SimpleNamespace(model_version_id=30, user_id=7)

    def service(self, dataset):
        return InferenceRecordService(AccessDb(self.model, dataset))

    def test_scenario_user_can_only_read_own_record(self):
        service = self.service(self.platform_dataset)
        service._require_record_access(user(7, "SCENARIO_USER", 10), self.record)
        with self.assertRaises(ServiceError) as ctx:
            service._require_record_access(user(8, "SCENARIO_USER", 10), self.record)
        self.assertEqual(ctx.exception.code, 403)

    def test_scenario_admin_is_limited_to_bound_scenario(self):
        service = self.service(self.company_dataset)
        service._require_record_access(user(9, "SCENARIO_ADMIN", 10), self.record)
        with self.assertRaises(ServiceError) as ctx:
            service._require_record_access(user(9, "SCENARIO_ADMIN", 11), self.record)
        self.assertEqual(ctx.exception.code, 403)

    def test_super_admin_cannot_read_company_dataset_records(self):
        service = self.service(self.platform_dataset)
        service._require_record_access(user(1, "SUPER_ADMIN"), self.record)
        with self.assertRaises(ServiceError) as ctx:
            self.service(self.company_dataset)._require_record_access(user(1, "SUPER_ADMIN"), self.record)
        self.assertEqual(ctx.exception.code, 403)

    def test_disabled_or_missing_user_is_rejected(self):
        with self.assertRaises(ServiceError) as ctx:
            self.service(self.platform_dataset)._require_record_access(
                SimpleNamespace(id=7, role="SCENARIO_USER", scenario_id=10, status="DISABLED"),
                self.record,
            )
        self.assertEqual(ctx.exception.code, 403)

    def test_saved_explanation_hides_private_snapshot_from_users(self):
        record = SimpleNamespace(explain_data={
            "ai_explanation": {
                "markdown": "### 研判结论\n风险",
                "source": "ai",
                "generated_at": "2026-09-14T00:00:00+00:00",
                "data_snapshot": {"sample": {"secret_feature": "private"}},
            }
        })
        public = InferenceRecordService._saved_explanation_for_role(record, "SCENARIO_USER")
        self.assertTrue(public["available"])
        self.assertNotIn("data_snapshot", public)
        admin = InferenceRecordService._saved_explanation_for_role(record, "SCENARIO_ADMIN")
        self.assertEqual(admin["data_snapshot"]["sample"]["secret_feature"], "private")

    def test_explanation_source_uses_server_record_facts(self):
        record = SimpleNamespace(
            id=55,
            model_version_id=30,
            user_id=7,
            is_risk_event=True,
            risk_score=0.91,
            prediction_label="risk",
            input_features={"server_feature": 42},
            explain_data={
                "prediction_label": "risk",
                "model_result": {"prediction_label": "forged-by-client"},
                "ai_explanation": {"markdown": "old wording"},
            },
        )

        class SourceDb(AccessDb):
            def get(self, model_type, identifier):
                name = getattr(model_type, "__name__", "")
                if name == "InferenceRecord":
                    return record
                return super().get(model_type, identifier)

        service = InferenceRecordService(SourceDb(self.model, self.platform_dataset))
        self.model.scenario = SimpleNamespace(code="network_security")
        response = service.get_explanation_source(user(7, "SCENARIO_USER", 10), 55)
        self.assertEqual(response.code, 0)
        self.assertEqual(response.data["sample"], {"server_feature": 42})
        self.assertNotIn("ai_explanation", response.data["model_result"])
        self.assertEqual(response.data["model_result"]["prediction_label"], "risk")


class _Request:
    method = "GET"

    def __init__(self, cookies):
        self.cookies = cookies


class _SessionDb:
    def __init__(self, session):
        self.session = session
        self.commits = 0

    def scalar(self, _statement):
        return self.session

    def commit(self):
        self.commits += 1


class AuthBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.pepper = "p" * 40
        os.environ["AUTH_SESSION_PEPPER"] = self.pepper
        self.session_token = "session-token"
        self.csrf_token = "csrf-token"
        self.session = SimpleNamespace(
            token_digest=digest_token(self.session_token),
            csrf_token_digest=digest_token(self.csrf_token),
            revoked_at=None,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            last_seen_at=None,
        )

    def test_unauthenticated_request_is_rejected(self):
        with patch.dict(os.environ, {"AUTH_SESSION_PEPPER": self.pepper}):
            with self.assertRaisesRegex(Exception, "未登录"):
                get_current_session(_Request({}), _SessionDb(self.session), None)

    def test_unsafe_request_requires_matching_cookie_and_header(self):
        request = _Request({"bayes_session": self.session_token, "bayes_csrf": self.csrf_token})
        request.method = "POST"
        db = _SessionDb(self.session)
        with patch.dict(os.environ, {"AUTH_SESSION_PEPPER": self.pepper}):
            with self.assertRaisesRegex(Exception, "CSRF"):
                get_current_session(request, db, "wrong-token")
            result = get_current_session(request, db, self.csrf_token)
        self.assertIs(result, self.session)
        self.assertEqual(db.commits, 1)

    def test_ai_setting_response_only_contains_masked_key(self):
        encrypted = _fernet().encrypt(b"sk-test-secret-1234").decode("utf-8")
        setting = SimpleNamespace(
            api_key_encrypted=encrypted,
            provider="openai-compatible",
            base_url="https://mock.example/v1",
            model="mock-model",
            enabled=True,
            updated_at=None,
        )

        class Db:
            def get(self, _model, _user_id):
                return setting

        with patch.dict(os.environ, {"AUTH_SESSION_PEPPER": self.pepper}):
            response = AISettingService(Db()).get(SimpleNamespace(id=7, status="ENABLED"))
        self.assertEqual(response.code, 0)
        self.assertEqual(response.data["api_key_masked"], "sk-t...1234")
        self.assertNotIn("api_key", response.data)


if __name__ == "__main__":
    unittest.main()
