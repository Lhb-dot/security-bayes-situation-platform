$ErrorActionPreference = "SilentlyContinue"
$Host.UI.RawUI.WindowTitle = "Security Platform"

$root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = "$root\backend"
$frontend= "$root\frontend"
$jar     = "$backend\lib\pmwnb-service.jar"
$java25  = "C:\Program Files\Eclipse Adoptium\jdk-25.0.4.7-hotspot\bin\java.exe"
$javaBin = if (Test-Path $java25) { $java25 } else { "java" }

$javaPid = $null; $pyPid = $null; $vuePid = $null; $predictPid = $null; $algoPids = @()

# ---- cleanup ----
function Stop-All {
    # ① 按本次启动时记录的 PID 杀
    if ($javaPid)    { Stop-Process -Id $javaPid    -Force -EA SilentlyContinue }
    if ($predictPid) { Stop-Process -Id $predictPid -Force -EA SilentlyContinue }
    foreach ($algoPid in $algoPids) { if ($algoPid) { Stop-Process -Id $algoPid -Force -EA SilentlyContinue } }
    if ($pyPid)      { Stop-Process -Id $pyPid      -Force -EA SilentlyContinue }
    if ($vuePid)     { Stop-Process -Id $vuePid     -Force -EA SilentlyContinue }

    # ② 按名字兜底杀（java/node/python 一个不漏）
    Get-Process -Name java,node,python -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue

    # ③ 按端口兜底杀：谁占着这些端口就杀谁（最彻底）
    #    12315-12319 是合并前各算法独占的端口，留着是为了清掉旧版本残留的进程
    foreach ($port in 12312,12313,12314,12315,12316,12317,12318,12319,5173) {
        Get-NetTCPConnection -LocalPort $port -State Listen -EA SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique |
            ForEach-Object { Stop-Process -Id $_ -Force -EA SilentlyContinue }
    }
}

Clear-Host
Write-Host "  Security Situation Platform" -ForegroundColor Cyan
Write-Host "  ----------------------------" -ForegroundColor DarkGray

# ---- pre-check ----
$err = $false
if (-not (Get-Command java   -EA SilentlyContinue)) { Write-Host "  [X] Java not installed"   -ForegroundColor Red;   $err=$true }
if (-not (Get-Command python -EA SilentlyContinue)) { Write-Host "  [X] Python not installed" -ForegroundColor Red;   $err=$true }
if (-not (Get-Command node   -EA SilentlyContinue)) { Write-Host "  [X] Node.js not installed" -ForegroundColor Red;  $err=$true }
if (-not (Test-Path $jar))  { Write-Host "  [X] lib/pmwnb-service.jar missing" -ForegroundColor Red; $err=$true }
if (-not (Test-Path "$backend\lib\nb-algorithm-service.jar")) { Write-Host "  [X] lib/nb-algorithm-service.jar missing (跑 scripts/build_nb_algorithm_jars.ps1 重建)" -ForegroundColor Red; $err=$true }
if ($err) { Write-Host ""; Read-Host "Press Enter to exit"; exit 1 }

# ---- 先清掉上次可能残留的进程（不依赖上次是否正常退出）----
Stop-All
Start-Sleep 1

# ---- PostgreSQL (数据库依赖, /api/v1 新世界必需) ----
Write-Host "  PostgreSQL    " -NoNewline
function Test-Pg {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.Connect("127.0.0.1", 5432)
        $ok = $c.Connected; $c.Close(); return $ok
    } catch { return $false }
}
$pgOk = $false
$t = (Get-Date).AddSeconds(5)
while (-not $pgOk -and (Get-Date) -lt $t) { $pgOk = Test-Pg; if (-not $pgOk) { Start-Sleep 1 } }
if (-not $pgOk) {
    Write-Host ":5432  DOWN" -ForegroundColor Yellow
    Write-Host "  -> docker compose up -d"
    Push-Location $root
    # 2>$null: 屏蔽 docker 的原始报错, 否则整段 npipe 错误会糊在上一条状态行末尾
    docker compose up -d 2>$null | Out-Null
    Pop-Location
    $t = (Get-Date).AddSeconds(40)
    while (-not $pgOk -and (Get-Date) -lt $t) { $pgOk = Test-Pg; if (-not $pgOk) { Start-Sleep 2 } }
    if (-not $pgOk) {
        Write-Host "     Docker Desktop 没启动? 启动后重跑本脚本, 或手动执行: docker compose up -d" -ForegroundColor DarkYellow
    }
}
if ($pgOk) { Write-Host ":5432  OK" -ForegroundColor Green }
else { Write-Host ":5432  FAIL (数据库不可用, /api/v1 接口将报错; 旧 /api/model 演示不受影响)" -ForegroundColor Red }

# ---- 数据库迁移 (alembic: 对齐数据库结构与最新代码) ----
if ($pgOk) {
    Write-Host "  DB Migrate    " -NoNewline
    Push-Location $backend
    $migExit = 0
    $migMsg = ""
    try {
        $migMsg = (& python -m alembic upgrade head 2>&1 | Out-String).Trim()
        $migExit = $LASTEXITCODE
    } catch {
        $migExit = 1
        $migMsg = $_.Exception.Message
    }
    Pop-Location
    if ($migExit -eq 0) { Write-Host "OK" -ForegroundColor Green }
    else {
        Write-Host "WARN (迁移失败)" -ForegroundColor Yellow
        Write-Host "      $migMsg" -ForegroundColor DarkYellow
    }
}

# ---- Java 服务日志目录 ----
# 三个 Java 服务统一把 stdout/stderr 重定向到文件：不重定向时子进程 stdout 会挂到
# 本窗口的控制台，窗口被关掉/输出阻塞时服务端 println 可能挂住（12315 一直这么做，
# 12313/12314 原先漏了，出问题也没日志可查）。
$logDir = Join-Path $backend "storage\logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

# ---- Java PMWNB ----
Write-Host "  Java PMWNB    " -NoNewline
$p = Start-Process -FilePath $javaBin -ArgumentList "-jar","lib\pmwnb-service.jar","12313" `
    -WorkingDirectory $backend -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDir "pmwnb-service.out.log") `
    -RedirectStandardError (Join-Path $logDir "pmwnb-service.err.log")
if ($p) { $javaPid = $p.Id }
$ok = $false
$t = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $t) {
    try { if ((Invoke-RestMethod "http://127.0.0.1:12313/health" -TimeoutSec 2).status -eq "ok") { $ok=$true; break } } catch {}
    Start-Sleep 1
}
if ($ok) { Write-Host ":12313  OK" -ForegroundColor Green }
else     { Write-Host ":12313  FAIL" -ForegroundColor Red }

# ---- Java Predict (通用预测服务, 12314) ----
Write-Host "  Predict       " -NoNewline
$p = Start-Process -FilePath $javaBin -ArgumentList "-jar","lib\predict-service.jar","12314" `
    -WorkingDirectory $backend -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDir "predict-service.out.log") `
    -RedirectStandardError (Join-Path $logDir "predict-service.err.log")
if ($p) { $predictPid = $p.Id }
$ok = $false
$t = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $t) {
    try { if ((Invoke-RestMethod "http://127.0.0.1:12314/health" -TimeoutSec 2).status -eq "ok") { $ok=$true; break } } catch {}
    Start-Sleep 1
}
if ($ok) { Write-Host ":12314  OK" -ForegroundColor Green }
else     { Write-Host ":12314  FAIL" -ForegroundColor Red }

# ---- Java NB 算法服务（5 个算法共用同一进程）----
# 5 个 jar 字节完全相同，原本是同一个程序起 5 次、只差第 2 个启动参数；
# 合并后算法由请求体的 algorithm_code 指定，端口 12315-12319 → 12315。
Write-Host "  Java NB Algo  " -NoNewline
$nbAlgoProc = Start-Process -FilePath $javaBin `
    -ArgumentList @("-jar", (Join-Path $backend "lib\nb-algorithm-service.jar"), "12315") `
    -WorkingDirectory $backend -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDir "nb-algorithm.out.log") `
    -RedirectStandardError (Join-Path $logDir "nb-algorithm.err.log")
if ($nbAlgoProc) { $algoPids += $nbAlgoProc.Id }
$nbOk = $false
$t = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $t) {
    try { if ((Invoke-RestMethod "http://127.0.0.1:12315/health" -TimeoutSec 2).status -eq "ok") { $nbOk = $true; break } } catch {}
    Start-Sleep 1
}
if ($nbOk) { Write-Host ":12315  OK  A2WNB/CAVWNB/EMAWNB/MAWNB/DIWNB" -ForegroundColor Green }
else       { Write-Host ":12315  FAIL" -ForegroundColor Red }

# ---- Python FastAPI ----
Write-Host "  FastAPI       " -NoNewline
$p = Start-Process -FilePath "python" -ArgumentList "-m","app.main" `
    -WorkingDirectory $backend -WindowStyle Hidden -PassThru
if ($p) { $pyPid = $p.Id }
$ok = $false
$t = (Get-Date).AddSeconds(45)
while ((Get-Date) -lt $t) {
    try { if (Invoke-RestMethod "http://127.0.0.1:12312/openapi.json" -TimeoutSec 2) { $ok=$true; break } } catch {}
    Start-Sleep 1
}
if ($ok) { Write-Host ":12312  OK" -ForegroundColor Green }
else     { Write-Host ":12312  FAIL" -ForegroundColor Red }

# ---- Vue Frontend ----
Write-Host "  Vue Frontend  " -NoNewline
$si = New-Object System.Diagnostics.ProcessStartInfo
$si.FileName = "cmd"
$si.Arguments = "/c cd /d `"$frontend`" && npm run dev"
$si.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$si.CreateNoWindow = $true
$p = [System.Diagnostics.Process]::Start($si)
if ($p) { $vuePid = $p.Id }
Start-Sleep 3
$ok = $false
$t = (Get-Date).AddSeconds(25)
while ((Get-Date) -lt $t) {
    try { if ((Invoke-WebRequest "http://localhost:5173" -TimeoutSec 2 -UseBasicParsing).StatusCode -eq 200) { $ok=$true; break } } catch {}
    Start-Sleep 1
}
if ($ok) { Write-Host ":5173  OK" -ForegroundColor Green }
else     { Write-Host ":5173  FAIL" -ForegroundColor Red }

# ---- done ----
Write-Host ""

if ($javaPid -and $pyPid -and $vuePid) {
    Write-Host ""
    Write-Host "  ====================================" -ForegroundColor Cyan
    Write-Host "  >>  http://localhost:5173           " -ForegroundColor White
    Write-Host "  >>  API Docs: http://localhost:12312/docs" -ForegroundColor White
    Write-Host "  ====================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Ctrl+C or close this window to stop all services." -ForegroundColor DarkGray
}
else {
    Write-Host "  Startup incomplete (see FAIL above)." -ForegroundColor Yellow
    Write-Host "  Close window to stop." -ForegroundColor DarkGray
}

try {
    while ($true) { Start-Sleep 1 }
} finally {
    Write-Host ""
    Write-Host "  Shutting down..." -ForegroundColor Yellow
    Stop-All
    Write-Host "  Stopped." -ForegroundColor Green
    Start-Sleep 1
}
