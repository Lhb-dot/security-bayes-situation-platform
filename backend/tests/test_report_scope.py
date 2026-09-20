"""报告数据范围（三级角色）测试。

范围规则：最外层管理员 = 全平台 / 本人；场景管理员 = 本场景全部用户 / 本人；
场景用户 = 仅本人。已取消"指定单个用户"。
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services.base import ServiceError  # noqa: E402
from app.services.report_service import ReportService  # noqa: E402


class ScopeDb:
    def get(self, model_type, identifier):
        return None


class ReportScopeTests(unittest.TestCase):
    def setUp(self):
        self.service = ReportService(ScopeDb())

    def test_scenario_user_is_always_pinned_to_own_data(self):
        user = SimpleNamespace(id=7, role="SCENARIO_USER", scenario_id=3)
        self.assertEqual(
            self.service._resolve_generation_scope(user, 3, "all"),
            ("SCENARIO_USER", 3, "self"),
        )

    def test_scenario_user_cannot_generate_for_another_scenario(self):
        user = SimpleNamespace(id=7, role="SCENARIO_USER", scenario_id=3)
        with self.assertRaisesRegex(ServiceError, "只能生成本人绑定场景的报告"):
            self.service._resolve_generation_scope(user, 4, "self")

    def test_scenario_admin_is_limited_to_bound_scenario(self):
        admin = SimpleNamespace(id=2, role="SCENARIO_ADMIN", scenario_id=3)
        with self.assertRaisesRegex(ServiceError, "只能生成本人绑定场景的报告"):
            self.service._resolve_generation_scope(admin, 4, "all")
        self.assertEqual(
            self.service._resolve_generation_scope(admin, None, "all"),
            ("SCENARIO_ADMIN", 3, "all"),
        )

    def test_super_admin_keeps_requested_scenario_and_scope(self):
        admin = SimpleNamespace(id=1, role="SUPER_ADMIN", scenario_id=None)
        self.assertEqual(
            self.service._resolve_generation_scope(admin, 5, "all"),
            ("SUPER_ADMIN", 5, "all"),
        )
        self.assertEqual(
            self.service._resolve_generation_scope(admin, None, "self"),
            ("SUPER_ADMIN", None, "self"),
        )

    def test_data_scope_label_is_role_aware(self):
        self.assertEqual(
            ReportService._data_scope_label("SCENARIO_USER", "self"), "本人个人数据"
        )
        self.assertEqual(
            ReportService._data_scope_label("SUPER_ADMIN", "all"), "全平台数据"
        )
        self.assertEqual(
            ReportService._data_scope_label("SCENARIO_ADMIN", "all"), "本场景全部用户数据"
        )


if __name__ == "__main__":
    unittest.main()
