import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services.base import ServiceError  # noqa: E402
from app.services.report_service import ReportService  # noqa: E402


class ScopeDb:
    def __init__(self, users):
        self.users = users

    def get(self, model_type, identifier):
        if getattr(model_type, "__name__", "") != "AppUser":
            return None
        return self.users.get(identifier)


class ReportScopeTests(unittest.TestCase):
    def test_scenario_user_is_forced_to_own_scope_for_generated_reports(self):
        user = SimpleNamespace(id=7, role="SCENARIO_USER", scenario_id=3)
        service = ReportService(ScopeDb({}))

        result = service._resolve_generation_scope(
            user,
            scenario_id=3,
            scope="all",
            target_user_id=99,
            force_user_scope=True,
        )

        self.assertEqual(result, ("SCENARIO_USER", 3, "self", 7))

    def test_scenario_admin_can_target_only_users_in_bound_scenario(self):
        admin = SimpleNamespace(id=2, role="SCENARIO_ADMIN", scenario_id=3)
        target = SimpleNamespace(id=9, scenario_id=4)
        service = ReportService(ScopeDb({9: target}))

        with self.assertRaisesRegex(ServiceError, "只能指定本人绑定场景内的用户"):
            service._resolve_generation_scope(
                admin,
                scenario_id=3,
                scope="user",
                target_user_id=9,
            )

    def test_super_admin_missing_target_is_rejected(self):
        admin = SimpleNamespace(id=1, role="SUPER_ADMIN", scenario_id=None)
        service = ReportService(ScopeDb({}))

        with self.assertRaisesRegex(ServiceError, "目标用户不存在"):
            service._resolve_generation_scope(
                admin,
                scenario_id=None,
                scope="all",
                target_user_id=404,
            )


if __name__ == "__main__":
    unittest.main()
