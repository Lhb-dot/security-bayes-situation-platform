"""风险事件 Service（RiskEvent）—— 风险事件生成、查询与处置。

对应需求文档章节：5.1（统一原则）、5.2（最小字段结构 / 访问控制）、
5.3（风险类型映射）、5.4（风险等级生成规则）、5.5（raw_features 使用规则）、
6.8（数据访问与态势统计规则）。

模型：app.models.risk_event.RiskEvent。

关键业务规则：
1. 风险事件由推理结果生成（正常结果只保存推理记录，不生成事件，需求 4.x）。
2. 冗余字段（original_label/risk_type/risk_level/risk_score/dataset_version/raw_features）
   写入时与来源保持一致（需求 5.2 + 数据库设计文档 v2 2.7 冗余说明）。
3. risk_level 由 risk_score 与场景阈值计算（需求 5.4）：high > medium，均配置在 risk_threshold。
4. 访问控制（需求 5.2）：普通用户强制按 created_by_user_id 过滤；管理员可查全部。
5. 历史风险事件不得被无痕删除或自动改写（需求 5.2 访问控制第 4 条）→ 不提供删除。
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select

from app.models.dataset import Dataset
from app.models.handling_record import HandlingRecord
from app.models.inference_record import InferenceRecord
from app.models.model_version import ModelVersion
from app.models.risk_event import RiskEvent
from app.models.risk_threshold import RiskThreshold
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    DATASET_RISK_TYPES,
    DATASET_VISIBILITY_PLATFORM,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_MEDIUM_THRESHOLD,
    RISK_EVENT_STATUS_PENDING,
    RISK_EVENT_STATUS_TRANSITIONS,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MEDIUM,
    RISK_TYPE_FLIGHT_DECK,
    RISK_TYPE_GEOLOGICAL,
    RISK_TYPE_NETWORK,
    RISK_TYPE_POWER,
    ROLE_ADMIN,
    ROLE_SCENARIO_ADMIN,
    ROLE_SUPER_ADMIN,
)
from app.utils.common import get_logger, paginate, row_to_dict

logger = get_logger("risk_event")


class RiskEventService(ServiceBase):
    """风险事件：生成（内部）/ 查询 / 处置状态流转。"""

    def _get(self, event_id: int) -> RiskEvent:
        event = self.db.get(RiskEvent, event_id)
        if event is None:
            raise ServiceError(404, "风险事件不存在")
        return event

    def _require_event_access(self, current_user, event: RiskEvent) -> None:
        """风险事件访问控制（需求 0.2 / 5.2）。

        - SUPER_ADMIN：仅 platform 数据集派生事件
        - SCENARIO_ADMIN：仅绑定场景事件
        - SCENARIO_USER：仅本人创建的事件
        """
        self.require_login(current_user)
        role = getattr(current_user, "role", None)
        if role == ROLE_SUPER_ADMIN:
            dataset = self.db.get(Dataset, event.dataset_id)
            if dataset is None or not self.is_platform_visibility(dataset.visibility):
                raise ServiceError(403, "无权限操作")
            return
        if role == ROLE_SCENARIO_ADMIN:
            dataset = self.db.get(Dataset, event.dataset_id)
            if (
                event.scenario_id != getattr(current_user, "scenario_id", None)
                or dataset is None
                or dataset.visibility not in ("platform", "company")
            ):
                raise ServiceError(403, "无权限操作")
            return
        if event.created_by_user_id != getattr(current_user, "id", None):
            raise ServiceError(403, "无权限操作")

    @staticmethod
    def _calc_risk_level(risk_score: float, medium: float, high: float) -> str:
        """需求 5.4 风险等级生成规则：
        risk_score >= high → HIGH；medium <= risk_score < high → MEDIUM；risk_score < medium → LOW。
        """
        score = float(risk_score)
        if score >= float(high):
            return RISK_LEVEL_HIGH
        if score >= float(medium):
            return RISK_LEVEL_MEDIUM
        return RISK_LEVEL_LOW

    def _get_thresholds(self, user_id: int, scenario_id: int):
        """获取当前推理账号在场景下的阈值。

        需求 5.4.1.6：本文不把未经验证的具体数值写成正式默认阈值；阈值应通过
        risk_threshold 配置提供。此处缺失时仅用兜底值并记录 warning，提示尽快配置。
        """
        threshold = self.db.scalar(
            select(RiskThreshold).where(
                RiskThreshold.user_id == user_id,
                RiskThreshold.scenario_id == scenario_id,
            )
        )
        if threshold is None:
            logger.warning(
                "账号 %s 在场景 %s 未配置风险阈值，使用兜底值 medium=%s high=%s",
                user_id, scenario_id, DEFAULT_MEDIUM_THRESHOLD, DEFAULT_HIGH_THRESHOLD,
            )
            return float(DEFAULT_MEDIUM_THRESHOLD), float(DEFAULT_HIGH_THRESHOLD)
        return float(threshold.medium_threshold), float(threshold.high_threshold)

    @staticmethod
    def _calc_fault_position(
        dataset_logical_id: str, input_features: Optional[Dict]
    ) -> tuple:
        """计算航母甲板故障点坐标（需求 V3.0 §7.4.1）。

        仅航母甲板作业场景生成坐标，其余场景返回 (None, None)（前端不渲染红点）。
        坐标基准：甲板底图原始宽度 1000px，取值范围 [0, 1000]。

        计算逻辑（占位，待与业务方确认正式映射）：
        用双机平均航向角把"风险发生方位"映射到底图——1 号机航向角决定横坐标、
        2 号机航向角决定纵坐标，均为 (角度 % 360) / 360 * 1000。
        输入缺失或非法时返回 None，不虚构坐标。
        """
        if DATASET_RISK_TYPES.get(dataset_logical_id) != RISK_TYPE_FLIGHT_DECK:
            return None, None
        feats = input_features if isinstance(input_features, dict) else {}

        def _ratio(key: str):
            try:
                val = float(feats.get(key))
            except (TypeError, ValueError):
                return None
            if val < 0:
                return None
            return round((val % 360) / 360 * 1000, 2)

        x = _ratio("Plane1_dir_mean_deg")
        y = _ratio("Plane2_dir_mean_deg")
        return x, y

    @staticmethod
    def _build_description(
        dataset_logical_id: str,
        prediction_label: str,
        input_features: Dict,
        risk_score: float,
        risk_level: str,
    ) -> str:
        """生成风险事件解释文本（需求 V3.0 §5.7.2：结合场景特征生成有信息量的说明）。

        模板按场景差异化（含风险评分、风险等级与关键特征值），面向业务人员，
        不使用 softmax/对数似然等算法术语（§5.7.3）；解释文本随事件持久化保存。
        特征值只读取输入特征中存在且非空的键，缺失时跳过该句，不虚构数据。
        """
        feats = input_features if isinstance(input_features, dict) else {}
        risk_type = DATASET_RISK_TYPES.get(dataset_logical_id)

        def _f(name: str):
            v = feats.get(name)
            return None if v in (None, "", "?") else v

        head = f"（风险评分：{risk_score}，风险等级：{risk_level}）"

        if risk_type == RISK_TYPE_POWER:
            # §5.7.2 电力：受影响设备/所属系统/问题现象(IssueType)/当前电压
            bits = [f"该样本被判定为形成电力系统风险{head}"]
            component, system = _f("Component"), _f("SystemName")
            issue, voltage = _f("IssueType"), _f("VoltageLevel_kV")
            if component:
                bits.append(f"受影响设备：{component}")
            if system:
                bits.append(f"所属系统：{system}")
            if issue:
                bits.append(f"问题现象：{issue}")
            if voltage:
                bits.append(f"当前电压 {voltage} kV")
            bits.append("建议核实相关设备是否存在越限或异常，并检查关联监测数据")
            return "，".join(bits) + "。"

        if risk_type == RISK_TYPE_NETWORK:
            # §5.7.2 网络：目标端口/协议/字节数/重传等明显异常特征
            bits = [f"该网络流量样本被判定为网络安全风险{head}"]
            dport = _f("L4_DST_PORT") or _f("dst_port")
            proto = _f("PROTOCOL") or _f("protocol_type")
            in_bytes = _f("IN_BYTES") or _f("src_bytes")
            retrans = _f("RETRANSMITTED_IN_BYTES") or _f("dst_bytes")
            if dport:
                bits.append(f"目标端口 {dport} 收到异常流量")
            if proto:
                bits.append(f"协议类型为 {proto}")
            if in_bytes:
                bits.append(f"流入字节数 {in_bytes}")
            if retrans:
                bits.append(f"流入方向重传 {retrans} 字节，重传率偏高")
            bits.append("建议重点关注该连接是否存在扫描或攻击行为")
            return "，".join(bits) + "。"

        if risk_type == RISK_TYPE_GEOLOGICAL:
            # §5.7.2 地质：坡度/TWI/距断层距离/岩性等关键因子
            bits = [f"该区域被判定为存在滑坡风险{head}"]
            slope = _f("Slope") or _f("slope")
            twi = _f("TWI") or _f("twi")
            dist_fault = _f("Dis2fault") or _f("DR")
            lith = _f("Lithology") or _f("lithology")
            if slope:
                bits.append(f"坡度 {slope}°")
            if twi:
                bits.append(f"TWI（地形湿度指数）{twi}")
            if dist_fault:
                bits.append(f"距断层距离 {dist_fault}")
            if lith:
                bits.append(f"岩性为 {lith}")
            bits.append("建议对该区域进行现场核查，并关注近期降雨情况")
            return "，".join(bits) + "。"

        if risk_type == RISK_TYPE_FLIGHT_DECK:
            # §5.7.2 航母：最小间距/接近率/航向角偏差等关键轨迹特征
            bits = [f"该双机协同作业样本被判定为存在碰撞风险{head}"]
            min_dist = _f("inter_dist_min")
            dist_change = _f("dist_change_mean") or _f("dist_change")
            plane1 = _f("Plane1_dir_mean_deg")
            plane2 = _f("Plane2_dir_mean_deg")
            if min_dist:
                bits.append(f"最小间距 {min_dist}m")
            if dist_change:
                bits.append(f"接近率 {abs(float(dist_change))} m/s")
            if plane1 and plane2:
                try:
                    diff = abs(float(plane1) - float(plane2))
                    bits.append(f"两机航向角偏差 {round(diff, 1)}°")
                except (TypeError, ValueError):
                    pass
            bits.append("建议立即关注双机相对状态，必要时进行避让调度")
            return "，".join(bits) + "。"

        return f"模型判定样本存在风险{head}（原始标签: {prediction_label}）。"

    # ------------------------------------------------------------------
    # 生成（由 InferenceRecordService 在推理后调用；需求 5.2/5.3/5.4/5.5）
    # ------------------------------------------------------------------
    def create_from_inference(
        self,
        current_user,
        record: InferenceRecord,
        model: ModelVersion,
        dataset: Dataset,
        risk_score: Optional[float],
    ) -> RiskEvent:
        """公开入口：根据推理结果生成风险事件（由 InferenceRecordService 调用）。

        - 校验 risk_score 必填（需求 5.2：risk_score 为风险类概率/置信度，必填项）；
        - 返回 RiskEvent ORM 对象，由调用方回填推理记录的 risk_level；
        - 异常（ServiceError 等）冒泡到调用方的 @service_call 统一转换。
        """
        self.require_login(current_user)
        if risk_score is None:
            raise ServiceError(400, "风险类预测必须提供 risk_score")
        return self._build_risk_event(
            current_user=current_user,
            record=record,
            model=model,
            dataset=dataset,
            risk_score=float(risk_score),
        )

    def _build_risk_event(
        self,
        current_user,
        record: InferenceRecord,
        model: ModelVersion,
        dataset: Dataset,
        risk_score: float,
    ) -> RiskEvent:
        """内部方法：按需求 5.2 最小字段结构组装 RiskEvent（冗余字段拷贝自主表）。"""
        risk_type = DATASET_RISK_TYPES.get(dataset.logical_id)
        if risk_type is None:
            raise ServiceError(
                400,
                f"数据集 {dataset.logical_id} 未登记风险类型映射（DATASET_RISK_TYPES），无法生成风险事件",
            )
        medium, high = self._get_thresholds(current_user.id, dataset.scenario_id)
        risk_level = self._calc_risk_level(risk_score, medium, high)

        # raw_features：只保存业务推理输入，不重复保存标签字段（需求 5.5.5）
        raw_features = dict(record.input_features or {})
        raw_features.pop(dataset.label_field, None)

        # 航母甲板故障点坐标（V3.0 §7.4.1）：仅航母场景非空，其余留空
        pos_x, pos_y = self._calc_fault_position(
            dataset.logical_id, record.input_features
        )

        event = RiskEvent(
            inference_record_id=record.id,
            created_by_user_id=record.user_id,
            scenario_id=dataset.scenario_id,
            dataset_id=dataset.id,
            dataset_version=dataset.version,
            algorithm_id=model.algorithm_id,
            model_version_id=model.id,
            original_label=record.prediction_label,
            risk_type=risk_type,
            risk_level=risk_level,
            risk_score=float(risk_score),
            # 需求 5.2：occurred_at 取推理完成并确认生成事件的时间——与推理记录保持一致
            occurred_at=record.executed_at,
            status=RISK_EVENT_STATUS_PENDING,
            raw_features=raw_features,
            description=self._build_description(
                dataset.logical_id,
                record.prediction_label,
                record.input_features,
                float(risk_score),
                risk_level,
            ),
            fault_position_x=pos_x,
            fault_position_y=pos_y,
        )
        self.db.add(event)
        self.db.flush()  # 获取 event.id，供调用方回填推理记录
        return event

    # ------------------------------------------------------------------
    # 查询（需求 5.2 访问控制：USER 按 created_by_user_id 强制过滤；ADMIN 全部）
    # ------------------------------------------------------------------
    @service_call
    def get_list(
        self,
        current_user,
        scenario_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ):
        """风险事件列表。

        - SUPER_ADMIN：仅 platform 数据集派生事件（可按场景/状态过滤）；
        - SCENARIO_ADMIN：自己场景内全部事件；
        - SCENARIO_USER：强制按 created_by_user_id 过滤（需求 5.2 访问控制第 1 条）。
        """
        self.require_login(current_user)
        role = getattr(current_user, "role", None)
        stmt = select(RiskEvent)
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
                Dataset.visibility.in_(("platform", "company")),
            )
        else:
            stmt = stmt.where(RiskEvent.created_by_user_id == current_user.id)
            if scenario_id is not None:
                self.require_scenario_access(current_user, scenario_id)
                stmt = stmt.where(RiskEvent.scenario_id == scenario_id)
        if status is not None:
            stmt = stmt.where(RiskEvent.status == status)
        stmt = stmt.order_by(RiskEvent.occurred_at.desc())
        result = paginate(self.db, stmt, page, page_size)
        result["items"] = [row_to_dict(e) for e in result["items"]]
        return ok(data=result)

    @service_call
    def get(self, current_user, event_id: int):
        """风险事件详情（按角色与数据边界校验）。"""
        event = self._get(event_id)
        self._require_event_access(current_user, event)
        return ok(data=row_to_dict(event))

    # ------------------------------------------------------------------
    # 处置状态流转（需求 5.2：新事件默认"待处置"，可变为"处理中"或"已处置"）
    # ------------------------------------------------------------------
    @service_call
    def update_status(
        self,
        current_user,
        event_id: int,
        new_status: str,
        comment: Optional[str] = None,
    ):
        """更新风险事件处置状态，并写入处置记录（handling_record）。

        状态流转：PENDING → PROCESSING → RESOLVED（由 RISK_EVENT_STATUS_TRANSITIONS 约束）。
        USER 仅能处置本人事件；ADMIN 可处置全部。
        """
        self.require_login(current_user)
        event = self._get(event_id)
        self._require_event_access(current_user, event)

        allowed = RISK_EVENT_STATUS_TRANSITIONS.get(event.status, ())
        if new_status not in allowed:
            raise ServiceError(
                400, f"风险事件状态不允许从 {event.status} 转换到 {new_status}"
            )

        status_before = event.status
        event.status = new_status

        record = HandlingRecord(
            risk_event_id=event.id,
            handler_id=current_user.id,
            action="UPDATE_STATUS",
            status_before=status_before,
            status_after=new_status,
            comment=comment,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        self.commit()
        return ok(data=row_to_dict(event), message="风险事件状态已更新")

    @service_call
    def add_comment(self, current_user, event_id: int, comment: str):
        """给风险事件追加处置说明（写 handling_record，不改状态）。"""
        self.require_login(current_user)
        event = self._get(event_id)
        self._require_event_access(current_user, event)
        if not comment or not str(comment).strip():
            raise ServiceError(400, "comment 不能为空")
        record = HandlingRecord(
            risk_event_id=event.id,
            handler_id=current_user.id,
            action="ADD_COMMENT",
            status_before=event.status,
            status_after=event.status,
            comment=str(comment).strip(),
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        self.commit()
        return ok(message="处置说明已记录")

    # ------------------------------------------------------------------
    # 删除：禁止（需求 5.2 访问控制第 4 条：历史风险事件不得被无痕删除或自动改写）
    # ------------------------------------------------------------------
    @service_call
    def delete(self, current_user, event_id: int):
        """风险事件不允许删除（需求 5.2：历史事件必须保持可追溯）。"""
        self.require_login(current_user)
        self._get(event_id)
        raise ServiceError(400, "历史风险事件不允许删除，需保持可追溯")
