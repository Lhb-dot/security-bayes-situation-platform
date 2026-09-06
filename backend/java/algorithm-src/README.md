# 算法源码目录（接入构建脚本用）

本目录存放朴素贝叶斯各算法的 Java 源码，供 `scripts/build_*.ps1` 重新编译 JAR 使用。
源码由算法组提供，加入本目录并纳入版本管理后，任何机器都能重新编译。

## 目录结构

```
algorithm-src/
├── PMWNB.zip                 # PMWNB 源码包（build_pmwnb_jar.ps1 引用）
└── NB/                       # 其余 4 个算法源码目录（build_nb_algorithm_jars.ps1 引用）
    ├── A2WNB/                # A²WNB 源码（含 RODE）
    ├── CAVWNB/               # CAVWNB 源码
    ├── DIWNB/                # DIWNB 源码（DIWNB_HE / DIWNB_HL / DIWNB_S）
    └── MVCAVWNB/             # MAWNB(MVCAVWNB) 与 EMAWNB 源码
```

## 说明

- `NB/` 下每个子目录里的 `*.java` 会被构建脚本递归编译（`-Filter *.java -File -Recurse`）。
- `PMWNB.zip` 当前仅被 `build_pmwnb_jar.ps1` 做存在性检查（`Test-Path`），PMWNB 本体复用现成的
  `backend/lib/pmwnb-service.jar`；若要真正从源码重建 PMWNB，需把 zip 内容接入构建脚本。
