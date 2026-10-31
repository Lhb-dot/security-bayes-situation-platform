"""数据集迭代（DatasetRevision）测试。

覆盖三块：
1. 迭代策略纯函数 resolve_iteration_policy 的决策矩阵（无 DB）；
2. 追加样本依赖的文件读写工具（ARFF / CSV 合并往返）；
3. DatasetService._revise 的产物 —— 原地更新 vs 新建版本。

不依赖真实数据库：用 FakeDb 承载 _revise 需要的 get / scalar / add / flush /
commit。
"""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services.dataset_iteration import (
    CHANGE_TYPE_APPEND_ROWS,
    CHANGE_TYPE_METADATA,
    CHANGE_TYPE_REPLACE_FILE,
    CHANGE_TYPE_SCHEMA_CHANGE,
    MODE_IN_PLACE,
    MODE_NEW_VERSION,
    change_type_label,
    resolve_iteration_policy,
)
from app.services.dataset_service import DatasetService
from app.utils.dataset_file_reader import read_all_rows, write_dataset_file

FIELDS = [
    {"name": "f1", "role": "feature", "type": "numeric", "enum_values": [], "sample_values": []},
    {"name": "label", "role": "label", "type": "enum", "enum_values": ["0", "1"], "sample_values": []},
]


class IterationPolicyTests(unittest.TestCase):
    def test_metadata_always_in_place(self):
        for referenced in (False, True):
            decision = resolve_iteration_policy(CHANGE_TYPE_METADATA, referenced=referenced)
            self.assertEqual(decision.mode, MODE_IN_PLACE)
            self.assertFalse(decision.is_breaking)

    def test_breaking_change_always_new_version(self):
        for referenced in (False, True):
            decision = resolve_iteration_policy(
                CHANGE_TYPE_SCHEMA_CHANGE, referenced=referenced
            )
            self.assertEqual(decision.mode, MODE_NEW_VERSION)
            self.assertTrue(decision.is_breaking)

    def test_compatible_append_in_place_when_unreferenced(self):
        decision = resolve_iteration_policy(CHANGE_TYPE_APPEND_ROWS, referenced=False)
        self.assertEqual(decision.mode, MODE_IN_PLACE)
        self.assertFalse(decision.is_breaking)

    def test_compatible_append_new_version_when_referenced(self):
        decision = resolve_iteration_policy(CHANGE_TYPE_APPEND_ROWS, referenced=True)
        self.assertEqual(decision.mode, MODE_NEW_VERSION)
        self.assertFalse(decision.is_breaking)

    def test_replace_file_breaking_only_when_schema_changed(self):
        same = resolve_iteration_policy(
            CHANGE_TYPE_REPLACE_FILE, referenced=False, schema_unchanged=True
        )
        self.assertEqual(same.mode, MODE_IN_PLACE)
        self.assertFalse(same.is_breaking)
        changed = resolve_iteration_policy(
            CHANGE_TYPE_REPLACE_FILE, referenced=False, schema_unchanged=False
        )
        self.assertEqual(changed.mode, MODE_NEW_VERSION)
        self.assertTrue(changed.is_breaking)

    def test_unknown_change_type_rejected(self):
        with self.assertRaises(ValueError):
            resolve_iteration_policy("not_a_type", referenced=False)

    def test_change_type_label_falls_back_to_raw_value(self):
        self.assertEqual(change_type_label(CHANGE_TYPE_APPEND_ROWS), "追加样本")
        self.assertEqual(change_type_label("custom"), "custom")


class FileHelperTests(unittest.TestCase):
    def test_arff_roundtrip_preserves_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "d.arff")
            write_dataset_file(path, FIELDS, [["1", "0"], ["2", "1"]], "arff")
            fields, rows = read_all_rows(path)
            self.assertEqual([f["name"] for f in fields], ["f1", "label"])
            self.assertEqual(rows, [["1", "0"], ["2", "1"]])

    def test_csv_roundtrip_preserves_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "d.csv")
            write_dataset_file(path, FIELDS, [["1", "0"]], "csv")
            fields, rows = read_all_rows(path)
            self.assertEqual([f["name"] for f in fields], ["f1", "label"])
            self.assertEqual(rows, [["1", "0"]])

    def test_arff_quotes_values_containing_comma(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "d.arff")
            write_dataset_file(path, FIELDS, [["1", "a,b"]], "arff")
            _, rows = read_all_rows(path)
            self.assertEqual(rows, [["1", "a,b"]])


class FakeDb:
    """_revise 需要的最小 Session 面：get / scalar / add / flush / commit / rollback。"""

    def __init__(self, dataset, *, referenced=False, max_version=1):
        self.dataset = dataset
        self.referenced = referenced
        self.max_version = max_version
        self.added = []
        self.commits = 0

    def get(self, model, _key):
        if getattr(model, "__name__", "") == "Dataset":
            return self.dataset
        return None

    def scalar(self, stmt):
        sql = str(stmt).lower()
        if "max(" in sql:
            return self.max_version
        if "count(" in sql:
            return 1 if self.referenced else 0
        return None

    def add(self, obj):
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = 900 + len(self.added)

    def flush(self):
        return None

    def commit(self):
        self.commits += 1

    def rollback(self):
        return None


def _dataset(**overrides):
    base = dict(
        id=11,
        logical_id="demo",
        version=1,
        scenario_id=3,
        file_path="data/demo/demo.arff",
        fields_schema=FIELDS,
        label_field="label",
        visibility="platform",
        uploader_role="SCENARIO_ADMIN",
        uploaded_by=5,
        status="ACTIVE",
        name=None,
        change_type="create",
        base_version_id=None,
        is_breaking=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _user():
    return SimpleNamespace(id=5, role="SCENARIO_ADMIN", scenario_id=3, status="ENABLED")


class ReviseServiceTests(unittest.TestCase):
    def test_unreferenced_append_updates_in_place(self):
        dataset = _dataset()
        db = FakeDb(dataset, referenced=False)
        service = DatasetService(db)

        result, decision = service._revise(
            _user(), 11, CHANGE_TYPE_APPEND_ROWS, file_path="data/demo/demo__rev1.arff"
        )

        self.assertEqual(decision.mode, MODE_IN_PLACE)
        self.assertIs(result, dataset)
        self.assertEqual(dataset.file_path, "data/demo/demo__rev1.arff")
        self.assertEqual(dataset.version, 1)  # 版本号不变
        self.assertEqual(len(db.added), 1)  # 只多了一条迭代记录
        revision = db.added[0]
        self.assertEqual(revision.change_type, CHANGE_TYPE_APPEND_ROWS)
        self.assertEqual(revision.mode, MODE_IN_PLACE)
        self.assertIsNone(revision.result_dataset_id)

    def test_referenced_append_creates_new_version(self):
        dataset = _dataset()
        db = FakeDb(dataset, referenced=True, max_version=1)
        service = DatasetService(db)

        result, decision = service._revise(
            _user(), 11, CHANGE_TYPE_APPEND_ROWS, file_path="data/demo/demo__rev2.arff"
        )

        self.assertEqual(decision.mode, MODE_NEW_VERSION)
        self.assertFalse(decision.is_breaking)
        self.assertEqual(result.version, 2)
        self.assertEqual(result.base_version_id, 11)
        self.assertEqual(result.change_type, CHANGE_TYPE_APPEND_ROWS)
        self.assertEqual(result.file_path, "data/demo/demo__rev2.arff")
        self.assertEqual(dataset.file_path, "data/demo/demo.arff")  # 旧版本文件冻结
        revisions = [o for o in db.added if o.__class__.__name__ == "DatasetRevision"]
        self.assertEqual(len(revisions), 1)
        self.assertEqual(revisions[0].result_dataset_id, result.id)

    def test_unreferenced_schema_change_still_creates_version(self):
        dataset = _dataset()
        db = FakeDb(dataset, referenced=False, max_version=1)
        service = DatasetService(db)
        new_schema = FIELDS + [
            {
                "name": "f2",
                "role": "feature",
                "type": "numeric",
                "enum_values": [],
                "sample_values": [],
            }
        ]

        result, decision = service._revise(
            _user(), 11, CHANGE_TYPE_SCHEMA_CHANGE, fields_schema=new_schema
        )

        self.assertEqual(decision.mode, MODE_NEW_VERSION)
        self.assertTrue(decision.is_breaking)
        self.assertEqual(result.version, 2)
        self.assertTrue(result.is_breaking)

    def test_metadata_change_in_place_without_version_bump(self):
        dataset = _dataset()
        db = FakeDb(dataset, referenced=True, max_version=3)
        service = DatasetService(db)

        result, decision = service._revise(_user(), 11, CHANGE_TYPE_METADATA, name="新名字")

        self.assertEqual(decision.mode, MODE_IN_PLACE)
        self.assertIs(result, dataset)
        self.assertEqual(dataset.name, "新名字")
        self.assertEqual(dataset.version, 1)

    def test_unknown_change_type_raises_service_error(self):
        service = DatasetService(FakeDb(_dataset()))
        with self.assertRaises(Exception) as ctx:
            service._revise(_user(), 11, "not_a_type")
        self.assertEqual(getattr(ctx.exception, "code", None), 400)


if __name__ == "__main__":
    unittest.main()