# =====================================================================
#  CSHSP Operation Toolkit v1.0 - settings_new.ps1
#  천안의료원 건강검진센터 Pilot 운영도구 환경설정 + 공용 함수
#
#  ★ 모든 설정은 이 파일에서만 수정한다. 다른 파일은 수정하지 않는다.
#  호환: Windows PowerShell 5.1 / PowerShell 7+, Windows 11
#  관리자 권한 불필요. 상대경로 기반(이 파일 위치 기준).
# =====================================================================
Set-StrictMode -Version 2.0

# --- 경로 (상대경로: tools 폴더 기준) --------------------------------
$Script:ToolkitRoot = $PSScriptRoot
$Script:ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

# --- GAS Web App URL (민감정보 — 저장소에 하드코딩하지 않는다) --------
# 이 값은 이 파일에 저장하지 않는다. Python 쪽(src/services/sheets_write_service.py 등)과
# 동일한 환경변수명(CSHSP_GAS_WEBAPP_URL)을 우선 사용하고, 미설정 시에만 대화형
# 세션에서 1회 입력을 받는다. 콘솔/로그에 실제 값을 echo하지 않는다.
# 둘 다 없으면 빈 값으로 Fail-Closed 처리한다 — 이 값을 쓰는 점검(Test-Http)은
# 예외를 그대로 catch해 WARN으로 보고하며, 별도로 아래에서 "미설정"임을 명확히 경고한다.
$Script:GasWebAppUrl = $env:CSHSP_GAS_WEBAPP_URL
if ([string]::IsNullOrWhiteSpace($Script:GasWebAppUrl)) {
    if ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
        Write-Host ''
        Write-Host '  [설정 필요] CSHSP_GAS_WEBAPP_URL 환경변수가 없습니다.' -ForegroundColor Yellow
        $Script:_gasUrlInput = Read-Host '  Google Apps Script Web App URL 입력(비워두면 건너뜀)'
        if (-not [string]::IsNullOrWhiteSpace($Script:_gasUrlInput)) {
            $Script:GasWebAppUrl = $Script:_gasUrlInput.Trim()
        }
        Remove-Variable -Name _gasUrlInput -Scope Script -ErrorAction SilentlyContinue
    }
}
if ([string]::IsNullOrWhiteSpace($Script:GasWebAppUrl)) {
    Write-Host '  [경고] AppsScriptUrl 미설정 — Apps Script 관련 점검은 실패/건너뜀 처리됩니다(Fail-Closed).' -ForegroundColor Yellow
    Write-Host '         설정: $env:CSHSP_GAS_WEBAPP_URL = ''https://script.google.com/...'' 후 재실행' -ForegroundColor DarkYellow
    $Script:GasWebAppUrl = ''
}

$Script:Settings = @{
    # 포트
    ApiPort              = 8600
    FrontendPort         = 4000
    BindHost             = '127.0.0.1'

    # 실행 대상
    UvicornApp           = 'src.api.api_server:app'

    # URL
    HealthUrl            = 'http://127.0.0.1:8600/api/health'
    DashboardUrl         = 'http://127.0.0.1:4000/app/pages/admin_dashboard_new.html'
    # [v1.1.0-beta1] Pilot 예약페이지 v3(Rule 기반 선택검사) 전환 — PM 승인 2026-07-12
    # Rollback: 아래 값을 'http://127.0.0.1:4000/app/pages/reservation_new.html' 로 되돌리면 즉시 v1 복귀
    ReservationUrl       = 'http://127.0.0.1:4000/app/pages/reservation_v3_new.html'
    AppsScriptUrl        = $Script:GasWebAppUrl

    # 폴더 (Toolkit 하위)
    LogFolder            = (Join-Path $PSScriptRoot 'logs')
    ReportFolder         = (Join-Path $PSScriptRoot 'reports')
    BackupFolder         = (Join-Path $PSScriptRoot 'backup')

    # 백업 대상 (ProjectRoot 기준 상대경로, 없는 항목은 자동 생략)
    BackupTargets        = @('data', 'tools\logs', 'tools\reports', 'app\config_v2_new.js', 'app\config.js', 'requirements.txt', '.env')

    # 정책
    BackupRetentionDays  = 30      # 보관일수 초과 백업 자동 삭제
    BackupFreshDays      = 3       # 최근 N일 내 백업 있으면 PASS
    HealthTimeoutSec     = 5       # HTTP 점검 타임아웃(초)
    ExternalTimeoutSec   = 12      # 외부(Apps Script) 타임아웃(초)
    StartupWaitSec       = 40      # API 기동 대기 최대(초)
}

# --- TLS (Apps Script HTTPS 호출용, PS5.1 대비) -----------------------
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch { }

# =====================================================================
#  공용 함수
# =====================================================================

function Initialize-Toolkit {
    # logs / reports / backup 폴더 자동 생성
    foreach ($f in @($Settings.LogFolder, $Settings.ReportFolder, $Settings.BackupFolder)) {
        if (-not (Test-Path -LiteralPath $f)) {
            New-Item -ItemType Directory -Path $f -Force | Out-Null
        }
    }
}

function Write-ToolkitLog {
    # 사용: Write-ToolkitLog -File 'pilot.log' -Level INFO -Message '...'
    param(
        [Parameter(Mandatory)][string]$File,
        [ValidateSet('INFO','WARN','ERROR','OK')][string]$Level = 'INFO',
        [Parameter(Mandatory)][string]$Message
    )
    try {
        Initialize-Toolkit
        $line = '[{0}] [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
        $path = Join-Path $Settings.LogFolder $File
        [System.IO.File]::AppendAllText($path, $line + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($true))
        if ($Level -eq 'ERROR' -and $File -ne 'error.log') {
            $epath = Join-Path $Settings.LogFolder 'error.log'
            [System.IO.File]::AppendAllText($epath, $line + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($true))
        }
    } catch { }  # 로그 실패가 본 작업을 막지 않도록
}

function Write-Step {
    # 컬러 콘솔 출력: [3/8] 메시지
    param([string]$Tag, [string]$Message, [ConsoleColor]$Color = 'Cyan')
    Write-Host ('  [{0}] ' -f $Tag) -ForegroundColor $Color -NoNewline
    Write-Host $Message
}

function Write-Banner {
    param([string]$Title)
    Write-Host ''
    Write-Host ('=' * 58) -ForegroundColor DarkCyan
    Write-Host ('   {0}' -f $Title) -ForegroundColor White
    Write-Host ('   CSHSP Operation Toolkit v1.0  |  ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) -ForegroundColor DarkGray
    Write-Host ('=' * 58) -ForegroundColor DarkCyan
}

function Get-PortOwnerPids {
    # 해당 포트를 LISTEN 중인 프로세스 PID 목록 (없으면 빈 배열)
    # 주의: 배열 풀림(unroll) 방지를 위해 단항 콤마로 배열째 반환한다.
    param([Parameter(Mandatory)][int]$Port)
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($null -eq $conns) { return ,@() }
        return ,@($conns | Select-Object -ExpandProperty OwningProcess -Unique)
    } catch { return ,@() }
}

function Test-Http {
    # URL 점검. 반환: @{ Ok=bool; Status=int|0; Detail=string; Body=string }
    param(
        [Parameter(Mandatory)][string]$Url,
        [int]$TimeoutSec = 5
    )
    try {
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec -MaximumRedirection 5 -ErrorAction Stop
        $body = ''
        try { $body = [string]$resp.Content } catch { }
        return @{ Ok = $true; Status = [int]$resp.StatusCode; Detail = ('HTTP {0}' -f [int]$resp.StatusCode); Body = $body }
    } catch {
        return @{ Ok = $false; Status = 0; Detail = $_.Exception.Message; Body = '' }
    }
}

function Get-PythonCommand {
    # python 실행파일 확인 (없으면 $null)
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { return $null }
    return $cmd.Source
}
