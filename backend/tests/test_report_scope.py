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
            ReportService._data_scope_label("SUPER_ADMIN", "all", None), "全平台数据"
        )
        self.assertEqual(
            ReportService._data_scope_label("SCENARIO_ADMIN", "all"), "本场景全部用户数据"
        )

    def test_super_admin_label_follows_the_chosen_scenario(self):
        """超管选了具体场景，统计范围就是那一个场景，不能再标「全平台数据」。

        实测超管+场景1 与场景管理员场景1 是同一批记录，标签必须一致。
        """
        self.assertEqual(
            ReportService._data_scope_label("SUPER_ADMIN", "all", 1), "本场景全部用户数据"
        )
        self.assertEqual(
            ReportService._data_scope_label("SUPER_ADMIN", "self", 1), "本人个人数据"
        )


class CapturingDb:
    """记录下发的 SQL，用来断言过滤条件加没加。"""

    def __init__(self):
        self.statements = []

    def scalars(self, stmt):
        self.statements.append(str(stmt))
        return SimpleNamespace(all=lambda: [])

    def execute(self, stmt):
        self.statements.append(str(stmt))
        return SimpleNamespace(all=lambda: [])


class GatherFilterTests(unittest.TestCase):
    """汇总口径的两条硬约束：场景角色必须有场景；个人数据不叠数据集可见性。"""

    def setUp(self):
        self.db = CapturingDb()
        self.service = ReportService(self.db)
        self.super_admin = SimpleNamespace(id=1, role="SUPER_ADMIN", scenario_id=None)

    def test_scenario_role_without_scenario_gets_nothing(self):
        """没有绑定场景时返回空，绝不退化成「不加场景过滤」= 全平台可见。"""
        for role in ("SCENARIO_ADMIN", "SCENARIO_USER"):
            user = SimpleNamespace(id=9, role=role, scenario_id=None)
            self.assertEqual(self.service._gather_events(user, role, None, "all"), [])
            self.assertEqual(self.service._gather_records(user, role, None, "all"), [])
        self.assertEqual(self.db.statements, [], "不该下发任何查询")

    def test_super_admin_aggregate_is_limited_to_platform_datasets(self):
        self.service._gather_events(self.super_admin, "SUPER_ADMIN", None, "all")
        self.service._gather_records(self.super_admin, "SUPER_ADMIN", None, "all")

        for sql in self.db.statements:
            self.assertIn("dataset.visibility", sql)

    def test_super_admin_personal_scope_ignores_dataset_visibility(self):
        """「本人个人数据」= 自己产生的记录，不该被数据集归属筛掉。"""
        self.service._gather_events(self.super_admin, "SUPER_ADMIN", None, "self")
        self.service._gather_records(self.super_admin, "SUPER_ADMIN", None, "self")

        self.assertEqual(len(self.db.statements), 2)
        for sql in self.db.statements:
            self.assertNotIn("dataset.visibility", sql)

    def test_scenario_user_published_filter_survives_personal_scope(self):
        """可见性规则与 scope 无关：场景用户看本人数据时也只看已发布模型。"""
        user = SimpleNamespace(id=9, role="SCENARIO_USER", scenario_id=3)
        self.service._gather_records(user, "SCENARIO_USER", 3, "self")

        sql = self.db.statements[0]
        self.assertIn("model_version.status", sql)
        self.assertIn("inference_record.user_id", sql)


if __name__ == "__main__":
    unittest.main()
