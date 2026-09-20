"""离散化参数适用性：只对含数值特征的数据集生效。

`discrete_method` / `discrete_bins` 由 Weka `Discretize` 过滤器消费，数据集本身已是
离散属性时过滤器空转（实测 bins=2 与 bins=100 的指标与模型字节几乎一致）。这些用例
锁定「纯离散数据集上不展示、不校验、不落库」这条口径。
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services.constants import (
    ALGORITHM_STATUS_AVAILABLE,
    DATASET_STATUS_ACTIVE,
    DATASET_VISIBILITY_PLATFORM,
)
from app.services.model_version_service import ModelVersionService
from app.utils.common import (
    dataset_has_numeric_features,
    strip_inapplicable_params,
    validate_params_schema,
)

DISCRETIZATION_SCHEMA = [
    {
        "name": "discrete_method",
        "type": "enum",
        "required": True,
        "default": "equal_width",
        "enum_values": ["equal_width", "equal_freq"],
        "requires_numeric_features": True,
    },
    {
        "name": "discrete_bins",
        "type": "int",
        "required": True,
        "default": 10,
        "min": 2,
        "max": 100,
        "requires_numeric_features": True,
    },
]

NUMERIC_FIELDS = [
    {"name": "duration", "role": "feature", "type": "numeric"},
    {"name": "protocol_type", "role": "feature", "type": "enum"},
    {"name": "label", "role": "label", "type": "enum"},
]
ENUM_ONLY_FIELDS = [
    {"name": "Lithology", "role": "feature", "type": "enum"},
    {"name": "Landuse", "role": "feature", "type": "enum"},
    {"name": "label", "role": "label", "type": "enum"},
]


class DatasetNumericFeatureTests(unittest.TestCase):
    def test_numeric_feature_detected(self):
        self.assertTrue(dataset_has_numeric_features(NUMERIC_FIELDS))

    def test_enum_only_dataset_has_no_numeric_feature(self):
        self.assertFalse(dataset_has_numeric_features(ENUM_ONLY_FIELDS))

    def test_label_type_is_not_counted(self):
        """标签字段即使是数值型也不算特征。"""
        self.assertFalse(
            dataset_has_numeric_features([{"name": "label", "role": "label", "type": "numeric"}])
        )

    def test_real_type_counts_as_numeric(self):
        self.assertTrue(
            dataset_has_numeric_features([{"name": "x", "role": "feature", "type": "real"}])
        )

    def test_malformed_schema_is_safe(self):
        self.assertFalse(dataset_has_numeric_features(None))
        self.assertFalse(dataset_has_numeric_features([None, "x", {}]))


class StripInapplicableParamsTests(unittest.TestCase):
    def test_enum_only_dataset_drops_discretization_params(self):
        stripped = strip_inapplicable_params(
            DISCRETIZATION_SCHEMA,
            {"discrete_method": "equal_freq", "discrete_bins": 50},
            False,
        )
        self.assertEqual(stripped, {})

    def test_numeric_dataset_keeps_params(self):
        params = {"discrete_method": "equal_freq", "discrete_bins": 50}
        self.assertEqual(strip_inapplicable_params(DISCRETIZATION_SCHEMA, params, True), params)

    def test_unrelated_params_survive(self):
        """只剔除声明了 requires_numeric_features 的参数，其余原样保留。"""
        schema = DISCRETIZATION_SCHEMA + [{"name": "objective", "type": "enum", "required": True}]
        stripped = strip_inapplicable_params(
            schema, {"discrete_bins": 10, "objective": "CLL"}, False
        )
        self.assertEqual(stripped, {"objective": "CLL"})

    def test_does_not_mutate_caller_dict(self):
        params = {"discrete_bins": 10}
        strip_inapplicable_params(DISCRETIZATION_SCHEMA, params, False)
        self.assertEqual(params, {"discrete_bins": 10})


class ValidateParamsSchemaTests(unittest.TestCase):
    def test_required_params_missing_on_numeric_dataset_fails(self):
        self.assertIsNotNone(validate_params_schema(DISCRETIZATION_SCHEMA, {}, True))

    def test_required_params_may_be_absent_on_enum_only_dataset(self):
        self.assertIsNone(validate_params_schema(DISCRETIZATION_SCHEMA, {}, False))

    def test_range_still_enforced_when_applicable(self):
        err = validate_params_schema(
            DISCRETIZATION_SCHEMA, {"discrete_method": "equal_width", "discrete_bins": 500}, True
        )
        self.assertIn("不能大于", err or "")


class TrainModelStripsDiscretizationTests(unittest.TestCase):
    """服务层：纯离散数据集训练时，落库的训练参数不含未生效的离散化参数。"""

    def _service(self, dataset, algorithm):
        service = ModelVersionService(Mock())
        service.db.get = Mock(side_effect=lambda model, pk: dataset if model.__name__ == "Dataset" else algorithm)
        service.db.add = Mock()
        service.commit = Mock()
        service._to_dict = Mock(return_value={})
        service.require_scenario_admin_of = Mock()
        service._validate_dataset_file = Mock(return_value=None)
        return service

    def _run(self, fields_schema, params):
        scenario = SimpleNamespace(id=1)
        dataset = SimpleNamespace(
            id=2,
            scenario_id=1,
            status=DATASET_STATUS_ACTIVE,
            visibility=DATASET_VISIBILITY_PLATFORM,
            fields_schema=fields_schema,
            file_path="data/x.arff",
            logical_id="x",
        )
        algorithm = SimpleNamespace(
            id=3,
            code="CAVWNB",
            status=ALGORITHM_STATUS_AVAILABLE,
            param_schema=DISCRETIZATION_SCHEMA,
        )
        service = self._service(dataset, algorithm)
        service.db.get = Mock(
            side_effect=lambda model, pk: {
                "Scenario": scenario,
                "Dataset": dataset,
                "Algorithm": algorithm,
            }[model.__name__]
        )
        user = SimpleNamespace(id=9, role="SUPER_ADMIN", status="ENABLED")
        service.create(user, 1, 2, 3, params)
        return service.db.add.call_args[0][0].training_parameters

    def test_enum_only_dataset_records_no_discretization_params(self):
        recorded = self._run(ENUM_ONLY_FIELDS, {"discrete_method": "equal_freq", "discrete_bins": 50})
        self.assertEqual(recorded, {})

    def test_numeric_dataset_records_discretization_params(self):
        params = {"discrete_method": "equal_freq", "discrete_bins": 50}
        self.assertEqual(self._run(NUMERIC_FIELDS, params), params)


if __name__ == "__main__":
    unittest.main()
