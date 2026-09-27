# X1b 分区审查报告：`backend/java/**` + `scripts/build_*.ps1`

> 分区：X1 的续作（X1 前一次派发异常退出）。Lead 已完成 `backend/deprecated/**` 整块删除，本报告**不涉及** `deprecated`。
> 写作用域：`backend/java/**`（只读审查）、`scripts/build_all_jars.ps1`、`scripts/build_nb_algorithm_jars.ps1`、`scripts/build_pmwnb_jar.ps1`（可修坏路径）、本报告。
> 不含 `scripts/**` 下的 `.py`（归 X2c）。

## §0 速览

| 项 | 结论 |
|---|---|
| 3 个 `build_*.ps1` 语法 | `Parser::ParseFile` 全部 errors=0 |
| 坏路径 | **发现 1 处并已修**：`build_pmwnb_jar.ps1` 引用不存在的 `PMWNB.zip`（该守卫 100% 抛异常，脚本此前完全不可执行）。另 2 个脚本路径全部有效，未改。 |
| `backend/java/**` | 66 个 `.java` + 1 个 `README.md` = 67 个 git 跟踪文件；`.java` 共 **10623 行**（换行符口径） |
| 被脚本编译的 `.java` | **47 个 / 7849 行** |
| 未被任何脚本编译的 `.java` | **19 个 / 2774 行** —— 但**不是死源码**：它们是未入库的 `pmwnb-service.jar` 内 `weka.classifiers.bayes.PMWNB.**` 类的**唯一源码记录**，删除会让 jar 彻底不可重建。**零删除建议。** |
| 重复算法源码 | 两处"同名算法两份实现"：`CAVWNB`（`zh` 包 17 文件 2291 行 vs `bayes.PMWNB` 包 16 文件 1600 行）与 `MVCAVWNB/{RF_m,SPODE}`。**包名不同 → FQN 不同 → 两份都在用，都不能删**；且 `zh` 版是超集（多 `regularizationLambda` + `evidenceWeightForBinaryClassification`）。<br>唯一**同 FQN 双实现**：`weka.classifiers.trees.RandomForest2`（`compat/` 70 行 shim vs `weka-src/` 666 行真实实现）——潜在隐患，见 §4。 |
| `compat/**` | 11 个文件**全部被引用、全部必需**，不是历史垫片。**零删除。** |
| 构建产物入库 | `git ls-files \| Select-String '__pycache__\|\.pyc$\|\.jar$\|\.class$'` → **0 命中**（复现 Lead 结论）。工作区里的 jar/class 均为未跟踪本地产物，`.gitignore:37/39` 已覆盖。 |
| 最严重结构风险 | `backend/lib/pmwnb-service.jar`（27.5 MB / 7292 entries）**未跟踪且仓库内无法从源码重建**；3 个脚本全部以它为前提。 |
| Java 安全 | 零硬编码凭据、零 `Runtime.exec`/`ProcessBuilder`、零 `ObjectInputStream`、三个服务全部绑定 `127.0.0.1`。仅记录"HTTP 无超时 + 固定 4 线程池"与"Weka 模型反序列化面"两项。 |
| 跨区提案 | 2 项（`algorithm-src/README.md` 文档过期；同 FQN `RandomForest2` 改名）。均**未应用**。 |
| 写操作 | 仅 `scripts/build_pmwnb_jar.ps1` 一个文件。 |

## §1 范围

**写作用域**：`backend/java/**`（只读审查，未改任何 `.java`、未删任何文件）、`scripts/build_all_jars.ps1`、`scripts/build_nb_algorithm_jars.ps1`、`scripts/build_pmwnb_jar.ps1`（可修坏路径）、本报告。
**明确不含**：`backend/deprecated/**`（Lead 已整体删除，本报告不涉及）、`scripts/**` 下的 `.py`（归 X2c）、`backend/lib/PredictServer.java`（不在我域，仅因被 `build_all_jars.ps1` 引用而纳入映射表并只读审查）。

**实际读取**：3 个 `build_*.ps1` 全文；`NbAlgorithmService.java`（import/main/服务段）、`PmwnbService.java`（import/端口段）、`PredictServer.java`（import/evidence 段）、`compat/{WANBIA,DiscreteEstimator,RandomForest2}.java` 全文、`algorithm-src/README.md` 全文、两份 `ObjectiveFunction.java`、`NB/CAVWNB/CAVWNB.java:300-335`；`backend/lib/*.jar` 的 zip 目录与目标 class 常量池（只读）。

**实际执行的命令**（全部只读）：`git ls-files` / `git ls-files -s` / `git grep` / `git status --short` / `git check-ignore -v`、`Get-ChildItem`、`Get-FileHash`、`Compare-Object`、`Select-String`、`System.IO.Compression.ZipFile`（列 jar 条目 + 扫 class 常量池）、`Parser::ParseFile`（语法检查）。
**未执行**（协议 §1.3/§1.4 禁止）：任何 `build_*.ps1`、`javac`、`java`、`jar`、启停服务、`pytest`、`git` 写操作。因此所有编译期结论均为**静态核对**，已在 §6/§10 注明。

## §2 源码 ↔ 构建脚本映射表

### 2.1 正向：脚本 → 源文件 → 产物

| 脚本 | 编译的源文件 | 输出 jar | `Main-Class` | 编译期 `-cp` |
|---|---|---|---|---|
| `build_nb_algorithm_jars.ps1` | 显式 3 个：`backend/java/NbAlgorithmService.java`、`compat/WANBIA.java`、`compat/DiscreteEstimator.java`（第 16-20 行）<br>glob：`algorithm-src/NB/{A2WNB,CAVWNB,DIWNB,MVCAVWNB}/*.java` = 32 个（第 21 行）<br>glob：`compat/**/*.java` = 11 个（第 22 行，含前 2 个 → 命令行 2 项重复）<br>**合计 46 个编译单元** | `backend/lib/nb-algorithm-service.jar`（实存 66 entries / 91220 B） | `com.security.bayes.nbservice.NbAlgorithmService` | `backend/lib/pmwnb-service.jar`（第 25 行） |
| `build_pmwnb_jar.ps1` | `backend/java/pmwnb-service/PmwnbService.java`（1 个） | `backend/lib/pmwnb-service.jar`（`Copy-Item` 覆盖 + `jar uf` 回写，第 26-27 行） | 无（沿用原 jar 的 manifest） | `$baseSnapshot`（原 jar 的副本，第 21 行） |
| `build_all_jars.ps1` 步骤 1 | 转调 `build_nb_algorithm_jars.ps1`（第 19 行） | 同 `nb-algorithm-service.jar` | — | — |
| `build_all_jars.ps1` 步骤 2 | `algorithm-src/PMWNB/weka-src/**/PMWNB/PMWNB/PMWNB.java`、`PMWNB_L.java`、`pmwnb-service/PmwnbService.java`（3 个） | `backend/lib/pmwnb-service.jar`（`jar uf`，第 36 行） | 无 | `backend/lib/pmwnb-service.jar`（第 34 行） |
| `build_all_jars.ps1` 步骤 3 | `backend/lib/PredictServer.java`（1 个，**不在 `backend/java/**`**） | `backend/lib/predict-service.jar`（实存 4 entries / 9310 B） | `PredictServer`（默认包） | `backend/lib/pmwnb-service.jar`（第 52 行）；manifest `Class-Path: pmwnb-service.jar` |

**去重后的被编译 `.java` 全集 = 47 个**（`NbAlgorithmService` 1 + `PmwnbService` 1 + `compat/**` 11 + `NB/A2WNB` 2 + `NB/CAVWNB` 17 + `NB/DIWNB` 9 + `NB/MVCAVWNB` 4 + `weka-src/PMWNB/PMWNB` 2）。

### 2.2 反向：`backend/java/**` 每个 `.java` 是否被脚本引用

**A. 被脚本引用（47 个 / 7849 行）**

| 目录 / 包 | 文件（行数） |
|---|---|
| `backend/java/`（1） | `NbAlgorithmService.java`(865) |
| `pmwnb-service/`（1） | `PmwnbService.java`(375) |
| `compat/`（11） | `DiscreteEstimator.java`(69)、`RandomForest2.java`(70)、`WANBIA.java`(11)、`lbfgsb/Bound.java`(13)、`lbfgsb/DifferentiableFunction.java`(5)、`lbfgsb/FunctionValues.java`(10)、`lbfgsb/IterationsInfo.java`(3)、`lbfgsb/LBFGSBException.java`(7)、`lbfgsb/Minimizer.java`(62)、`lbfgsb/Result.java`(14)、`lbfgsb/StopConditions.java`(19) |
| `algorithm-src/NB/A2WNB/`（2） | `A2WNB.java`(185)、`RODE.java`(468) |
| `algorithm-src/NB/CAVWNB/`（17） | `AdditionObjectiveFunction.java`(41)、`BaseObjectiveFunction.java`(26)、`BaseWANBObjectiveFunction.java`(124)、`BaseWeightComputer.java`(83)、`CAVWNB.java`(772)、`CAVWNB_MSE.java`(588)、`EmptyRegularizer.java`(18)、`L2Regularizer.java`(41)、`MASPObjectiveFunction.java`(182)、`MSEObjectiveFunction.java`(125)、`ObjectiveFunction.java`(8)、`ObjectiveFunctionFactory.java`(15)、`RegularizedObjectiveFunctionFactory.java`(17)、`RegularizerFactory.java`(20)、`WANBDistribution.java`(212)、`WANBObjectiveFunction.java`(11)、`WeightComputer.java`(8) |
| `algorithm-src/NB/DIWNB/`（9） | `ArrayCom.java`(21)、`AVFWNB.java`(196)、`DIWNB_HE.java`(188)、`DIWNB_HL.java`(148)、`DIWNB_S.java`(153)、`DWNB.java`(139)、`IWNB.java`(174)、`KNNs_hard.java`(151)、`KNNs_soft.java`(120) |
| `algorithm-src/NB/MVCAVWNB/`（4） | `EMAWNB.java`(251)、`MVCAVWNB.java`(243)、`RF_m.java`(55)、`SPODE.java`(896) |
| `algorithm-src/PMWNB/weka-src/…/PMWNB/PMWNB/`（2） | `PMWNB.java`(163)、`PMWNB_L.java`(484) |

**B. 未被任何脚本引用（19 个 / 2774 行）—— 见 §3 判定，不建议删除**

| 文件 | 行数 | 包 |
|---|---|---|
| `algorithm-src/PMWNB/weka-src/…/PMWNB/CAVWNB/AdditionObjectiveFunction.java` | 42 | `weka.classifiers.bayes.PMWNB.CAVWNB` |
| `…/PMWNB/CAVWNB/BaseObjectiveFunction.java` | 26 | 同上 |
| `…/PMWNB/CAVWNB/BaseWANBObjectiveFunction.java` | 115 | 同上 |
| `…/PMWNB/CAVWNB/BaseWeightComputer.java` | 81 | 同上 |
| `…/PMWNB/CAVWNB/CAVWNB.java` | 720 | 同上 |
| `…/PMWNB/CAVWNB/EmptyRegularizer.java` | 19 | 同上 |
| `…/PMWNB/CAVWNB/L2Regularizer.java` | 36 | 同上 |
| `…/PMWNB/CAVWNB/MASPObjectiveFunction.java` | 180 | 同上 |
| `…/PMWNB/CAVWNB/MSEObjectiveFunction.java` | 123 | 同上 |
| `…/PMWNB/CAVWNB/ObjectiveFunction.java` | 8 | 同上 |
| `…/PMWNB/CAVWNB/ObjectiveFunctionFactory.java` | 15 | 同上 |
| `…/PMWNB/CAVWNB/RegularizedObjectiveFunctionFactory.java` | 12 | 同上 |
| `…/PMWNB/CAVWNB/RegularizerFactory.java` | 16 | 同上 |
| `…/PMWNB/CAVWNB/WANBDistribution.java` | 188 | 同上 |
| `…/PMWNB/CAVWNB/WANBObjectiveFunction.java` | 11 | 同上 |
| `…/PMWNB/CAVWNB/WeightComputer.java` | 8 | 同上 |
| `…/PMWNB/PMWNB/RF_m.java` | 31 | `weka.classifiers.bayes.PMWNB.PMWNB` |
| `…/PMWNB/PMWNB/SPODE.java` | 477 | 同上 |
| `…/PMWNB/…/weka/classifiers/trees/RandomForest2.java` | 666 | `weka.classifiers.trees` |
| （非 `.java`）`algorithm-src/README.md` | 22 | — |

小计：CAVWNB 目录 16 文件 1600 行 + 31 + 477 + 666 = **2774 行 / 19 文件**；`47 + 19 = 66` ✓，`7849 + 2774 = 10623` ✓。
（Lead 给的 66 文件与我的计数完全一致；行数 Lead 记 10685、我实测 10623，差 62 行属计数口径差异——例如是否把 `README.md` 的 22 行与文件尾行计入。不影响任何结论。）

## §3 未被任何脚本引用的 `.java`（疑似死源码，只报告）

**结论：19 个"未被脚本编译"的 `.java` 中，0 个是真正的死源码，因此本分区零删除。**

判定依据（三条独立证据）：

1. **它们是 jar 内类的源码记录，不是孤儿文件。** `backend/lib/pmwnb-service.jar`（未跟踪的现成产物，7292 entries）内确实存在 `weka/classifiers/bayes/PMWNB/PMWNB/{PMWNB,PMWNB_L,RF_m,SPODE}.class`、`weka/classifiers/bayes/PMWNB/CAVWNB/*.class`、`weka/classifiers/trees/RandomForest2.class`。而这些类的**唯一源码**就是 §2.2-B 这 19 个文件（`zh` 包下的同名文件包名不同，不能互相顶替）。
2. **`weka-src` 版与 jar 版 API 一致，说明它就是这个 jar 的源码快照。** `PMWNB.java:135` 的 `getView1BaseCAVWNB()` 在 jar 的 `PMWNB.class` 常量池中存在（扫描 True）；`WANBDistribution` 的 `getWeights/getCardinalities/getOffset/getThetaUC/getAttValueCounts` 在两份源码与 jar 中同时存在；`evidenceWeightForBinaryClassification` 在 `weka-src` 版与 jar 版中**同时缺失**（只加在 `zh` 版上）——源码与 jar 严格对应，不存在"源码比 jar 新/旧"的漂移。
3. **删除的后果不可逆。** `backend/lib/pmwnb-service.jar` 未被 git 跟踪（§7），仓库内也没有任何脚本能从源码重建它（`weka-src` 只是局部快照，缺 Weka 核心类；`build_*` 三个脚本全部以"已存在的 pmwnb-service.jar"为前提）。删掉这 19 个文件 = 永久失去该 jar 内 PMWNB/CAVWNB/RandomForest2 的源码。

**因此：报告为"疑似死源码"但不建议删除。** 若 Lead 出于瘦身目的仍要处理，唯一安全前提是先把 `pmwnb-service.jar` 纳入版本管理或归档到不可变存储，并确认 7292 entries 可完整复现——当前条件不成立。

## §4 重复算法源码判定

协议 §3.E：**不改 Java 算法逻辑**，本节只做结构判定，未改任何 `.java`。

### 4.1 `CAVWNB`：两份实现（`zh` 包 vs `bayes.PMWNB` 包）

| 维度 | A = `algorithm-src/NB/CAVWNB/` | B = `algorithm-src/PMWNB/weka-src/…/PMWNB/CAVWNB/` |
|---|---|---|
| `package` | `weka.classifiers.zh.CAVWNB`（全目录唯一） | `weka.classifiers.bayes.PMWNB.CAVWNB`（全目录唯一） |
| 文件数 / 行数 | 17 / 2291 | 16 / 1600 |
| 文件名差异 | 多 `CAVWNB_MSE.java`(588) | 无 |
| `CAVWNB.java` 行数 | 772 | 720 |
| 归一化 diff（剥掉 `package` 行） | `Compare-Object` → **64 行差异**（各 32 行） | 同左 |
| A 独有 | `private double regularizationLambda = 1.0;`、`public double[] evidenceWeightForBinaryClassification(Instance)`（`CAVWNB.java:323`，委托 `distrib.evidenceWeightForBinaryClassification`） | — |
| 关键方法签名共有 | `geDistribution()`(A:127 / B:124)、`distributionForInstance(Instance)`、`buildClassifier(Instances)` | 同左 |
| 谁引用 | `NbAlgorithmService.java:13-14,131` 硬引用 `weka.classifiers.zh.CAVWNB.CAVWNB`；被 `build_nb_algorithm_jars.ps1` glob 编译进 `nb-algorithm-service.jar`（jar 内确有 `weka/classifiers/zh/CAVWNB/CAVWNB.class`、`CAVWNB_MSE.class`） | `PMWNB_L.java:5,45,48,51,54,57` 引用 `weka.classifiers.bayes.PMWNB.CAVWNB.CAVWNB`；**不被任何脚本编译**，靠 `-cp pmwnb-service.jar` 从 jar 解析；jar 内确有该类 |

**判定：两份都不能删。** 理由：
- **不是同一份代码的两份拷贝**——包名不同 ⇒ FQN 不同 ⇒ 是两个独立编译产物，分别进两个 jar、被两个不同服务使用，不存在"重复定义同一个类"的编译错误或运行歧义。
- **A 是超集**：A 额外带 `regularizationLambda` 与 `evidenceWeightForBinaryClassification`，是平台为"特征证据分解"扩展的版本（`PredictServer.java:168` 的 `feature_evidence` 链路依赖同类能力）。B 是原始版本。
- **删 A** → `nb-algorithm-service.jar` 编不出来，CAVWNB 算法与 `/predict` 的证据输出全断。
- **删 B** → `pmwnb-service.jar` 内 `bayes.PMWNB.CAVWNB.*` 失去唯一源码记录（jar 不可重建，见 §3 证据 3）。

### 4.2 `MVCAVWNB/{RF_m,SPODE}`：两份实现

| 文件 | A = `NB/MVCAVWNB/` | B = `weka-src/…/PMWNB/PMWNB/` |
|---|---|---|
| 包 | `weka.classifiers.zh.MVCAVWNB` | `weka.classifiers.bayes.PMWNB.PMWNB` |
| `RF_m.java` | 55 行；`import weka.classifiers.trees.RandomForest2;` | 31 行；同 import |
| `SPODE.java` | 896 行 | 477 行 |
| A 独有文件 | `EMAWNB.java`(251)、`MVCAVWNB.java`(243) | `PMWNB.java`(163)、`PMWNB_L.java`(484) |
| 谁引用 | `NbAlgorithmService.java:15-16,133-134`（MAWNB/EMAWNB）；脚本 glob 编译 | `PMWNB_L.java:6-7,26,28` 直接 `new SPODE()` / `new RF_m()` |

**判定：两份都不能删**，同 4.1 的理由（包名不同、服务不同、各为对方 jar 的唯一源码）。另注意 A 的 `RF_m` 比 B 长 24 行，与 `SPODE` 896 vs 477 的差异都表明二者是**不同演化分支**，不是简单拷贝。

### 4.3 ⚠ 唯一一处**同 FQN 双实现**：`weka.classifiers.trees.RandomForest2`

| 维度 | `compat/RandomForest2.java` | `weka-src/…/weka/classifiers/trees/RandomForest2.java` |
|---|---|---|
| FQN | `weka.classifiers.trees.RandomForest2` | **完全相同** |
| 行数 | 70 | 666 |
| 性质 | 手写 shim（内含 `private final RandomForest forest`，`setNumIterations(50)`、`setSeed(1)` 硬编码） | 真实实现（含 `diversity_JSD`、`setMaxDepth`、`setNumFeatures`、`getTechnicalInformation`、`enumerateMeasures` 等完整 API） |
| 被谁编译 | 被 `build_nb_algorithm_jars.ps1` 编译进 `nb-algorithm-service.jar` | **不被任何脚本编译** |
| 出现在哪个 jar | `nb-algorithm-service.jar` → `weka/classifiers/trees/RandomForest2.class` | `pmwnb-service.jar` → `weka/classifiers/trees/RandomForest2.class`（12242 B） |

**"jar 里那个是 666 行真实实现"的证据**（只读常量池扫描）：`pmwnb-service.jar` 内 `weka/classifiers/trees/RandomForest2.class` 含 `diversity_JSD`=True、`setMaxDepth`=True、`getTechnicalInformation`=True、`distributionForInstance_c_p_diversity`=True、`numFeaturesTipText`=True、`setNumFeatures`=True —— 这些标识符**只存在于 666 行版本**，70 行 shim 里一个都没有（shim 的公开方法仅 `buildClassifier / distributionForInstance / distributionForInstance_c_p / distributionForInstance_c_p_x / distributionForInstance1 / distributionForInstance2 / getTreesDetails`）。

**判定：不能删任何一个，但这是本分区唯一的结构性隐患。**
- 现状可运行：`start_all.ps1:135` 用 `-jar lib\nb-algorithm-service.jar 12315` 启动 NB 服务，`-jar` 时应用自身 jar 优先，因此 `zh.MVCAVWNB.RF_m` 拿到的是 **shim**（正是它需要的 `distributionForInstance_c_p_x` 等历史 API）；`start_all.ps1:116` 的 predict 服务只带 `predict-service.jar` + manifest `Class-Path: pmwnb-service.jar`，拿到的是**真实实现**。两者互不干扰。
- 隐患：`nb-algorithm-service.jar` 的 manifest 声明了 `Class-Path: pmwnb-service.jar`（`build_nb_algorithm_jars.ps1:32`），两个 jar **同时在一个 JVM 的 classpath 上**，仅靠"应用 jar 优先"这一条隐式规则区分。一旦有人改用 `-cp`、调整顺序、或把两个 jar 合并/换用 fat-jar 打包，`RF_m` 会静默换用另一份实现，**行为改变且无任何报错**。
- 建议见 §9 提案 2（改名 compat 版），**未应用**（属改 Java 算法源码，协议 §3.E 禁止）。

## §5 `compat/**` 判定

**结论：11 个文件全部必需，`compat/**` 不是历史垫片，零删除。** 逐个引用方（`git grep` 全仓）：

| compat 类 | 提供的 FQN | 引用方（文件:行） | 该 FQN 是否已在 `pmwnb-service.jar` 内 |
|---|---|---|---|
| `WANBIA.java`(11) | `weka.classifiers.bayes.WANBIA.WANBIA` | `algorithm-src/NB/A2WNB/A2WNB.java:23` `new weka.classifiers.bayes.WANBIA.WANBIA()` | **否**（扫 jar 内 `WANBIA` 零命中）→ 只能由 compat 提供 |
| `DiscreteEstimator.java`(69) | `weka.estimators.DiscreteEstimator` | `NB/CAVWNB/CAVWNB.java:42`、`CAVWNB_MSE.java:42`、`WANBDistribution.java:11` | 是（jar 内有真实 Weka 版）→ 见下方风险 |
| `RandomForest2.java`(70) | `weka.classifiers.trees.RandomForest2` | `NB/MVCAVWNB/RF_m.java:4` | 是（但为 666 行真实实现）→ 见 §4.3 |
| `lbfgsb/Bound.java`(13) | `lbfgsb.Bound` | `NB/CAVWNB/BaseWeightComputer.java:6` | 是（jar 内有 `lbfgsb/Bound.class`） |
| `lbfgsb/DifferentiableFunction.java`(5) | `lbfgsb.DifferentiableFunction` | `BaseWeightComputer.java:7`、`ObjectiveFunction.java:3` | 是 |
| `lbfgsb/FunctionValues.java`(10) | `lbfgsb.FunctionValues` | `AdditionObjectiveFunction.java:5`、`BaseWANBObjectiveFunction.java:5`、`EmptyRegularizer.java:6`、`L2Regularizer.java:6` | 是 |
| `lbfgsb/IterationsInfo.java`(3) | `lbfgsb.IterationsInfo` | 经 `Minimizer`/`Result` 间接（`BaseWeightComputer.java:9-11`） | 是 |
| `lbfgsb/LBFGSBException.java`(7) | `lbfgsb.LBFGSBException` | `BaseWeightComputer.java:8` | 是 |
| `lbfgsb/Minimizer.java`(62) | `lbfgsb.Minimizer` | `BaseWeightComputer.java:9` | 是 |
| `lbfgsb/Result.java`(14) | `lbfgsb.Result` | `BaseWeightComputer.java:10` | 是 |
| `lbfgsb/StopConditions.java`(19) | `lbfgsb.StopConditions` | `BaseWeightComputer.java:11` | 是 |

**"零引用"检查（结论：无零引用项）**：11 个类全部至少有一个 `import`/限定名引用，命令与输出见上表"引用方"列（`git grep -n -E 'lbfgsb|weka\.estimators\.DiscreteEstimator|classifiers\.bayes\.WANBIA|classifiers\.trees\.RandomForest2' -- 'backend/java/**'`）。
**注意**：`compat/**` 的引用方**只在 Java 源码内部**，`backend/app/**`、`backend/tests/**`、`scripts/*.py` 全都不直接引用（它们通过 HTTP 调服务）——这正是它容易被误判为"历史垫片"的原因，但结论相反。

**风险（报告项，不改）**：`nb-algorithm-service.jar` 自带 `weka/estimators/DiscreteEstimator.class`（compat shim），而 manifest 又引入 `Class-Path: pmwnb-service.jar`（内含真实 Weka 的同类）。因 `-jar` 启动时应用 jar 优先，**NB 服务 JVM 内 `weka.classifiers.bayes.NaiveBayes`（来自 pmwnb jar，由 `compat/WANBIA extends NaiveBayes` 使用）会解析到 shim 而非真实 Weka 实现**。shim 同时提供了 `(int, boolean)` 与 `(int, double)` 构造器 + `getProbability`，签名层面兼容，因此当前可运行；但精度行为与"用真实 Weka"是否一致，需起服务实测才能断言——协议禁止启服务，故**仅报告，不断言**。

## §6 构建脚本坏路径（已修）

### 6.1 已修：`scripts/build_pmwnb_jar.ps1` 引用了不存在的 `PMWNB.zip`

**坏路径**：`backend\java\algorithm-src\PMWNB\PMWNB.zip`

**证据（3 条独立）**：
1. `Test-Path -LiteralPath 'backend\java\algorithm-src\PMWNB\PMWNB.zip'` → `False`；`backend/java/algorithm-src/PMWNB/` 下只有 `weka-src/` 一个子目录。
2. `git ls-files | Select-String '\.zip$'` → **0 命中**：该 zip 从未纳入版本管理。
3. 该路径被第 12 行用作**硬守卫**：`if (-not (Test-Path -LiteralPath $sourceZip)) { throw "找不到 PMWNB 源码 ZIP: $sourceZip" }` → 脚本此前**必然在第 12 行抛异常退出，100% 不可执行**。

**改动（3 处，改前 → 改后）**：

| # | 改前 | 改后 | 依据 |
|---|---|---|---|
| 1 | `$sourceZip = Join-Path $repo "backend\java\algorithm-src\PMWNB\PMWNB.zip"`（第 4 行） | 整行删除 | 该变量除下方守卫与一行提示文案外**零使用**（`Select-String 'sourceZip'` 改后残留 0 处）；保留一个指向不存在文件的变量只会误导读者 |
| 2 | `if (-not (Test-Path -LiteralPath $sourceZip)) { throw "找不到 PMWNB 源码 ZIP: $sourceZip" }`（第 12 行） | 整行删除 | 守卫对象不存在且非本脚本所需；脚本真正的三个前置条件（base jar / 服务源码 / javac）在上下两行仍完整保留 |
| 3 | `Write-Host "Compiling configurable PMWNB service; source reference: $sourceZip ..."`（第 20 行） | `Write-Host "Compiling configurable PMWNB service from $serviceSource ..."` | 改指真实存在且真正被编译的 `backend\java\pmwnb-service\PmwnbService.java`（`$serviceSource`，第 9 行已定义） |

**行为不变证明**：脚本的实际工作链（第 16-18 行清理 buildRoot + 复制 base jar 快照 → 第 21 行 `javac -cp $baseSnapshot -d $classes $serviceSource` → 第 26-27 行 `Copy-Item` 还原 + `jar uf` 回写）**一行未动**。删除的是"对不存在文件的检查"与"提示文案中的死变量"，不改变任何编译/打包行为。`backend/java/algorithm-src/README.md:21-22` 亦自述该 zip "当前仅被 `build_pmwnb_jar.ps1` 做存在性检查"——即该引用本就不参与构建，移除后脚本语义 = 原设计意图。

**自验输出（§1.4）**：
```
$ [System.Management.Automation.Language.Parser]::ParseFile('scripts\build_pmwnb_jar.ps1', [ref]$tokens, [ref]$errs)
ParseFile errors: 0
  (none)
tokens=168
=== residual sourceZip references (expect 0) ===
0
```
未运行 `build_pmwnb_jar.ps1`、未运行 `javac`（协议 §1.4 禁止写 `backend/lib/*.jar`），故只做语法 + 路径静态核对，**未实际编译**。

### 6.2 逐条核对：其余路径全部有效（未改）

| 脚本 | 检查项 | 结果 |
|---|---|---|
| 3 个脚本 | `$repo = Split-Path -Parent $PSScriptRoot` → 仓库根 | ✓ 脚本位于 `scripts/`，上一级即根 |
| 3 个脚本 | 输出目录 `backend\lib` | ✓ 存在（含 3 个 jar + `PredictServer.java`） |
| `build_all_jars.ps1` | `PMWNB.java`(25)、`PMWNB_L.java`(26)、`PmwnbService.java`(27) | ✓ 三个全部 `Test-Path` True |
| `build_all_jars.ps1` | `backend\lib\PredictServer.java`(41) | ✓ 存在（18226 B） |
| `build_all_jars.ps1` | `backend\java\.build-all`(13)、`.build-all\pmwnb-classes`(28)、`predict-classes`(42) | ✓ 均 `New-Item -Force` 创建 |
| `build_all_jars.ps1` | `jar uf $pmwnbJar -C $pmwnbClasses .`(36)、`jar cfm $predictJar $manifest -C $predictClasses .`(55) | ✓ `cfm` 参数序 = `<jar> <manifest> -C <dir> .` 正确 |
| `build_nb_algorithm_jars.ps1` | `algorithm-src\NB`(4) 及 `A2WNB/CAVWNB/DIWNB/MVCAVWNB`(21) | ✓ 4 个子目录存在（2/17/9/4 个 `.java`） |
| `build_nb_algorithm_jars.ps1` | `backend\lib\pmwnb-service.jar`(5,10) | ✓ 存在（27575786 B） |
| `build_nb_algorithm_jars.ps1` | `compat`(18-19,22) | ✓ 存在（11 个 `.java`） |
| `build_pmwnb_jar.ps1` | `pmwnb-service\PmwnbService.java`(9)、`backend\lib\pmwnb-service.jar`(5,10) | ✓ 均存在 |
| 3 个脚本 | `Main-Class` 类名 vs 实际源码 | ✓ `com.security.bayes.nbservice.NbAlgorithmService` ↔ `NbAlgorithmService.java:1 package com.security.bayes.nbservice;`；`PredictServer` ↔ `PredictServer.java` **无 package 声明**（默认包）→ 二者均正确 |
| 3 个脚本 | jar 名 vs `start_all.ps1` 期望名 | ✓ `nb-algorithm-service.jar`(start_all:44,135)、`pmwnb-service.jar`(:7,102)、`predict-service.jar`(:116) 三处一致 |
| 3 个脚本 | 是否引用已删除的 `backend/deprecated` | ✓ **零命中**（`git grep -n -I 'deprecated' -- 'scripts/*.ps1'` → 空）→ 无需修 |

### 6.3 `-cp` classpath 充分性（静态核对，未编译）

对 5 个编译单元（`NbAlgorithmService`、`PMWNB`、`PMWNB_L`、`PmwnbService`、`PredictServer`）共 **105 条 `import`** 逐条在 3 个 jar 内查 `X.class` 与嵌套类 `X$*.class`：

- 唯一"未解析"项 `weka.core.converters.ConverterUtils.DataSource` 经复核为**我的检查器误报**：jar 内实为 `weka/core/converters/ConverterUtils$DataSource.class`（已单独确认存在）→ **零真实未解析**。
- 进一步对 `PredictServer.java` 实际调用的方法做**目标 class 常量池扫描**，确认 `-cp pmwnb-service.jar` 充分：

```
weka/classifiers/bayes/PMWNB/PMWNB/PMWNB.class
  distributionForView1 True   distributionForView2 True   toView1 True
  distributionForSubmodels True   getView1BaseCAVWNB True
weka/classifiers/bayes/PMWNB/CAVWNB/CAVWNB.class
  geDistribution True
weka/classifiers/bayes/PMWNB/CAVWNB/WANBDistribution.class
  getWeights True   getCardinalities True   getOffset True
  getThetaUC True   getAttValueCounts True
```
即 `build_all_jars.ps1` 步骤 3 编译 `PredictServer` 所需的全部外部符号都在 `pmwnb-service.jar` 内 → 第 52 行 `-cp $pmwnbJar` **充分**。`build_all_jars.ps1` 步骤 2 与 `build_nb_algorithm_jars.ps1` 同理通过。

### 6.4 未修（仅记录，非坏路径）

1. `build_nb_algorithm_jars.ps1:18-19` 显式列出 `compat\WANBIA.java`、`compat\DiscreteEstimator.java`，第 22 行 `Get-ChildItem compat -Recurse` 又把这两个加了一遍 → javac 命令行出现 2 个重复源文件。javac 会自行去重，**无功能影响**；清理属可选优化，为保持最小 diff 未改。
2. `algorithm-src/README.md:20` 称 NB 子目录"递归编译（`-Filter *.java -File -Recurse`）"，但脚本第 21 行**没有 `-Recurse`**（4 个子目录都是平铺的，故无功能差异）→ 文档与实现不符，见 §9 提案 1。
3. `build_nb_algorithm_jars.ps1:47-55` 清理 5 个历史 jar 名（`a2wnb/cavwnb/diwnb/emawnb/mawnb-service.jar`）的逻辑**保留正确**：这些名字在 `start_all.ps1`、`backend/app/**` 中已无引用，且每个删除都有 `Test-Path` 守卫，不会误删。

## §7 产物入库核查

**结论：`backend/lib/*.jar`、所有 `.class`、所有 `__pycache__`/`.pyc` 均未被 git 跟踪 —— 复现并确认 Lead 的预检。**

```
$ git ls-files | Select-String '__pycache__|\.pyc$|\.jar$|\.class$'
matches=0
```

屏蔽来源（`.gitignore`）：
```
   8: __pycache__/
  37: backend/java/.build-*/
  39: *.jar
```
`git check-ignore -v` 逐条验证：
```
backend/java/.build-nb/MANIFEST.MF   -> .gitignore:37:backend/java/.build-*/
backend/java/.build-all/MANIFEST.MF  -> .gitignore:37:backend/java/.build-*/
backend/lib/nb-algorithm-service.jar -> .gitignore:39:*.jar
```
`git status --short --untracked-files=all -- backend/java` → **空**（`backend/java` 下零未跟踪文件）。即 `backend/java/.build-all/**`、`backend/java/.build-nb/**` 这两个本地编译目录已被 `.gitignore:37` 完整覆盖，**无需新增 ignore 规则**（我原本准备的 `.gitignore` 提案据此撤销）。

**工作区实存的本地产物（未跟踪，属正常构建输出，不算入库死代码）**：
```
nb-algorithm-service.jar    91220 B   (66 entries)
pmwnb-service.jar        27575786 B   (7292 entries)
predict-service.jar          9310 B   (4 entries)
backend/java/.build-all/{pmwnb-classes,predict-classes,MANIFEST.MF}
backend/java/.build-nb/{classes,MANIFEST.MF}
```

**⚠ 本分区最严重的结构风险（报告项，非我域可修）**：
`backend/lib/pmwnb-service.jar` 是**未跟踪且不可重建**的 27.5 MB 二进制。三个脚本**全部以"它已存在"为前提**：`build_pmwnb_jar.ps1:13` 守卫、`build_nb_algorithm_jars.ps1:10` 守卫、`build_all_jars.ps1:34/52` 的 `-cp` 与 `:36` 的 `jar uf` 目标。而仓库内**没有任何路径能从源码完整重建它**：`weka-src/**` 只是 PMWNB 局部源码快照（19 个 `.java`），缺 Weka 核心（jar 内 7292 entries 里绝大多数是 shaded Weka）；原始 `PMWNB.zip` 从未入库。**该文件一旦丢失，PMWNB/CAVWNB 服务将无法重建。** 建议 Lead 将其归档到不可变存储或 LFS（属 X3/根目录职责，见 §9 提案 3）。

## §8 Java 安全问题（只报告）

**审查命令**：`git grep -n -I -E 'ObjectInputStream|Runtime\.getRuntime|ProcessBuilder|ServerSocket|new Socket|InetAddress|\.exec\(|readObject|System\.out\.print|System\.err\.print|password|passwd|secret|token' -- 'backend/java/*.java' 'backend/java/**/*.java'`，并对 3 个服务入口文件单独核对 bind/port。

| 检查项 | 结论 | 证据 |
|---|---|---|
| 硬编码口令/密钥 | **零命中** | 上述 grep 的 `password\|passwd\|secret\|token` 在 `backend/java/**` 下无任何命中（命中项全部来自 `System.out` 分支）。**未打印任何凭据内容**（本就没有）。 |
| `ObjectInputStream` / `readObject` 反序列化 | **零命中** | 三个服务通过 `weka.core.SerializationHelper.read(...)` 读取本地 `.model` 文件（`NbAlgorithmService.java`、`PmwnbService.java`、`PredictServer.java` 均有 `import weka.core.SerializationHelper;`）。**风险面是模型文件本身**（Weka 反序列化可构造任意对象），但模型来自本机训练流程、路径由服务端决定，**未见用户可控的路径拼接或上传入口** → 记为已知面，非本次可修项。 |
| `Runtime.exec` / `ProcessBuilder` | **零命中** | 无任何子进程调用。 |
| 对外网络暴露 | **无** | 三个服务全部绑定回环：`NbAlgorithmService.java:97`、`PmwnbService.java:53`、`PredictServer.java:72` 均为 `HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0)`；无 `0.0.0.0`。 |
| 硬编码端口 | **未见** | 端口取自 `port` 变量，由启动参数传入（`start_all.ps1:102/116/135` 分别传 `12313/12314/12315`）；源码内无端口字面量常量。 |
| 硬编码绝对路径 | **仅注释，无实际影响** | `NB/CAVWNB/CAVWNB.java:70-71`、`CAVWNB_MSE.java:68-69` 及 `weka-src` 同位置出现 `/home/nayyar/workspace/.../chess.arff` —— 是 vendored 算法原作者 javadoc 里的**用法示例注释**，不参与运行期路径构造。 |
| 路径拼接/穿越 | **未见** | 未见用户输入参与文件路径拼接。 |
| `System.out` 打印敏感信息 | **无敏感信息** | 命中项分两类：(a) 服务运维日志 `NbAlgorithmService.java:64`（缓存淘汰）、`:104`（启动监听地址）；(b) vendored 算法源码中大量**已被注释掉**的调试输出（`NB/CAVWNB/CAVWNB.java`、`CAVWNB_MSE.java:215-235`、`MVCAVWNB/SPODE.java`、`weka-src` 各同名文件）。`CAVWNB_MSE.java:215-235` 与 `WANBDistribution.java:137`（`System.out.println("tintin")`）是**未注释的调试输出**，但只打印权重矩阵/无意义串，不含凭据。 |
| 无超时 socket | **报告项：三个服务均无请求超时** | 均用 `com.sun.net.httpserver.HttpServer`，未设置 `sun.net.httpserver.maxReqTime`/`maxRspTime` 等超时；`/train` 是同步长耗时处理，执行器为**固定 4 线程** `Executors.newFixedThreadPool(4)`（`NbAlgorithmService.java:102`、`PmwnbService.java:58`、`PredictServer.java:75`），无排队上限/背压。慢训练请求可占满线程池导致服务无响应。**属可用性风险，非安全漏洞；不改**（Java 算法/服务源码禁改，协议 §3.E）。 |
| 并发/状态 | 报告项：`NbAlgorithmService` 内有 LRU 模型缓存（`:64` 淘汰最久未使用） | 未见加锁证据，`setExecutor` 为 4 线程并发 → 缓存是否线程安全**未细查**（§10）。 |

**总结：未发现硬编码凭据、命令执行、对外绑定、反序列化用户输入。** 仅记录 2 项非阻塞风险（HTTP 无超时 + 固定线程池；Weka 模型反序列化面）与 1 项待查项（模型缓存线程安全）。

## §9 跨区提案

以下**均未应用**。

### 提案 1：`backend/java/algorithm-src/README.md` 已过期（我的域内文件，但按"只读审查"约束未改）

**问题**（3 处与实现不符）：
- 第 10 行 `├── PMWNB.zip  # PMWNB 源码包（build_pmwnb_jar.ps1 引用）` —— zip 从未入库、磁盘上不存在，且该引用已在 §6.1 移除。
- 第 21-22 行"`PMWNB.zip` 当前仅被 `build_pmwnb_jar.ps1` 做存在性检查（`Test-Path`）" —— 已不成立。
- 第 20 行"递归编译（`-Filter *.java -File -Recurse`）" —— 脚本第 21 行无 `-Recurse`。
- 另缺一条关键事实：`weka-src/**` 不被任何脚本编译，且 `pmwnb-service.jar` 不可重建。

**建议 diff**：
```diff
 algorithm-src/
-├── PMWNB.zip                 # PMWNB 源码包（build_pmwnb_jar.ps1 引用）
+├── PMWNB/weka-src/           # PMWNB 局部源码快照（jar 的源码记录；不被任何脚本编译）
 └── NB/                       # 其余 4 个算法源码目录（build_nb_algorithm_jars.ps1 引用）
@@
-- `NB/` 下每个子目录里的 `*.java` 会被构建脚本递归编译（`-Filter *.java -File -Recurse`）。
-- `PMWNB.zip` 当前仅被 `build_pmwnb_jar.ps1` 做存在性检查（`Test-Path`），PMWNB 本体复用现成的
-  `backend/lib/pmwnb-service.jar`；若要真正从源码重建 PMWNB，需把 zip 内容接入构建脚本。
+- `NB/` 下每个子目录里的 `*.java` 会被构建脚本编译（`-Filter *.java -File`；4 个子目录均为平铺）。
+- `PMWNB/weka-src/**` **不被任何构建脚本编译**，仅作为 `backend/lib/pmwnb-service.jar` 内
+  `weka.classifiers.bayes.PMWNB.**` 与 `weka.classifiers.trees.RandomForest2` 的源码记录，请勿删除。
+- `backend/lib/pmwnb-service.jar` **未被 git 跟踪，且仓库内无法从源码完整重建**（weka-src 缺 Weka 核心）。
+  三个 `build_*.ps1` 均要求该 jar 已存在。丢失即无法重建，需另行归档。
```
**影响面**：纯文档，零代码影响。**不改的替代方案**：保持现状，但后续读者会继续被 `PMWNB.zip` 误导（本分区已因此浪费排查成本）。

### 提案 2：同 FQN `weka.classifiers.trees.RandomForest2` 双实现（**属改 Java 算法源码，协议 §3.E 禁止，仅登记**）

**问题**：`compat/RandomForest2.java`(70 行 shim) 与 `weka-src/…/trees/RandomForest2.java`(666 行真实实现) **FQN 完全相同**，分别进 `nb-algorithm-service.jar` 与 `pmwnb-service.jar`；NB 服务 JVM 因 manifest `Class-Path` 同时加载两者，仅靠"`-jar` 时应用 jar 优先"这一隐式规则区分（详见 §4.3）。
**建议**：把 compat 版改名为 `weka.classifiers.trees.RandomForest2Compat`，并同步修改唯一引用方 `NB/MVCAVWNB/RF_m.java:4` 的 import。
**影响面**：仅 2 个文件、1 行 import；`nb-algorithm-service.jar` 需重建。**为什么非改不可**：这是全分区唯一"同名同类两份不同实现"的结构，任何 classpath 调整/打包方式变更都会导致 MVCAVWNB **静默换用另一份实现**（无报错、行为改变）。
**不改的替代方案**：在 `build_nb_algorithm_jars.ps1` 顶部加注释显式声明"本 jar 内的 `weka.classifiers.trees.RandomForest2` 是 shim，必须优先于 pmwnb-service.jar 内的同名类"——零风险但只防文档层面的误改。**因涉及算法源码，我不动手。**

### 提案 3：`backend/lib/pmwnb-service.jar` 不可重建（属 X3/根目录职责）

**问题**：27.5 MB / 7292 entries 的未跟踪二进制，是 3 个脚本与 3 个服务的前置依赖，但仓库内无完整源码可重建（详见 §7 风险段）。
**建议**：归档到不可变存储（或 LFS），并在 `docs/` 或根 `README.md` 中记录其来源、版本与校验和（`SHA256`）。
**影响面**：不改代码。**不改的替代方案**：接受"该 jar 一旦丢失即需向算法组重新索取"的运维前提——但该前提目前**未在任何文档中写明**。

## §10 未及细查

1. **未实际编译、未运行任何脚本。** 协议 §1.4 明确禁止写 `backend/lib/*.jar`，因此 §6 的全部"路径有效/`-cp` 充分/Main-Class 对齐"结论都是**静态核对**（`Test-Path` + jar 条目枚举 + class 常量池扫描 + import 解析），**不等于编译通过**。若 Lead 要最终确认，需在服务停止后跑一次 `scripts/build_all_jars.ps1`。
2. **未逐行阅读 66 个 `.java` 的算法逻辑**（10623 行，且协议 §3.E 禁改）。本分区定位是结构审查（谁引用谁、重复源码、死兼容类、构建产物入库），故只做了引用面/API 面审查。
3. **`NbAlgorithmService.java`(865 行) 只读了 import、main/服务段与缓存段**，未逐函数理解全部 8 个算法的训练/预测分支；`PmwnbService.java`(375) 只读了 import 与端口段。
4. **`backend/lib/PredictServer.java`(399 行) 不在我的写作用域**（`backend/lib/**` 非 `backend/java/**`），仅因被 `build_all_jars.ps1` 引用而纳入映射表；我只读了 import 段、`:150-189` 与 `:264-298`，**未评估它自身的死代码/复杂度**——建议 Lead 把它指派给一个真正拥有 `backend/lib/**` 的分区。
5. **未验证 NB 服务运行期 `weka.estimators.DiscreteEstimator` shim 遮蔽真实 Weka 实现是否影响 `NaiveBayes` 精度**（需起服务，协议禁止）。§5 末尾只报告结构事实，不断言行为。
6. **未审计 `pmwnb-service.jar` 的 7292 个 entry**（27.5 MB），只针对性扫描了 PMWNB/CAVWNB/WANBDistribution/RF_m/SPODE/RandomForest2/WANBIA/lbfgsb/ConverterUtils 相关条目。
7. **未核对 `backend/java/.build-*/` 下残留 `.class` 与当前源码是否一致**（可能是旧构建的中间产物）——因它们被 `.gitignore` 覆盖且不影响入库，判断为低价值。
8. **`start_all.ps1` 仅核对了 jar 名一致性**（§6.2），未审其启动逻辑（属 X3 分区）。

## §11 `git status --short`

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

**归属说明**：上表中**唯一属于我的改动是 `M scripts/build_pmwnb_jar.ps1`**（§6.1 的 3 处修改）；`?? docs/全项目代码审查/` 是我的报告目录（未跟踪，正常）。其余 `M`/`D` 条目全部是**其他并行代理正在进行的改动**（`D backend/deprecated/**` 是 Lead 已执行的删除），**与我无关，我未触碰**。我的分区内文件 `backend/java/**` 在 `git status` 中**零出现** —— 未改任何 `.java`、未删任何文件，符合任务约束。

我未修改任何分区外文件。
