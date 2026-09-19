"""Deterministic feature dictionaries for the non-network scenarios.

The carrier dataset contains 278 repeated time-step features. Keeping the
field families here makes the catalog auditable while avoiding a hand-written
copy that can silently drift or omit one of the steps. The returned mapping is
expanded before it is exposed by the explanation service, so callers still
receive an ordinary ``required_feature_names`` list and feature dictionary.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def _metadata(display_name: str, meaning: str, high: str, low: str, abnormal: str, action: str) -> dict[str, str]:
    return {
        "display_name": display_name,
        "meaning": meaning,
        "high_value_meaning": high,
        "low_value_meaning": low,
        "abnormal_value_meaning": abnormal,
        "recommended_action": action,
    }


def _power_catalog() -> dict[str, dict[str, str]]:
    return {
        "Component": _metadata("设备组件", "发生监测数据的设备或组件", "可能表示该组件负荷或异常事件集中", "可能表示设备未产生有效监测", "未知设备编码或设备标识缺失", "核对设备台账并检查该组件近期告警"),
        "SystemName": _metadata("所属系统", "数据所属的电力业务或监测系统", "可能表示系统侧异常较集中", "可能表示监测范围较小", "系统名称不在登记值域", "确认系统拓扑和监测链路"),
        "VoltageLevel_kV": _metadata("电压等级", "设备或线路的额定电压等级（kV）", "需结合额定值判断越限，可能增加绝缘与设备压力", "可能与低压运行或数据缺失有关", "偏离设备额定电压或单位异常", "对照额定电压检查越限和保护配置"),
        "CurrentAmp": _metadata("电流值", "设备或线路的运行电流（A）", "可能表示过载、短路前兆或负荷突增", "可能表示轻载或采集异常", "超过额定电流或出现突变", "核查负荷曲线、保护动作和现场电流"),
        "Temperature_C": _metadata("温度", "设备监测温度（℃）", "可能表示过热、散热故障或接触不良", "可能表示传感器断线或环境温度异常", "超出设备工作范围或瞬时跳变", "检查散热、接点和温度传感器"),
        "Sensor_Packet_Loss_%": _metadata("传感器丢包率", "遥测数据包丢失比例（%）", "可能导致状态判断不完整并放大误报漏报", "表示通信质量较好", "高于通信质量阈值或持续升高", "检查通信链路、采集网关和网络拥塞"),
        "PowerFrequencyHz": _metadata("电网频率", "电网运行频率（Hz）", "偏高可能表示发电与负荷不平衡", "偏低可能表示负荷突增或供给不足", "偏离额定频率或短时剧烈波动", "核对区域频率、功率平衡和调频动作"),
        "IssueType": _metadata("问题类型", "监测记录标注的问题类别", "高风险问题类型可能与设备保护或供电连续性有关", "无明显问题类型不代表绝对安全", "未知问题编码或问题类型与设备不匹配", "结合原始告警和设备运行工况人工复核"),
    }


def _geological_catalog() -> dict[str, dict[str, str]]:
    names = {
        "Lithology": "岩性类型", "Landuse": "土地利用类型", "Aspect": "坡向", "Slope": "坡度",
        "EVI": "增强植被指数", "Elevation": "高程", "Roughness": "地表粗糙度", "Slope_roughness": "坡度粗糙度",
        "G_curvature": "总曲率", "Pla_curvature": "平面曲率", "Pro_curvature": "剖面曲率", "Relief": "地形起伏度",
        "LS": "坡长坡度因子", "SPI": "水流功率指数", "TWI": "地形湿度指数", "Dis2roads": "距道路距离",
        "Dis2fault": "距断层距离", "Dis2river": "距河流距离", "dist_roads": "距道路距离", "DEM": "数字高程",
        "plan_curvature": "平面曲率", "profil_curvature": "剖面曲率", "Geology": "地质岩组", "LandCover": "土地覆盖",
        "DF": "断层因子", "DR": "道路因子", "DW": "水系因子", "LULC": "土地利用覆盖", "NDVI": "归一化植被指数",
        "PC": "剖面曲率", "Precip": "降水量", "TPI": "地形位置指数", "Temp": "温度", "twi": "地形湿度指数",
        "curvature": "曲率", "slope": "坡度", "elevation": "高程", "aspect": "坡向", "lithology": "岩性类型",
        "land_use": "土地利用类型",
        "location_accuracy": "位置精度", "landslide_category": "滑坡类别", "landslide_trigger": "滑坡触发因素",
        "landslide_setting": "滑坡环境", "fatality_count": "死亡人数", "injury_count": "受伤人数",
        "country_name": "国家名称", "admin_division_population": "行政区人口", "gazeteer_distance": "距最近地名距离",
        "longitude": "经度", "latitude": "纬度",
    }
    return {
        name: _metadata(
            display,
            f"地质风险分析字段：{display}",
            "数值偏高可能表示坡面、汇水或外部扰动增强，需结合该数据集量纲判断",
            "数值偏低可能表示相关致灾因素较弱，但不能单独排除风险",
            "超出数据集正常范围、单位异常或出现缺失编码",
            "结合降雨、地形、地质和现场巡查结果进行人工复核",
        )
        for name, display in names.items()
    }


def _carrier_catalog() -> dict[str, dict[str, str]]:
    catalog: dict[str, dict[str, str]] = {}

    def add(name: str, display: str, meaning: str, high: str, low: str) -> None:
        catalog[name] = _metadata(
            display, meaning, high, low,
            "出现缺失值、非物理值或与轨迹时间顺序不一致",
            "暂停高风险协同动作，核对轨迹、间距和通信数据",
        )

    for plane in (1, 2):
        for index in range(1, 50):
            add(f"Plane{plane}_dir_angle_deg_{index}", f"{plane}号机第{index}步航向角", "舰载机离散时间步航向角（度）", "航向快速变化可能表示机动或协同冲突", "航向稳定或变化较小")
        for suffix, display in (("mean_deg", "均值"), ("std_deg", "标准差"), ("max_deg", "最大值"), ("min_deg", "最小值"), ("range_deg", "极差")):
            add(f"Plane{plane}_dir_{suffix}", f"{plane}号机航向角{display}", "单机航向角统计量（度）", "统计量偏高可能表示航向变化或机动增强", "统计量偏低可能表示航向较稳定")
    for index in range(1, 50):
        add(f"relative_angle_deg_{index}", f"第{index}步两机相对角度", "两机离散时间步相对航向角（度）", "相对角度偏大可能表示协同方向不一致", "相对角度较小表示方向更接近")
    for suffix, display in (("mean_deg", "均值"), ("std_deg", "标准差"), ("max_deg", "最大值"), ("min_deg", "最小值")):
        add(f"relative_angle_{suffix}", f"相对角度{display}", "两机相对角度统计量（度）", "相对角度波动或极值偏大可能增加协同风险", "相对角度较稳定")
    for index in range(1, 51):
        add(f"inter_distance_{index}", f"第{index}步两机间距", "两机离散时间步空间间距", "间距过小可能表示碰撞风险升高", "间距较大表示空间缓冲较足")
    for suffix, display in (("mean", "均值"), ("std", "标准差"), ("min", "最小值"), ("max", "最大值"), ("range", "极差"), ("median", "中位数")):
        add(f"inter_dist_{suffix}", f"两机间距{display}", "两机间距统计量", "间距统计量偏小或波动偏大可能表示安全裕度不足", "间距较大且稳定")
    for name, display, meaning, high, low in (
        ("start_dist", "起始间距", "作业窗口开始时两机间距", "起始间距偏小会压缩处置时间", "起始间距较大"),
        ("end_dist", "结束间距", "作业窗口结束时两机间距", "结束间距偏小可能存在收拢风险", "结束间距较大"),
        ("dist_change", "间距变化量", "作业窗口内两机间距变化量", "快速负向变化表示两机正在接近", "正向变化表示两机正在远离"),
        ("dist_change_ratio", "间距变化率", "作业窗口内两机间距相对变化率", "负向幅度较大表示接近速度较快", "正向幅度较大表示远离较快"),
    ):
        add(name, display, meaning, high, low)
    for index in range(1, 50):
        add(f"dist_change_step_{index}", f"第{index}步间距变化", "相邻时间步两机间距变化量", "负向突变可能表示快速接近", "正向变化可能表示正在远离")
    for suffix, display in (("mean_step", "均值"), ("std_step", "标准差"), ("max_step", "最大值"), ("min_step", "最小值")):
        add(f"dist_change_{suffix}", f"间距变化{display}", "逐时间步间距变化统计量", "接近变化或波动偏大可能增加风险", "间距变化较稳定")
    for name, display, meaning, high, low in (
        ("Plane1_total_distance", "1号机总航程", "1号机作业窗口总航程", "航程偏大可能表示机动或绕行增加", "航程较小可能表示动作有限"),
        ("Plane2_total_distance", "2号机总航程", "2号机作业窗口总航程", "航程偏大可能表示机动或绕行增加", "航程较小可能表示动作有限"),
        ("total_dist_diff", "总航程差值", "两机总航程差值", "差值偏大可能表示协同不同步", "差值较小表示航程接近"),
        ("total_dist_ratio", "总航程比值", "两机总航程比值", "明显偏离1可能表示协同节奏差异", "接近1表示航程较一致"),
    ):
        add(name, display, meaning, high, low)
    for name, display in (("PlaneID1", "1号机标识"), ("PlaneID2", "2号机标识")):
        add(name, display, "参与协同作业的舰载机标识", "标识异常或频繁变化可能表示数据拼接问题", "标识稳定且在登记范围内")
    return catalog


def expand_scenario_feature_catalog(configs: Any) -> dict[str, dict[str, Any]]:
    """Fill all scenario feature dictionaries using the repository catalog."""
    if not isinstance(configs, dict):
        return {}
    result = deepcopy(configs)
    catalogs = {
        "power_system": _power_catalog(),
        "geological_risk": _geological_catalog(),
        "flightdeck_operation": _carrier_catalog(),
    }
    for code, catalog in catalogs.items():
        config = result.get(code)
        if not isinstance(config, dict):
            continue
        existing = config.get("feature_dictionary")
        merged = dict(existing) if isinstance(existing, dict) else {}
        for name, metadata in catalog.items():
            merged.setdefault(name, metadata)
        config["feature_dictionary"] = merged
        config["required_feature_names"] = list(merged)
    return result
