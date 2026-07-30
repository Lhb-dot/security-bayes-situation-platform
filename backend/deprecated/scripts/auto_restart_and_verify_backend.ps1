param(
    [int]$Port = 12312,
    [switch]$StartCrawl = $false,
    [int]$StartupTimeoutSec = 60
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Write-Step {
    param([string]$Message)
    Write-Host "`n[STEP] $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-WarnMsg {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$algoDir = Resolve-Path (Join-Path $scriptDir "..")
$serverPath = Join-Path $algoDir "server.py"

if (-not (Test-Path $serverPath)) {
    throw "server.py not found: $serverPath"
}

Write-Step "Find and stop old process on port $Port"
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -ne $listener) {
    $oldPid = $listener.OwningProcess
    Write-Host "Found process PID=$oldPid" -ForegroundColor DarkYellow
    try {
        Stop-Process -Id $oldPid -Force
        Start-Sleep -Seconds 1
        Write-Ok "Old process stopped"
    }
    catch {
        Write-WarnMsg "Failed to stop old process. Please stop PID=$oldPid manually. Error: $($_.Exception.Message)"
    }
}
else {
    Write-Ok "No listener found on port"
}

Write-Step "Start backend server.py"
$proc = Start-Process -FilePath "python" -ArgumentList "server.py" -WorkingDirectory $algoDir -PassThru
Write-Host "New process PID=$($proc.Id)" -ForegroundColor DarkYellow

$baseUrl = "http://localhost:$Port"
$strategicEventsUrl = "$baseUrl/strategic_events.json"
$crawlStatusUrl = "$baseUrl/api/crawl_status"
$startCrawlUrl = "$baseUrl/api/start_crawl"

Write-Step "Wait for service ready (timeout: $StartupTimeoutSec sec)"
$deadline = (Get-Date).AddSeconds($StartupTimeoutSec)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $pingResp = Invoke-WebRequest -Uri $strategicEventsUrl -UseBasicParsing -TimeoutSec 5
        if ($pingResp.StatusCode -eq 200) {
            $ready = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $ready) {
    Write-Err "Service was not ready before timeout"
    Write-Host "Check process manually: Get-Process -Id $($proc.Id)"
    exit 1
}
Write-Ok "Service is ready"

Write-Step "Verify GET /strategic_events.json"
$eventsResp = Invoke-WebRequest -Uri $strategicEventsUrl -UseBasicParsing -TimeoutSec 10
$eventsRaw = $eventsResp.Content
$events = @()
if (-not [string]::IsNullOrWhiteSpace($eventsRaw)) {
    $events = $eventsRaw | ConvertFrom-Json
}

if ($events -isnot [System.Array]) {
    $events = @($events)
}

Write-Ok "strategic_events count: $($events.Count)"
if ($events.Count -gt 0) {
    $sample = $events[0] | ConvertTo-Json -Depth 6 -Compress
    Write-Host "Sample: $sample" -ForegroundColor Gray
}
else {
    Write-WarnMsg "Event list is empty now"
}

Write-Step "Verify GET /api/crawl_status"
$statusResp = Invoke-WebRequest -Uri $crawlStatusUrl -UseBasicParsing -TimeoutSec 10
$statusObj = $statusResp.Content | ConvertFrom-Json
Write-Ok "crawl_status.success = $($statusObj.success)"
if ($null -ne $statusObj.state) {
    Write-Host "state.running = $($statusObj.state.running), task_id = $($statusObj.state.task_id)" -ForegroundColor Gray
}

if ($StartCrawl) {
    Write-Step "Optional: POST /api/start_crawl"
    $payload = '{}'
    $startResp = Invoke-WebRequest -Uri $startCrawlUrl -Method Post -ContentType "application/json" -Body $payload -UseBasicParsing -TimeoutSec 20
    $startObj = $startResp.Content | ConvertFrom-Json
    Write-Ok "start_crawl.success = $($startObj.success), message = $($startObj.message)"
}

Write-Step "Done"
Write-Ok "Frontend can request: $strategicEventsUrl"
Write-Host "Stop backend later: Stop-Process -Id $($proc.Id) -Force" -ForegroundColor DarkYellow
