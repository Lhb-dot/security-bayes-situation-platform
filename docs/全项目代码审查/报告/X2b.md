# X2b 分区审查报告 · `backend/alembic/**`

> 分区：X2b（`backend/alembic/**`，32 个 git 跟踪文件，1840 行）
> 硬约束：**不修改任何 `versions/*.py`**（历史不可变）。唯一可改 `env.py` / `script.py.mako` / `README`。
> 报告骨架先落盘，逐节回填。

---

## §0 速览

| 项 | 结论 |
|---|---|
| 分区文件 | `backend/alembic/**`，git 跟踪 **32** 个：`env.py`、`script.py.mako`、`README` + **29** 个 `versions/*.py` |
| 行数 | 29 个迁移共 **1705** 行；加 `env.py` 77 + `script.py.mako` 28 + `README` 1 = **1811** 行（任务书估 1840，含空行口径差异） |
| 迁移链 | **线性，单 head**（`20260927_000001`）、单 base（`85b25ac03ba5`）；**无分叉、无断链、无孤立迁移、无重复 revision id** |
| 硬编码 revision | 全仓库仅 1 处，是 `backend/app/models/__init__.py:4` 的**注释**，非代码引用 |
| 迁移↔模型漂移 | **10 项**（详见 §6.2）：只存在于迁移的 CHECK 2 项、只存在于迁移的部分索引 2 项（**autogenerate 会提议删除**）、约束名新老环境不一致 1 类（4 个 FK）、`server_default` 漂移 4 项、模型有而迁移链无 `create_table` 1 项 |
| **重大发现** | 基线迁移用 `create_all()` 建**当前**全量 schema，导致**全新库 `alembic upgrade head` 会在第 5 个 revision 报 `DuplicateColumn` 中断**（§6.1） |
| 可逆性 | 可逆 **7** / 有损 **9** / 不可逆 **13**（§6.3） |
| 破坏性无保护操作 | **12 个迁移文件、25 条 DDL**（20 `add_column` + 2 `create_table` + 3 `create_foreign_key`）在**全新库上必然冲突**（§6.1）；但 **`NOT NULL` 新列无 `server_default` = 0 处**（§6.4）✓ |
| 建议新增索引 | **8** 条（§6.5），其中 3 条已被既有部分索引部分覆盖 |
| FK `ondelete` 不一致 | 全库 **31** 个 FK：仅 **2** 个带 `ondelete=CASCADE`，**29** 个无 `ondelete`（§6.6） |
| 已改动 | **仅 `backend/alembic/env.py` 1 行**（`%` 转义，`py_compile` EXIT=0）；**未动任何 `versions/*.py`** |
| 跨区提案 | **4** 项（§8）：新库引导流程（最高优先级，跨 `scripts/`+`docs/`+`start_all.ps1`）、`downgrade base` 告警、模型侧对齐漂移、`alembic.ini`/`script.py.mako`/`README` 约定沉淀 |

---

## §1 范围与文件清单

写作用域：`backend/alembic/**`。**唯一被允许修改的**是 `env.py` / `script.py.mako` / `README`。

| 文件 | 改前行数 | 改后行数 | 是否改动 |
|---|---|---|---|
| `backend/alembic/env.py` | 77 | 80 | **是**（+3 注释行，1 行代码语义变化） |
| `backend/alembic/script.py.mako` | 28 | 28 | 否 |
| `backend/alembic/README` | 1 | 1 | 否 |
| `versions/*.py`（29 个） | 1705 | 1705 | **否（硬约束，绝不修改）** |

命令与输出（`git ls-files`）：

```
$ git ls-files backend/alembic | Measure-Object  →  32
$ git ls-files backend/alembic | Select-String '__pycache__|\.pyc' | Measure-Object  →  0
```

**`versions/__pycache__` 未入库**（0 个跟踪文件）——磁盘上存在 31 个 `.pyc`，其中 `15ce513deaef_diff_*.pyc` 与 `20260903_000001_fi*.pyc` 对应的 `.py` **在仓库里根本不存在**（历史遗留垃圾，非「已提交死代码」）。按协议 §3.B 判定为磁盘垃圾，**不写进已提交死代码，也不删**（不属于我的写作用域内的跟踪文件）。

---

## §2 迁移链与 head

### §2.1 完整链（29 个迁移，`revision → down_revision`）

| # | revision | down_revision | 文件 | 说明 |
|---|---|---|---|---|
| 1 | `85b25ac03ba5` | `None` | `85b25ac03ba5_create_core_tables.py` | 基线：`Base.metadata.create_all()` 建全部表 |
| 2 | `d6adba5112b8` | `85b25ac03ba5` | `d6adba5112b8_seed_scenario_and_algorithm.py` | seed 3 场景 + 5 算法 |
| 3 | `a3b5c7d9e1f2` | `d6adba5112b8` | `20260806_120000_add_geological_risk_scenario.py` | 第 4 个场景 `geological_risk` |
| 4 | `20260808_000001` | `a3b5c7d9e1f2` | `..._update_algorithm_param_schema.py` | 5 算法 `param_schema`/`display_name` |
| 5 | `20260814_000001` | `20260808_000001` | `..._add_user_scenario.py` | `app_user.scenario_id` + FK |
| 6 | `20260814_000002` | `20260814_000001` | `..._add_risk_event_position.py` | `risk_event.fault_position_x/y` |
| 7 | `20260814_000003` | `20260814_000002` | `..._add_dataset_visibility.py` | `dataset.visibility/uploader_role` |
| 8 | `20260814_000004` | `20260814_000003` | `..._migrate_roles.py` | `ADMIN→SUPER_ADMIN`、`USER→SCENARIO_USER` + 场景绑定 |
| 9 | `20260816_000001` | `20260814_000004` | `..._add_report_schedule_fields.py` | `report.scenario_id/format/scheduled/interval_days` |
| 10 | `20260820_000001` | `20260816_000001` | `..._add_auth_sessions_and_role_constraints.py` | **建 `auth_session` 表** + 2 条 `app_user` CHECK |
| 11 | `20260820_000002` | `20260820_000001` | `..._bind_risk_thresholds_to_users.py` | 两表加 `user_id`、改 PK、加 FK |
| 12 | `20260820_000003` | `20260820_000002` | `..._restrict_threshold_precision.py` | `Numeric(5,4)→(4,2)` |
| 13 | `20260820_000004` | `20260820_000003` | `..._add_model_disabled_status.py` | `model_version` `OFFLINE→DISABLED` |
| 14 | `20260822_000001` | `20260820_000004` | `..._add_report_title.py` | `report.title` |
| 15 | `20260822_000002` | `20260822_000001` | `..._replace_diwnb_with_cavwnb.py` | `DIWNB→CAVWNB` |
| 16 | `20260822_000003` | `20260822_000002` | `..._wire_real_algorithm_parameters.py` | 5 算法 `param_schema` |
| 17 | `20260822_000004` | `20260822_000003` | `..._remove_unimplemented_a2_task.py` | A2WNB schema 收敛为 2 项 |
| 18 | `20260822_000005` | `20260822_000004` | `..._add_pmwnb_discretization_params.py` | PMWNB 离散参数 |
| 19 | `20260822_000006` | `20260822_000005` | `..._update_algorithm_display_names.py` | `display_name` 统一格式 |
| 20 | `20260822_000007` | `20260822_000006` | `..._restore_diwnb_and_clear_pmwnb_params.py` | 恢复 DIWNB + 清 PMWNB 参数 |
| 21 | `20260906_000001` | `20260822_000007` | `..._add_explain_and_report_data.py` | `inference_record.explain_data` + `report.report_data` |
| 22 | `20260913_000001` | `20260906_000001` | `..._add_user_ai_setting.py` | **建 `user_ai_setting` 表** |
| 23 | `20260914_000002` | `20260913_000001` | `..._add_model_evaluation.py` | `model_version.model_attributes/ai_evaluation` |
| 24 | `20260915_000001` | `20260914_000002` | `..._clean_algorithm_display_text.py` | 文案清理（description + param help） |
| 25 | `20260915_000002` | `20260915_000001` | `..._add_dataset_name.py` | `dataset.name` |
| 26 | `20260920_000001` | `20260915_000002` | `..._fix_a2wnb_description.py` | A2WNB `description` |
| 27 | `20260920_000002` | `20260920_000001` | `..._mark_discretization_numeric_only.py` | 加 `requires_numeric_features` 标记 |
| 28 | `20260923_000001` | `20260920_000002` | `..._add_report_next_run_at.py` | `report.next_run_at` + 部分索引 |
| 29 | `20260927_000001` | `20260923_000001` | `..._add_risk_event_hidden.py` | `risk_event.hidden_at/hidden_by_user_id` + FK + 部分索引 |

**head = `20260927_000001`（唯一）**，**base = `85b25ac03ba5`（唯一，`down_revision=None`）**。

### §2.2 链结构结论

- **线性**：`revision` 集合与 `down_revision` 集合构成一条 29 节点的单链。每个 `down_revision`（除 base 的 `None`）都能在 `revision` 集合里找到对应节点 → **零断链**。
- **无分叉**：每个 `down_revision` 只被一个子节点引用，除 head 外每个 revision 恰好有一个子节点 → **无多 head、无孤立迁移**。
- **无重复 revision id**：29 个 id 两两不同（其中 3 个是哈希风格 `85b25ac03ba5`/`d6adba5112b8`/`a3b5c7d9e1f2`，26 个是日期风格 `YYYYMMDD_NNNNNN`）。
- 编号有空档：**不存在** `20260903_000001`、`20260914_000001`（`20260914_000002` 是 `20260913_000001` 的直接子节点）。空档无害，但 `versions/__pycache__` 里留着这两个编号的 `.pyc`，说明迁移文件被删过/改过名。

### §2.3 硬编码 revision 字符串

```
$ git grep -n -E '85b25ac03ba5|d6adba5112b8|a3b5c7d9e1f2|20260814_000001|20260820_000001|20260822_00000|20260927_000001' \
    -- . ':!backend/alembic/versions' ':!docs'
backend/app/models/__init__.py:4:metadata.create_all 依赖这一点）。基线迁移 85b25ac03ba5 直接调用
[exit 0]
```

**唯一命中是注释**，`backend/app/**`、`scripts/**`、`start_all.ps1` 里没有任何代码依赖具体 revision 字符串（无 `stamp <rev>`、无 `upgrade <rev>` 硬编码）。`start_all.ps1:86` 用的是 `python -m alembic upgrade head`（相对 head，安全）。

### §2.4 基线 `create_all()` 对「迁移链完整性」意味着什么（核实 B6b-2 的 U4）

**核实结果：成立，且比 B6b-2 描述的更严重。**

```
$ git grep -n 'create_all' -- backend/app
backend/app/models/__init__.py:4:  (注释)
backend/app/models/__init__.py:5:  (注释)
```

全项目**只有**基线迁移 `85b25ac03ba5:29-30` 调用 `create_all`：

```python
bind = op.get_bind()
Base.metadata.create_all(bind=bind)
```

含义与后果：

1. **迁移链不是 schema 的事实来源，模型才是。** 基线在**执行时**导入 `app.models`，把**当下**全部 14 张表按**当下**的列/类型/索引一次性建出来。所以「迁移链的累加结果」**不等于**「实际 schema」——实际 schema 是「当前模型」+「迁移里那些模型没声明的对象」。
2. **新老环境一致性完全依赖「模型零漂移」**：只要有人在 `app/models/**` 里改一个列（哪怕只是加个 `server_default`），老库（走迁移链）与新库（走 `create_all`）就会分叉，而 `alembic_version` 两边都是 head，**没有任何机制能发现这个分叉**。
3. **全新库跑不通 `alembic upgrade head`**（详见 §6.1）：基线 `create_all` 已经建出全部当前列，紧随其后的增量迁移又去 `add_column` 同一列 → `DuplicateColumn`。
4. 作者**知道**这个矛盾，并只在**两处**做了兼容（`20260820_000002:17-19`、`20260820_000003:13-14` 用 `context.is_offline_mode()` + `sa.inspect` 做幂等守卫），其余 11 处未加守卫。这就是为什么这两处看起来「风格突兀」——它们是补丁，不是设计。

---

## §3 A. 弃用（deprecated）

逐项查了什么 + 结论：

| 检查项 | 命令 | 结论 |
|---|---|---|
| `datetime.utcnow()` | `git grep -n 'utcnow' -- backend/alembic` | **零命中**。时间戳一律用 aware 时间：`datetime(2026,8,2,tzinfo=timezone.utc)`（`d6adba5112b8:29`、`20260806_120000:30`）。**唯一** `datetime.now(timezone.utc)` 在 `20260822_000007:93`（DIWNB 的 `created_at`）——aware 不算弃用，但**非确定值**（见 §6.8）。 |
| `server_default` 里用 Python 可调用/`utcnow` | `git grep -n 'server_default=' -- backend/alembic` | 8 处，全是**字面量或 `sa.false()`/`sa.true()`**（`20260814_000003:24`、`20260816_000001:36,40`、`20260822_000001:16`、`20260913_000001:16,20`）。**无 `datetime.utcnow`**、**无 `func.now()` 与模型不一致**问题。 |
| 非 PostgreSQL 方言 | `git grep -n 'dialects' -- backend/alembic` | 只出现 `sqlalchemy.dialects.postgresql.JSONB`（`20260906_000001:15,26,30`、`20260914_000002:5,17,21`）。项目是 PG-only，**必要且正确**；无 MySQL/SQLite/`sa.JSON` 混用。 |
| `sa.text` 隐式类型转换 | 逐文件读 | **无隐式转换**。jsonb 一律显式：`CAST(:param_schema AS jsonb)`（`d6adba5112b8:63`、`20260808_000001:121`、`20260822_000002:46`、`20260822_000003:119`、`20260822_000004:43`、`20260822_000005:45`、`20260822_000007:77,85,103`）、`param_schema::text`（`20260915_000001:53`）、`'{"...": true}'::jsonb`（`20260920_000002:32`）。 |
| 旧式 `op.execute(裸字符串)` | 逐文件读 | 4 处裸字符串：`d6adba5112b8:75,77`、`a3b5c7d9e1f2:54`、`20260814_000004:22,23,42,43`、`20260820_000001:12,13,14,15-25`、`20260820_000002:80-93`、`20260923_000001:29-36`。**不算弃用**（Alembic 官方支持，且 offline 模式必须用纯 SQL），但与同仓库「`sa.text` + `bindparams`」风格并存 → 一致性瑕疵，记 §5。**注意：这些裸字符串里没有任何一处拼接用户输入**，无注入面。 |
| Alembic 旧 API | `git grep -n 'get_bind\|is_offline_mode\|postgresql_using\|type_=' -- backend/alembic` | **全部是当前 API**：`op.get_bind()`（9 处）、`context.is_offline_mode()`（`20260820_000002:17`、`20260820_000003:13`）、`postgresql_using=`（`20260820_000003:20,27,34,41,48,55`）、`drop_constraint(..., type_="primary"/"check"/"foreignkey")`。**无 `alembic.op.get_bind().execute` 之外的老式 `context.execute` 误用**（offline 分支用的是 `context.configure(url=...)` + `context.run_migrations()`，标准写法）。 |
| `revision` 注解风格 | `git grep -l '^revision: str'` / `'^revision = '` | 混用：**4 个**用 `revision: str = ...`（基线、seed、`20260806`、`20260808`），**25 个**用 `revision = "..."`。两者都非弃用（Alembic 1.18 生成的模板本身就用注解形式），但**仓库内不统一** → 记 §5。 |
| `import sqlalchemy as sa` 是否仍被 Alembic 需要 | 见 §4 | 1 处未使用（基线）。 |

**A 节结论：本分区无「弃用」级问题（0 项需修）。** 只有 2 项风格不一致（裸 SQL vs `sa.text`、`revision` 注解形式），归入 §5。

---

## §4 B. 残留 / 死代码

| 检查项 | 命令 | 结论 |
|---|---|---|
| 注释掉的代码 | 逐文件读 29 个 + `env.py` + `mako` | **无**。所有注释都是说明性中文注释（需求出处、设计权衡），无被注释掉的语句。 |
| `print` / `breakpoint` | `git grep -n -E 'print\(\|breakpoint\(' -- backend/alembic` | **零命中**。 |
| `TODO`/`FIXME`/`XXX` | `git grep -n -E 'TODO\|FIXME\|XXX' -- backend/alembic` | **零命中**。 |
| `pass` 占位 | `git grep -n -E '^\s+pass\s*$' -- backend/alembic` | **零命中** → **无空迁移**。29 个 `upgrade()`/`downgrade()` 全部有真实实现。 |
| 未使用 import | `git grep -n '\bsa\.' -- .../85b25ac03ba5_create_core_tables.py` | **1 处**：`85b25ac03ba5_create_core_tables.py:14` `import sqlalchemy as sa` **完全未使用**（该文件只用 `op` 与 `Base`）。这是 `script.py.mako` 模板的样板 import。**不可改**（迁移不可变），仅报告。其余 28 个迁移的 `sa` / `json` / `datetime` / `postgresql` / `Sequence, Union` **全部有使用**。 |
| 构建产物入库 | `git ls-files backend/alembic \| Select-String '__pycache__\|\.pyc'` → **0** | `versions/__pycache__`（31 个 `.pyc`）**未跟踪**，属磁盘垃圾。其中 `15ce513deaef_diff_*.pyc`、`20260903_000001_fi*.pyc` 对应的 `.py` 在仓库中不存在 → 迁移被删/改名的残留。**不写进「已提交死代码」，不删**（非跟踪文件，且不属于需要交付的清理项）。 |
| `README` 是否模板默认文字 | 读全文 | **是**：全文只有一行 `Generic single-database configuration.`（Alembic 脚手架原文）。→ **提案补写**（§8.4）。 |
| `script.py.mako` 是否模板默认文字 | 读全文 | **是**：与 Alembic 1.18 官方模板逐字相同，生成的 stub 用 `pass`、revision id 用哈希。项目实际约定（日期前缀 revision id、中文 docstring 写明需求出处、`downgrade` 必须实现）**完全没有沉淀进模板** → **提案**（§8.4）。 |
| 过期文档 | 读 `alembic.ini`、`env.py:18` | 2 处**与代码不符的注释**：① `env.py:18` 写「全部 **12** 张表」，实际 `app/models/__init__.py:9` 自述 **14** 张；② `alembic.ini:1` 与 `:89` 仍是脚手架文案与 `driver://user:pass@localhost/dbname` 占位串（该串不是真实凭据，无泄漏）。→ `env.py:18` 已随本次改动修正；`alembic.ini` 在分区外，记 §8.3。 |
| 失效的 offline 路径 | 读 `20260820_000002:17-19`、`20260820_000003:13-14` | 这两个迁移在 `--sql`（offline）模式下**直接 `return`**，即 `alembic upgrade head --sql` 输出的 SQL **缺失**这 11 条 `alter_column` + 建列/改 PK/FK 语句。这不是「死代码」，而是**主动放弃 offline 能力**——因为基线的 `create_all()` 无法转成 SQL，offline 模式在本项目**从根上不可用**。→ 记 §6.9。 |

**B 节结论：无已提交死代码。** 1 处未使用 import（迁移内，不可改）+ 2 处模板默认文件（`README`/`script.py.mako`，可改但改动需 Lead 认可内容，见提案）+ 1 处过期注释（已在 `env.py` 修正）。

---

## §5 C. 复杂度（over-complex）

| 检查项 | 结论 |
|---|---|
| 超长 `upgrade()`（> 80 行） | **0 个**。最长 `20260820_000002.upgrade` 56 行（含注释），其次 `20260820_000003.upgrade` 46 行。 |
| 超长文件（> 800 行） | **0 个**。最长 `20260808_000001_update_algorithm_param_schema.py` 144 行。 |
| 深层嵌套（> 3 层） | **0 处**。最深处是 `20260822_000007:81-95`（`if not exists:` → `conn.execute(...)`，2 层）。 |
| **重复样板（本分区最突出的复杂项）** | **同一段「离散化方式 + 分箱数量」参数定义被复制 5 次**：<br>① `20260808_000001:33-61`（`_enum`/`_num` 工厂 + 字面量）<br>② `20260822_000003:15-55`（`_enum`/`_int` 工厂 + 字面量，**与①的同名函数实现不同**：`_num` 有 `min/max/step`，`_int` 固定 `step=1`）<br>③ `20260822_000004:16-41`（纯字面量）<br>④ `20260822_000005:15-40`（纯字面量，仅 `description` 多了「PMWNB 」前缀）<br>⑤ `20260822_000007:17-42`（DIWNB）+ `:45-70`（PMWNB 旧值，供 downgrade）<br>③④⑤ 三处字面量**逐字相同**（除 description 前缀）。→ **只提案，不新建文件**（§8.4）：迁移是不可变历史，正确做法是把参数定义收敛到 `app/services/algorithm_config.py` 之类，由**新迁移**引用，而不是回改旧迁移。 |
| 互相抵消的迁移 | `20260822_000003:92-103` 给 A2WNB 装上 `[discrete_method, discrete_bins, rode_task]`，紧接着 `20260822_000004:16-41` 又把它替换为 `[discrete_method, discrete_bins]`（docstring 说明 `rode_task` 的源码分支未实现）。**两个相邻迁移一半互相抵消** → 历史冗余，不可改，仅记录。 |
| 魔法字符串 | 角色（`'ADMIN'`/`'SUPER_ADMIN'`/`'SCENARIO_ADMIN'`/`'SCENARIO_USER'`）、模型状态（`'OFFLINE'`/`'DISABLED'`）、算法 code（5+1 个）、场景 code（4 个）、可见性（`'platform'`）、格式（`'markdown'`）全部以**裸字符串**散落在 8 个迁移里。迁移之间**无法共享常量**（新建 `alembic/constants.py` 会引入「迁移依赖仓库代码」的脆弱耦合，且协议禁止新建文件）→ **只报告，不提案改动**。 |
| 复杂 SQL | `20260920_000002:25-60` 两段 `jsonb_array_elements(...) WITH ORDINALITY` + `jsonb_agg(... ORDER BY ordinality)`。写法**正确且幂等**（用 ordinality 保序，用 `jsonb_typeof = 'array'` 与 `EXISTS` 双重守卫），且已具名为 `_ADD_FLAG`/`_REMOVE_FLAG` → **可接受，不改**。 |
| 重复 `sa.inspect` | `20260820_000002` 三次 `sa.inspect(op.get_bind())`（`:20`、`:39`、`:51`）。看似可合并，但 `:39` 与 `:51` 之间执行了 `alter_column`（DDL），inspector 缓存必须刷新 → **重取是正确的，不改**。 |
| 风格不统一 | ① 4 个迁移用 `revision: str = ...`、25 个用 `revision = ...`；② 数据变更有的走 `sa.text().bindparams()`、有的走裸字符串；③ 5 个迁移有中文 docstring 写需求出处，5 个只有一行英文标题（`20260820_000001`、`20260820_000002`、`20260820_000003`、`20260820_000004`、`20260822_000002` 等）。**历史文件不可改**，价值在于**把约定写进 `script.py.mako`** → 提案 §8.4。 |

**C 节结论：无函数级复杂度过高问题；本分区的「复杂」全部表现为跨迁移的重复样板，而重复样板的正确解法是模板 + 新迁移，不是回改历史。**

---

## §6 D. 正确性隐患（重点）

### §6.1 【最高优先级】全新库无法 `alembic upgrade head`——链在第 5 个 revision 断裂

**证据链（全部为静态可验证事实，未执行任何 alembic 命令）：**

1. `85b25ac03ba5_create_core_tables.py:17,29-30`：
   ```python
   import app.models          # 把「当前」全部 14 张表注册到 Base.metadata
   ...
   bind = op.get_bind()
   Base.metadata.create_all(bind=bind)
   ```
   `create_all` 用的是**运行时**的模型定义，不是 2026-08-02 写这个文件时的 12 张表。`app/models/__init__.py:9` 自述现有 **14** 张表。
2. 因此在**空库**上，第 1 个 revision 就把 **14 张表 + 全部当前列/索引/约束**建好了。
3. 第 5 个 revision `20260814_000001_add_user_scenario.py:25-28` 紧接着执行：
   ```python
   op.add_column("app_user", sa.Column("scenario_id", sa.BigInteger(), nullable=True))
   ```
   而 `app_user.scenario_id` **已经在第 1 步被建出来了** → PostgreSQL 报 `DuplicateColumn: column "scenario_id" of relation "app_user" already exists`，`upgrade head` 中断。

**完整的冲突清单（12 个文件、25 条 DDL，全部必然失败）：**

| revision | 冲突 DDL | 失败原因 |
|---|---|---|
| `20260814_000001` | `add_column app_user.scenario_id`；`create_foreign_key fk_app_user_scenario` | 列已存在；同名 FK 已由 `create_all` 以 `app_user_scenario_id_fkey` 建出（名字不同，但列已有 FK，重复 FK 也会成功建出**重复外键**） |
| `20260814_000002` | `add_column risk_event.fault_position_x/y` | 列已存在 |
| `20260814_000003` | `add_column dataset.visibility/uploader_role` | 列已存在 |
| `20260816_000001` | `add_column report.scenario_id/format/scheduled/interval_days`；`create_foreign_key fk_report_scenario` | 列已存在 |
| `20260820_000001` | `create_table auth_session`；`create_index ix_auth_session_*` ×2 | 表与索引已存在 |
| `20260822_000001` | `add_column report.title` | 列已存在 |
| `20260906_000001` | `add_column inference_record.explain_data`、`report.report_data` | 列已存在 |
| `20260913_000001` | `create_table user_ai_setting` | 表已存在 |
| `20260914_000002` | `add_column model_version.model_attributes/ai_evaluation` | 列已存在 |
| `20260915_000002` | `add_column dataset.name` | 列已存在 |
| `20260923_000001` | `add_column report.next_run_at` | 列已存在 |
| `20260927_000001` | `add_column risk_event.hidden_at/hidden_by_user_id`；`create_foreign_key risk_event_hidden_by_user_id_fkey` | 列与同名 FK 均已存在 |

**作者知道这个矛盾，并只补了 2 个补丁**：`20260820_000002:17-19` 与 `20260820_000003:13-14` 用 `context.is_offline_mode()` + `sa.inspect(op.get_bind())` 做「列/主键/FK 存在则跳过」的幂等守卫，注释原文写着 *"Keep this migration safe for both legacy databases and fresh installs that already have the new columns."* —— 说明**「fresh install 已经有新列」正是 `create_all` 造成的**，而另外 12 个文件没跟上。

**影响**：`start_all.ps1:86` 执行的就是 `python -m alembic upgrade head`。任何新环境（新同事、CI、换机、docker 重建卷）都**无法**用仓库里的迁移链把库建起来；现有 12312 上的库能跑，只是因为它的 `alembic_version` 已经在 head、`upgrade head` 是空操作。**迁移链对本项目而言是「只写不读的历史」，不是可重放的事实来源。**

**为什么不能靠改迁移修**：这是协议 §3.E 的硬约束——`versions/*.py` 是不可变历史，改了会让已部署环境的 `alembic_version` 与实际 schema 不一致。**唯一正确解法见 §8.1 提案**（新增一个「新库引导」迁移，或在文档/脚本层显式声明「新库 = `create_all` + `stamp head`」）。

---

### §6.2 迁移 ↔ 模型 漂移核对（**只报告，不改迁移、不改模型**）

核对方法：逐个迁移的 `create_table`/`add_column`/`create_index`/`create_check_constraint`/`create_foreign_key` 与 `backend/app/models/**` 逐列比对。

**先更正 B6b-2 的两条结论（我读到的与报告不一致）：**

```
$ git grep -n 'create_table' -- backend/alembic/versions
20260820_000001_add_auth_sessions_and_role_constraints.py:26:    op.create_table(
20260913_000001_add_user_ai_setting.py:13:    op.create_table(
```

- ❌ B6b-2 称「`auth_session` 在 alembic 里没有任何 `create_table`」→ **不成立**，`20260820_000001:26-39` 明确建了 `auth_session`（含 `ondelete="CASCADE"`、`token_digest` UNIQUE、两个索引）。
- ❌ B6b-2 称「`user_ai_setting` 在 alembic 里没有任何 `create_table`」→ **不成立**，`20260913_000001:13-25` 明确建了。
- ✅ B6b-2 称「`situation_snapshot` 在 alembic 里没有任何 `create_table`」→ **成立**，全仓库只有基线 `create_all` 能建它。
- ✅ B6b-2 称「`ck_app_user_role` / `ck_app_user_role_scenario` 只存在于迁移、模型未声明」→ **成立**（`20260820_000001:42-52`；`app_user.py:15-17` 的 `__table_args__` 只有 `uk_app_user_username`）。

**漂移项清单（共 10 项）：**

| # | 漂移方向 | 对象 | 位置 | 后果 |
|---|---|---|---|---|
| M1 | 模型有 / 迁移链无 | `situation_snapshot` 整表 | 模型 `app/models/situation_snapshot.py:15`；迁移里 0 处 `create_table` | 只有基线的 `create_all` 能建它；`alembic autogenerate` 在**老库**上会提议 `create_table("situation_snapshot")`（老库若是在该模型加入前建的，表确实缺） |
| M2 | 迁移有 / 模型无 | `ck_app_user_role` | `20260820_000001:42-46` | 约束只在 DB 里存在；模型层无保护，`app_user.role` 可以被任意字符串写入（走裸 SQL 时）；autogenerate 不检测 CHECK，所以不会被误删，但也**永远不会被新建库之外的工具同步** |
| M3 | 迁移有 / 模型无 | `ck_app_user_role_scenario` | `20260820_000001:47-52` | 同上；这条是「角色 ↔ 场景绑定」的一致性不变量，模型层完全没有 |
| M4 | 迁移有 / 模型无 | 部分索引 `ix_report_due_schedule` | `20260923_000001:38-44` | **Alembic autogenerate 会比较索引**，模型里 `report.py` 没有任何 `Index(...)` → 下次 autogenerate 会生成 `op.drop_index("ix_report_due_schedule")`，**把调度器依赖的索引删掉** |
| M5 | 迁移有 / 模型无 | 部分索引 `ix_risk_event_visible` | `20260927_000001:43-49` | 同上，autogenerate 会提议 `drop_index("ix_risk_event_visible")` |
| M6 | 约束名不一致 | `fk_app_user_scenario` / `fk_report_scenario` / `fk_risk_threshold_user` / `fk_threshold_audit_log_user` | `20260814_000001:29`、`20260816_000001:27`、`20260820_000002:53,61` | 模型里这 4 列都只写匿名 `ForeignKey("x.id")`，`create_all` 生成 PG 默认名（`app_user_scenario_id_fkey` 等）。**老库（走迁移）= `fk_*`；新库（走 `create_all`）= `*_fkey`** → 同一份代码在两种环境里约束名不同，任何按名字 `drop_constraint` 的运维脚本会在一半环境失败。注：`risk_event_hidden_by_user_id_fkey`（`20260927_000001:36`）恰好等于 PG 默认名，**这一条是一致的** |
| M7 | `server_default` 漂移 | `report.format` | 迁移 `20260816_000001:36` `server_default="markdown"`；模型 `report.py:41` 只有 `default="markdown"` | 模型**无** server_default。开启 `compare_server_default` 后 autogenerate 会生成 `alter_column("report","format", server_default=None)`——**破坏性 DDL** |
| M8 | `server_default` 漂移 | `report.scheduled` | 迁移 `20260816_000001:40` `server_default=sa.false()`；模型 `report.py:42` 只有 `default=False` | 同上 |
| M9 | `server_default` 漂移 | `user_ai_setting.provider` | 迁移 `20260913_000001:16` `server_default="openai-compatible"`；模型 `user_ai_setting.py:19` 只有 `default=` | 同上 |
| M10 | `server_default` 漂移 | `user_ai_setting.enabled` | 迁移 `20260913_000001:20` `server_default=sa.true()`；模型 `user_ai_setting.py:23` 只有 `default=True` | 同上 |

**已核对一致、无漂移的项（避免误判）：**

- 类型/精度：`risk_threshold.medium/high_threshold` 与 `threshold_audit_log.old/new_medium/high` 迁移改成 `Numeric(4,2)`（`20260820_000003`），模型 `risk_threshold.py:27-28`、`threshold_audit_log.py:26-29` 也全是 `Numeric(4,2)` → **一致** ✓
- 可空性：所有 `add_column` 的 `nullable` 与模型逐一核对 → **一致** ✓
- 长度：`String(16/32/64/128/255)` 全部与模型一致 ✓
- `dataset.visibility`：迁移 `server_default="platform"`，模型 `dataset.py:38-40` 已显式补 `default="platform", server_default="platform"` → **一致** ✓（模型侧已对齐）
- `report.title`：迁移 `20260822_000001:16` 加完 `server_default` 后 `:18` 又显式 `server_default=None`，模型只有 Python `default=` → **一致** ✓（作者手工对齐过，是 M7–M10 的「正确样板」）
- 模型声明的索引 `idx_ir_user_time`、`idx_re_user_scenario_status`、`uk_mv_default`（部分唯一索引）、`ix_auth_session_user_id/expires_at`、`uk_*`/`chk_rt_threshold`：都由基线 `create_all` 建立，两条路径一致 ✓

---

### §6.3 `downgrade()` 可逆性三分类（29 个迁移逐个判定）

| 分类 | 数量 | 迁移 |
|---|---|---|
| **可逆（无损，`downgrade` 能精确还原 `upgrade` 前状态）** | **7** | `20260808_000001`（回占位文案 + `[]`）、`20260820_000003`（`Numeric(4,2)→(5,4)`，只放宽精度）、`20260822_000005`（PMWNB 置 `[]`，正是其 upgrade 前状态）、`20260822_000006`（回旧 `display_name`，字典完整）、`20260915_000001`（`OLD_DESCRIPTIONS` 6 条 + 反序替换 param help）、`20260920_000001`、`20260920_000002`（`_REMOVE_FLAG` 精确逆操作） |
| **有损（能执行，但丢信息或语义不等价）** | **9** | `d6adba5112b8`（`DELETE` seed 行；若已被引用会 FK 报错）、`a3b5c7d9e1f2`（`DELETE geological_risk`；`app_user.scenario_id` 已引用则报错）、`20260814_000004`（三级角色塌缩回两级：`SUPER_ADMIN`/`SCENARIO_ADMIN`/`SCENARIO_USER` **全部**变成 `ADMIN`/`USER`，三级信息永久丢失；且**未清 `scenario_id`**，留下「ADMIN 却绑着场景」的脏状态）、`20260820_000002`（`DELETE ... USING` 自连接去重，**主动删掉每场景除最新外的所有阈值行**）、`20260820_000004`（`DISABLED→OFFLINE` 无法区分「本来就是 OFFLINE 的行」，反向污染）、`20260822_000002`（`CAVWNB→DIWNB` 改名；若 upgrade 走的是 `DELETE FROM algorithm WHERE code='DIWNB'` 分支，downgrade 会把 CAVWNB 直接改名成 DIWNB，**语义不等价**）、`20260822_000003`（把 **5 个算法**的 `param_schema` 一律置 `[]`，而 upgrade 前它们是有值的；MAWNB/EMAWNB 的 schema **永久丢失**）、`20260822_000004`（A2WNB 置 `[]`，**应为** `20260822_000003` 写入的 `A2_SCHEMA`（含 `rode_task`）→ **实现错误**，见 §6.3.1）、`20260822_000007`（`DELETE FROM algorithm WHERE code='DIWNB'`；`model_version.algorithm_id` 有 FK 且无 `ondelete` → 一旦有 DIWNB 训练出的模型，**downgrade 直接 FK 报错**） |
| **不可逆（`drop_column` / `drop_table`，数据永久丢失）** | **13** | `85b25ac03ba5`（`drop_all` **删全库**）、`20260814_000001`、`20260814_000002`、`20260814_000003`、`20260816_000001`、`20260820_000001`（`drop_table auth_session` = 全员强制重新登录）、`20260822_000001`、`20260906_000001`、`20260913_000001`（`drop_table user_ai_setting` = 所有用户的 API Key 配置丢失）、`20260914_000002`、`20260915_000002`、`20260923_000001`（丢调度状态）、`20260927_000001`（丢隐藏状态与操作人） |

合计 7 + 9 + 13 = **29** ✓

#### §6.3.1 `downgrade()` 实现错误（3 处，均为「回滚到错误的前置状态」）

1. **`20260822_000004:48-54`** —— `downgrade` 把 A2WNB 的 `param_schema` 置为 `[]`。但它 `down_revision` 是 `20260822_000003`，而 `20260822_000003:92-103` 给 A2WNB 装的是 `A2_SCHEMA = [DISCRETE_METHOD, DISCRETE_BINS, _int("rode_task", ...)]`。**正确回滚值应为 `A2_SCHEMA`，不是 `[]`。** 写 `[]` 会让 `downgrade` 后的状态与 `20260822_000003` 结束时的状态不一致（`alembic downgrade -1` 之后再 `upgrade` 得到的结果与原来不同）。
2. **`20260822_000003:126-132`** —— `downgrade` 把 **5 个算法**的 `param_schema` 全置 `[]`。其中 MAWNB/EMAWNB 在 `20260822_000003` 之前（即 `20260808_000001` 写入的状态）**是有 schema 的**；PMWNB 在 `20260822_000002` 之后是有 `CAVWNB_SCHEMA` 的。全部置 `[]` 是「一刀切」，与任何前置状态都不符。
3. **`20260814_000004:41-43`** —— `downgrade` 只回滚 `role`，**没有回滚 `upgrade:31-38` 写入的 `scenario_id`**。回滚后数据库里留下「`role='ADMIN'`（两级模型下 ADMIN 不绑场景）但 `scenario_id` 非空」的状态，与 `20260814_000001` 的语义（管理员 `scenario_id = NULL`）矛盾。

> 这三处**均不可修**（迁移不可变）。价值在于：`20260820_000002`/`20260820_000003` 证明作者后来学会了写幂等/可逆的 downgrade，而早期迁移没有。这直接支撑 §8.4 的「把约定写进 `script.py.mako`」提案。

#### §6.3.2 无「upgrade 加索引、downgrade 删别的索引」类错误

逐对核对 `create_index`/`drop_index`：`20260820_000001:40-41` ↔ `:58-59`（同名同表 ✓）、`20260923_000001:38-44` ↔ `:48`（✓）、`20260927_000001:43-49` ↔ `:53`（✓）。**无错配。**
`create_foreign_key`/`drop_constraint` 配对：`20260814_000001`（✓）、`20260816_000001`（✓）、`20260927_000001`（✓）、`20260820_000002` 用 `_drop_foreign_key` 按 inspector 查名（✓，比硬编码名更稳）。**无错配。**
类型改动配对：`20260820_000003` upgrade 6 列 → downgrade 6 列，**列名与顺序完全对应** ✓。

---

### §6.4 破坏性操作 / 数据保护逐项核对

| 检查项 | 结论 |
|---|---|
| `NOT NULL` 新增列**无 `server_default`**（在已有数据的表上会直接失败） | **0 处。** 逐条核对：`20260814_000003:24`（`nullable=False` + `server_default="platform"` ✓）、`20260816_000001:36,40`（`server_default="markdown"` / `sa.false()` ✓）、`20260822_000001:16`（`server_default="未命名报告"` ✓）。其余 `add_column` 全部 `nullable=True`。 |
| 「先加可空列 → 回填 → 收紧为 `NOT NULL`」模式 | **2 处，写法正确** ✓：`20260820_000002:23-30`（`risk_threshold.user_id`）、`:42-49`（`threshold_audit_log.user_id`）。先 `nullable=True`，`UPDATE ... SET user_id = updated_by/operator_id`，再 `alter_column(nullable=False)`。**无数据丢失风险**（唯一隐患：若某行 `updated_by` 为 NULL，`alter_column` 会报错——`updated_by` 在模型里是 `nullable=False`，所以不会）。 |
| 收紧长度 / 改类型的保护 | **1 处，有保护** ✓：`20260820_000003:15-56` 6 列 `Numeric(5,4)→Numeric(4,2)`，全部带 `postgresql_using="ROUND(x::numeric, 2)"`。**注意有损**：`(5,4)` 能存 `1.2345`，`(4,2)` 只能存 `1.23` → **小数位被截断**（值域反而变宽，不会溢出）。这是**有意的业务收紧**（阈值只允许 2 位小数），但存量数据确实被改写了。 |
| `drop_column` / `drop_table` | 全部集中在 `downgrade()`，见 §6.3（13 个不可逆）。**`upgrade()` 里 0 处 `drop_column`/`drop_table`** ✓ —— 这是好设计：正向路径从不删列。 |
| 全库删除 | `85b25ac03ba5:33-36` `downgrade` 调用 `Base.metadata.drop_all(bind=bind)` → **`alembic downgrade base` 会删掉全部 14 张表**。对一个已上线的库，这是最危险的一条。建议在 `env.py` 或文档里加显式告警（见 §8.2 提案）。 |
| 无 `WHERE` 的 `UPDATE`/`DELETE` | `20260820_000001:12-14` 三条 `UPDATE app_user SET role = ... WHERE role = '...'`（有 WHERE ✓）、`20260820_000004:13-18`（有 WHERE ✓）、`20260822_000002:41` `DELETE FROM algorithm WHERE code='DIWNB'`（有 WHERE ✓）、`20260822_000007:100`（有 WHERE ✓）。**无全表 UPDATE/DELETE** ✓ |

---

### §6.5 建议新增索引 · 汇总总表（跨代理汇总 + 我的核实）

核实方法：`git grep -n 'Index(\|create_index' -- backend/app/models backend/alembic/versions`，逐条与既有索引比对。**只汇总，不新建迁移**（见 §8.1）。

| # | 建议索引 | 来源代理 | 该代理的依据 | 我的核实结论 |
|---|---|---|---|---|
| I1 | `situation_snapshot(scenario_id, snapshot_time DESC)` | **B6b-2-D4** | 快照表按场景 + 时间倒序查询 | ✅ **成立，且是缺口最大的**：模型 `situation_snapshot.py` 无 `Index`，迁移链**零** `create_index`；PG 不为 FK 自动建索引 → 该表目前**只有主键索引** |
| I2 | `risk_event(dataset_id)` | **B4b-2** | 按数据集回溯风险事件 | ✅ **成立**：`risk_event.py:33` 无索引 |
| I3 | `handling_record(risk_event_id)` | **B4b-2** | 事件详情页取处置记录 | ✅ **成立**：`handling_record.py:18` 无索引（明细页每条事件都全表扫） |
| I4 | `threshold_audit_log(user_id, operated_at)` | **B4b-2** | 审计日志按目标用户 + 时间查 | ✅ **成立**：`threshold_audit_log.py` 无 `Index`；注意列名是 `user_id`（目标用户）而非 `operator_id` |
| I5 | `risk_event(hidden_at, occurred_at)` | **B4b-2** | 列表默认过滤 `hidden_at IS NULL` 再按 `occurred_at DESC` | ⚠️ **已被部分覆盖**：`20260927_000001:43-49` 建了 `ix_risk_event_visible(occurred_at) WHERE hidden_at IS NULL` —— 对「默认列表」这个主查询**已是最优**（部分索引更小）。仅当需要「勾选显示已隐藏」时也走索引排序才需补 → **降级为可选** |
| I6 | `report(scheduled, next_run_at)` | **B2-P3** | 调度器扫描到期报告 | ✅ **已满足，建议关闭该条**：`20260923_000001:38-44` 的 `ix_report_due_schedule(next_run_at) WHERE scheduled IS TRUE AND next_run_at IS NOT NULL` 的谓词里**已含 `scheduled IS TRUE`**，等价于对 `(scheduled, next_run_at)` 的过滤；再加一个 `(scheduled, next_run_at)` 是冗余索引 |
| I7 | `auth_session` 过期行清理 | **B4b-2** | 定期删过期会话 | ⚠️ **索引已存在**：`ix_auth_session_expires_at`（模型 `auth_session.py:23` + 迁移 `20260820_000001:41`），模型 docstring 也写明「为『清理过期会话』预留」。**真正的缺口是清理任务本身**（全项目没有消费者）→ 应改判为「需后台清理 job」，不是索引 |
| I8 | 其余 FK 列索引（我补充） | **X2b** | PG **不会**为 FK 列自动建索引；这些列都参与 `WHERE x_id = ?` 或 `JOIN` | ✅ **成立**，共 15 列：`dataset.scenario_id`、`dataset.uploaded_by`、`model_version.{scenario_id,dataset_id,algorithm_id,trained_by,published_by}`、`report.generated_by`、`risk_event.{inference_record_id,algorithm_id,model_version_id,hidden_by_user_id}`、`risk_threshold.updated_by`、`threshold_audit_log.{scenario_id,operator_id}`、`handling_record.handled_by`、`inference_record.model_version_id`（`inference_record.user_id` 已被 `idx_ir_user_time` 前缀覆盖 ✓，`risk_event.created_by_user_id/scenario_id` 已被 `idx_re_user_scenario_status` 前缀覆盖 ✓） |

**汇总：8 条建议，其中 3 条应改判**（I5 降级为可选、I6 关闭、I7 改为清理任务），**5 条确认有效**（I1–I4 + I8）。

---

### §6.6 外键 `ondelete` 策略全表（31 个 FK）

`git grep -n 'ondelete' -- backend/app/models` 只命中 2 行 → **31 个 FK 里仅 2 个声明了 `ondelete`，29 个是 PG 默认 `NO ACTION`（禁止删除被引用行）**。

| # | 表.列 | 引用 | `ondelete` | 影响 |
|---|---|---|---|---|
| 1 | `auth_session.user_id` | `app_user.id` | **CASCADE** | 删用户自动清会话 ✓ |
| 2 | `user_ai_setting.user_id` | `app_user.id` | **CASCADE** | 删用户自动清 AI 配置 ✓ |
| 3 | `app_user.scenario_id` | `scenario.id` | **无** | 删场景前必须先解绑全部用户 |
| 4 | `dataset.scenario_id` | `scenario.id` | **无**（B6b-2-D3 已报） | 有数据集就不能删场景 |
| 5 | `dataset.uploaded_by` | `app_user.id` | **无**（B6b-2-D3 已报） | 有上传记录就不能删用户；与 #1/#2 的 CASCADE 策略**直接冲突**（同一个 `app_user`，会话可级联删、数据集不行） |
| 6 | `handling_record.risk_event_id` | `risk_event.id` | **无** | 有处置记录就不能删事件（**这与「历史风险事件不得删除」的业务规则一致 ✓**） |
| 7 | `handling_record.handled_by` | `app_user.id` | **无** | 有处置记录就不能删用户 |
| 8 | `inference_record.user_id` | `app_user.id` | **无** | 有推理记录就不能删用户 |
| 9 | `inference_record.model_version_id` | `model_version.id` | **无** | 有推理记录就不能删模型 |
| 10 | `model_version.scenario_id` | `scenario.id` | **无** | 有模型就不能删场景 |
| 11 | `model_version.dataset_id` | `dataset.id` | **无** | 有模型就不能删数据集 |
| 12 | `model_version.algorithm_id` | `algorithm.id` | **无** | 有模型就不能删算法 → 使 `20260822_000007` 的 `DELETE FROM algorithm WHERE code='DIWNB'` 在 downgrade 时可能失败（§6.3） |
| 13 | `model_version.trained_by` | `app_user.id` | **无** | 有模型就不能删用户 |
| 14 | `model_version.published_by` | `app_user.id` | **无**（可空） | 同上 |
| 15 | `report.generated_by` | `app_user.id` | **无** | 有报告就不能删用户 |
| 16 | `report.target_user_id` | `app_user.id` | **无**（可空，遗留列） | 同上 |
| 17 | `report.scenario_id` | `scenario.id` | **无**（可空） | 有报告就不能删场景 |
| 18 | `risk_event.inference_record_id` | `inference_record.id` | **无** | 有事件就不能删推理记录 |
| 19 | `risk_event.created_by_user_id` | `app_user.id` | **无** | 有事件就不能删用户 |
| 20 | `risk_event.scenario_id` | `scenario.id` | **无** | 有事件就不能删场景 |
| 21 | `risk_event.dataset_id` | `dataset.id` | **无** | 有事件就不能删数据集 |
| 22 | `risk_event.algorithm_id` | `algorithm.id` | **无** | 有事件就不能删算法 |
| 23 | `risk_event.model_version_id` | `model_version.id` | **无** | 有事件就不能删模型 |
| 24 | `risk_event.hidden_by_user_id` | `app_user.id` | **无**（可空，本次新增） | 隐藏事件的操作人不能被删；**与 #1/#2 策略不一致** |
| 25 | `risk_threshold.user_id` | `app_user.id` | **无**（主键之一） | 有阈值配置就不能删用户 |
| 26 | `risk_threshold.scenario_id` | `scenario.id` | **无**（主键之一） | 有阈值配置就不能删场景 |
| 27 | `risk_threshold.updated_by` | `app_user.id` | **无** | 同上 |
| 28 | `situation_snapshot.scenario_id` | `scenario.id` | **无** | 有快照就不能删场景 |
| 29 | `threshold_audit_log.user_id` | `app_user.id` | **无** | 审计日志**刻意**不级联（审计要求，✓ 合理） |
| 30 | `threshold_audit_log.scenario_id` | `scenario.id` | **无** | 同上 ✓ |
| 31 | `threshold_audit_log.operator_id` | `app_user.id` | **无** | 同上 ✓ |

**结论与建议**：策略不一致分两类——(a) **应当一致却不同**：`auth_session`/`user_ai_setting` 对 `app_user` 用 `CASCADE`，而 `dataset.uploaded_by`/`inference_record.user_id`/`report.generated_by` 等对同一张 `app_user` 用 `NO ACTION`；(b) **应当保持 `NO ACTION`**：`threshold_audit_log.*`、`handling_record.risk_event_id`（审计与「不可删事件」业务规则）。**只有 (a) 是问题，且我倾向不改**——`CASCADE` 用在「纯附属数据」（会话、个人 AI 配置）是对的，用在「业务事实」（数据集、报告、推理记录）上会造成静默数据丢失。**建议在模型注释里把这个判断标准写明**，而不是统一 `ondelete`。→ 记 §8.3 提案。

---

### §6.7 口令 / 密钥写入迁移

```
$ git grep -n -i -E 'password|passwd|secret' -- backend/alembic
(no output)          [exit 1 = 无匹配]
```

**零命中。** 本分区**没有任何硬编码凭据**。相关旁证（都不是泄漏）：
- `backend/alembic.ini:89` `sqlalchemy.url = driver://user:pass@localhost/dbname` —— Alembic 脚手架**占位串**，且 `env.py:25` 会用 `app.db.DATABASE_URL` 覆盖它，从不生效。**不含真实凭据。**
- `20260913_000001_add_user_ai_setting.py:19` 的 `api_key_encrypted` 是**列名**，不是值 ✓
- `20260822_000002:41` 等处的算法 `description` 是业务文案 ✓

> 按任务要求，本节不打印任何可疑内容；实际上没有可打印的内容。

---

### §6.8 `env.py` 正确性核对

| 检查项 | 结论 |
|---|---|
| `run_migrations_online` 是否用对了连接 | ✅ **正确**。`:25` 用 `app.db.DATABASE_URL` 覆盖 ini 里的占位串，`:59-63` `engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)` 拿到该 URL 建 engine，`:65-71` `with connectable.connect() as connection:` → `context.configure(connection=connection, ...)` → `begin_transaction()` → `run_migrations()`。连接来源唯一（`app.db`），**不存在「ini 与实际连的不是一个库」的风险**；`NullPool` 对一次性迁移是正确的（不驻留连接）。 |
| `compare_type` | **未显式设置**。实测 `alembic 1.18.5` / `sqlalchemy 2.0.51`：自 Alembic 1.12.0 起 `compare_type` 默认 **True** → **实际已开启** ✓。类型漂移（如 `Numeric(5,4)` vs `(4,2)`）会被 autogenerate 检出。 |
| `compare_server_default` | **未显式设置，且默认 False → 关闭**。这正是 M7–M10 四处 `server_default` 漂移**至今没被发现**的原因。**但不能直接打开**：一打开，autogenerate 立刻会为 `report.format`、`report.scheduled`、`user_ai_setting.provider`、`user_ai_setting.enabled` 生成 `alter_column(..., server_default=None)` —— **破坏性 DDL**。正确顺序是「先让模型与 DB 对齐（或补 `server_default`），再开启」。→ §8.3 提案 |
| 已修缺陷：`%` 未转义 | ❌→✅ `:25` 原为 `config.set_main_option("sqlalchemy.url", DATABASE_URL)`。`DATABASE_URL` 来自环境变量 / `.env`，**可能含 URL 编码字符**（口令里的 `%40`、`%23` 等）。`ConfigParser` 默认启用 `%` 插值，把裸 `%` 交给 `set_main_option` 会**在 `before_set` 阶段直接抛异常**。实测（不接触 DB）：<br>`ValueError: invalid interpolation syntax in 'postgresql+psycopg2://u:p%40ss@h/db' at position 25`<br>已改为 `DATABASE_URL.replace("%", "%%")`；实测读回 `get_main_option` 得到**原值**（`round-trip ok: True`）。**无 `%` 时行为完全不变**，是严格改进。 |
| `sys.path.insert`（`:15`） | ⚠️ 无条件 insert、重复 import 会重复插入。进程内只跑一次，**无害，不改**。注释已解释「无论从哪个目录启动 alembic」，与 `alembic.ini:21 prepend_sys_path = .` 互补 ✓ |
| 过期注释（`:18`） | ⚠️ 原文写「全部 **12** 张表」，实际 14 张（`app/models/__init__.py:9` 自述 14）。本次已随手修正为 14 ✓ |
| 其他缺失配置 | `render_as_batch`（PG 不需要 ✓）、`include_schemas`（单 schema ✓）、`version_table`（默认 `alembic_version` ✓）——**均不需要**。 |

**`env.py` 改动**（唯一改动的文件，共 1 行代码 + 3 行注释）：

```diff
 # 数据库连接以 app/db.py 的 DATABASE_URL 为准（.env 未配置时回落 docker-compose 默认值）
-config.set_main_option("sqlalchemy.url", DATABASE_URL)
+# DATABASE_URL 来自环境变量 / .env，可能含 URL 编码字符（如口令里的 %40）。
+# ConfigParser 默认启用 % 插值，直接把裸 % 交给 set_main_option 会抛
+# ValueError: invalid interpolation syntax；转义成 %% 后读回仍是原值。
+config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
```

---

### §6.9 offline（`--sql`）模式在本项目不可用

- 基线 `85b25ac03ba5:29-30` 用 `op.get_bind()` + `Base.metadata.create_all(bind=bind)`。在 offline 模式下 `op.get_bind()` 返回的是 Alembic 的 `MockConnection`，它**只能**承载 `op.*` 指令（`op.execute` / `op.create_table` 等），`Base.metadata.create_all()` 无法据此编译出可执行的 DDL 文本 → **`alembic upgrade head --sql` 的第 1 个 revision 就不会产出建表 SQL**。
- `20260820_000002:17-19` 与 `20260820_000003:13-14` **主动 `return`**（注释写明 "Fresh-install offline SQL already contains the current ORM schema."），即这两个迁移在 offline 下**确定性地什么都不做**。
- 结论：**本项目的 `--sql` 输出必然不完整，不可用于生产变更审核或手工执行**。应把「不支持 offline / 不要用 `--sql`」写进 `README`（§8.4），否则运维照 `--sql` 产物执行会得到一个**缺列缺表**的库。

---

## §7 已改动清单

**本分区共改动 1 个文件、1 行代码（+3 行注释）。**

| 文件 | 改动 | 理由 | 验证 |
|---|---|---|---|
| `backend/alembic/env.py:25` | `config.set_main_option("sqlalchemy.url", DATABASE_URL)` → `... DATABASE_URL.replace("%", "%%")`（另加 3 行中文注释） | `DATABASE_URL` 来自环境变量 / `.env`，可能含 URL 编码字符（`%40` 等）；`ConfigParser` 默认 `%` 插值，裸 `%` 会让 `set_main_option` 直接抛 `ValueError: invalid interpolation syntax`（实测复现）。转义后读回为原值（实测 `round-trip ok: True`）。**无 `%` 时行为完全不变** | `python -m py_compile alembic/env.py` → **EXIT=0**；`Config` 往返实测 → **EXIT=0** |
| `backend/alembic/env.py:18` | 注释「全部 **12** 张表」→「全部 **14** 张表」 | 与 `app/models/__init__.py:9` 自述的 14 张一致 | 目视核对 |
| `versions/*.py`（29 个） | **零改动** | 协议 §3.E 硬约束 | `git diff --stat -- backend/alembic` → 只有 `env.py \| 5 ++++-`，`1 file changed, 4 insertions(+), 1 deletion(-)`，**无任何 `versions/` 文件** |
| `script.py.mako` | **零改动** | 属「可改但需 Lead 认可内容」，见 §8.4 | `git diff --stat` 无该文件 |
| `README` | **零改动** | 同上 | `git diff --stat` 无该文件 |

**自检（协议要求）**：因 `env.py` 有改动，已执行 `cd backend && python -m py_compile alembic/env.py`，**EXIT=0**（见上表）。

**未修改**：`backend/app/**`（只读核对）、`backend/tests/**`（未触碰）、`backend/alembic.ini`（分区外，只读）、`scripts/**`、`start_all.ps1`、`frontend/**`。

---

## §8 跨区提案（**只提案，未实施**）

### §8.1 【最高优先级】修复「全新库无法 `alembic upgrade head`」（对应 §6.1）

**问题**：基线 `create_all()` 建当前全量 schema，导致其后 12 个迁移的 25 条 DDL 在空库上必然 `DuplicateColumn`/`DuplicateTable`。

**候选方案与我推荐的一个**：

| 方案 | 做法 | 评价 |
|---|---|---|
| A. 新增「守卫补丁」迁移 | 在 head 之后新增一个用 `sa.inspect` 守卫的迁移，把 25 条 DDL 重做一遍 | ❌ **无效**。新库会在**第 5 个 revision**（`20260814_000001`）就中断，根本走不到 head 之后的新迁移 |
| B. **新库引导流程 = `create_all` + `stamp head`** | 新增 `scripts/init_db.py`（导入 `app.models` 后 `Base.metadata.create_all(engine)`，再 `alembic stamp head`）；`start_all.ps1:86` 改为「检测到空库走 init_db，否则走 `upgrade head`」；文档同步 | ✅ **推荐**。与 `app/models/__init__.py:3-6` 的既有注释完全一致（注释原文：「基线迁移 85b25ac03ba5 直接调用 `Base.metadata.create_all()`，**漏导入任何一个模型都会让全新环境的库缺表**」→ 作者本来就把 `create_all` 当新库建库路径）。**不碰任何 `versions/*.py`**，不违反 §3.E |
| C. 回改 12 个迁移使其幂等 | 给每条 DDL 加 `sa.inspect` 守卫 | ❌ **违反协议 §3.E 硬约束**（迁移不可变） |
| D. 压平历史、重建单一基线 | 新 `revision` 重写全部 DDL，老库 `stamp` | ⚠️ 风险最高：需对**已部署库**做 `stamp`，一旦 stamp 错位就永久失配；且丢失全部历史 |

**涉及分区（全部在 X2b 之外，需 Lead 决策）**：`scripts/`（新增 `init_db.py`）、`start_all.ps1`、`docs/本地环境部署启动手册.md`、`docs/数据库配置指南.md`。

**验收方式**（交 Lead/集成者）：起一个空 PostgreSQL 库，按方案 B 的流程执行，确认 14 张表齐备且 `alembic_version` = `20260927_000001`。

### §8.2 `alembic downgrade base` 的破坏性告警

`85b25ac03ba5:33-36` 的 `downgrade` 是 `Base.metadata.drop_all(bind=bind)` —— **一条命令删掉全部 14 张表**。建议二选一（**需 Lead 决定，我未实施**）：
- 在 `backend/alembic/env.py` 的 `run_migrations_online()` 里检测 `config.cmd_opts` 是否为 `downgrade` 且目标是 `base`，打印醒目警告（`env.py` 在我的分区内，但属行为改动，不宜由单个 review agent 独断）；
- 或在 `README` / 部署文档里写死「**禁止在生产库执行 `alembic downgrade base`**」（零风险，推荐）。

### §8.3 模型侧对齐（消除 §6.2 的 M2–M10）

**全部落在 `backend/app/models/**`，在 X2b 分区之外，需与 B6b-2 的 owner 协调**：

| 项 | 建议改动 |
|---|---|
| M2/M3 | `app_user.py` 的 `__table_args__` 补 `CheckConstraint("role IN ('SUPER_ADMIN','SCENARIO_ADMIN','SCENARIO_USER')", name="ck_app_user_role")` 与 `CheckConstraint("(role = 'SCENARIO_USER' AND scenario_id IS NOT NULL) OR role <> 'SCENARIO_USER'", name="ck_app_user_role_scenario")` —— 与 `20260820_000001:42-52` 逐字一致，使模型成为单一事实来源 |
| M4/M5 | `report.py` 补 `Index("ix_report_due_schedule", "next_run_at", postgresql_where=text("scheduled IS TRUE AND next_run_at IS NOT NULL"))`；`risk_event.py` 补 `Index("ix_risk_event_visible", "occurred_at", postgresql_where=text("hidden_at IS NULL"))` —— **不加就会在下一次 autogenerate 时被 `drop_index` 删掉** |
| M6 | 给 4 个 FK 显式加 `name=`（`fk_app_user_scenario` / `fk_report_scenario` / `fk_risk_threshold_user` / `fk_threshold_audit_log_user`），或在 `app/db.py` 的 `MetaData(naming_convention=...)` 里统一命名策略 |
| M7–M10 | 给 `report.format`、`report.scheduled`、`user_ai_setting.provider`、`user_ai_setting.enabled` 补 `server_default=`，或反过来在**新迁移**里 `alter_column(server_default=None)` 把 DB 侧清掉。**两者必须先做完其一，才允许开启 `compare_server_default`**（§6.8） |

### §8.4 约定沉淀（`script.py.mako` / `README` / `alembic.ini`）

`script.py.mako` 与 `README` 在我的分区内，`alembic.ini` 在分区外。**三者都是 Alembic 脚手架原文，项目实际约定一条都没沉淀**。建议内容（**需 Lead 认可后统一落地，避免 16 个 agent 各写一版**）：

1. **`script.py.mako`**：把 `revision = ${repr(up_revision)}` 改为 `revision: str = ${repr(up_revision)}`（与仓库里 4 个文件的风格对齐——但 25 个文件是另一种风格，**故此项需 Lead 先定标准**）；模板 docstring 里预置「需求出处」「是否幂等」「`downgrade` 是否可逆（可逆/有损/不可逆）」三行必填；`downgrade()` 里预置 `raise NotImplementedError("downgrade 未实现")` 而不是 `pass`，**强制作者思考回滚**（对应 §6.3 的 9+13 个有损/不可逆迁移）。
2. **`README`**（现仅 1 行 `Generic single-database configuration.`）应写明：
   - **新库建库路径**（§8.1 的结论，不能只写 `alembic upgrade head`）；
   - **禁止 `downgrade base`**；
   - **不支持 offline `--sql`**（§6.9）；
   - **迁移文件不可改**（§3.E 的原因：已部署库的 `alembic_version` 会与实际 schema 失配）；
   - **数据迁移必须用 aware 时间 + 固定常量**（`20260822_000007:93` 的 `datetime.now(timezone.utc)` 与 `d6adba5112b8:29` 的固定 `SEED_TIME` 是两种风格，后者才可重放）；
   - 命名规范：`YYYYMMDD_NNNNNN_描述.py`（现有 26 个文件的约定）。
3. **`alembic.ini`（分区外）**：未设置 `file_template`，`alembic revision` 默认生成 `<hash>_<slug>.py`，与现有 26 个日期前缀文件名**不一致** → 建议加 `file_template = %%(year)d%%(month).2d%%(day).2d_%%(rev)s_%%(slug)s`（需与既有 `20260822_000003` 这种「日期_序号」格式再对齐，故需 Lead 定夺）。另建议清掉 `:1-88` 的大段脚手架注释，并在 `:89` 把 `driver://user:pass@localhost/dbname` 占位串替换为注释说明「本值由 `env.py` 从 `app.db.DATABASE_URL` 覆盖，此处不生效」（避免被误认为凭据或误以为改这里有用）。

---

## §9 未及细查 / 存疑（诚实边界）

1. **§6.1 未实机复现。** 协议禁止我执行 `alembic upgrade/downgrade/revision/stamp`，所以「全新库在第 5 个 revision 中断」是**静态推断**：`create_all` 的运行时语义 + `op.add_column` 对已存在列的行为（PG `DuplicateColumn`）。推断链完整，但**没有真实空库的执行日志**。建议集成者用 §8.1 的验收方式实证一次。
2. **§6.5 的索引建议是「结构性缺口」判断，不是慢查询结论。** 我没有读 `backend/app/services/**` 与 API 层，也没有做 `EXPLAIN ANALYZE`，所以 I1–I4、I8 的依据是「PG 不为 FK 列自动建索引 + 该列参与等值/JOIN 过滤」这一结构事实，**不是**实测到的慢查询。I5–I7 我做了覆盖性核实并给出改判。
3. **§6.2 是「迁移文件 ↔ 模型文件」比对，不是「迁移文件 ↔ 实际库」比对。** 我未连库（也不应连），所以无法确认实际库里 `ck_app_user_role` 等是否真的建上了、`server_default` 是否与迁移文件一致。若实际库有手工 DDL 变更，M1–M10 的判定需重新校准。
4. **`versions/__pycache__` 里 `15ce513deaef_diff_*.pyc` 与 `20260903_000001_fi*.pyc` 的来源未追溯。** 对应的 `.py` 不在仓库，我**没有**去 git 历史里查它们被哪个 commit 删除或改名——与当前链的完整性无关（`git ls-files` 确认 0 个 `.pyc` 被跟踪），故未深挖。
5. **`20260820_000001:12-14` 的角色映射是否覆盖全部历史取值未逐 commit 追溯。** 例如 `SCENARIO_ADMIN` 是在 `20260814_000004` 引入还是在 `20260820_000001` 的 CHECK 里首次出现，我只按文件内容判断，未核对引入时点的所有 `role` 写入点（那属于 service 层，不在我的分区）。
6. **`20260915_000001` 的 `REPLACE(param_schema::text, :old, :new)::jsonb` 未做全量取值验证。** 我核对了 6 组替换目标都带 `"` 引号边界、不会跨键误伤，但**没有**逐个算法把替换前后的 `param_schema` JSON 展开比对（需读 `algorithm` 表真实数据，未连库）。这是全仓库最脆弱的一处数据迁移写法，建议集成者重点复核。
7. **`85b25ac03ba5` docstring 写「12 张表」**（`:5`）而实际 14 张——我判定为「迁移文件内的过期注释，不可改」，与 `env.py:18` 的同类问题（已修）性质相同。
8. **未评估 `20260820_000002` 的 `DELETE ... USING` 自连接去重在海量数据下的性能**（当前 `risk_threshold` 数据量未知），也未评估 `20260820_000003` 的 6 次 `ALTER TABLE ... TYPE` 在大表上的锁表时长。两者都只在**回滚**路径上，风险可接受。

---

## §10 `git status --short`（原样粘贴）

```
 M .gitignore
 M README.md
 M backend/alembic/env.py
 M backend/app/algorithms/pmwnb_demo.py
 M backend/app/api/deps.py
 M backend/app/api/legacy_model_routes.py
 M backend/app/api/v1/endpoints/ai_setting_routes.py
 M backend/app/api/v1/endpoints/auth_routes.py
 M backend/app/api/v1/endpoints/dashboard_routes.py
 M backend/app/api/v1/endpoints/dataset_routes.py
 M backend/app/api/v1/endpoints/explanation_routes.py
 M backend/app/api/v1/endpoints/inference_record_routes.py
 M backend/app/api/v1/endpoints/model_evaluation_routes.py
 M backend/app/api/v1/endpoints/model_version_routes.py
 M backend/app/api/v1/endpoints/report_routes.py
 M backend/app/api/v1/endpoints/risk_event_routes.py
 M backend/app/api/v1/endpoints/risk_threshold_routes.py
 M backend/app/api/v1/endpoints/scenario_routes.py
 M backend/app/api/v1/endpoints/situation_routes.py
 M backend/app/api/v1/endpoints/user_routes.py
 M backend/app/config.py
 M backend/app/main.py
 M backend/app/models/__init__.py
 M backend/app/models/app_user.py
 M backend/app/models/auth_session.py
 M backend/app/models/dataset.py
 M backend/app/models/report.py
 M backend/app/schemas/explanation.py
 M backend/app/schemas/explanation_contract.py
 M backend/app/schemas/report.py
 M backend/app/schemas/risk_event.py
 M backend/app/schemas/risk_threshold.py
 M backend/app/services/algorithm_service.py
 M backend/app/services/base.py
 M backend/app/services/batch_inference_runner.py
 M backend/app/services/constants.py
 M backend/app/services/dashboard_service.py
 M backend/app/services/dataset_service.py
 M backend/app/services/explanation_service.py
 M backend/app/services/export_job_service.py
 M backend/app/services/handling_record_service.py
 M backend/app/services/inference_record_service.py
 M backend/app/services/model_evaluation_service.py
 M backend/app/services/model_version_service.py
 M backend/app/services/report_export.py
 M backend/app/services/report_generate_runner.py
 M backend/app/services/report_scheduler.py
 M backend/app/services/report_service.py
 M backend/app/services/risk_event_service.py
 M backend/app/services/risk_threshold_service.py
 M backend/app/services/risk_view.py
 M backend/app/services/scenario_analytics.py
 M backend/app/services/scenario_service.py
 M backend/app/services/threshold_audit_log_service.py
 M backend/app/services/training_executor.py
 M backend/app/services/user_service.py
 M backend/app/utils/auth.py
 M backend/app/utils/common.py
 M backend/app/utils/dataset_file_reader.py
D  backend/deprecated/multi_source_crawler.py
D  backend/deprecated/scripts/add_dify_client.py
D  backend/deprecated/scripts/auto_restart_and_verify_backend.ps1
D  backend/deprecated/scripts/convert_events_to_structured.py
D  backend/deprecated/scripts/generate_events_network.py
D  backend/deprecated/scripts/replace_ai_client.py
D  backend/deprecated/scripts/run_rerun_check.py
D  backend/deprecated/scripts/test_dify.py
D  backend/deprecated/scripts/test_dify_simple.py
D  backend/deprecated/scripts/test_frequency.py
D  backend/deprecated/scripts/test_main_dify.py
D  backend/deprecated/scripts/update_llm_client.py
D  backend/deprecated/scripts/verify_opinion_apis.ps1
 M backend/tests/test_ai_service.py
 M backend/tests/test_discretization_applicability.py
 M "docs/\346\225\260\346\215\256\345\272\223\350\256\276\350\256\241\346\226\207\346\241\243v2.md"
 M "docs/\346\225\260\346\215\256\345\272\223\351\205\215\347\275\256\346\214\207\345\215\227.md"
 M "docs/\346\234\254\345\234\260\347\216\257\345\242\203\351\203\250\347\275\262\345\220\257\345\212\250\346\211\213\345\206\214.md"
 M "docs/\350\267\257\347\224\261\347\216\260\347\212\266\350\260\203\346\237\245.md"
 M frontend/src/App.vue
 M frontend/src/api/datasetApi.ts
 M frontend/src/api/inferenceRecordApi.ts
 M frontend/src/api/reportApi.ts
 M frontend/src/api/riskThresholdApi.ts
 M frontend/src/api/scenarioApi.ts
 M frontend/src/api/situationApi.ts
 M frontend/src/components/common/DataPreviewTable.vue
 M frontend/src/components/dashboard/DashBars.vue
 M frontend/src/components/dashboard/DashEvents.vue
 M frontend/src/components/dashboard/DashKpis.vue
 M frontend/src/components/dashboard/DashScatter.vue
 M frontend/src/components/dashboard/DashTable.vue
 M frontend/src/components/dashboard/dash.css
 M frontend/src/router/guards.ts
 M frontend/src/router/index.ts
 M frontend/src/stores/batchJobStore.ts
 M frontend/src/stores/riskEventStore.ts
 M frontend/src/stores/trainingJobStore.ts
 M frontend/src/style.css
 M frontend/src/utils/request.js
 M frontend/src/utils/scrollAnchor.ts
 M frontend/src/utils/scrollChain.ts
 M frontend/src/views/Alert/AlertsView.vue
 M frontend/src/views/Event/RiskEventDetailView.vue
 M frontend/src/views/Home/dashboard/sections/ProfileFlightdeck.vue
 M frontend/src/views/Home/dashboard/sections/ProfileGeological.vue
 M frontend/src/views/Home/dashboard/sections/ProfileNetwork.vue
 M frontend/src/views/Home/dashboard/sections/ProfilePower.vue
 M frontend/src/views/Home/dashboard/sections/WorkspaceFlightdeck.vue
 M frontend/src/views/Login.vue
 M frontend/src/views/Model/DatasetCenter.vue
 M frontend/src/views/Model/InferenceRecords.vue
 M frontend/src/views/Model/ModelCenter.vue
 M frontend/src/views/Model/ReportCenter.vue
 M frontend/src/views/Model/RiskAnalysis.vue
 M frontend/src/views/Model/RiskInference.vue
 M frontend/src/views/Model/ScenarioCenter.vue
 M frontend/src/views/Model/Settings.vue
 M frontend/src/views/Model/UserManagement.vue
 M scripts/build_pmwnb_jar.ps1
?? "docs/\345\205\250\351\241\271\347\233\256\344\273\243\347\240\201\345\256\241\346\237\245/"
?? "docs/\345\234\272\346\231\257\347\256\241\347\220\206\345\221\230\351\246\226\351\241\265\345\256\241\346\237\245/\351\207\215\346\236\204\346\212\245\345\221\212/"
```

### §10.1 归属说明（重要）

上表是**整个并行审查会话的全仓库快照**，绝大多数条目属于**其它 15 个 agent 的分区**（`frontend/**`、`backend/app/**`、`backend/tests/**`、`scripts/**`、`docs/**`、`backend/deprecated/**` 的删除）。

**X2b 分区内的改动，用 `git diff --stat -- backend/alembic` 精确归属**：

```
$ git diff --stat -- backend/alembic
 backend/alembic/env.py | 5 ++++-
 1 file changed, 4 insertions(+), 1 deletion(-)
```

→ **X2b 只改了 `backend/alembic/env.py` 一个文件**，`versions/` 下 29 个迁移脚本**零改动**（`git diff` 里没有任何 `versions/` 路径），`script.py.mako` / `README` 零改动。

`?? docs/全项目代码审查/` 是本轮审查的**新建未跟踪目录**（含 `审查协议.md` 与 `报告/X2b.md`），属审查产物本身。

---

我未修改任何分区外文件。
