$ErrorActionPreference = "Stop"

# Rebuild three groups of JARs in dependency order:
#   1) NB algorithm service JARs (a2wnb/cavwnb/diwnb/emawnb/mawnb)
#   2) pmwnb-service.jar (recompile PMWNB algorithm class with view/evidence methods)
#   3) predict-service.jar (recompile PredictServer to emit PMWNB views + feature evidence)
#
# Prerequisite: stop the services that hold file locks on these JARs first
# (close the start_all.ps1 window).

$repo = Split-Path -Parent $PSScriptRoot
$lib = Join-Path $repo "backend\lib"
$buildRoot = Join-Path $repo "backend\java\.build-all"
$pmwnbJar = Join-Path $lib "pmwnb-service.jar"
$predictJar = Join-Path $lib "predict-service.jar"

# 1) NB algorithm JARs
Write-Host "==> [1/3] Rebuilding NB algorithm JARs ..."
& (Join-Path $PSScriptRoot "build_nb_algorithm_jars.ps1")

if (Test-Path $buildRoot) { Remove-Item -LiteralPath $buildRoot -Recurse -Force }
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null

# 2) pmwnb-service.jar: recompile PMWNB algorithm class
$pmwnbSource = Join-Path $repo "backend\java\algorithm-src\PMWNB\weka-src\src\main\java\weka\classifiers\bayes\PMWNB\PMWNB\PMWNB.java"
$pmwnbClasses = Join-Path $buildRoot "pmwnb-classes"
New-Item -ItemType Directory -Path $pmwnbClasses -Force | Out-Null
Write-Host "==> [2/3] Compiling and updating pmwnb-service.jar ..."
if (-not (Test-Path -LiteralPath $pmwnbSource)) { throw "PMWNB source not found: $pmwnbSource" }
& javac -encoding UTF-8 -cp $pmwnbJar -d $pmwnbClasses $pmwnbSource
if ($LASTEXITCODE -ne 0) { throw "PMWNB.java compile failed" }
& jar uf $pmwnbJar -C $pmwnbClasses .
if ($LASTEXITCODE -ne 0) { throw "pmwnb-service.jar update failed" }
Write-Host "     Updated $pmwnbJar"

# 3) predict-service.jar: recompile PredictServer
$predictSource = Join-Path $lib "PredictServer.java"
$predictClasses = Join-Path $buildRoot "predict-classes"
New-Item -ItemType Directory -Path $predictClasses -Force | Out-Null
$manifest = Join-Path $buildRoot "MANIFEST.MF"
@(
    "Manifest-Version: 1.0",
    "Main-Class: PredictServer",
    "Class-Path: pmwnb-service.jar",
    ""
) | Set-Content -LiteralPath $manifest -Encoding ascii
Write-Host "==> [3/3] Compiling and packaging predict-service.jar ..."
& javac -encoding UTF-8 -cp $pmwnbJar -d $predictClasses $predictSource
if ($LASTEXITCODE -ne 0) { throw "PredictServer.java compile failed" }
if (Test-Path $predictJar) { Remove-Item -LiteralPath $predictJar -Force }
& jar cfm $predictJar $manifest -C $predictClasses .
if ($LASTEXITCODE -ne 0) { throw "predict-service.jar packaging failed" }
Write-Host "     Created $predictJar"

Write-Host ""
Write-Host "All JARs built successfully." -ForegroundColor Green
