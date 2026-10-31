"""API v1 端点路由包。

每个文件对应一个 Service，共 15 个路由模块。user_routes / scenario_routes /
dataset_routes / algorithm_routes / model_version_routes /
inference_record_routes / risk_event_routes / risk_threshold_routes /
report_routes / dashboard_routes / situation_routes 各自对应同名 Service，
前缀是 /api/v1/<资源复数>。auth_routes 是身份认证（登录 / 登出 / 当前用户），
挂在 /api/v1/auth；model_evaluation_routes 对应 ModelEvaluationService，挂在
/api/v1/model-versions 下做模型评价；ai_setting_routes 对应 AISettingService，
在 /api/v1/settings/ai；explanation_routes 是模型解释的流式生成，没有统一前缀。
"""
