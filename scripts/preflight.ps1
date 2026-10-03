$ErrorActionPreference = "Continue"

# 干净 checkout 冒烟自检：拦截三类"作者本机能跑、别人 checkout 跑不起来"的坑。
#   1) Java jar 缺失  —— 构建产物，若缺失从 git 恢复
#   2) 后端 import 失败 —— 代码引用了从未提交/被忽略的模块
#   3) 前端依赖缺失  —— package.json 声明了依赖但 node_modules 没装
# 可独立运行，也可在 start_all.ps1 开头调用。任何一项失败 => exit 1。

$repo     = Split-Path -Parent $PSScriptRoot
$backend  = Join-Path $repo "backend"
$frontend = Join-Path $repo "frontend"
$lib      = Join-Path $backend "lib"

$script:errors = @()

function Step {
    param([string]$Label, [bool]$Ok, [string]$Detail = "")
    if ($Ok) {
        Write-Host ("  [OK]   {0}" -f $Label) -ForegroundColor Green
    } else {
        Write-Host ("  [FAIL] {0}" -f $Label) -ForegroundColor Red
        if ($Detail) { Write-Host ("         {0}" -f $Detail) -ForegroundColor DarkYellow }
        $script:errors += $Label
    }
}

Write-Host ""
Write-Host "  Pre-flight check" -ForegroundColor Cyan
Write-Host "  ----------------" -ForegroundColor DarkGray

# ---- 1) Java jars ----
$jars = @(
    "pmwnb-service.jar", "predict-service.jar",
    "a2wnb-service.jar", "cavwnb-service.jar", "diwnb-service.jar",
    "emawnb-service.jar", "mawnb-service.jar"
)
$missing = @($jars | Where-Object { -not (Test-Path (Join-Path $lib $_)) })
if ($missing.Count -gt 0) {
    Write-Host ("  缺 jar：{0}，尝试从 git 恢复 ..." -f ($missing -join ', ')) -ForegroundColor Yellow
    git restore --worktree -- "backend/lib/*.jar" 2>$null                  # 已跟踪：从 HEAD 恢复
    git restore --source=1229b55^ --worktree -- "backend/lib/*.jar" 2>$null # 兜底：从历史提交恢复
}
$missing = @($jars | Where-Object { -not (Test-Path (Join-Path $lib $_)) })
Step "Java jars ($lib)" ($missing.Count -eq 0) (
    $(if ($missing.Count) {
        "仍缺: $($missing -join ', ') —— 请重新构建，或执行 git restore --source=1229b55^ --worktree -- backend/lib/*.jar"
    } else { "" })
)

# ---- 2) 后端 import ----
Push-Location $backend
$out = (& python -c "import app.main" 2>&1 | Out-String).Trim()
$exit = $LASTEXITCODE
Pop-Location
Step "后端 import (python -c 'import app.main')" ($exit -eq 0) $out

# ---- 3) 前端依赖 ----
$needInstall = -not (Test-Path (Join-Path $frontend "node_modules"))
if (-not $needInstall) {
    foreach ($pkg in @("unplugin-auto-import", "unplugin-vue-components")) {
        if (-not (Test-Path (Join-Path $frontend "node_modules\$pkg"))) { $needInstall = $true; break }
    }
}
if ($needInstall) {
    Write-Host "  前端依赖缺失，执行 npm install ..." -ForegroundColor Yellow
    Push-Location $frontend
    $out = (& npm install 2>&1 | Out-String).Trim()
    $exit = $LASTEXITCODE
    Pop-Location
    Step "前端依赖 (npm install)" ($exit -eq 0) $out
} else {
    Step "前端依赖 (node_modules)" $true ""
}

# ---- 汇总 ----
Write-Host ""
if ($script:errors.Count -eq 0) {
    Write-Host "  Pre-flight PASS" -ForegroundColor Green
    exit 0
} else {
    Write-Host ("  Pre-flight FAIL: {0}" -f ($script:errors -join ' | ')) -ForegroundColor Red
    exit 1
}
