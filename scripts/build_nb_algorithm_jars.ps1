$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$nbRoot = Join-Path $repo "backend\java\algorithm-src\NB"
$pmwnbJar = Join-Path $repo "backend\lib\pmwnb-service.jar"
$buildRoot = Join-Path $repo "backend\java\.build-nb"
$classes = Join-Path $buildRoot "classes"
$lib = Join-Path $repo "backend\lib"

if (-not (Test-Path $pmwnbJar)) { throw "找不到依赖 JAR: $pmwnbJar" }
if (-not (Test-Path $nbRoot)) { throw "找不到算法源码目录: $nbRoot" }

if (Test-Path $buildRoot) { Remove-Item -LiteralPath $buildRoot -Recurse -Force }
New-Item -ItemType Directory -Path $classes -Force | Out-Null

$sources = @(
    (Join-Path $repo "backend\java\NbAlgorithmService.java"),
    (Join-Path $repo "backend\java\compat\WANBIA.java"),
    (Join-Path $repo "backend\java\compat\DiscreteEstimator.java")
)
$sources += Get-ChildItem (Join-Path $nbRoot "A2WNB"), (Join-Path $nbRoot "CAVWNB"), (Join-Path $nbRoot "DIWNB"), (Join-Path $nbRoot "MVCAVWNB") -Filter *.java -File | Select-Object -ExpandProperty FullName
$sources += Get-ChildItem (Join-Path $repo "backend\java\compat") -Filter *.java -File -Recurse | Select-Object -ExpandProperty FullName

Write-Host "Compiling supplied NB Java sources..."
& javac -encoding UTF-8 -cp $pmwnbJar -d $classes $sources
if ($LASTEXITCODE -ne 0) { throw "javac 编译失败" }

$manifest = Join-Path $buildRoot "MANIFEST.MF"
@(
    "Manifest-Version: 1.0",
    "Main-Class: com.security.bayes.nbservice.NbAlgorithmService",
    "Class-Path: pmwnb-service.jar",
    ""
) | Set-Content -LiteralPath $manifest -Encoding ascii

function New-AlgorithmJar {
    param(
        [string]$Name,
        [string[]]$Entries
    )
    $target = Join-Path $lib $Name
    if (Test-Path $target) { Remove-Item -LiteralPath $target -Force }
    # Each service JAR is self-contained with the four compiled algorithm families.
    # The second startup argument selects the active classifier implementation.
    & jar cfm $target $manifest -C $classes .
    if ($LASTEXITCODE -ne 0) { throw "jar 打包失败: $Name" }
    Write-Host "Created $target"
}

New-AlgorithmJar "a2wnb-service.jar" @(
    "weka/classifiers/zh/A2WNB",
    "weka/classifiers/bayes/WANBIA",
    "weka/estimators/DiscreteEstimator.class"
)
New-AlgorithmJar "cavwnb-service.jar" @(
    "weka/classifiers/zh/CAVWNB",
    "weka/estimators/DiscreteEstimator.class"
)
New-AlgorithmJar "diwnb-service.jar" @(
    "weka/classifiers/mkx/DIWNB",
    "weka/estimators/DiscreteEstimator.class"
)
New-AlgorithmJar "emawnb-service.jar" @(
    "weka/classifiers/zh/MVCAVWNB",
    "weka/classifiers/zh/CAVWNB",
    "weka/estimators/DiscreteEstimator.class"
)
New-AlgorithmJar "mawnb-service.jar" @(
    "weka/classifiers/zh/MVCAVWNB",
    "weka/classifiers/zh/CAVWNB",
    "weka/estimators/DiscreteEstimator.class"
)

Write-Host "All NB algorithm JARs built successfully."
