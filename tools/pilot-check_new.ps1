# =====================================================================
#  CSHSP Operation Toolkit v1.0 - pilot-check_new.ps1
#  Pilot 자동 점검: Git / Python / 포트 / API / 페이지 / Sheets / 백업 / 로그
#  사용:
#    .\pilot-check_new.ps1              # 콘솔 점검 (색상 출력)
#    .\pilot-check_new.ps1 -PassThru    # 결과 객체 반환 (보고서 생성용)
# =====================================================================
param(
    [switch]$PassThru,
    [switch]$Quiet
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'settings_new.ps1')
Initialize-Toolkit

$results = New-Object System.Collections.ArrayList

function Add-Check {
    param([string]$Name, [ValidateSet('PASS','FAIL','WARN')][string]$Status, [string]$Detail)
    [void]$results.Add([pscustomobject]@{ Name = $Name; Status = $Status; Detail = $Detail })
    Write-ToolkitLog -File 'health.log' -Level $(if ($Status -eq 'PASS') { 'OK' } elseif ($Status -eq 'WARN') { 'WARN' } else { 'ERROR' }) -Message ('{0}: {1} - {2}' -f $Name, $Status, $Detail)
}

if (-not $Quiet) { Write-Banner 'CSHSP Pilot 자동 점검 (pilot-check)' }
Write-ToolkitLog -File 'health.log' -Level INFO -Message '=== pilot-check 시작 ==='

# 1. Git Status ---------------------------------------------------------
try {
    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($null -eq $git) {
        Add-Check 'Git Status' 'WARN' 'git 명령을 찾을 수 없음 (점검 생략)'
    } elseif (-not (Test-Path (Join-Path $ProjectRoot '.git'))) {
        Add-Check 'Git Status' 'WARN' 'git 저장소가 아님'
    } else {
        $branch = (& git -C $ProjectRoot rev-parse --abbrev-ref HEAD 2>&1 | Out-String).Trim()
        $dirty  = @(& git -C $ProjectRoot status --porcelain 2>&1)
        if ($dirty.Count -eq 0) {
            Add-Check 'Git Status' 'PASS' ('브랜치 {0}, 변경사항 없음' -f $branch)
        } else {
            Add-Check 'Git Status' 'WARN' ('브랜치 {0}, 커밋되지 않은 변경 {1}건' -f $branch, $dirty.Count)
        }
    }
} catch { Add-Check 'Git Status' 'WARN' $_.Exception.Message }

# 2. Python -------------------------------------------------------------
try {
    $py = Get-PythonCommand
    if ($null -eq $py) {
        Add-Check 'Python' 'FAIL' 'python을 찾을 수 없음 (PATH 확인 필요)'
    } else {
        $v = ((& $py --version) 2>&1 | Out-String).Trim()
        Add-Check 'Python' 'PASS' $v
    }
} catch { Add-Check 'Python' 'FAIL' $_.Exception.Message }

# 3~4. 포트 -------------------------------------------------------------
foreach ($pc in @(@{ N = ('Port {0} (API)' -f $Settings.ApiPort); P = $Settings.ApiPort },
                  @{ N = ('Port {0} (Frontend)' -f $Settings.FrontendPort); P = $Settings.FrontendPort })) {
    $pids = Get-PortOwnerPids -Port $pc.P
    if ($pids.Count -gt 0) {
        Add-Check $pc.N 'PASS' ('LISTEN 중 (PID {0})' -f ($pids -join ','))
    } else {
        Add-Check $pc.N 'FAIL' '서버가 실행 중이 아님 - pilot-start_new.bat 실행 필요'
    }
}

# 5. API Health ----------------------------------------------------------
$r = Test-Http -Url $Settings.HealthUrl -TimeoutSec $Settings.HealthTimeoutSec
if ($r.Ok) { Add-Check 'API Health' 'PASS' ($r.Detail + ' ' + ($r.Body -replace '\s+', ' ').Substring(0, [Math]::Min(80, $r.Body.Length))) }
else       { Add-Check 'API Health' 'FAIL' $r.Detail }

# 6. Dashboard URL ---------------------------------------------------------
$r = Test-Http -Url $Settings.DashboardUrl -TimeoutSec $Settings.HealthTimeoutSec
if ($r.Ok) { Add-Check 'Dashboard 페이지' 'PASS' $r.Detail } else { Add-Check 'Dashboard 페이지' 'FAIL' $r.Detail }

# 7. Reservation URL -------------------------------------------------------
$r = Test-Http -Url $Settings.ReservationUrl -TimeoutSec $Settings.HealthTimeoutSec
if ($r.Ok) { Add-Check '예약 페이지' 'PASS' $r.Detail } else { Add-Check '예약 페이지' 'FAIL' $r.Detail }

# 8. Google Apps Script URL (외부망 - 실패 시 WARN) --------------------------
$r = Test-Http -Url $Settings.AppsScriptUrl -TimeoutSec $Settings.ExternalTimeoutSec
if ($r.Ok) { Add-Check 'Apps Script URL' 'PASS' $r.Detail }
else       { Add-Check 'Apps Script URL' 'WARN' ('응답 없음(외부망/방화벽 확인): ' + $r.Detail) }

# 9. Google Sheets 연결 (action=ping) ----------------------------------------
$r = Test-Http -Url ($Settings.AppsScriptUrl + '?action=ping') -TimeoutSec $Settings.ExternalTimeoutSec
if ($r.Ok -and $r.Body -match '(ok|pong|success|true)') {
    Add-Check 'Google Sheets 연결' 'PASS' 'ping 응답 정상'
} elseif ($r.Ok) {
    Add-Check 'Google Sheets 연결' 'WARN' ('응답은 있으나 ping 확인 불가: ' + ($r.Body -replace '\s+', ' ').Substring(0, [Math]::Min(60, $r.Body.Length)))
} else {
    Add-Check 'Google Sheets 연결' 'WARN' ('응답 없음(외부망 확인): ' + $r.Detail)
}

# 10. Backup 확인 --------------------------------------------------------------
try {
    $zips = @(Get-ChildItem -LiteralPath $Settings.BackupFolder -Filter 'Backup_*.zip' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
    if ($zips.Count -eq 0) {
        Add-Check 'Backup' 'WARN' '백업 파일 없음 - backup-db_new.ps1 실행 필요'
    } else {
        $latest = $zips[0]
        $age = ((Get-Date) - $latest.LastWriteTime).TotalDays
        if ($age -le $Settings.BackupFreshDays) {
            Add-Check 'Backup' 'PASS' ('최근 백업: {0} ({1:N1}일 전, {2:N1} MB)' -f $latest.Name, $age, ($latest.Length / 1MB))
        } else {
            Add-Check 'Backup' 'WARN' ('마지막 백업이 {0:N1}일 전 ({1}) - 새 백업 권장' -f $age, $latest.Name)
        }
    }
} catch { Add-Check 'Backup' 'WARN' $_.Exception.Message }

# 11. Logs 확인 -----------------------------------------------------------------
try {
    $probe = Join-Path $Settings.LogFolder ('.write_test_{0}.tmp' -f $PID)
    Set-Content -LiteralPath $probe -Value 'test' -Encoding Ascii
    Remove-Item -LiteralPath $probe -Force
    $logCount = @(Get-ChildItem -LiteralPath $Settings.LogFolder -Filter '*.log' -ErrorAction SilentlyContinue).Count
    Add-Check 'Logs 폴더' 'PASS' ('쓰기 가능, 로그 파일 {0}개' -f $logCount)
} catch { Add-Check 'Logs 폴더' 'FAIL' ('로그 폴더 쓰기 불가: ' + $_.Exception.Message) }

# --- 종합 -----------------------------------------------------------------------
$failCnt = @($results | Where-Object { $_.Status -eq 'FAIL' }).Count
$warnCnt = @($results | Where-Object { $_.Status -eq 'WARN' }).Count
$overall = if ($failCnt -gt 0) { 'FAIL' } elseif ($warnCnt -gt 0) { 'WARN' } else { 'PASS' }

if (-not $Quiet) {
    Write-Host ''
    foreach ($item in $results) {
        $color = switch ($item.Status) { 'PASS' { 'Green' } 'WARN' { 'Yellow' } default { 'Red' } }
        Write-Host ('  [{0}] ' -f $item.Status.PadRight(4)) -ForegroundColor $color -NoNewline
        Write-Host ($item.Name.PadRight(24)) -NoNewline
        Write-Host (' ' + $item.Detail) -ForegroundColor DarkGray
    }
    Write-Host ''
    Write-Host ('  ' + ('-' * 56)) -ForegroundColor DarkCyan
    $ocolor = switch ($overall) { 'PASS' { 'Green' } 'WARN' { 'Yellow' } default { 'Red' } }
    Write-Host ('  종합 결과: {0}  (PASS {1} / WARN {2} / FAIL {3})' -f $overall, (@($results | Where-Object { $_.Status -eq 'PASS' }).Count), $warnCnt, $failCnt) -ForegroundColor $ocolor
    if ($overall -eq 'FAIL') {
        Write-Host '  → 조치: pilot-start_new.bat 실행 후 재점검하거나 logs\error.log 확인' -ForegroundColor Yellow
    }
    Write-Host ''
}
Write-ToolkitLog -File 'health.log' -Level INFO -Message ('=== pilot-check 완료: {0} (PASS {1}/WARN {2}/FAIL {3}) ===' -f $overall, (@($results | Where-Object { $_.Status -eq 'PASS' }).Count), $warnCnt, $failCnt)

if ($PassThru) {
    return [pscustomobject]@{
        CheckedAt = Get-Date
        Overall   = $overall
        Items     = @($results)
    }
}
if ($overall -eq 'FAIL') { exit 1 } else { exit 0 }
