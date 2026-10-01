"""API v1 端点路由包。

每个文件对应一个 Service（15 个路由模块）：
- user_routes.py            → UserService               → /api/v1/users
- scenario_routes.py        → ScenarioService           → /api/v1/scenarios
- dataset_routes.py         → DatasetService            → /api/v1/datasets
- algorithm_routes.py       → AlgorithmService          → /api/v1/algorithms
- model_version_routes.py   → ModelVersionService       → /api/v1/model-versions
- inference_record_routes.py→ InferenceRecordService    → /api/v1/inference-records
- risk_event_routes.py      → RiskEventService          → /api/v1/risk-events
- risk_threshold_routes.py  → RiskThresholdService      → /api/v1/risk-thresholds
- report_routes.py          → ReportService             → /api/v1/reports
- auth_routes.py            → 身份认证（登录 / 登出 / 当前用户） → /api/v1/auth
- dashboard_routes.py       → DashboardService          → /api/v1/dashboard
- model_evaluation_routes.py→ ModelEvaluationService    → /api/v1/model-versions（模型评价）
- ai_setting_routes.py      → AISettingService          → /api/v1/settings/ai
- situation_routes.py       → SituationSnapshotService  → /api/v1/situation
- explanation_routes.py     → 模型解释（流式生成）        → /api/v1（无统一前缀）
"""
