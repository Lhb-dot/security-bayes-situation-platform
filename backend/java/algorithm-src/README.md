# 算法源码目录（接入构建脚本用）

本目录存放朴素贝叶斯各算法的 Java 源码，供 `scripts/build_*.ps1` 重新编译 JAR 使用。
源码由算法组提供，加入本目录并纳入版本管理后，任何机器都能重新编译。

## 目录结构

```
algorithm-src/
├── PMWNB.zip                 # PMWNB 源码包（build_pmwnb_jar.ps1 引用）
└── NB/                       # 8 个算法源码目录（build_nb_algorithm_jars.ps1 引用）
    ├── A2WNB/                # A²WNB 源码（含 RODE）
    ├── CAVWNB/               # CAVWNB 源码
    ├── DIWNB/                # DIWNB 源码（DIWNB_HE / DIWNB_HL / DIWNB_S）
    ├── MVCAVWNB/             # MAWNB(MVCAVWNB) 与 EMAWNB 源码
    ├── KFDB/                 # KFDB 源码（作者仓库 src/ 原样 + 平台适配器 KFDB.java）
    ├── FLNB/                 # FLNB 源码（FLNB_poly / FLNB_log + 平台适配器 FLNB.java）
    └── FTAWNB/               # FTAWNB 源码
```

## 说明

- `NB/` 下每个子目录里的 `*.java` 会被构建脚本递归编译（`-Filter *.java -File -Recurse`）。
  - 例外：`KFDB/src/KFDB/{Evaluation,KFDB_CV}.java` 与 `KFDB/src/hdp/testing/` 是作者自带的
    实验入口 / 测试 main（写死了作者本机数据集路径），构建脚本显式排除。
  - `KFDB` 依赖 `backend/lib/MLTools.jar` 与 `backend/lib/commons-math3-3.6.1.jar`
    （编译期与运行期都需要），`nb-algorithm-service.jar` 的 `Class-Path` 已登记这两个 JAR。
    仓库按既有约定不跟踪 `*.jar`，这两个依赖取自 KFDB 作者仓库 `KFDB-Code.zip` 内的
    `KFDB/lib/`，需手动放到 `backend/lib/`（与 `pmwnb-service.jar` 的获取方式一致）。
- `PMWNB.zip` 当前仅被 `build_pmwnb_jar.ps1` 做存在性检查（`Test-Path`），PMWNB 本体复用现成的
  `backend/lib/pmwnb-service.jar`；若要真正从源码重建 PMWNB，需把 zip 内容接入构建脚本。
