"""首页聚合服务。

首页展示需要的是页面级统计，而不是数据集预览或风险事件分页列表。
本服务集中处理三类首页数据：平台总览、场景画像、场景用户工作台。
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import os
from statistics import mean
from typing import Any, Iterable

from sqlalchemy import func, select

from app.models.algorithm import Algorithm
from app.models.app_user import AppUser
from app.models.dataset import Dataset
from app.models.inference_record import InferenceRecord
from app.models.model_version import ModelVersion
from app.models.risk_event import RiskEvent
from app.models.scenario import Scenario
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    DATASET_RISK_TYPES,
    DATASET_STATUS_ACTIVE,
    DATASET_VISIBILITY_COMPANY,
    DATASET_VISIBILITY_PLATFORM,
    MODEL_STATUS_PUBLISHED,
    ROLE_SCENARIO_ADMIN,
    ROLE_SCENARIO_USER,
    ROLE_SUPER_ADMIN,
    RISK_TYPE_FLIGHT_DECK,
    RISK_TYPE_GEOLOGICAL,
    RISK_TYPE_NETWORK,
    RISK_TYPE_POWER,
)
from app.services.training_executor import resolve_dataset_path
from app.utils.arff_reader import count_arff_rows, read_arff
from app.utils.common import row_to_dict


_CARRIER_IDS = {
    "carrier_feature2_biaoqian",
    "carrier_feature2_lisan",
    "carrier_paired_trail",
}
_FLOW_LABELS = ["≤128", "129-256", "257-512", "513-1024", ">1024"]
_STATUS_LABELS = {"PENDING": "待处置", "PROCESSING": "处理中", "RESOLVED": "已处置"}


def _num(value: Any) -> float | None:
    if value in (None, "", "?"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        text = str(value)
        if text.startswith(("(", "[")) and "-" in text:
            try:
                a, b = text[1:-1].split("-", 1)
                return (float(a.strip()) + float(b.strip())) / 2
            except (TypeError, ValueError):
                return None
    return None


def _field_index(fields: list[dict]) -> dict[str, int]:
    return {str(field.get("name")): index for index, field in enumerate(fields)}


def _values(rows: list[list[str]], index: int | None) -> list[str]:
    if index is None:
        return []
    return [row[index] for row in rows if index < len(row) and row[index] not in ("", "?")]


def _top(values: Iterable[Any], limit: int = 10) -> list[dict[str, Any]]:
    return [{"value": value, "count": count} for value, count in Counter(values).most_common(limit)]


def _numeric_stats(rows: list[list[str]], index: int | None) -> dict[str, Any] | None:
    if index is None:
        return None
    nums = [value for row in rows if index < len(row) for value in [_num(row[index])] if value is not None]
    if not nums:
        return None
    return {"mean": round(mean(nums), 2), "min": round(min(nums), 2), "max": round(max(nums), 2)}


def _label_is_risk(value: Any) -> bool:
    return str(value).strip().lower() not in {"", "?", "0", "normal", "no", "false"}


def _read_dataset(dataset: Dataset) -> tuple[list[dict], list[list[str]]]:
    path = resolve_dataset_path(dataset.file_path)
    if not os.path.exists(path):
        return [], []
    return read_arff(path, max_rows=None)


def _dataset_count(dataset: Dataset) -> int:
    path = resolve_dataset_path(dataset.file_path)
    return count_arff_rows(path) if os.path.exists(path) else 0


def _group_key(dataset: Dataset) -> str:
    return "carrier_shared_source" if dataset.logical_id in _CARRIER_IDS else dataset.logical_id


def _risk_counts(fields: list[dict], rows: list[list[str]], label_field: str | None) -> tuple[int, int]:
    index = _field_index(fields).get(label_field or "")
    values = _values(rows, index)
    return len(rows), sum(1 for value in values if _label_is_risk(value))


def _merge_rows(datasets: list[Dataset]) -> tuple[list[dict], list[list[str]], list[dict]]:
    sources: list[tuple[list[dict], list[list[str]]]] = []
    dataset_stats: list[dict] = []
    for dataset in datasets:
        fields, rows = _read_dataset(dataset)
        if not fields:
            continue
        sources.append((fields, rows))
        total, risk = _risk_counts(fields, rows, dataset.label_field)
        dataset_stats.append({
            "dataset_id": dataset.id,
            "logical_id": dataset.logical_id,
            "record_count": total,
            "risk_count": risk,
            "risk_rate": round(risk / total, 4) if total else 0,
        })
    all_fields: list[dict] = []
    for fields, _ in sources:
        known = {field.get("name") for field in all_fields}
        for field in fields:
            if field.get("name") not in known:
                all_fields.append(field)
                known.add(field.get("name"))
    all_names = [field.get("name") for field in all_fields]
    all_rows: list[list[str]] = []
    for fields, rows in sources:
        local_names = [field.get("name") for field in fields]
        positions = {name: index for index, name in enumerate(local_names)}
        for row in rows:
            all_rows.append([row[positions[name]] if name in positions and positions[name] < len(row) else "?" for name in all_names])
    return all_fields, all_rows, dataset_stats


def _event_scope(stmt, current_user, scenario_id: int | None = None):
    role = getattr(current_user, "role", None)
    if role == ROLE_SUPER_ADMIN:
        stmt = stmt.join(Dataset, Dataset.id == RiskEvent.dataset_id).where(
            Dataset.visibility == DATASET_VISIBILITY_PLATFORM
        )
        if scenario_id is not None:
            stmt = stmt.where(RiskEvent.scenario_id == scenario_id)
    elif role == ROLE_SCENARIO_ADMIN:
        bound = getattr(current_user, "scenario_id", None)
        if scenario_id is not None and scenario_id != bound:
            raise ServiceError(403, "无权限操作")
        stmt = stmt.join(Dataset, Dataset.id == RiskEvent.dataset_id).where(
            RiskEvent.scenario_id == bound,
            Dataset.visibility.in_((DATASET_VISIBILITY_PLATFORM, DATASET_VISIBILITY_COMPANY)),
        )
    else:
        stmt = stmt.where(RiskEvent.created_by_user_id == current_user.id)
        if scenario_id is not None:
            stmt = stmt.where(RiskEvent.scenario_id == scenario_id)
    return stmt


def _event_summary(events: list[RiskEvent]) -> dict[str, Any]:
    score_bins = {"0.5-0.7": 0, "0.7-0.9": 0, "0.9-1.0": 0}
    status = {"PENDING": 0, "PROCESSING": 0, "RESOLVED": 0}
    today = datetime.now(timezone.utc).date()
    daily: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "resolved": 0, "pending": 0})
    for event in events:
        score = float(event.risk_score or 0)
        if score < 0.7:
            score_bins["0.5-0.7"] += 1
        elif score < 0.9:
            score_bins["0.7-0.9"] += 1
        else:
            score_bins["0.9-1.0"] += 1
        if event.status in status:
            status[event.status] += 1
        day = event.occurred_at.astimezone(timezone.utc).strftime("%Y-%m-%d") if event.occurred_at else "未知"
        daily[day]["total"] += 1
        if event.status == "RESOLVED":
            daily[day]["resolved"] += 1
        else:
            daily[day]["pending"] += 1
    return {
        "total": len(events),
        "pending": status["PENDING"],
        "processing": status["PROCESSING"],
        "resolved": status["RESOLVED"],
        "today": sum(1 for event in events if event.occurred_at and event.occurred_at.astimezone(timezone.utc).date() == today),
        "high_confidence": sum(1 for event in events if float(event.risk_score or 0) >= 0.8),
        "score_bins": [{"label": label, "count": count} for label, count in score_bins.items()],
        "status_funnel": [{"label": _STATUS_LABELS[label], "status": label, "count": count} for label, count in status.items()],
        "daily_trend": [
            {"date": day, **daily[day]} for day in sorted(daily)[-7:]
        ],
    }


class DashboardService(ServiceBase):
    @service_call
    def get_admin_overview(self, current_user):
        self.require_super_admin(current_user)
        scenarios = self.db.scalars(select(Scenario).order_by(Scenario.id)).all()
        datasets = self.db.scalars(
            select(Dataset).where(
                Dataset.status == DATASET_STATUS_ACTIVE,
                Dataset.visibility == DATASET_VISIBILITY_PLATFORM,
            ).order_by(Dataset.id)
        ).all()
        grouped: dict[str, list[Dataset]] = defaultdict(list)
        for dataset in datasets:
            grouped[_group_key(dataset)].append(dataset)
        effective_samples = sum(max(_dataset_count(item) for item in group) for group in grouped.values() if group)
        published_models = self.db.scalar(
            select(func.count()).select_from(ModelVersion).where(ModelVersion.status == MODEL_STATUS_PUBLISHED)
        ) or 0
        algorithm_count = self.db.scalar(
            select(func.count()).select_from(Algorithm).where(Algorithm.status == "AVAILABLE")
        ) or 0
        inference_count = self.db.scalar(select(func.count()).select_from(InferenceRecord)) or 0
        user_count = self.db.scalar(select(func.count()).select_from(AppUser)) or 0
        event_stats = _event_scope(select(RiskEvent), current_user)
        events = self.db.scalars(event_stats).all()

        scenario_cards = []
        for scenario in scenarios:
            scene_datasets = [dataset for dataset in datasets if dataset.scenario_id == scenario.id]
            scene_groups: dict[str, list[Dataset]] = defaultdict(list)
            for dataset in scene_datasets:
                scene_groups[_group_key(dataset)].append(dataset)
            scene_samples = sum(max(_dataset_count(item) for item in group) for group in scene_groups.values() if group)
            scene_events = [event for event in events if event.scenario_id == scenario.id]
            scene_inferences = self.db.scalar(
                select(func.count()).select_from(InferenceRecord).join(
                    ModelVersion, ModelVersion.id == InferenceRecord.model_version_id
                ).where(ModelVersion.scenario_id == scenario.id)
            ) or 0
            scene_models = self.db.scalar(
                select(func.count()).select_from(ModelVersion).where(ModelVersion.scenario_id == scenario.id)
            ) or 0
            scene_stats = _event_summary(scene_events)
            label_counts = []
            for dataset in scene_datasets:
                fields, rows = _read_dataset(dataset)
                total, risk = _risk_counts(fields, rows, dataset.label_field)
                if total:
                    label_counts.append((total, risk))
            total_labels = sum(item[0] for item in label_counts)
            risk_labels = sum(item[1] for item in label_counts)
            scene_cards.append({
                "scenario_id": scenario.id,
                "code": scenario.code,
                "name": scenario.name,
                "access_status": scenario.access_status,
                "dataset_count": len(scene_datasets),
                "effective_sample_count": scene_samples,
                "risk_rate": round(risk_labels / total_labels, 4) if total_labels else 0,
                "published_model_count": sum(
                    1 for model in self.db.scalars(select(ModelVersion).where(
                        ModelVersion.scenario_id == scenario.id,
                        ModelVersion.status == MODEL_STATUS_PUBLISHED,
                    )).all()
                ),
                "inference_count": scene_inferences,
                "event_count": scene_stats["total"],
                "pending_count": scene_stats["pending"],
            })
        return ok(data={
            "totals": {
                "scenario_count": len(scenarios),
                "effective_dataset_count": len(grouped),
                "effective_sample_count": effective_samples,
                "algorithm_count": algorithm_count,
                "published_model_count": published_models,
                "inference_count": inference_count,
                "risk_event_count": len(events),
                "pending_event_count": sum(1 for event in events if event.status == "PENDING"),
                "user_count": user_count,
            },
            "scenarios": scenario_cards,
        })

    @service_call
    def get_profile(self, current_user, scenario_id: int):
        self.require_scenario_admin_of(current_user, scenario_id)
        stmt = select(Dataset).where(
            Dataset.scenario_id == scenario_id,
            Dataset.status == DATASET_STATUS_ACTIVE,
        )
        if getattr(current_user, "role", None) == ROLE_SUPER_ADMIN:
            stmt = stmt.where(Dataset.visibility == DATASET_VISIBILITY_PLATFORM)
        else:
            stmt = stmt.where(Dataset.visibility.in_((DATASET_VISIBILITY_PLATFORM, DATASET_VISIBILITY_COMPANY)))
        datasets = self.db.scalars(stmt.order_by(Dataset.id)).all()
        scenario = self.db.get(Scenario, scenario_id)
        if scenario is None:
            raise ServiceError(404, "场景不存在")
        fields, rows, dataset_stats = _merge_rows(datasets)
        risk_type = DATASET_RISK_TYPES.get(datasets[0].logical_id) if datasets else None
        data = {
            "scenario_id": scenario_id,
            "scenario_code": scenario.code,
            "scenario_name": scenario.name,
            "dataset_count": len(datasets),
            "sample_count": len(rows),
            "risk_type": risk_type,
            "datasets": dataset_stats,
        }
        if risk_type == RISK_TYPE_NETWORK:
            data.update(self._network_profile(datasets, fields, rows))
        elif risk_type == RISK_TYPE_POWER:
            data.update(self._power_profile(fields, rows))
        elif risk_type == RISK_TYPE_FLIGHT_DECK:
            data.update(self._flight_profile(fields, rows))
        elif risk_type == RISK_TYPE_GEOLOGICAL:
            data.update(self._geological_profile(datasets, fields, rows, dataset_stats))
        return ok(data=data)

    @service_call
    def get_workspace(self, current_user, scenario_id: int):
        self.require_scenario_access(current_user, scenario_id)
        stmt = _event_scope(select(RiskEvent).where(RiskEvent.scenario_id == scenario_id), current_user, scenario_id)
        events = self.db.scalars(stmt.order_by(RiskEvent.occurred_at.desc())).all()
        summary = _event_summary(events)
        recent = [row_to_dict(event) for event in events[:20]]
        dataset = self.db.scalar(
            select(Dataset).where(
                Dataset.scenario_id == scenario_id,
                Dataset.status == DATASET_STATUS_ACTIVE,
                Dataset.visibility.in_((DATASET_VISIBILITY_PLATFORM, DATASET_VISIBILITY_COMPANY)),
            ).order_by(Dataset.id)
        )
        risk_type = events[0].risk_type if events else (DATASET_RISK_TYPES.get(dataset.logical_id) if dataset else None)
        data = {
            "scenario_id": scenario_id,
            "risk_type": risk_type,
            "summary": summary,
            "recent_events": recent,
        }
        if risk_type == RISK_TYPE_NETWORK:
            data.update(self._network_workspace(events))
        elif risk_type == RISK_TYPE_POWER:
            data.update(self._power_workspace(events))
        elif risk_type == RISK_TYPE_FLIGHT_DECK:
            data.update(self._flight_workspace(events))
        elif risk_type == RISK_TYPE_GEOLOGICAL:
            data.update(self._geological_workspace(events))
        return ok(data=data)

    @staticmethod
    def _network_profile(datasets, fields, rows):
        cmap = _field_index(fields)
        ports = _top(_values(rows, cmap.get("L4_DST_PORT")), 10)
        protocols = _top(_values(rows, cmap.get("PROTOCOL")), 8)
        flags = _top(_values(rows, cmap.get("flag")), 8)
        services = _top(_values(rows, cmap.get("service")), 8)
        byte_columns = [name for name in cmap if "BYTES" in name.upper() and "NUM_PKTS" in name.upper()]
        segments = [0, 0, 0, 0, 0]
        for row in rows:
            total = sum(_num(row[cmap[name]]) or 0 for name in byte_columns if cmap[name] < len(row))
            bucket = 0 if total <= 128 else 1 if total <= 256 else 2 if total <= 512 else 3 if total <= 1024 else 4
            segments[bucket] += 1
        in_values = [_num(value) for value in _values(rows, cmap.get("IN_BYTES"))]
        retrans_values = [_num(value) for value in _values(rows, cmap.get("RETRANSMITTED_IN_BYTES"))]
        in_values = [value for value in in_values if value is not None]
        retrans_values = [value for value in retrans_values if value is not None]
        avg_in = mean(in_values) if in_values else 0
        avg_retrans = mean(retrans_values) if retrans_values else 0
        return {
            "distinct_port_count": len(set(item["value"] for item in ports)),
            "protocol_distribution": protocols,
            "top_ports": ports,
            "flag_distribution": flags,
            "service_distribution": services,
            "flow_segments": {"labels": _FLOW_LABELS, "counts": segments},
            "avg_in_bytes": round(avg_in, 2),
            "avg_retrans_in_bytes": round(avg_retrans, 2),
            "retransmission_ratio": round(avg_retrans / avg_in, 4) if avg_in else 0,
        }

    @staticmethod
    def _power_profile(fields, rows):
        cmap = _field_index(fields)
        params = {
            name: stats for name in ("VoltageLevel_kV", "CurrentAmp", "Temperature_C", "PowerFrequencyHz", "Sensor_Packet_Loss_%")
            if (stats := _numeric_stats(rows, cmap.get(name))) is not None
        }
        components = _values(rows, cmap.get("Component"))
        issues = _values(rows, cmap.get("IssueType"))
        systems = _values(rows, cmap.get("SystemName"))
        target = _values(rows, cmap.get("Target_Event"))
        component_rows: dict[str, list[str]] = defaultdict(list)
        component_index, target_index = cmap.get("Component"), cmap.get("Target_Event")
        if component_index is not None:
            for row in rows:
                if component_index < len(row):
                    component_rows[row[component_index]].append(row[target_index] if target_index is not None and target_index < len(row) else "0")
        fault_rates = [
            {"value": component, "count": len(values), "fault_rate": round(sum(_label_is_risk(value) for value in values) / len(values), 4) if values else 0}
            for component, values in component_rows.items()
        ]
        fault_count = sum(_label_is_risk(value) for value in target)
        return {
            "fault_count": fault_count,
            "fault_rate": round(fault_count / len(target), 4) if target else 0,
            "params": params,
            "issue_distribution": _top(issues, 8),
            "component_distribution": _top(components, 8),
            "system_distribution": _top(systems, 8),
            "device_fault_rates": sorted(fault_rates, key=lambda item: item["fault_rate"], reverse=True),
        }

    @staticmethod
    def _flight_profile(fields, rows):
        cmap = _field_index(fields)
        collision = _values(rows, cmap.get("Collision"))
        min_index = cmap.get("inter_dist_min")
        collision_index = cmap.get("Collision")
        min_values = [_num(row[min_index]) for row in rows if min_index is not None and min_index < len(row)]
        min_values = [value for value in min_values if value is not None]
        curve = []
        for step in range(1, 51):
            values = [_num(row[cmap[f"inter_distance_{step}"]]) for row in rows if f"inter_distance_{step}" in cmap and cmap[f"inter_distance_{step}"] < len(row)]
            values = [value for value in values if value is not None]
            curve.append({"step": step, "mean": round(mean(values), 2) if values else None})
        by_collision = {}
        for label, is_collision in (("collision", True), ("normal", False)):
            values = []
            if min_index is not None and collision_index is not None:
                for row in rows:
                    if min_index >= len(row) or collision_index >= len(row):
                        continue
                    value = _num(row[min_index])
                    if value is not None and _label_is_risk(row[collision_index]) == is_collision:
                        values.append(value)
            by_collision[label] = {"count": len(values), "mean_min_distance": round(mean(values), 2) if values else None}
        return {
            "sample_count": len(rows),
            "collision_count": sum(_label_is_risk(value) for value in collision),
            "collision_rate": round(sum(_label_is_risk(value) for value in collision) / len(collision), 4) if collision else 0,
            "min_inter_distance": round(min(min_values), 2) if min_values else None,
            "mean_inter_distance": round(mean(min_values), 2) if min_values else None,
            "distance_curve": curve,
            "collision_comparison": by_collision,
            "plane1_angle_stats": _numeric_stats(rows, cmap.get("Plane1_dir_mean_deg")),
            "plane2_angle_stats": _numeric_stats(rows, cmap.get("Plane2_dir_mean_deg")),
        }

    @staticmethod
    def _geological_profile(datasets, fields, rows, dataset_stats):
        cmap = _field_index(fields)
        factors = {name: stats for name in ("Slope", "TWI", "Elevation", "Relief", "SPI", "Dis2roads", "Dis2fault", "Dis2river") if (stats := _numeric_stats(rows, cmap.get(name))) is not None}
        catalog = {}
        for field_name, aliases in {
            "trigger": ("landslide_trigger", "Trigger", "trigger"),
            "type": ("landslide_type", "Type", "type"),
            "magnitude": ("magnitude", "Magnitude", "scale"),
            "country": ("country", "Country", "国家"),
        }.items():
            index = next((cmap.get(alias) for alias in aliases if alias in cmap), None)
            if index is not None:
                catalog[field_name] = _top(_values(rows, index), 10)
        return {"factors": factors, "catalog_distribution": catalog, "dataset_stats": dataset_stats}

    @staticmethod
    def _event_values(events, key):
        return [event.raw_features.get(key) for event in events if isinstance(event.raw_features, dict) and event.raw_features.get(key) not in (None, "", "?")]

    @classmethod
    def _network_workspace(cls, events):
        ports = _top(cls._event_values(events, "L4_DST_PORT") or cls._event_values(events, "dst_port"), 8)
        return {"top_ports": ports, "abnormal_ports": [], "port_deviation": []}

    @classmethod
    def _power_workspace(cls, events):
        features = {}
        for name in ("VoltageLevel_kV", "CurrentAmp", "Temperature_C", "PowerFrequencyHz"):
            values = [_num(value) for value in cls._event_values(events, name)]
            values = [value for value in values if value is not None]
            if values:
                features[name] = {"mean": round(mean(values), 2), "min": round(min(values), 2), "max": round(max(values), 2)}
        pairs = Counter((str(event.raw_features.get("Component")), str(event.raw_features.get("IssueType"))) for event in events if isinstance(event.raw_features, dict))
        return {"telemetry": features, "component_issue_distribution": [{"component": pair[0], "issue": pair[1], "count": count} for pair, count in pairs.most_common(20)], "device_ranking": _top(cls._event_values(events, "Component"), 10)}

    @classmethod
    def _flight_workspace(cls, events):
        positions = [{"event_id": event.id, "x": float(event.fault_position_x) if event.fault_position_x is not None else None, "y": float(event.fault_position_y) if event.fault_position_y is not None else None, "risk_score": float(event.risk_score)} for event in events]
        distances = [_num(value) for value in cls._event_values(events, "inter_dist_min")]
        distances = [value for value in distances if value is not None]
        return {"positions": positions, "distance_distribution": {"min": min(distances) if distances else None, "max": max(distances) if distances else None, "mean": round(mean(distances), 2) if distances else None}, "direction_stats": {name: _numeric_stats([[str(value)] for value in cls._event_values(events, name)], {name: 0}) for name in ("Plane1_dir_mean_deg", "Plane2_dir_mean_deg")}}

    @classmethod
    def _geological_workspace(cls, events):
        triggers = _top(cls._event_values(events, "landslide_trigger"), 10)
        slopes = [(_num(value), event) for event, value in ((event, event.raw_features.get("Slope")) for event in events if isinstance(event.raw_features, dict))]
        buckets: dict[str, list[RiskEvent]] = defaultdict(list)
        for slope, event in slopes:
            if slope is None:
                continue
            label = "<5°" if slope < 5 else "5-15°" if slope < 15 else "15-25°" if slope < 25 else "≥25°"
            buckets[label].append(event)
        ranking = [{"label": label, "count": len(items), "mean_risk_score": round(mean(float(item.risk_score) for item in items), 4)} for label, items in buckets.items()]
        return {"trigger_distribution": triggers, "slope_ranking": sorted(ranking, key=lambda item: item["mean_risk_score"], reverse=True), "factor_contribution": []}
