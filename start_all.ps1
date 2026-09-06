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

    # ③ 按端口兜底杀：谁占着 12312/12313/12314/5173 就杀谁（最彻底）
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
    Write-Host "  -> docker compose up -d ..." -NoNewline
    Push-Location $root
    docker compose up -d | Out-Null
    Pop-Location
    $t = (Get-Date).AddSeconds(40)
    while (-not $pgOk -and (Get-Date) -lt $t) { $pgOk = Test-Pg; if (-not $pgOk) { Start-Sleep 2 } }
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

# ---- Java PMWNB ----
Write-Host "  Java PMWNB    " -NoNewline
$p = Start-Process -FilePath $javaBin -ArgumentList "-jar","lib\pmwnb-service.jar","12313" `
    -WorkingDirectory $backend -WindowStyle Hidden -PassThru
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
    -WorkingDirectory $backend -WindowStyle Hidden -PassThru
if ($p) { $predictPid = $p.Id }
$ok = $false
$t = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $t) {
    try { if ((Invoke-RestMethod "http://127.0.0.1:12314/health" -TimeoutSec 2).status -eq "ok") { $ok=$true; break } } catch {}
    Start-Sleep 1
}
if ($ok) { Write-Host ":12314  OK" -ForegroundColor Green }
else     { Write-Host ":12314  FAIL" -ForegroundColor Red }

# ---- Java algorithm services ----
$algorithmServices = @(
    @{ Name = "A2WNB"; Jar = "a2wnb-service.jar"; Port = 12315; Code = "A2WNB" },
    @{ Name = "CAVWNB"; Jar = "cavwnb-service.jar"; Port = 12316; Code = "CAVWNB" },
    @{ Name = "EMAWNB"; Jar = "emawnb-service.jar"; Port = 12317; Code = "EMAWNB" },
    @{ Name = "MAWNB"; Jar = "mawnb-service.jar"; Port = 12318; Code = "MAWNB" },
    @{ Name = "DIWNB"; Jar = "diwnb-service.jar"; Port = 12319; Code = "DIWNB" }
)
$algoLogDir = Join-Path $backend "storage\logs"
New-Item -ItemType Directory -Path $algoLogDir -Force | Out-Null
foreach ($svc in $algorithmServices) {
    Write-Host ("  Java {0}    " -f $svc.Name) -NoNewline
    $svcArgs = @("-jar", (Join-Path $backend ("lib\{0}" -f $svc.Jar)), [string]$svc.Port, $svc.Code)
    $svcProc = Start-Process -FilePath $javaBin -ArgumentList $svcArgs `
        -WorkingDirectory $backend -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $algoLogDir ("{0}.out.log" -f $svc.Name)) `
        -RedirectStandardError (Join-Path $algoLogDir ("{0}.err.log" -f $svc.Name))
    if ($svcProc) { $algoPids += $svcProc.Id }
    $svcOk = $false
    $t = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $t) {
        try { if ((Invoke-RestMethod ("http://127.0.0.1:{0}/health" -f $svc.Port) -TimeoutSec 2).status -eq "ok") { $svcOk = $true; break } } catch {}
        Start-Sleep 1
    }
    if ($svcOk) { Write-Host (":{0}  OK" -f $svc.Port) -ForegroundColor Green }
    else { Write-Host (":{0}  FAIL" -f $svc.Port) -ForegroundColor Red }
}

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
# FastAPI 起来后,顺带探测数据库新接口 /api/v1 是否真的连通
if ($ok) {
    try {
        $h = @{ "X-User-Id" = "1" }
        $r = Invoke-RestMethod "http://127.0.0.1:12312/api/v1/scenarios" -Headers $h -TimeoutSec 5
        if ($r.code -eq 0) { Write-Host "    /api/v1     OK (数据库已连接)" -ForegroundColor Green }
        else { Write-Host "    /api/v1     WARN ($($r.message))" -ForegroundColor Yellow }
    } catch {
        Write-Host "    /api/v1     WARN (数据库未就绪, 新接口暂不可用)" -ForegroundColor Yellow
    }
}

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
