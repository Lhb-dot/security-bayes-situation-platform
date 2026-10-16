# 现有后端能力对应表

以下对应表适用于原有接口支撑的展示项，不代表已完成真实数据联调。

**2026-10-16 设计探索例外：** 按用户“暂不考虑后端”的要求，滑坡页新增 `GeologicalObservatory.vue` / `landslideDesign.ts` 分类画像。土质 / 岩质及五个亚类的样本标注、类型与规模交叉矩阵、按类型联动诱因等均为独立设计示意。目前数据库没有滑坡数据集，不能确认存在相应标签；现有画像接口只返回各维度的边际分布，不能据此推导联合分布。未来若保留这套交互，需要真实分类标注及联合统计数据，或缩减为现有接口支持的独立分布。正式后端未修改。

统一数据画像接口：`GET /api/v1/dashboard/scenarios/{id}/profile`，实现位于 `backend/app/services/dashboard_service.py`。

| 预览展示 | 已有返回字段 / 计算 | 当前实现 |
| --- | --- | --- |
| 有效资源、样本、正类占比 | `dataset_count`、`dataset_file_count`、`sample_count`、`risk_rate` | `get_profile` 按内容指纹去重，读取全量标签统计 |
| 数据资产台账 | `datasets[].logical_id/version/record_count/attribute_count/visibility` | `_DatasetReader.describe` |
| 建模覆盖 | `modeling[].published/draft/total` | `_modeling_stats`；draft 实际代表所有非 PUBLISHED 状态，前端显示“未发布” |
| 网络协议、端口、服务 | `protocol_distribution`、`distinct_port_count`、`top_ports`、`services` | `_network_profile`；端口直接显示端口号，不推断实际应用 |
| 网络维度覆盖、标签口径 | `dimension_coverage`、`caliber_matrix` | `_network_dimension_coverage`、`_network_caliber_matrix` |
| 电参量均值及范围 | `params[].stats.mean/min/max`、`unit` | `_power_profile`；仅用 VoltageLevel_kV、CurrentAmp、Temperature_C、PowerFrequencyHz、Sensor_Packet_Loss_% |
| 电力问题、设备故障率、系统分布 | `issues`、`device_fault_rates`、`systems` | `_power_profile`；问题分布统计全部样本，并非仅故障样本 |
| 工频合格、丢包与基线 | `telemetry_by_dataset` | `_power_telemetry_by_dataset`；工频区间 49.8–50.2 Hz，基线校验均值 |
| 航保间距剖面 | `distance_curve[].step/mean` | `_flight_profile` 对 inter_distance_1…50 列分别求均值；不是实时轨迹 |
| 航保间距、航程、航向对照 | `distance`、`collision_comparison`、`total_distance`、`direction`、`relative_angle` | `_flight_profile`，只取数值原始集；距离保留原始单位，角度为算术均值 |
| 航保编码及去重 | `encoding_family`、`redundancy`、`groups` | `_flight_encoding_family`、`_flight_redundancy` |
| 地形因子覆盖与职责 | `factor_count`、`factor_coverage`、`roles` | `_geological_profile`；因子限定为 Slope、TWI、Elevation、Relief、SPI、Dis2roads、Dis2fault、Dis2river |
| 灾害诱因、类型、国家 | `catalog_distribution.trigger/category/country` | `_geological_profile`，来自全球编目，不代表实时风险事件 |
| 事件处置、近 10 天推理 | `/workspace` 的 `summary.pending/processing/resolved`、`activity_trend[].date/total/risk` | `get_workspace`、`_activity_trend`，场景管理员取本场景，当前按 UTC 日期分桶 |
| 场景用户注册、启用、停用 | `GET /api/v1/users`，遍历分页，按 `status` 分组 | `Authz.scope_users` 中场景管理员只能取本场景 SCENARIO_USER；因此移除管理员总数展示 |

接入约束：

- 场景管理员看板使用其本人的身份与既有权限。SUPER_ADMIN 的 `/workspace` 返回本人记录，不能标为全场景；未来接入时按该角色显示“本人”范围，不要求修改后端。
- 分类 TOP N 柱图只表示当前排名；问题类型环图补“其余 / 缺失”，避免把局部类别冒充全量比例。
- 均值、样本数和分类分布属于数据集画像，处置和推理趋势属于系统记录。页面不承诺实时传感器、真实在线航迹或新模型结果。
- 后端无记录或字段缺失时保留空态，不为填满大屏生成业务数值。
