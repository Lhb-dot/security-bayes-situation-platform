# F6c 分区审查报告 · `frontend/src/style.css`

> 本报告为**重试版**（上一次同任务代理异常退出，零改动、无报告）。
> 写作用域：`frontend/src/style.css` + 本报告文件。未修改任何其他文件。
> 生存纪律：报告骨架先落盘，逐节回填。

---

## §0 结论速览

| 项 | 结果 |
|---|---|
| 文件行数 | **1469 → 574**（净删 **895 行**，-60.9%；`git diff --numstat` 实测 `4 insertions / 899 deletions`，与行数差完全吻合） |
| 抽取到的类名总数 | 168 |
| **确定死类**（全仓零引用，含前缀网） | **127** |
| 疑似死类（仅出现在注释/文档） | 2（`.metric-card*`、`.dashboard-grid`，见 §2.2） |
| 动态不可判定 | 0（本文件无任何被动态拼接消费的类名） |
| 已删死的 `@keyframes` | 2（`pulse`、`ping`） |
| `.el-*` 保护 | **全部保留，一个未删**；零引用但保留的运行时类共 **21** 个（19 个 `.el-*` + 2 个 EP 过渡类 `dialog-fade-*`） |
| 剩余零引用选择器（扣除「不动」项） | **0** |
| `!important` | **27 处，数量与位置均未变**（全部是刻意的 Element Plus 覆盖） |
| 未定义却被引用的 CSS 变量（bug） | **0** |
| 定义了但零引用的真 CSS 变量 | **0**（22 个 `--el-*` 是 EP 运行时消费的覆盖变量，刻意保留） |
| `::v-deep` / `/deep/` / `>>>` | 0 |
| `transition: all` | 0 |
| `@import` / 外部网络资源 | 0 / 0（离线可用） |
| 空规则块 | 0 |
| 重复选择器 | 仅 `.app-shell`（基础规则 + `@media(max-width:768px)` 覆盖，刻意） |
| `z-index` 魔法数值 | 8 → **4**（1 / 10 / 1 / 5，均带注释或为局部层级） |
| `vue-tsc --noEmit` | **EXIT=0**，无输出 |
| 跨区提案 | 1 条（过期文档，不改代码，见 §6） |

**一句话**：`style.css` 里约 2/3 的规则是早已被删除的旧版 dashboard / 战情室（war-room）/ 威胁地图（threat-map）视图的遗留样式，全仓零引用；本次按「确定死类」逐条清除，活类与 `.el-*` 运行时类零改动，类型检查通过。

---

## §1 分区与文件清单

| 文件 | 改前行数 | 改后行数 | 说明 |
|---|---|---|---|
| `frontend/src/style.css` | 1469 | **574** | 删 895 行死规则（+4 行是分组首行改写与 1 处注释措辞） |
| `docs/全项目代码审查/报告/F6c.md` | 0（新建） | — | 本报告 |

> **行数口径说明（重要，含一个工具陷阱）**：分区表标注 1470 行，`read` 工具实测 **1469** 行（文件末尾有换行符），HEAD blob 亦为 1469 行 —— 一致。
> 但用 `(Get-Content frontend/src/style.css).Count` 会得到 **549**、`Measure-Object -Line` 会得到 1243，二者都是**错的**：本机是 Windows PowerShell 5.1，`Get-Content` 默认按 ANSI 解码，把这个含中文注释的 UTF-8 文件读坏，连带吞掉 25 个换行。用 `-Encoding utf8` 或 python 读同一文件均得 **574**。
> **权威口径**：改前 **1469** → 改后 **574**，净删 **895** 行；与 `git diff --numstat` 的 `4 / 899` 完全吻合（899 − 4 = 895）。

---

## §2 选择器全量抽取与三张分类表

### §2.0 抽取与反查方法

抽取脚本 `tmp/_f6c_extract.py`（临时文件，`tmp/` 已被 `.gitignore` 忽略，未污染仓库）：

1. 先按 `/* … */` 把注释替换为等长空白（**保留行号**），避免注释里的类名被误判为定义；
2. 正则 `\.(-?[_a-zA-Z][\w-]*)` 抽类名、`#(-?[_a-zA-Z][\w-]*)` 抽 id、`@keyframes\s+([\w-]+)` 抽动画名、`--([\w-]+)\s*:` 抽变量定义、`var\(\s*(--[\w-]+)` 抽变量引用；
3. 反查范围：`frontend/src/**` 全部 `.vue/.ts/.js`，**另加 `frontend/index.html` 与 `frontend/public/**`**（共 88 个文件），逐类名做 `(?<![\w-])name(?![\w-])` 词边界匹配 —— 因此 `class="a b"` 字面命中、`:class="{ a: x }"` 命中、以及任何字符串字面量命中都算「活」；
4. **动态前缀网**：从源码抽出所有 `` `xxx-${…}` ``、`` `xxx--${…}` ``、`` 'xxx-' + … `` 形式，得到 32 个动态前缀（`ev-status--`、`ev-level--`、`level-badge--`、`model-status--`、`report-status--`、`scenario-card__status--`、`d-kpi--`、`stat-card--`、`format-badge--`、`algo-`、`ds-`、`lg-`、`st-`、`t-`、`m-` …），再做前缀匹配；另加一轮「全字面量集 vs 类名」的双向前缀比对，避免漏网；
5. 输出落盘 `tmp/_f6c_selectors.txt`（含每类名的定义行号、命中文件、以及全部 CSS 债清单）。

原始命令与输出见 §5。

### §2.1 确定死类（127 个，全仓零引用）

反查结论：**这 127 个类名在 `frontend/src/**` + `index.html` + `public/**` 中零命中**；再做前缀网比对，仅 `page-container`、`line-chart*` 命中了 `page` / `line` 这两个**通用词**字面量（源码里是图表类型 `'line'` 之类的值，不存在 `` `line-${…}` `` 拼接），经人工确认为误报，仍属死类。

按所属遗留视图分组（行号为**改前**行号）：

**A 组 · 旧 dashboard 网格与 hero 面板（28 个）**
`page-container`(78)、`hero-panel`(94,200,1153)、`detail-hero`(97)、`dashboard-grid`(168,174,179,1144)、`detail-grid`(169,175,183,1145)、`metrics-row`(201,278,1146,1154)、`alert-feed`(202,1155)、`hero-panel__content`(206,1159)、`hero-panel__desc`(213)、`hero-panel__actions`(219)、`hero-button`(227)、`hero-chip`(237)、`hero-panel__pulse`(245,1195)、`pulse-core`(252,260)、`pulse-ring`(253,267)、`pulse-ring--delay`(274)、`metric-card`(284,321,1191)、`metric-card--button`(290,298)、`metric-card__icon`(304)、`metric-card__label`(316)、`metric-card__delta`(326,331,335)、`safe`(331,704)、`metric-card__hint`(339)、`chart-card`(346)、`chart-card--wide`(350,1150)、`dashboard-span-4`(354,1151)、`detail-chip`(367)、`detail-layout`(786)

**B 组 · 旧折线图 / 环形图 / 排行（21 个）**
`line-chart`(377,382)、`line-chart__grid`(387)、`line-chart__point`(392)、`line-chart__focus-line`(399)、`line-chart__tooltip`(404,418)、`line-chart__labels`(422,430,434)、`donut-layout`(439)、`donut-chart`(444)、`donut-chart__inner`(454,464,468)、`donut-legend`(473)、`ranking-list`(474)、`alert-feed__list`(475)、`detail-list`(476,997)、`timeline`(477)、`donut-legend__item`(483,493)、`ranking-list__item`(484)、`alert-feed__item`(485,708,720,727)、`ranking-list__label`(674)、`ranking-list__index`(682)、`ranking-list__bar`(687)、`ranking-list__fill`(695,700,704)

**C 组 · 威胁地图 threat-map（26 个）**
`threat-map`(501)、`threat-map--large`(506)、`threat-map__board`(506,545,560)、`threat-map__toolbar`(510,520)、`scope-switch`(511,525)、`threat-map__detail-meta`(512,1200)、`scope-switch__item`(532,540)、`threat-map__canvas`(555)、`threat-map__background`(570)、`threat-map__svg`(580,586)、`threat-map__labels`(581)、`threat-map__arc`(591,600,605,610,615)、`is-critical`(605,606)、`threat-map__missile`(606,611,616,620)、`is-high`(610,611)、`is-medium`(615,616)、`threat-map__point-core`(624)、`threat-map__point-wave`(628)、`threat-map__focus`(633)、`threat-map__focus-ring`(637)、`threat-map__label`(643,656,661)、`threat-map__focus-label`(644,652,657,662)、`threat-map__detail`(666)、`detail-hero__sub`(728)、`alert-feed__meta`(733)

**D 组 · 旧告警表 / 战情室 war-room / 遮罩弹窗（30 个）**
`alerts-table__row`(709,721,773,1173)、`risk-critical`(748)、`risk-high`(753)、`risk-medium`(758)、`alerts-page`(763)、`alerts-table`(767)、`alerts-table__head`(772,780,1172,1187)、`war-room`(791)、`overlay-modal`(800)、`overlay-modal__backdrop`(809)、`overlay-modal__panel`(816)、`metric-modal__summary`(824,831,837,842,848,1177)、`war-room__backdrop`(854)、`war-room__topbar`(863,870,879,884,1163)、`war-room__metrics`(864,872,890,896)、`war-room__main`(865,880,922,1168)、`war-room__actions`(871,889)、`war-room__feed`(873,891,946)、`war-room__playbook`(874,892,947)、`war-room__metric`(900,908,916)、`war-room__feed-item`(909,910,951,962)、`war-room__map`(929,941)、`war-room__side`(933,940)、`war-room__playbook-item`(952,963)、`detail-hero__header`(967,1162)、`detail-block--wide`(975,1152)、`detail-paragraph`(991)、`timeline__content`(992)、`log-panel`(1003)、`timeline__item`(1013,1040)、`timeline__dot`(1019,1029,1040)、`timeline__head`(1044)

**E 组 · 未用到的语义色残留（2 个）**
`is-critical` / `is-high` / `is-medium` 已计入 C 组；另有 `.metric-card__delta.safe` 与 `.ranking-list__fill.safe` 两条规则 —— 裸类 `safe` 在 style.css 里只出现于这两处、且宿主类均死。同组的 `.danger` 虽然类名在别处（`DashKpis.vue` / `thresholdStore.ts` 的等级字面量）出现，但 style.css 里的两条 `.metric-card__delta.danger` / `.ranking-list__fill.danger` 规则因宿主类死亡而同样死 —— **一并删除，不影响那些 `.vue` 里的 `danger` 用法（它们的样式在各自 scoped 块里）**。

**删除后剩余零引用选择器 = 21 个，全部属于 §2.3「不动」清单 → 非不动项为 0。**

### §2.2 疑似死类（仅出现在注释/文档）

对 127 个死类做**全仓**（排除 `node_modules` / `dist` / `.git` / `tmp` / 本次审查文档）复查，仅 2 处命中，且都在**文档**里、不是代码：

```
.workbuddy-ai\memory\2026-09-27.md:160:  `.result-body` / `.result-version*` / `.train-metrics` / `.metric-card*` / `.result-detail*`）、
frontend\前端更新（7.30所做修改）.md:159: | `.dashboard-grid` 列数 | `1.6fr 1.4fr`（2 列，覆盖全局 12 列语义） | `repeat(12, minmax(0, 1fr))`（与全局 span 12/8/4 匹配） |
```

即 `.metric-card*` 与 `.dashboard-grid` 属「**仅被文档提及、代码零引用**」。二者都已按确定死类删除；那两处文档随之过期，走 §6 提案，**未擅自修改**。

### §2.3 动态不可判定 / 不动项（21 个，全部保留）

**（1）`.el-*` 运行时类 —— 19 个，一律不动**（Element Plus 运行时生成，源码里 grep 不到不代表没用；其中 `main.ts` 里 `import 'element-plus/theme-chalk/el-*.css'` 会形成「字面命中」假象，但即使零命中也不删）：

| 类名 | 改前行号 | 保护理由 |
|---|---|---|
| `el-dialog__header` | 1230 | EP 运行时生成 |
| `el-message-box__header` / `__title` / `__headerbtn` / `__close` / `__status` | 1277–1304 | 同上 |
| `el-message-box-icon--warning` / `--error` / `--success` / `--info` / `--primary` | 1294–1304 | 同上 |
| `el-notification__title` | 1327 | 同上 |
| `el-notification--success` / `--error` / `--warning` / `--info` | 1331–1340 | 同上 |
| `el-button--success` / `--danger` / `--info` | 1404–1427 | 同上（`.is-plain` 语义色覆盖） |

**（2）Element Plus 过渡类 —— 2 个，不动**（**这是本次最容易误删的一处**）：
`dialog-fade-enter-active`(1464)、`dialog-fade-leave-active`(1465) —— 它们不带 `.el-` 前缀，但同样是 EP 在 `el-dialog` 开合时**运行时挂上的 transition 类名**，与同组的 `.el-overlay` 一起构成「禁用弹窗开合动画」这条规则。整条规则原样保留。

**（3）动态拼接消费的类：0 个。** 32 个动态前缀中，没有一个能匹配到本文件里的任何类名（前缀网比对结果只有 `page` / `line` 两个通用词误报）。本文件不存在 `` `ev-status--${status}` `` 这类「由本文件提供样式、由组件拼类名」的类。

---

## §3 CSS 债普查（逐项，数量 + 行号）

| 债项 | 改前 | 改后 | 明细 / 处理 |
|---|---|---|---|
| `::v-deep` / `/deep/` / `>>>` | 0 | 0 | 本文件是全局样式表，无 scoped 穿透语法。**经查无问题** |
| 同一选择器重复定义 | 7 组 | **1 组（刻意）** | 改前 `.app-shell`(57,1182)、`.hero-panel__pulse`(243,1193)、`.metric-card h3`(319,1189)、`.alerts-table__head,.alerts-table__row`(770,1170)、`.alerts-table__head`(778,1185)、`.metric-modal__summary`(822,1175)、`.war-room__main`(920,1166) —— 其中 6 组是「死块被复制一遍」的遗留重复，随死类一并消失；剩下 `.app-shell`(57) + `@media(max-width:768px)`(305) 是**媒体查询覆盖**，非债 |
| 同属性多次声明 | 0 | 0 | 逐规则扫过，无同规则内重复属性。**经查无问题** |
| `!important` | **27** | **27（未增未减）** | 1 处在 `body.el-popup-parent--hidden{width:100%!important}`(42)（与 `scrollbar-gutter` 成对，注释已说明）；其余 26 处全在 Element Plus 按钮覆盖块（1382–1422 一带），是**编译期样式注入顺序导致必须 `!important`** 的刻意选择，注释已说明。**全部保留** |
| `z-index` 魔法数值 | 8 处 | **4 处** | 改后：`.topbar,.state-card{z-index:1}`(80)、`.topbar{z-index:10}`(90，带注释)、`.nav-tabs{z-index:1}`(129，带注释)、`.pane-loading{z-index:5}`(256，带注释「高于 el-table 固定列的 3」)。删除的 4 处来自 `.war-room{z-index:20}`、`.overlay-modal{z-index:25}`、`.overlay-modal__panel{z-index:1}`、`.war-room__topbar/__metrics/__main{z-index:1}` |
| `transition: all` | 0 | 0 | 全量扫描 `transition\s*:\s*all` 零命中；文件里用的是 `transition: 0.25s ease` 与具名属性过渡。**经查无问题** |
| 定义了但零引用的 CSS 变量 | 24 个「定义」中 **0 个真变量** | 同 | 22 个是 `--el-messagebox-*`(8)、`--el-notification-*`(8)、`--el-table-*`(6)，**由 Element Plus 运行时读取**（`var()` 不在本文件里，grep 不到属正常），刻意保留；1 个 `--primary` 是正则误报（来自 `.el-button--primary:hover` 的选择器文本，非变量声明）；真变量只有 `--font-ui`(2)，已被 `font-family: var(--font-ui)`(3) 使用。**无死变量** |
| **引用了但未定义的 CSS 变量（bug）** | **0** | **0** | `=== VAR USES UNDEFINED ===` 段为空。**这是 bug 类问题，本文件无此 bug** |
| 空规则块 | 0 | 0 | `\{\s*\}` 零命中。**经查无问题** |
| 零引用 `@keyframes` | 2 | **0** | 改前 4 个动画：`pulse`(1103)、`ping`(1117) 全仓零引用 → **删除**；`float`(1128) 被 `datasetApi.ts`/`DatasetCenter.vue`/`RiskAnalysis.vue`/`RiskInference.vue` 引用 → 保留；`spin`(1137) 被 `Login.vue`/`RiskAnalysis.vue`/`RiskInference.vue` 及本文件 `.loader`(1068) 引用 → 保留 |
| 裸元素 / `*` 全局选择器 | 7 处 | 7 处（全部保留） | `*`(18)、`html`(27)、`body`(31)、`button,input,textarea`(45)、`button`(51)、`#app`(55)，加上 `body.el-popup-parent--hidden`(41)。均为**有意的全局 reset / 根容器**，非债 |
| `@import` | 0 | 0 | 零命中；样式全部由 `main.ts` 的 `import './style.css'` 单一入口引入 |
| 外部网络资源（`url(http…)` / `url(//…)`） | 0 | 0 | 零命中 → **离线构建/离线运行不会因字体或图片失效**。`--font-ui` 用的是系统字体栈 |
| 过期注释 | 1 处 | 0 | `.topbar` 的 `z-index:10` 注释原文「低于弹窗层 20/25」指向的是本次删除的 `.war-room`(20)/`.overlay-modal`(25)，删除后已成悬空引用 → 已改为「高于页面内容，让用户悬停弹层不被盖住」。**仅改注释，不改任何声明值** |

---

## §4 已删清单与零引用证据

### §4.1 删除方式

**没有使用正则批量删除**（容易切碎多选择器分组、误伤活类）。做法是通读全文后**逐块判定**，然后整文件重写：

- 整条规则的所有选择器都死 → 整块删除；
- 规则是**混合分组**（既有活类又有死类）→ **只摘掉死选择器、保留活选择器及其全部声明**。这类共 7 处，逐一列出：

| 改前行 | 原分组 | 处理后 |
|---|---|---|
| 77–82 | `.topbar, .page-container, .state-card` | `.topbar, .state-card` |
| 94–99 | `.hero-panel h2, .section-heading h2, .section-heading h3, .detail-hero h2` | `.section-heading h2, .section-heading h3` |
| 366–375 | `.section-tag, .detail-chip` | `.section-tag` |
| 473–481 | `.donut-legend, .ranking-list, .alert-feed__list, .detail-list, .timeline, .detail-info` | `.detail-info` |
| 483–491 | `.donut-legend__item, .ranking-list__item, .alert-feed__item, .detail-info > div` | `.detail-info > div` |
| 1143–1180 `@media(1200px)` | 6 条规则、含 `.topbar`/`.topbar__actions` | 仅保留 `.topbar, .topbar__actions{flex-direction:column;align-items:stretch}` |
| 1182–1204 `@media(768px)` | 5 条规则、含 `.app-shell` | 仅保留 `.app-shell{padding:18px}` |

> **权重不变证明**：CSS 选择器列表中每个选择器各自独立计算特异性，从分组里摘掉兄弟选择器**不会改变保留选择器的特异性**，因此不会改变任何视觉输出。
> **声明零改动**：所有保留下来的规则，其属性名/值/顺序**逐字未动**（可 `git diff` 核对：diff 只应出现删除行、分组首行改写、以及 §3 里那一处注释措辞）。

### §4.2 删除批次与每批前的重跑反查

按协议「每删一批前重跑反查」，实际执行为：**先跑全量反查 → 得 127 死类 → 对最高风险的 3 组再做定向反查 → 才动手**：

```powershell
# 定向反查 1：短前缀 is-* 是否被动态拼接（这是前缀网长度阈值 3 会漏掉的一类）
> grep -n "is-\$\{|`is-|'is-'|\"is-|is-critical|is-high|is-medium" frontend/src
frontend/src\style.css:605: .threat-map__arc.is-critical,
frontend/src\style.css:606: .threat-map__missile.is-critical {
frontend/src\style.css:610: .threat-map__arc.is-high,
frontend/src\style.css:611: .threat-map__missile.is-high {
frontend/src\style.css:615: .threat-map__arc.is-medium,
frontend/src\style.css:616: .threat-map__missile.is-medium {
# → 除本文件外零命中，且不存在 `is-${…}` 拼接 → 安全

# 定向反查 2：line-chart / page-container / risk-critical|high|medium / safe
> grep -n "line-chart|page-container|`line-|'line-|risk-critical|risk-high|risk-medium|\bsafe\b" frontend/src
（16 处命中，全部位于 frontend/src/style.css 自身；frontend/src 其余文件零命中）
# → 安全

# 定向反查 3：全仓（含 index.html / public / 后端 / 文档），排除 node_modules|dist|.git|tmp
> Select-String -Pattern 'threat-map|war-room|metric-card|hero-panel|line-chart|alerts-table|timeline__|donut-chart|ranking-list|pulse-ring|detail-hero|overlay-modal|scope-switch|log-panel|dashboard-grid|metric-modal|alert-feed|pulse-core|detail-chip|detail-layout|alerts-page|chart-card|dashboard-span-4|detail-block--wide|detail-paragraph|detail-list|hero-button|hero-chip|page-container|metric-card__hint|detail-grid|metrics-row'
.workbuddy-ai\memory\2026-09-27.md:160: ... `.metric-card*` ...
frontend\前端更新（7.30所做修改）.md:159: | `.dashboard-grid` 列数 | ...
# → 代码零命中，仅 2 处文档提及（见 §2.2 / §6）
```

### §4.3 明确**没有**删的东西（红线自查）

- ❌ 未改任何类名（无重命名、无 BEM 改写）；
- ❌ 未改任何**仍被引用**规则的声明值（`git diff` 中保留规则的属性行零变更）；
- ❌ 未删任何 `.el-*`（19 个零引用的也保留）；
- ❌ 未删 `.el-overlay` 所在的那条「禁用弹窗动画」规则，也未删其中的 `dialog-fade-*`；
- ❌ 未删 `:root` 里在用的变量（`--font-ui` 保留），也未删 EP 覆盖变量；
- ❌ 未改 `@media` 断点值、未改任何颜色/尺寸/间距；
- ❌ 未动 `body.el-popup-parent--hidden` 与 `html{scrollbar-gutter:stable}` 这一对（注释明确「别单独删其中一个」）；
- ❌ 未改 `@keyframes float` / `spin`。

---

## §5 自验原始输出

### §5.1 反查脚本重跑（清理后）

```
$ python tmp/_f6c_extract.py
written D:\001Mine\009Code\project\security-bayes-situation-platform\tmp\_f6c_selectors.txt
classes 61 dead 21
important 27 vdeep 0 keyframes 2
vars def 24 used 1
empty blocks 0
undefined vars []
```

清理后 21 个「零引用」逐个核对，**全部**是 §2.3 的不动项：

```
=== DEAD CLASSES (21) ===
el-dialog__header / el-message-box__header / el-message-box__title / el-message-box__headerbtn
el-message-box__close / el-message-box__status / el-message-box-icon--warning / --error / --success / --info / --primary
el-notification__title / el-notification--success / --error / --warning / --info
el-button--success / el-button--danger / el-button--info
dialog-fade-enter-active / dialog-fade-leave-active
```

→ **剩余零引用选择器（非「不动」）= 0**，达成目标。

其他债务段重跑结果：

```
=== VAR USES UNDEFINED ===      (空)   ← 未定义变量 bug：0
=== ::v-deep/deep/>>> (0) ===   (空)
=== @import (0) ===             (空)
=== url(http) (0) ===           (空)
=== transition: all (0) ===     (空)
=== EMPTY BLOCKS (0) ===        (空)
=== z-index (4) ===  80:1  90:10  129:1  256:5
=== DUPLICATE SELECTORS ===  .app-shell  57,305   ← 基础规则 + 768px 媒体查询覆盖，刻意
=== !IMPORTANT (27) ===  (27 条，与改前完全一致)
=== KEYFRAMES (2) ===  float(引用命中 4 文件)  spin(引用命中 3 文件)
```

### §5.2 类型检查（协议 §1.4 指定命令，带私有 tsBuildInfoFile）

```
$ cd frontend
$ npx vue-tsc --noEmit -p tsconfig.app.json --tsBuildInfoFile node_modules/.tmp/tsb-F6c.json
（无任何输出）

EXIT=0
```

**行为不变证明**：`vue-tsc` 零输出、EXIT=0，说明本次改动未引入任何类型/模板层破坏；改动本身是纯 CSS 选择器删除，且删除前已证明零引用、删除时未触碰任何被引用规则的声明。

> 注：本次改动是纯 CSS，`vue-tsc` 对 CSS 无感知，因此它在这里的作用是**证明没有连带破坏**（例如误删导致模板引用的 class 消失并不会被 TS 捕获）。真正的零引用证据是 §4.2 的 grep。

### §5.3 diff 取证：本次改动**只删不加**（唯一的 4 行新增全部是分组首行与 1 处注释）

```
$ git diff HEAD --numstat -- frontend/src/style.css
4       899     frontend/src/style.css
（4 行新增 / 899 行删除 → 净删 895 行，与 1469 → 574 完全吻合）

$ git diff --cached --numstat -- frontend/src/style.css
（空 —— index 与 HEAD 一致，说明动手前 style.css 没有任何他人/历史遗留的未提交改动）

$ git show :frontend/src/style.css | Measure-Object | .Count   → 1469
$ git show HEAD:frontend/src/style.css | Measure-Object | .Count → 1469
$ python -c "...open('frontend/src/style.css','rb')..."  → LF 574, CRLF 0
$ python -c "...open('frontend/src/style.css',encoding='utf-8')..." → 574 行

$ git diff -U0 -- frontend/src/style.css | Select-String '^\+' （去掉 +++ 行）
+  z-index: 10; /* 高于页面内容，让用户悬停弹层不被盖住 */     ← 仅注释措辞，声明值 10 未变
+.section-heading h3 {                                        ← 从混合分组里摘掉死兄弟后的分组首行
+.section-tag {                                               ← 同上
+  .topbar__actions {                                         ← @media 内分组首行
```

**结论**：整个改动是**纯删除**，新增的 4 行没有一行是声明（property: value）。这从 diff 层面证明了「未改任何视觉输出」——不存在被改写的属性值。

---

## §6 跨区变更提案

### 提案 1（唯一一条，低优先级，**不改代码，仅文档**）

**位置**：`frontend/前端更新（7.30所做修改）.md:159`（分区外）
**现状**：

```
| `.dashboard-grid` 列数 | `1.6fr 1.4fr`（2 列，覆盖全局 12 列语义） | `repeat(12, minmax(0, 1fr))`（与全局 span 12/8/4 匹配） |
```

**问题**：该行描述「全局 `.dashboard-grid` 12 列语义」与 `.dashboard-span-4` / `.chart-card--wide` 的 span 8/4 配合。这些规则已确认全仓零引用（旧 dashboard 视图已删除），本次随死类一并从 `frontend/src/style.css` 移除，该文档行随之成为**指向已不存在代码的过期文档**（协议 §3.B「过期文档」）。

**建议 diff**（由 Lead 串行裁决，我未应用）：

```diff
-| `.dashboard-grid` 列数 | `1.6fr 1.4fr`（2 列，覆盖全局 12 列语义） | `repeat(12, minmax(0, 1fr))`（与全局 span 12/8/4 匹配） |
+| ~~`.dashboard-grid` 列数~~（该全局类及其 span 8/4 配套规则已随旧 dashboard 视图删除，`frontend/src/style.css` 中不再存在） |
```

**影响面**：仅文档可读性，零运行时影响。
**不改的替代方案**：保留现状，由后续统一的历史文档归档任务处理。**我倾向后者**——历史变更日志（「7.30 所做修改」）记录的是当时的事实，事后改写反而失真，建议只加一句「（后续已删除）」而不是划掉。

### 明确不提案的项

- `frontend/src/components/dashboard/dash.css`（F7 分区）里有一套 `d-*` 前缀的 dashboard 样式，与本次删除的旧 `style.css` dashboard 规则**类名不重叠**（`d-card`/`d-kpi`/`d-donut` vs `chart-card`/`donut-chart`/`metric-card`），不存在重复定义或冲突，**无需跨区协调**。
- 未发现需要改分区外文件的硬约束冲突。

---

## §7 未及细查项 / 存疑

1. **行数口径不一致（已查明，是工具坑，非代码问题）**：分区表写 1470，实测 1469（HEAD blob 与 `read` 工具一致）。而 `Get-Content` 默认编码在 Windows PowerShell 5.1 下按 ANSI 解码本文件（含中文注释的 UTF-8），会得到 549 / 1243 这类**偏小的假值**并吞掉换行。**权威值：改前 1469、改后 574、净删 895**（与 `git diff --numstat` 的 4/899 吻合）。已写进 §1 供后续代理避坑。
2. **`.el-*` 的「零引用」判定天然不可靠**：本文件 19 个 `.el-*` 里，有些在 `main.ts` 的 `import 'element-plus/theme-chalk/el-*.css'` 语句里形成「字面命中」，有些（如 `el-message-box__status`）则完全零命中。二者**一律按运行时类保留**，未做任何区分性删除。若后续有人要做 EP 样式瘦身，必须用真实浏览器跑一遍所有弹窗/通知/表格态，**不能靠 grep**。
3. **`!important` 未做清理**：27 处里 26 处在 EP 按钮覆盖块。注释已解释「EP 组件样式由 unplugin-vue-components 编译期注入、加载在本文件之后，同权重会被压掉」。**要真正去掉 `!important`，需要改 `main.ts` 的样式引入顺序或改用 `.el-overlay .el-button` 之类的提权写法** —— 那属于 F5（`main.ts`）分区，且涉及全局视觉回归风险，本次不动。**这是本文件最大的一处技术债，但「能安全修」不成立，故只报告不修。**
4. **`.dialog-fade-enter-active` / `.dialog-fade-leave-active` 的归属**：它们不是 `.el-*` 前缀，若机械按「非 `.el-` 即候选死类」处理会被误删。本次人工识别为 EP 运行时过渡类并保留。**建议协议补一条**：「EP 运行时生成的类名不限于 `.el-` 前缀，还包括 `dialog-fade-*`、`el-fade-in-*`、`el-zoom-in-*` 等过渡类」。
5. **未做浏览器视觉回归**：协议禁止起服务/构建，因此「行为不变」是**静态证明**（零引用 grep + 声明零改动 + 混合分组特异性不变）而非截图对比。若要绝对把握，需 Lead 在串行阶段跑一次 `npm run build` 后人工过一遍各页面。
6. **并发噪声**：本次 `vue-tsc` 运行期间其他代理正在改 `frontend/src/**`，但检查结果为 0 错误，未出现需要「忽略分区外报错」的情况。

---

## §8 `git status --short`

```
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
?? "docs/全项目代码审查/"
?? "docs/场景管理员首页审查/重构报告/"
```

**归属说明（重要）**：上面绝大多数 `M` 是**其他并行代理**正在改的文件（后端 B1–B7、前端 F1–F7）。**属于本次 F6c 的只有两处**：

1. `M frontend/src/style.css` —— 本次唯一改动的代码文件；
2. `?? docs/全项目代码审查/` —— 本报告所在的未跟踪目录（含全部 16 个分区的报告，我仅写入 `报告/F6c.md`）。

`tmp/_f6c_extract.py`、`tmp/_f6c_verify.py`、`tmp/_f6c_selectors.txt`、`tmp/_f6c_verify.txt` 是本次的临时脚本与证据产物，`tmp/` 已被 `.gitignore` 忽略（未出现在 `git status` 中），**未污染仓库**，Lead 可随时删除。

---

我未修改任何分区外文件。
