$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$nbRoot = Join-Path $repo "backend\java\algorithm-src\NB"
$pmwnbJar = Join-Path $repo "backend\lib\pmwnb-service.jar"
$buildRoot = Join-Path $repo "backend\java\.build-nb"
$classes = Join-Path $buildRoot "classes"
$lib = Join-Path $repo "backend\lib"
$kfdbRoot = Join-Path $nbRoot "KFDB"
$mltoolsJar = Join-Path $lib "MLTools.jar"
$commonsMathJar = Join-Path $lib "commons-math3-3.6.1.jar"

if (-not (Test-Path $pmwnbJar)) { throw "找不到依赖 JAR: $pmwnbJar" }
if (-not (Test-Path $nbRoot)) { throw "找不到算法源码目录: $nbRoot" }
if (-not (Test-Path $mltoolsJar)) { throw "找不到 KFDB 依赖 JAR: $mltoolsJar" }
if (-not (Test-Path $commonsMathJar)) { throw "找不到 KFDB 依赖 JAR: $commonsMathJar" }

if (Test-Path $buildRoot) { Remove-Item -LiteralPath $buildRoot -Recurse -Force }
New-Item -ItemType Directory -Path $classes -Force | Out-Null

$sources = @(
    (Join-Path $repo "backend\java\NbAlgorithmService.java"),
    (Join-Path $repo "backend\java\compat\WANBIA.java"),
    (Join-Path $repo "backend\java\compat\DiscreteEstimator.java")
)
$sources += Get-ChildItem (Join-Path $nbRoot "A2WNB"), (Join-Path $nbRoot "CAVWNB"), (Join-Path $nbRoot "DIWNB"), (Join-Path $nbRoot "MVCAVWNB") -Filter *.java -File | Select-Object -ExpandProperty FullName
$sources += Get-ChildItem (Join-Path $nbRoot "FLNB"), (Join-Path $nbRoot "FTAWNB") -Filter *.java -File | Select-Object -ExpandProperty FullName
# KFDB 仓库源码（KFDB / hdp / tools 三个包）+ 平台适配器 KFDB.java。
# 排除作者自带的 KFDB_CV / Evaluation / hdp\testing（实验入口与测试 main，平台不用，
# 且 KFDB_CV 里写死了作者本机数据集路径）。
$sources += Join-Path $kfdbRoot "KFDB.java"
$sources += Get-ChildItem (Join-Path $kfdbRoot "src\KFDB") -Filter *.java -File |
    Where-Object { $_.Name -notin @("Evaluation.java", "KFDB_CV.java") } |
    Select-Object -ExpandProperty FullName
$sources += Get-ChildItem (Join-Path $kfdbRoot "src\hdp") -Filter *.java -File | Select-Object -ExpandProperty FullName
$sources += Get-ChildItem (Join-Path $kfdbRoot "src\hdp\logStirling") -Filter *.java -File | Select-Object -ExpandProperty FullName
$sources += Get-ChildItem (Join-Path $kfdbRoot "src\hdp\logStirling\cache") -Filter *.java -File | Select-Object -ExpandProperty FullName
$sources += Get-ChildItem (Join-Path $kfdbRoot "src\tools") -Filter *.java -File | Select-Object -ExpandProperty FullName
$sources += Get-ChildItem (Join-Path $repo "backend\java\compat") -Filter *.java -File -Recurse | Select-Object -ExpandProperty FullName

Write-Host "Compiling supplied NB Java sources..."
# KFDB 的 hdp 包依赖 mltools（MLTools.jar）与 commons-math3；只在编译期需要 mltools
# 的类在运行期不会加载（lgCache 已标 transient，logStirling 分支在 KFDB_MSE/ACC 下不走）。
& javac -encoding UTF-8 -cp "$pmwnbJar;$commonsMathJar;$mltoolsJar" -d $classes $sources
if ($LASTEXITCODE -ne 0) { throw "javac 编译失败" }

$manifest = Join-Path $buildRoot "MANIFEST.MF"
@(
    "Manifest-Version: 1.0",
    "Main-Class: com.security.bayes.nbservice.NbAlgorithmService",
    "Class-Path: pmwnb-service.jar commons-math3-3.6.1.jar MLTools.jar",
    ""
) | Set-Content -LiteralPath $manifest -Encoding ascii

# 单个服务 JAR：5 个算法（A2WNB/CAVWNB/DIWNB/MAWNB/EMAWNB）由同一个进程提供，
# 算法随请求体的 algorithm_code 指定，因此只需要一个包含全部算法类的 JAR。
# 合并前这里是 5 个 JAR，但打包命令始终用 -C $classes .（整个目录），
# 传入的 $Entries 从未被使用，5 个文件因此字节完全相同——本次一并去掉这个死参数。
$jarName = "nb-algorithm-service.jar"
$target = Join-Path $lib $jarName
if (Test-Path $target) { Remove-Item -LiteralPath $target -Force }
& jar cfm $target $manifest -C $classes .
if ($LASTEXITCODE -ne 0) { throw "jar 打包失败: $jarName" }
Write-Host "Created $target"

# 清掉合并前遗留的 5 个同名异构 JAR，避免"到底跑的是哪个"的混淆
$legacyJars = @(
    "a2wnb-service.jar", "cavwnb-service.jar", "diwnb-service.jar",
    "emawnb-service.jar", "mawnb-service.jar"
)
foreach ($name in $legacyJars) {
    $stale = Join-Path $lib $name
    if (Test-Path $stale) { Remove-Item -LiteralPath $stale -Force; Write-Host "Removed legacy $stale" }
}

Write-Host "NB algorithm service JAR built successfully."
