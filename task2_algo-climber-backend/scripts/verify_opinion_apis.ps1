param(
    [string]$BaseUrl = "http://127.0.0.1:12312"
)

$ErrorActionPreference = "Stop"

function Invoke-Api {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Url,
        [object]$Body
    )

    try {
        if ($null -ne $Body) {
            $json = $Body | ConvertTo-Json -Depth 10 -Compress
            $jsonBytes = [System.Text.Encoding]::UTF8.GetBytes($json)
            $resp = Invoke-RestMethod -Method $Method -Uri $Url -ContentType "application/json; charset=utf-8" -Body $jsonBytes
        }
        else {
            $resp = Invoke-RestMethod -Method $Method -Uri $Url
        }

        return [PSCustomObject]@{
            ok = $true
            status = 200
            data = $resp
            error = ""
        }
    }
    catch {
        $status = 0
        $msg = $_.Exception.Message
        if ($_.Exception.PSObject.Properties.Name -contains "Response" -and $null -ne $_.Exception.Response) {
            try {
                $status = [int]$_.Exception.Response.StatusCode
            }
            catch {
                $status = 0
            }
        }

        return [PSCustomObject]@{
            ok = $false
            status = $status
            data = $null
            error = $msg
        }
    }
}

function New-CaseResult {
    param(
        [string]$Id,
        [string]$Api,
        [string]$Scenario,
        [string]$Expected,
        [string]$Actual,
        [bool]$Pass
    )

    [PSCustomObject]@{
        Id = $Id
        Api = $Api
        Scenario = $Scenario
        Expected = $Expected
        Actual = $Actual
        Result = $(if ($Pass) { "PASS" } else { "FAIL" })
    }
}

$results = @()

# T1: GET /api/opinion/tasks
$r1 = Invoke-Api -Method "GET" -Url "$BaseUrl/api/opinion/tasks?limit=50"
$r1Pass = $r1.status -eq 200 -and $null -ne $r1.data -and $r1.data.success -eq $true
$existingTaskId = $null
if ($r1Pass -and $r1.data.tasks.Count -gt 0) {
    $existingTaskId = $r1.data.tasks[-1].id
}
$results += New-CaseResult -Id "T1" -Api "GET /api/opinion/tasks" -Scenario "success" -Expected "200 + success=true" -Actual "status=$($r1.status), total=$($r1.data.total)" -Pass $r1Pass

# T2: POST /api/opinion/tasks
$createBody = @{
    task_name = "API验证任务"
    keywords = @("舆情", "战争")
    subjects = @("中国", "日本", "台湾")
    depth = 200
    intensity = 75
    output_dir = "output"
}
$r2 = Invoke-Api -Method "POST" -Url "$BaseUrl/api/opinion/tasks" -Body $createBody
$createdTaskId = $null
if ($r2.status -eq 200 -and $null -ne $r2.data) {
    $createdTaskId = $r2.data.task_id
}
$r2Pass = $r2.status -eq 200 -and $null -ne $r2.data -and $r2.data.success -eq $true
$results += New-CaseResult -Id "T2" -Api "POST /api/opinion/tasks" -Scenario "create task" -Expected "200 + returns task_id" -Actual "status=$($r2.status), task_id=$createdTaskId" -Pass $r2Pass

$verifyTaskId = ""
if (-not [string]::IsNullOrWhiteSpace("$createdTaskId")) {
    $verifyTaskId = "$createdTaskId"
}
elseif (-not [string]::IsNullOrWhiteSpace("$existingTaskId")) {
    $verifyTaskId = "$existingTaskId"
}

if ([string]::IsNullOrWhiteSpace($verifyTaskId)) {
    $results += New-CaseResult -Id "T3" -Api "POST /api/opinion/events" -Scenario "query by task_id" -Expected "200 + events array" -Actual "no available task_id" -Pass $false
    $results += New-CaseResult -Id "T4" -Api "POST /api/opinion/raw" -Scenario "query by task_id" -Expected "200 + raw_items array" -Actual "no available task_id" -Pass $false
    $results += New-CaseResult -Id "T5" -Api "POST /api/opinion/raw" -Scenario "filter check" -Expected "200 + filter applied" -Actual "no available task_id" -Pass $false
    $results += New-CaseResult -Id "T6" -Api "POST /api/opinion/raw" -Scenario "task not found" -Expected "404" -Actual "not executed" -Pass $false
    $results += New-CaseResult -Id "T7" -Api "POST /api/opinion/raw" -Scenario "limit out of range" -Expected "422" -Actual "not executed" -Pass $false
}
else {
    # T3: POST /api/opinion/events
    try {
        $eventsBody = @{ task_id = $verifyTaskId; limit = 20 }
        $r3 = Invoke-Api -Method "POST" -Url "$BaseUrl/api/opinion/events" -Body $eventsBody
        $r3Pass = $r3.status -eq 200 -and $null -ne $r3.data -and $r3.data.success -eq $true -and $null -ne $r3.data.events
        $results += New-CaseResult -Id "T3" -Api "POST /api/opinion/events" -Scenario "query by task_id" -Expected "200 + events array" -Actual "status=$($r3.status), total=$($r3.data.total), task_id=$verifyTaskId" -Pass $r3Pass
    }
    catch {
        $results += New-CaseResult -Id "T3" -Api "POST /api/opinion/events" -Scenario "query by task_id" -Expected "200 + events array" -Actual "unexpected error: $($_.Exception.Message)" -Pass $false
    }

    # T4: POST /api/opinion/raw
    try {
        $rawBody = @{ task_id = $verifyTaskId; limit = 20 }
        $r4 = Invoke-Api -Method "POST" -Url "$BaseUrl/api/opinion/raw" -Body $rawBody
        $r4Pass = $r4.status -eq 200 -and $null -ne $r4.data -and $r4.data.success -eq $true -and $null -ne $r4.data.raw_items
        $results += New-CaseResult -Id "T4" -Api "POST /api/opinion/raw" -Scenario "query by task_id" -Expected "200 + raw_items array" -Actual "status=$($r4.status), total=$($r4.data.total), task_id=$verifyTaskId" -Pass $r4Pass
    }
    catch {
        $results += New-CaseResult -Id "T4" -Api "POST /api/opinion/raw" -Scenario "query by task_id" -Expected "200 + raw_items array" -Actual "unexpected error: $($_.Exception.Message)" -Pass $false
    }

    # T5: POST /api/opinion/raw (filter)
    try {
        $rawFilterBody = @{
            task_id = $verifyTaskId
            title = "war"
            keyword = "public opinion"
            source = "Sina"
            limit = 50
        }
        $r5 = Invoke-Api -Method "POST" -Url "$BaseUrl/api/opinion/raw" -Body $rawFilterBody
        $r5Pass = $r5.status -eq 200 -and $null -ne $r5.data -and $r5.data.success -eq $true
        $results += New-CaseResult -Id "T5" -Api "POST /api/opinion/raw" -Scenario "filter check(title/keyword/source)" -Expected "200 + filter applied" -Actual "status=$($r5.status), total=$($r5.data.total)" -Pass $r5Pass
    }
    catch {
        $results += New-CaseResult -Id "T5" -Api "POST /api/opinion/raw" -Scenario "filter check(title/keyword/source)" -Expected "200 + filter applied" -Actual "unexpected error: $($_.Exception.Message)" -Pass $false
    }

    # T6: POST /api/opinion/raw (404)
    try {
        $r6 = Invoke-Api -Method "POST" -Url "$BaseUrl/api/opinion/raw" -Body @{ task_id = "t-not-exists"; limit = 20 }
        $r6Pass = $r6.status -eq 404
        $results += New-CaseResult -Id "T6" -Api "POST /api/opinion/raw" -Scenario "task not found" -Expected "404" -Actual "status=$($r6.status), error=$($r6.error)" -Pass $r6Pass
    }
    catch {
        $results += New-CaseResult -Id "T6" -Api "POST /api/opinion/raw" -Scenario "task not found" -Expected "404" -Actual "unexpected error: $($_.Exception.Message)" -Pass $false
    }

    # T7: POST /api/opinion/raw (422)
    try {
        $r7 = Invoke-Api -Method "POST" -Url "$BaseUrl/api/opinion/raw" -Body @{ task_id = $verifyTaskId; limit = 5001 }
        $r7Pass = $r7.status -eq 422
        $results += New-CaseResult -Id "T7" -Api "POST /api/opinion/raw" -Scenario "limit out of range(limit=5001)" -Expected "422" -Actual "status=$($r7.status), error=$($r7.error)" -Pass $r7Pass
    }
    catch {
        $results += New-CaseResult -Id "T7" -Api "POST /api/opinion/raw" -Scenario "limit out of range(limit=5001)" -Expected "422" -Actual "unexpected error: $($_.Exception.Message)" -Pass $false
    }
}

$reportDir = Join-Path $PSScriptRoot "..\docs\verification_reports"
$reportDir = [System.IO.Path]::GetFullPath($reportDir)
if (-not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportPath = Join-Path $reportDir "opinion_api_verify_$timestamp.md"

$passCount = ($results | Where-Object { $_.Result -eq "PASS" }).Count
$failCount = ($results | Where-Object { $_.Result -eq "FAIL" }).Count

$lines = @()
$lines += "# Opinion API Verification Report"
$lines += ""
$lines += "- GeneratedAt: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$lines += "- BaseUrl: $BaseUrl"
$lines += "- VerifyTaskId: $verifyTaskId"
$lines += "- Passed: $passCount"
$lines += "- Failed: $failCount"
$lines += ""
$lines += "| CaseID | API | Scenario | Expected | Actual | Result |"
$lines += "|---|---|---|---|---|---|"
foreach ($item in $results) {
    $actual = ($item.Actual -replace "\|", "\\|")
    $lines += "| $($item.Id) | $($item.Api) | $($item.Scenario) | $($item.Expected) | $actual | $($item.Result) |"
}

Set-Content -Path $reportPath -Value $lines -Encoding UTF8

Write-Host "Verification finished. Report generated: $reportPath"
Write-Host "Passed: $passCount, Failed: $failCount"
