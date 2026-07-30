# Git 多人协作开发规范

## 一、分支命名规则

| 分支类型 | 命名格式 | 示例 |
|---|---|---|
| 主分支 | `main` | `main` |
| 功能分支 | `feature/<模块>-<简述>` | `feature/pmwnb-weighted-inference` |
| 修复分支 | `fix/<模块>-<简述>` | `fix/threshold-race-condition` |
| 重构分支 | `refactor/<范围>-<简述>` | `refactor/backend-layered-structure` |
| 文档分支 | `docs/<范围>` | `docs/deploy-guide` |
| 发布分支 | `release/<版本号>` | `release/v1.2.0` |

**当前阶段每人建议使用的分支：**

| 成员 | 负责模块 | 建议分支名 |
|---|---|---|
| 前端开发 | Vue 页面、组件、路由 | `feature/frontend-<功能名>` |
| 后端开发 | FastAPI 接口、服务层 | `feature/backend-<功能名>` |
| 算法开发 | 贝叶斯模型、推理逻辑 | `feature/algo-<功能名>` |
| Bug 修复 | 任何模块 | `fix/<模块>-<问题简述>` |

> 命名用英文小写 + 连字符，如 `feature/frontend-alert-page`，不用中文、不用下划线。

## 二、新建分支与开发流程

```bash
# 1. 切换到 main 并拉取最新代码
git checkout main
git pull origin main

# 2. 基于 main 创建新分支
git checkout -b feature/<模块>-<简述>

# 3. 编码、本地测试……

# 4. 查看改动，暂存提交
git status
git add <files>                 # 或用 git add -A 暂存全部
git commit -m "type: 简述"      # 格式见下方第三节

# 5. 推送到远程仓库
git push origin feature/<模块>-<简述>

# 6. 后续如果 main 有更新，合并到当前分支
git fetch origin main
git merge origin/main
```

## 三、Commit 提交信息规范

**格式：**

```
<type>: <简短描述>

<详细说明（可选）>

<关联 Issue（可选）>
```

**type 类型：**

| Type | 说明 |
|---|---|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 代码重构 |
| `docs` | 文档更新 |
| `style` | 代码格式（不影响逻辑） |
| `test` | 测试相关 |
| `chore` | 构建/工具/依赖 |

**示例：**

```
feat: 加权归一化风险推理，修复概率误判bug

使用 predict_proba 全部三类概率加权计算综合风险分，
归一化后匹配全局阈值，解决低置信度误判为高危的问题。

Closes #12
```

## 四、Issue 管理

### 创建 Issue

在 GitHub 仓库 Issues 页面创建，标题简明扼要，内容包含：

1. **问题描述**：当前什么现象、预期什么行为
2. **复现步骤**：操作顺序，附截图或日志
3. **环境信息**：操作系统、Python 版本、Node 版本

### Issue 标签

| 标签 | 用途 |
|---|---|
| `bug` | 功能缺陷 |
| `enhancement` | 功能增强 |
| `documentation` | 文档相关 |
| `good first issue` | 新手友好 |

### 关联 Commit

Commit 信息末尾加 `Closes #<Issue编号>`，合并后自动关闭对应 Issue。

## 五、Pull Request 流程

### 提交 PR

1. 分支推送到 GitHub 后，在仓库页面点击 **"Compare & pull request"**
2. 标题写清楚改了什么，正文写变更说明和测试情况
3. 右侧 Assignees 指派自己，Reviewers 选一位队友
4. 关联对应 Issue（如有）：在正文写 `Closes #<编号>`

### Review 与合并

1. Reviewer 检查代码逻辑、风格、是否有遗漏
2. 通过后在 PR 页面点 **"Merge pull request"** → **"Confirm merge"**
3. 合并后删除远程功能分支（页面会提示）

## 六、禁止提交的文件（黑名单）

已在 `.gitignore` 中配置，不得 `git add -f` 强制添加：

```
node_modules/          # 前端依赖
__pycache__/           # Python 编译缓存
*.pyc *.pyo            # Python 字节码
.env                   # 环境变量（含敏感信息）
*.pkl *.model          # 训练模型文件
logs/                  # 运行日志
data/                  # 数据集
.vscode/               # IDE 个人配置
*.log                  # 日志文件
dist/                  # 前端构建产物
```

## 七、docs/ 目录规范

`docs/` 存放项目级文档，不存放代码和配置：

| 应放入 docs/ | 不应放入 docs/ |
|---|---|
| 部署手册、开发规范 | Python 脚本、测试文件 |
| API 接口说明 | 模型文件 `.pkl` `.model` |
| 架构设计文档 | 数据集 CSV |
| 会议纪要、技术方案 | 个人笔记、临时草稿 |

文档用 Markdown 格式，文件名中文或英文均可，建议以功能或主题命名（如 `本地环境部署启动手册.md`）。
