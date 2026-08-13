$ErrorActionPreference = "SilentlyContinue"
$Host.UI.RawUI.WindowTitle = "Security Platform"

$root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = "$root\backend"
$frontend= "$root\frontend"
$jar     = "$backend\lib\pmwnb-service.jar"

$javaPid = $null; $pyPid = $null; $vuePid = $null

# ---- cleanup ----
function Stop-All {
    if ($javaPid) { Stop-Process -Id $javaPid -Force -EA SilentlyContinue }
    if ($pyPid)   { Stop-Process -Id $pyPid   -Force -EA SilentlyContinue }
    if ($vuePid)  { Stop-Process -Id $vuePid  -Force -EA SilentlyContinue }
    Get-Process -Name java,node -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
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

# ---- Java PMWNB ----
Write-Host "  Java PMWNB    " -NoNewline
$p = Start-Process -FilePath "java" -ArgumentList "-jar","lib\pmwnb-service.jar","12313" `
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

# ---- Python FastAPI ----
Write-Host "  FastAPI       " -NoNewline
$p = Start-Process -FilePath "python" -ArgumentList "-m","app.main" `
    -WorkingDirectory $backend -WindowStyle Hidden -PassThru
if ($p) { $pyPid = $p.Id }
$ok = $false
$t = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $t) {
    try { if (Invoke-RestMethod "http://127.0.0.1:12312/api/model/dataset-list" -TimeoutSec 2) { $ok=$true; break } } catch {}
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
