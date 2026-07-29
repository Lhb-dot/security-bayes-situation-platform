# 多场景贝叶斯分类态势感知系统需求分析

> **负责人：** 王执乾、鑫彤  
> **文档状态：** 正式需求  
> **适用范围：** 系统第一阶段开发  
> **约束：** 本文仅回答会议确定的六个需求问题。后续设计、开发和测试应以本文为业务基线；发生需求变更时，应先更新本文再修改实现。

---

## 1. 三个场景分别是什么？

系统正式支持以下三个应用场景：

| 场景编码 | 场景名称 | 第一阶段状态 | 场景说明 |
|---|---|---|---|
| `network_security` | 网络安全 | 实际接入 | 对网络连接或网络流量样本进行二分类，判断其属于正常行为还是网络安全风险。 |
| `power_system` | 电力系统 | 实际接入 | 对电力设备与监测系统样本进行二分类，判断其是否形成目标电力风险事件。 |
| `flightdeck_operation` | 航母甲板作业 | 仅预留接口 | 第一阶段保留场景入口、数据集接入接口和风险映射接口；当前不配置实际数据集，不开展真实训练、推理和风险事件生成。 |

### 1.1 场景使用约束

1. 用户在训练、推理、数据集查看和态势查看前，必须先确定当前场景。
2. 数据集只能归属于一个场景；不同场景的数据集不得混合训练。
3. 模型版本必须同时绑定场景和数据集。
4. 航母甲板作业场景在第一阶段可以被展示和选择，但涉及数据、训练、推理的操作应明确显示“暂未接入数据集”，不得使用虚构数据代替正式数据。

---

## 2. 每个场景有哪些数据集？

| 场景 | 数据集编码 | 当前数据集文件 | 数据格式 | 当前样本数 | 第一阶段用途 |
|---|---|---|---|---:|---|
| 网络安全 | `kdd_train_20_percent` | `KDDTrain+_20Percent0503` | ARFF | 7556 | 训练、评估和单条样本推理 |
| 网络安全 | `nf_unsw_nb15_v2` | `NF-UNSW-NB15-v20503` | ARFF | 23897 | 训练、评估和单条样本推理 |
| 电力系统 | `powergrid_knowledgebase` | `powergrid_knowledgebase_dataset0503` | ARFF | 2000 | 训练、评估和单条样本推理 |
| 航母甲板作业 | — | 第一阶段无正式数据集 | — | — | 仅预留后续数据集注册和接入能力 |

### 2.1 当前附件标签分布

以下统计只描述当前提供的数据文件，不作为固定字段约束：

| 数据集 | 正常或负类 | 风险或正类 |
|---|---:|---:|
| KDDTrain+ 20 Percent | `normal`：4034 | `anomaly`：3522 |
| NF-UNSW-NB15-v2 | `0`：22952 | `1`：945 |
| PowerGrid Knowledgebase | `0`：406 | `1`：1594 |

### 2.2 数据集绑定规则

1. `KDDTrain+_20Percent0503` 和 `NF-UNSW-NB15-v20503` 固定归属于网络安全场景。
2. `powergrid_knowledgebase_dataset0503` 固定归属于电力系统场景。
3. 第一阶段不得把三个数据集合并为一个训练集。
4. 每次训练只能选择一个场景下的一个数据集。
5. 数据集名称、所属场景、固定字段和标签字段应作为数据集元数据保存，供字段预览、训练校验和推理表单生成使用。

---

## 3. 每个数据集有哪些固定字段？

### 3.1 固定字段的统一要求

1. 系统应按“数据集”维护独立的固定字段结构，不以一套字段强行覆盖所有场景。
2. 训练数据必须包含该数据集定义的全部字段；字段缺失、重名、类型不匹配或标签字段缺失时，不得启动训练。
3. 单条样本推理只接收输入特征，不要求用户填写分类标签。
4. 字段预览必须展示字段名、字段类型、字段角色和样例值。
5. 枚举字段必须按当前数据集定义的值域进行校验。
6. 不同数据集即使字段数量相同，也不得仅按列序号互换使用；必须同时校验数据集标识和字段名。
7. 以下字段结构以当前上传的ARFF文件为正式第一阶段结构。

### 3.2 KDDTrain+ 20 Percent

- **总字段数：** 41
- **输入特征数：** 40
- **标签字段：** `class`
- **分类目标：** `normal` / `anomaly`

| 序号 | 字段名 | 类型 | 字段角色 | 业务含义 |
|---:|---|---|---|---|
| 1 | `duration` | 数值型 | 输入特征 | 连接持续时间。 |
| 2 | `protocol_type` | 枚举型 | 输入特征 | 传输层或网络层协议类型。 |
| 3 | `service` | 枚举型 | 输入特征 | 目标端口对应的网络服务类型。 |
| 4 | `flag` | 枚举型 | 输入特征 | 连接状态标志。 |
| 5 | `src_bytes` | 数值型 | 输入特征 | 从源端到目标端传输的字节数。 |
| 6 | `dst_bytes` | 数值型 | 输入特征 | 从目标端到源端传输的字节数。 |
| 7 | `land` | 枚举型 | 输入特征 | 源地址与目标地址、源端口与目标端口是否相同；1表示相同。 |
| 8 | `wrong_fragment` | 数值型 | 输入特征 | 错误分片数量。 |
| 9 | `urgent` | 数值型 | 输入特征 | 紧急数据包数量。 |
| 10 | `hot` | 数值型 | 输入特征 | 敏感或高风险操作特征数量。 |
| 11 | `num_failed_logins` | 数值型 | 输入特征 | 登录失败次数。 |
| 12 | `logged_in` | 枚举型 | 输入特征 | 是否成功登录；1表示成功登录。 |
| 13 | `num_compromised` | 数值型 | 输入特征 | 检测到的系统受损或越权特征数量。 |
| 14 | `root_shell` | 数值型 | 输入特征 | 是否获得root shell；1表示是。 |
| 15 | `su_attempted` | 数值型 | 输入特征 | 是否尝试执行su提权操作。 |
| 16 | `num_root` | 数值型 | 输入特征 | root权限相关操作数量。 |
| 17 | `num_file_creations` | 数值型 | 输入特征 | 文件创建操作数量。 |
| 18 | `num_shells` | 数值型 | 输入特征 | 启动shell的数量。 |
| 19 | `num_access_files` | 数值型 | 输入特征 | 访问敏感文件的数量。 |
| 20 | `is_host_login` | 枚举型 | 输入特征 | 是否属于主机级登录。 |
| 21 | `is_guest_login` | 枚举型 | 输入特征 | 是否使用访客账户登录。 |
| 22 | `count` | 数值型 | 输入特征 | 统计窗口内连接到同一目标主机的连接数量。 |
| 23 | `srv_count` | 数值型 | 输入特征 | 统计窗口内访问同一服务的连接数量。 |
| 24 | `serror_rate` | 数值型 | 输入特征 | 同一目标主机连接中SYN错误连接的比例。 |
| 25 | `srv_serror_rate` | 数值型 | 输入特征 | 同一服务连接中SYN错误连接的比例。 |
| 26 | `rerror_rate` | 数值型 | 输入特征 | 同一目标主机连接中REJ错误连接的比例。 |
| 27 | `srv_rerror_rate` | 数值型 | 输入特征 | 同一服务连接中REJ错误连接的比例。 |
| 28 | `same_srv_rate` | 数值型 | 输入特征 | 同一目标主机连接中使用相同服务的比例。 |
| 29 | `diff_srv_rate` | 数值型 | 输入特征 | 同一目标主机连接中使用不同服务的比例。 |
| 30 | `srv_diff_host_rate` | 数值型 | 输入特征 | 同一服务连接中访问不同目标主机的比例。 |
| 31 | `dst_host_count` | 数值型 | 输入特征 | 目标主机统计窗口内的连接数量。 |
| 32 | `dst_host_srv_count` | 数值型 | 输入特征 | 目标主机统计窗口内使用同一服务的连接数量。 |
| 33 | `dst_host_same_srv_rate` | 数值型 | 输入特征 | 目标主机连接中使用相同服务的比例。 |
| 34 | `dst_host_diff_srv_rate` | 数值型 | 输入特征 | 目标主机连接中使用不同服务的比例。 |
| 35 | `dst_host_same_src_port_rate` | 数值型 | 输入特征 | 目标主机连接中使用相同源端口的比例。 |
| 36 | `dst_host_srv_diff_host_rate` | 数值型 | 输入特征 | 目标主机同一服务连接中访问不同主机的比例。 |
| 37 | `dst_host_serror_rate` | 数值型 | 输入特征 | 目标主机连接中SYN错误连接的比例。 |
| 38 | `dst_host_srv_serror_rate` | 数值型 | 输入特征 | 目标主机同一服务连接中SYN错误连接的比例。 |
| 39 | `dst_host_rerror_rate` | 数值型 | 输入特征 | 目标主机连接中REJ错误连接的比例。 |
| 40 | `dst_host_srv_rerror_rate` | 数值型 | 输入特征 | 目标主机同一服务连接中REJ错误连接的比例。 |
| 41 | `class` | 枚举型 | 分类标签 | 二分类标签：normal表示正常，anomaly表示异常或攻击。 |

#### 3.2.1 枚举值域

- `protocol_type`：`tcp`、`udp`、`icmp`
- `flag`：`OTH,REJ,RSTO,RSTOS0,RSTR,S0,S1,S2,S3,SF,SH`
- `service`：

```text
aol,auth,bgp,courier,csnet_ns,ctf,daytime,discard,domain,domain_u,echo,eco_i,ecr_i,efs,exec,finger,ftp,ftp_data,gopher,harvest,hostnames,http,http_2784,http_443,http_8001,imap4,IRC,iso_tsap,klogin,kshell,ldap,link,login,mtp,name,netbios_dgm,netbios_ns,netbios_ssn,netstat,nnsp,nntp,ntp_u,other,pm_dump,pop_2,pop_3,printer,private,red_i,remote_job,rje,shell,smtp,sql_net,ssh,sunrpc,supdup,systat,telnet,tftp_u,tim_i,time,urh_i,urp_i,uucp,uucp_path,vmnet,whois,X11,Z39_50
```

- `land`、`logged_in`、`is_host_login`、`is_guest_login`：`0` 或 `1`
- `class`：`normal` 或 `anomaly`

> 当前文件已形成固定的 41 列结构。开发时不得按原始NSL-KDD的其他版本自行增加当前文件中不存在的字段。

### 3.3 NF-UNSW-NB15-v2

- **总字段数：** 41
- **输入特征数：** 40
- **标签字段：** `Label`
- **分类目标：** `0` / `1`

| 序号 | 字段名 | 类型 | 字段角色 | 业务含义 |
|---:|---|---|---|---|
| 1 | `L4_SRC_PORT` | 数值型 | 输入特征 | 四层源端口。 |
| 2 | `L4_DST_PORT` | 数值型 | 输入特征 | 四层目标端口。 |
| 3 | `PROTOCOL` | 数值型 | 输入特征 | IP协议编号。 |
| 4 | `L7_PROTO` | 数值型 | 输入特征 | 应用层协议编号。 |
| 5 | `IN_BYTES` | 数值型 | 输入特征 | 流入方向字节数。 |
| 6 | `IN_PKTS` | 数值型 | 输入特征 | 流入方向数据包数。 |
| 7 | `OUT_BYTES` | 数值型 | 输入特征 | 流出方向字节数。 |
| 8 | `OUT_PKTS` | 数值型 | 输入特征 | 流出方向数据包数。 |
| 9 | `TCP_FLAGS` | 数值型 | 输入特征 | 连接级TCP标志位汇总值。 |
| 10 | `CLIENT_TCP_FLAGS` | 数值型 | 输入特征 | 客户端方向TCP标志位汇总值。 |
| 11 | `SERVER_TCP_FLAGS` | 数值型 | 输入特征 | 服务器方向TCP标志位汇总值。 |
| 12 | `FLOW_DURATION_MILLISECONDS` | 数值型 | 输入特征 | 流持续时间，单位为毫秒。 |
| 13 | `DURATION_IN` | 数值型 | 输入特征 | 流入方向持续时间。 |
| 14 | `DURATION_OUT` | 数值型 | 输入特征 | 流出方向持续时间。 |
| 15 | `MIN_TTL` | 数值型 | 输入特征 | 观测到的最小TTL。 |
| 16 | `MAX_TTL` | 数值型 | 输入特征 | 观测到的最大TTL。 |
| 17 | `LONGEST_FLOW_PKT` | 数值型 | 输入特征 | 流中最长数据包长度。 |
| 18 | `SHORTEST_FLOW_PKT` | 数值型 | 输入特征 | 流中最短数据包长度。 |
| 19 | `MIN_IP_PKT_LEN` | 数值型 | 输入特征 | 最小IP数据包长度。 |
| 20 | `MAX_IP_PKT_LEN` | 数值型 | 输入特征 | 最大IP数据包长度。 |
| 21 | `SRC_TO_DST_SECOND_BYTES` | 数值型 | 输入特征 | 源到目标方向的每秒字节量。 |
| 22 | `DST_TO_SRC_SECOND_BYTES` | 数值型 | 输入特征 | 目标到源方向的每秒字节量。 |
| 23 | `RETRANSMITTED_IN_BYTES` | 数值型 | 输入特征 | 流入方向重传字节数。 |
| 24 | `RETRANSMITTED_IN_PKTS` | 数值型 | 输入特征 | 流入方向重传数据包数。 |
| 25 | `RETRANSMITTED_OUT_BYTES` | 数值型 | 输入特征 | 流出方向重传字节数。 |
| 26 | `RETRANSMITTED_OUT_PKTS` | 数值型 | 输入特征 | 流出方向重传数据包数。 |
| 27 | `SRC_TO_DST_AVG_THROUGHPUT` | 数值型 | 输入特征 | 源到目标方向平均吞吐量。 |
| 28 | `DST_TO_SRC_AVG_THROUGHPUT` | 数值型 | 输入特征 | 目标到源方向平均吞吐量。 |
| 29 | `NUM_PKTS_UP_TO_128_BYTES` | 数值型 | 输入特征 | 长度不超过128字节的数据包数。 |
| 30 | `NUM_PKTS_128_TO_256_BYTES` | 数值型 | 输入特征 | 长度在128至256字节区间的数据包数。 |
| 31 | `NUM_PKTS_256_TO_512_BYTES` | 数值型 | 输入特征 | 长度在256至512字节区间的数据包数。 |
| 32 | `NUM_PKTS_512_TO_1024_BYTES` | 数值型 | 输入特征 | 长度在512至1024字节区间的数据包数。 |
| 33 | `NUM_PKTS_1024_TO_1514_BYTES` | 数值型 | 输入特征 | 长度在1024至1514字节区间的数据包数。 |
| 34 | `TCP_WIN_MAX_IN` | 数值型 | 输入特征 | 流入方向最大TCP窗口值。 |
| 35 | `TCP_WIN_MAX_OUT` | 数值型 | 输入特征 | 流出方向最大TCP窗口值。 |
| 36 | `ICMP_TYPE` | 数值型 | 输入特征 | ICMP类型编码。 |
| 37 | `ICMP_IPV4_TYPE` | 数值型 | 输入特征 | IPv4 ICMP类型编码。 |
| 38 | `DNS_QUERY_TYPE` | 数值型 | 输入特征 | DNS查询类型编码。 |
| 39 | `DNS_TTL_ANSWER` | 数值型 | 输入特征 | DNS应答记录TTL。 |
| 40 | `FTP_COMMAND_RET_CODE` | 数值型 | 输入特征 | FTP命令返回码。 |
| 41 | `Label` | 枚举型 | 分类标签 | 二分类标签：0表示正常流量，1表示攻击流量。 |

#### 3.3.1 值域要求

- 除 `Label` 外，当前文件中的字段均为数值型。
- `Label` 只允许取 `0` 或 `1`。
- `0` 统一解释为正常流量，`1` 统一解释为攻击流量。

### 3.4 PowerGrid Knowledgebase

- **总字段数：** 9
- **输入特征数：** 8
- **标签字段：** `Target_Event`
- **分类目标：** `0` / `1`

| 序号 | 字段名 | 类型 | 字段角色 | 业务含义 |
|---:|---|---|---|---|
| 1 | `Component` | 枚举型 | 输入特征 | 发生监测数据的电力设备或组件。 |
| 2 | `SystemName` | 枚举型 | 输入特征 | 数据所属的电力业务或监测系统。 |
| 3 | `VoltageLevel_kV` | 数值型 | 输入特征 | 电压等级，单位为kV。 |
| 4 | `CurrentAmp` | 数值型 | 输入特征 | 电流值，单位为A。 |
| 5 | `Temperature_C` | 数值型 | 输入特征 | 温度，单位为℃。 |
| 6 | `Sensor_Packet_Loss_\%` | 数值型 | 输入特征 | 传感器数据包丢失率，单位为百分比。 |
| 7 | `PowerFrequencyHz` | 数值型 | 输入特征 | 电网频率，单位为Hz。 |
| 8 | `IssueType` | 枚举型 | 输入特征兼事件解释字段 | 观测到的问题类型；作为当前数据集的输入与事件解释字段，不作为本阶段分类目标。 |
| 9 | `Target_Event` | 枚举型 | 分类标签 | 二分类标签：0表示未形成目标风险事件，1表示形成目标风险事件。 |

#### 3.4.1 枚举值域

- `Component`：`'Circuit Breaker',Transformer,Feeder,'SCADA Unit',PMU,'Voltage Regulator','Protective Relay'`
- `SystemName`：`'Load Balancing System','Fault Detection System','Topology Mapping Unit','Power Quality Analyzer'`
- `IssueType`：`'Data Loss','Harmonic Distortion','Unexpected Trip','Current Spike','Voltage Sag','Frequency Drift'`
- `Target_Event`：`0` 或 `1`

#### 3.4.2 `IssueType` 与 `Target_Event` 的关系

1. `Target_Event` 是本阶段模型的二分类标签。
2. `IssueType` 不是本阶段的六分类标签。
3. `IssueType` 表示样本中观测到或记录的问题现象，可作为当前固定输入字段，并在风险事件中用于补充具体问题说明。
4. `Target_Event=0` 的样本也可能具有 `IssueType`，因此“存在某种问题现象”不等同于“已经形成目标风险事件”。
5. 只有模型最终判定为 `Target_Event=1` 时，系统才生成电力系统风险事件。

### 3.5 航母甲板作业场景字段

第一阶段没有正式数据集，因此：

1. 不定义具体字段名、字段类型和分类标签。
2. 不允许开发人员根据演示需要自行虚构正式字段。
3. 系统只需支持后续为该场景注册数据集及其字段结构。
4. 正式数据接入后，应通过需求变更补充本节，再启用训练和推理功能。

---

## 4. 每个场景识别哪些风险？

### 4.1 网络安全场景

第一阶段只进行二分类，不识别DoS、Probe、Exploit、Backdoor等具体攻击子类。

| 数据集 | 正常结果 | 风险结果 | 统一业务解释 |
|---|---|---|---|
| KDDTrain+ 20 Percent | `class=normal` | `class=anomaly` | 风险结果统一解释为“网络安全风险” |
| NF-UNSW-NB15-v2 | `Label=0` | `Label=1` | 风险结果统一解释为“网络安全风险” |

规则：

1. 正常结果只保存推理结果，不生成 `RiskEvent`。
2. 风险结果生成网络安全场景的 `RiskEvent`。
3. 两个网络数据集的原始标签不同，但系统对外统一为“正常”与“网络安全风险”。
4. 原始标签必须保留在 `original_label` 中，以便追溯模型输出。

### 4.2 电力系统场景

| 标签结果 | 业务解释 | 是否生成风险事件 |
|---|---|---|
| `Target_Event=0` | 未形成目标电力风险事件 | 否 |
| `Target_Event=1` | 形成电力系统风险 | 是 |

当 `Target_Event=1` 时，`IssueType` 用于说明该事件涉及的具体问题现象，当前可能值包括：

- Data Loss：数据丢失
- Harmonic Distortion：谐波失真
- Unexpected Trip：意外跳闸
- Current Spike：电流尖峰
- Voltage Sag：电压暂降
- Frequency Drift：频率漂移

这些值用于事件解释和展示，不改变第一阶段“是否形成风险事件”的二分类目标。

### 4.3 航母甲板作业场景

1. 第一阶段不识别具体航母甲板作业风险。
2. 系统预留航母甲板作业风险的大类编码和映射接口。
3. 在正式数据集、固定字段和标签定义完成前，不得生成真实航母甲板作业 `RiskEvent`。
4. 预留风险大类可使用 `FLIGHT_DECK_OPERATION_RISK`，但其具体标签映射必须在后续需求中确定。

---

## 5. 这些风险怎么统一成 `RiskEvent`？

### 5.1 统一原则

不同场景的字段结构和原始标签不同，但所有风险结果必须转换为统一的 `RiskEvent` 结构。统一结构负责支持风险列表、全局态势总览、场景态势展示和后续处置；场景差异字段统一保存在 `raw_features` 中。

### 5.2 `RiskEvent` 最小字段结构

| 字段 | 必填 | 含义 | 生成规则 |
|---|---|---|---|
| `event_id` | 是 | 风险事件唯一编号 | 系统生成，不得重复 |
| `scenario_id` | 是 | 所属场景 | 取当前训练或推理绑定的场景 |
| `dataset_id` | 是 | 来源数据集 | 取当前推理使用的数据集 |
| `model_version_id` | 是 | 产生结果的模型版本 | 取实际执行推理的模型版本 |
| `original_label` | 是 | 数据集原始预测标签 | 保留 `anomaly`、`1` 等原始输出 |
| `risk_type` | 是 | 统一风险类型 | 按场景和标签映射生成 |
| `risk_level` | 是 | 低、中、高风险等级 | 由 `risk_score` 和可配置阈值计算 |
| `risk_score` | 是 | 风险类别的模型概率或置信度 | 取模型对风险类的输出分数 |
| `occurred_at` | 是 | 风险事件产生时间 | 取推理完成并确认生成事件的时间 |
| `status` | 是 | 事件处置状态 | 新事件默认“待处置”，后续可变为“处理中”或“已处置” |
| `raw_features` | 是 | 原始输入特征JSON | 保存通过字段校验后的本次推理输入 |
| `description` | 是 | 风险说明 | 根据场景、数据集、原始标签及解释字段生成 |

### 5.3 风险类型映射

| 场景 | 数据集 | 原始预测结果 | 是否生成事件 | `risk_type` |
|---|---|---|---|---|
| 网络安全 | KDDTrain+ 20 Percent | `normal` | 否 | — |
| 网络安全 | KDDTrain+ 20 Percent | `anomaly` | 是 | `NETWORK_SECURITY_RISK` |
| 网络安全 | NF-UNSW-NB15-v2 | `0` | 否 | — |
| 网络安全 | NF-UNSW-NB15-v2 | `1` | 是 | `NETWORK_SECURITY_RISK` |
| 电力系统 | PowerGrid Knowledgebase | `Target_Event=0` | 否 | — |
| 电力系统 | PowerGrid Knowledgebase | `Target_Event=1` | 是 | `POWER_SYSTEM_RISK` |
| 航母甲板作业 | 第一阶段无数据集 | — | 否 | 仅预留 `FLIGHT_DECK_OPERATION_RISK` |

### 5.4 风险等级生成规则

系统不在需求文档中写死具体阈值数值，而是使用可配置阈值：

```text
若模型结果为正常类：
    保存推理结果，不生成 RiskEvent

若模型结果为风险类：
    risk_score >= high_threshold
        risk_level = HIGH

    medium_threshold <= risk_score < high_threshold
        risk_level = MEDIUM

    risk_score < medium_threshold
        risk_level = LOW
```

约束：

1. `high_threshold` 必须大于 `medium_threshold`。
2. 阈值调整只影响风险等级，不改变模型的原始预测标签。
3. `risk_score` 必须表示风险类别概率或可比较的置信度分数，不得使用准确率、召回率等模型整体评价指标代替。
4. 每个风险事件必须可追溯到场景、数据集和模型版本。

### 5.5 `raw_features` 使用规则

1. `RiskEvent` 的公共字段保持跨场景一致。
2. 网络连接字段、电力设备字段以及未来航母甲板字段差异较大，不应全部展开为统一事件表的固定列。
3. `raw_features` 保存本次推理的原始字段和值，格式为JSON对象。
4. `raw_features` 中的键名应保持数据集正式字段名，不进行随意改名。
5. `raw_features` 只保存业务推理输入，不重复保存标签字段。
6. 电力事件的 `description` 应结合 `IssueType` 生成，例如“检测到电力系统风险，问题现象为 Voltage Sag”。

### 5.6 示例

#### 网络安全风险事件

```json
{
  "event_id": "evt_network_000001",
  "scenario_id": "network_security",
  "dataset_id": "nf_unsw_nb15_v2",
  "model_version_id": "model_000012",
  "original_label": "1",
  "risk_type": "NETWORK_SECURITY_RISK",
  "risk_level": "HIGH",
  "risk_score": 0.93,
  "occurred_at": "由系统生成",
  "status": "待处置",
  "raw_features": {
    "L4_SRC_PORT": 7636,
    "L4_DST_PORT": 6452,
    "PROTOCOL": 6
  },
  "description": "模型判定该网络流量样本存在网络安全风险。"
}
```

#### 电力系统风险事件

```json
{
  "event_id": "evt_power_000001",
  "scenario_id": "power_system",
  "dataset_id": "powergrid_knowledgebase",
  "model_version_id": "model_000020",
  "original_label": "1",
  "risk_type": "POWER_SYSTEM_RISK",
  "risk_level": "MEDIUM",
  "risk_score": 0.78,
  "occurred_at": "由系统生成",
  "status": "待处置",
  "raw_features": {
    "Component": "Feeder",
    "SystemName": "Topology Mapping Unit",
    "VoltageLevel_kV": 757.97,
    "IssueType": "Voltage Sag"
  },
  "description": "模型判定该样本形成电力系统风险，问题现象为 Voltage Sag。"
}
```

---

## 6. 系统第一阶段必须做哪些功能？

### 6.1 优先级定义

- **P0：** 第一阶段必须完成，是系统形成“场景选择—数据集查看—模型训练—单条推理—风险事件—态势展示”业务闭环的验收底线。
- **P1：** 在P0完成后实现的重要增强功能。
- **P2：** 后续扩展功能，暂不作为第一阶段重点。

### 6.2 正式功能优先级表

| 模块 | 功能 | 正式需求说明 | 优先级 |
|---|---|---|---|
| 场景管理 | 场景列表 | 展示网络安全、电力系统、航母甲板作业三个场景卡片，并标明场景当前接入状态。 | P0 |
| 场景管理 | 场景切换 | 用户选择场景后，全局按场景筛选数据；训练、推理和展示均使用当前场景上下文。 | P0 |
| 数据集管理 | 数据集列表 | 按场景展示数据集；网络安全展示两个数据集，电力系统展示一个数据集，航母甲板作业显示暂未接入。 | P0 |
| 数据集管理 | 字段预览 | 查看数据集固定字段、类型、字段角色和样例数据。 | P0 |
| 模型训练 | 选择场景和数据集 | 训练前必须绑定场景和数据集；不得跨场景或跨数据集合并训练。 | P0 |
| 模型训练 | 训练贝叶斯模型 | 使用选定数据集执行贝叶斯分类模型训练，并返回 Accuracy、Recall、F1、G-mean。第一阶段默认实现算法为PMWNB。 | P0 |
| 风险研判 | 单条样本推理 | 根据所选数据集固定字段生成输入项，校验后执行推理，输出风险概率和风险等级。 | P0 |
| 风险事件 | 风险事件列表 | 对网络、电力及未来航母风险事件使用统一结构展示；第一阶段航母场景无真实事件。 | P0 |
| 态势展示 | 全局态势总览 | 展示三个场景风险对比；未接入或无事件的场景必须显示真实状态，不使用虚构事件补齐。 | P0 |
| 报告生成 | 生成态势报告 | 根据场景、风险事件和态势结果生成报告，并支持导出 Markdown、HTML或PDF。 | P1 |
| 模型管理 | 模型版本对比 | 对比不同训练记录及其数据集、模型版本和评价指标。 | P1 |
| 用户权限 | 登录和权限 | 支持登录及权限控制，暂不作为第一阶段重点。 | P2 |

### 6.3 第一阶段P0业务闭环

第一阶段至少应实现以下闭环：

```text
查看三个场景
→ 选择已接入场景
→ 查看该场景的数据集
→ 预览并校验固定字段
→ 选择场景和数据集训练PMWNB模型
→ 查看 Accuracy、Recall、F1、G-mean
→ 使用对应固定字段完成单条样本推理
→ 输出风险概率和风险等级
→ 风险类结果转换为统一 RiskEvent
→ 在风险事件列表和全局态势总览中展示
```

P0功能未全部贯通前，系统不能视为完成第一阶段最低要求。
