"""API v1 端点路由包。

每个文件对应一个 Service（9 个核心资源）：
- user_routes.py            → UserService            → /api/v1/users
- scenario_routes.py        → ScenarioService        → /api/v1/scenarios
- dataset_routes.py         → DatasetService         → /api/v1/datasets
- algorithm_routes.py       → AlgorithmService       → /api/v1/algorithms
- model_version_routes.py   → ModelVersionService    → /api/v1/model-versions
- inference_record_routes.py→ InferenceRecordService → /api/v1/inference-records
- risk_event_routes.py      → RiskEventService       → /api/v1/risk-events
- risk_threshold_routes.py  → RiskThresholdService   → /api/v1/risk-thresholds
- report_routes.py          → ReportService          → /api/v1/reports
"""
