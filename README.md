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
│       ├── Dashboard/          # 仪表盘总览
│       ├── Dataset/            # 数据集上传与管理
│       ├── Model/              # 模型训练、阈值配置
│       ├── Inference/          # 单条流量风险预测推理
│       ├── Alert/              # 安全告警列表与详情
│       └── Report/             # 训练历史实验记录报表
├── backend/                    # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py             # 启动入口（整合所有路由）
│   │   ├── api/                # 接口路由层
│   │   ├── services/           # 业务逻辑层
│   │   └── algorithms/         # 贝叶斯算法核心（PMWNB）
│   ├── deprecated/             # 二期归档（舆情爬虫、Dify 等拓展模块）
│   └── storage/models/         # 训练产物：.pkl / .model 模型文件
├── data/                       # 训练数据集（CSV）
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

# 3. Python FastAPI 后端（端口 12312）
cd backend/ && python -m app.main
```

> 详细部署说明：[docs/本地环境部署启动手册.md](docs/本地环境部署启动手册.md)
>
> 团队协作规范：[docs/Git多人协作开发规范.md](docs/Git多人协作开发规范.md)
