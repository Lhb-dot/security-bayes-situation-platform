# Security Bayes Platform

基于 **Vue 3 + FastAPI + PMWNB 矩阵加权贝叶斯** 的安全风险智能感知与预测平台。

> 支持网络入侵检测、电力停电预警、航母舰面调度等多场景风险研判。

## 核心功能

| 模块 | 说明 |
|---|---|
| 态势监控大屏 | 攻击趋势、威胁地图、风险统计可视化 |
| AI 模型训练 | 朴素贝叶斯 / PMWNB 矩阵加权贝叶斯，多数据集支持 |
| 风险推理预测 | 三特征输入 → 加权归一化 → 阈值分级输出 |
| 安全告警列表 | 告警条目展示、详情查看、一键跳转 AI 研判 |
| 全局阈值配置 | 前端可视化配置高/中/低阈值，实时同步后端判定 |
| 实验记录报表 | 训练历史查询、删除，支持论文多组对比 |

## 项目目录

```
security-bayes-platform/
├── frontend/                   # Vue 3 + Vite + Element Plus 前端
│   └── src/views/
│       ├── Home/               # 首页看板（dashboard/ 总览 + 四场景分区）
│       ├── Model/              # 模型中心、训练、推理、报告、设置、用户管理
│       ├── Dataset/            # 数据集上传与管理
│       ├── Alert/              # 安全告警列表
│       ├── Event/              # 风险事件详情
│       ├── Login.vue           # 登录页
│       └── NotFoundView.vue    # 404 兜底页
├── backend/                    # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py             # 启动入口（挂载 2 个 router：/api/v1 下 15 个路由模块共 103 个端点 + legacy /api/model 8 个端点）
│   │   ├── api/                # 接口路由层（v1/endpoints/ 15 个模块 + legacy_model_routes）
│   │   ├── services/           # 业务逻辑层
│   │   ├── algorithms/         # 贝叶斯算法核心（PMWNB）
│   │   ├── schemas/            # Pydantic 数据校验模型
│   │   └── models/             # 数据库 ORM 模型（14 张表）
│   ├── alembic/                # 数据库迁移（Alembic）
│   ├── lib/                    # Java 服务 jar（pmwnb / predict / nb-algorithm）
│   └── storage/                # 运行时持久化
│       ├── models/             # 训练产物：.pkl / .model 文件
│       └── output/             # 运行时生成的 JSON 数据
├── data/                       # 训练数据集（ARFF）
├── scripts/                    # 核心测试与工具脚本
├── logs/                       # 运行日志
└── docs/                       # 项目文档
```

## 一键启动

```cmd
REM 命令提示符或双击运行
start_all.bat
```

```powershell
# PowerShell（需先放行脚本策略，仅首次）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\start_all.ps1
```

或分别启动：

```bash
# 1. 前端（端口 5173）
cd frontend/ && npm install && npm run dev

# 2. Java PMWNB 推理服务（端口 12313）
java -jar backend/lib/pmwnb-service.jar 12313

# 3. Java 通用预测服务（端口 12314）
java -jar backend/lib/predict-service.jar 12314

# 4. Java NB 算法服务（端口 12315，A2WNB / CAVWNB / EMAWNB / MAWNB / DIWNB 共用同一进程）
java -jar backend/lib/nb-algorithm-service.jar 12315

# 5. Python FastAPI 后端（端口 12312）
cd backend/ && python -m app.main
```

> 详细部署说明：[docs/本地环境部署启动手册.md](docs/本地环境部署启动手册.md)
>
> 团队协作规范：[docs/Git多人协作开发规范.md](docs/Git多人协作开发规范.md)
