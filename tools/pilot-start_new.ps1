# =====================================================================
#  CSHSP Operation Toolkit v1.0 - pilot-start_new.ps1
#  Pilot 자동 시작 (pilot-start_new.bat 더블클릭으로 실행됨)
#  설정 변경은 settings_new.ps1 에서만 한다.
# =====================================================================
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'settings_new.ps1')
Initialize-Toolkit

$exitCode = 0
try {
    Write-Banner 'CSHSP Pilot 시작 (pilot-start)'
    Write-ToolkitLog -File 'pilot.log' -Level INFO -Message '=== pilot-start 시작 ==='

    # [1/8] 프로젝트 루트 확인 -----------------------------------------
    Write-Step '1/8' ('프로젝트 루트 확인: ' + $ProjectRoot)
    $apiFile = Join-Path $ProjectRoot 'src\api\api_server.py'
    if (-not (Test-Path -LiteralPath $apiFile)) {
        throw ('프로젝트 파일을 찾을 수 없습니다: ' + $apiFile + ' — tools 폴더가 CMC_Platform_new 안에 있는지 확인하세요.')
    }
    Write-ToolkitLog -File 'pilot.log' -Level INFO -Message ('ProjectRoot=' + $ProjectRoot)

    # [2/8] Python 확인 -------------------------------------------------
    $py = Get-PythonCommand
    if ($null -eq $py) {
        throw 'Python을 찾을 수 없습니다. https://www.python.org 에서 설치 후 다시 실행하세요. (설치 시 "Add python to PATH" 체크)'
    }
    $pyVer = (& $py --version) 2>&1 | Out-String
    Write-Step '2/8' ('Python 확인: ' + $pyVer.Trim())
    Write-ToolkitLog -File 'pilot.log' -Level INFO -Message ('Python=' + $pyVer.Trim())

    # [3/8] API 서버 (Port 8600) ----------------------------------------
    $apiPids = Get-PortOwnerPids -Port $Settings.ApiPort
    if ($apiPids.Count -gt 0) {
        Write-Step '3/8' ('API 서버가 이미 실행 중입니다 (Port {0}, PID {1}) — 중복 실행하지 않습니다.' -f $Settings.ApiPort, ($apiPids -join ',')) 'Yellow'
        Write-ToolkitLog -File 'pilot.log' -Level WARN -Message ('API 이미 실행 중 PID=' + ($apiPids -join ','))
    } else {
        Write-Step '3/8' ('API 서버 시작... (Port {0})' -f $Settings.ApiPort)
        $apiOut = Join-Path $Settings.LogFolder 'api_server.out.log'
        $apiErr = Join-Path $Settings.LogFolder 'api_server.err.log'
        $apiArgs = @('-m','uvicorn', $Settings.UvicornApp, '--host', $Settings.BindHost, '--port', $Settings.ApiPort)
        $p = Start-Process -FilePath $py -ArgumentList $apiArgs -WorkingDirectory $ProjectRoot `
             -WindowStyle Hidden -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr -PassThru
        Write-ToolkitLog -File 'pilot.log' -Level INFO -Message ('API 시작 PID=' + $p.Id)
    }

    # [4/8] Frontend 서버 (Port 4000) -----------------------------------
    $fePids = Get-PortOwnerPids -Port $Settings.FrontendPort
    if ($fePids.Count -gt 0) {
        Write-Step '4/8' ('Frontend가 이미 실행 중입니다 (Port {0}, PID {1}) — 중복 실행하지 않습니다.' -f $Settings.FrontendPort, ($fePids -join ',')) 'Yellow'
        Write-ToolkitLog -File 'pilot.log' -Level WARN -Message ('Frontend 이미 실행 중 PID=' + ($fePids -join ','))
    } else {
        Write-Step '4/8' ('Frontend 서버 시작... (Port {0})' -f $Settings.FrontendPort)
        $feOut = Join-Path $Settings.LogFolder 'frontend.out.log'
        $feErr = Join-Path $Settings.LogFolder 'frontend.err.log'
        $feArgs = @('-m','http.server', $Settings.FrontendPort, '--bind', $Settings.BindHost)
        $p = Start-Process -FilePath $py -ArgumentList $feArgs -WorkingDirectory $ProjectRoot `
             -WindowStyle Hidden -RedirectStandardOutput $feOut -RedirectStandardError $feErr -PassThru
        Write-ToolkitLog -File 'pilot.log' -Level INFO -Message ('Frontend 시작 PID=' + $p.Id)
    }

    # [5/8] API Health 대기 ---------------------------------------------
    Write-Step '5/8' ('API Health 확인 중... (' + $Settings.HealthUrl + ')')
    $healthy = $false
    $deadline = (Get-Date).AddSeconds($Settings.StartupWaitSec)
    $attempt = 0
    while ((Get-Date) -lt $deadline) {
        $attempt++
        $pct = [Math]::Min(99, [int](($attempt * 2 / $Settings.StartupWaitSec) * 100))
        Write-Progress -Activity 'API 기동 대기' -Status ('시도 ' + $attempt) -PercentComplete $pct
        $r = Test-Http -Url $Settings.HealthUrl -TimeoutSec $Settings.HealthTimeoutSec
        if ($r.Ok) { $healthy = $true; break }
        Start-Sleep -Seconds 2
    }
    Write-Progress -Activity 'API 기동 대기' -Completed
    if (-not $healthy) {
        $errLog = Join-Path $Settings.LogFolder 'api_server.err.log'
        throw ('API Health 응답 없음 ({0}초 대기). 오류 로그를 확인하세요: {1}' -f $Settings.StartupWaitSec, $errLog)
    }
    Write-Step 'OK ' 'API Health 정상' 'Green'
    Write-ToolkitLog -File 'pilot.log' -Level OK -Message 'API Health 정상'

    # [6/8] Frontend 응답 확인 -------------------------------------------
    $r = Test-Http -Url $Settings.DashboardUrl -TimeoutSec $Settings.HealthTimeoutSec
    if ($r.Ok) {
        Write-Step '6/8' 'Frontend 응답 정상' 'Green'
        Write-ToolkitLog -File 'pilot.log' -Level OK -Message 'Frontend 응답 정상'
    } else {
        Write-Step '6/8' ('Frontend 응답 확인 실패: ' + $r.Detail + ' (페이지가 늦게 뜰 수 있습니다)') 'Yellow'
        Write-ToolkitLog -File 'pilot.log' -Level WARN -Message ('Frontend 응답 실패: ' + $r.Detail)
    }

    # [7/8] 브라우저 열기 -------------------------------------------------
    Write-Step '7/8' 'Dashboard / 예약 페이지 열기'
    Start-Process $Settings.DashboardUrl
    Start-Sleep -Milliseconds 700
    Start-Process $Settings.ReservationUrl
    Write-ToolkitLog -File 'pilot.log' -Level INFO -Message '브라우저 오픈 완료'

    # [8/8] 완료 -----------------------------------------------------------
    Write-Host ''
    Write-Host '  ==========================================' -ForegroundColor Green
    Write-Host '   Pilot 시작 완료! 브라우저를 확인하세요.' -ForegroundColor Green
    Write-Host '  ==========================================' -ForegroundColor Green
    Write-Host ('   Dashboard : ' + $Settings.DashboardUrl) -ForegroundColor Gray
    Write-Host ('   예약 페이지: ' + $Settings.ReservationUrl) -ForegroundColor Gray
    Write-Host ('   종료 방법  : tools\pilot-stop_new.bat 더블클릭') -ForegroundColor Gray
    Write-ToolkitLog -File 'pilot.log' -Level OK -Message '=== pilot-start 완료 ==='
}
catch {
    $exitCode = 1
    $msg = $_.Exception.Message
    Write-Host ''
    Write-Host ('  [오류] ' + $msg) -ForegroundColor Red
    Write-Host ''
    Write-Host '  ── 복구 방법 ─────────────────────────────' -ForegroundColor Yellow
    Write-Host '   1) tools\pilot-stop_new.bat 실행 후 다시 시작해 보세요.'
    Write-Host '   2) tools\pilot-check_new.ps1 로 상태를 점검하세요.'
    Write-Host ('   3) 로그 확인: ' + (Join-Path $Settings.LogFolder 'error.log'))
    Write-Host '   4) 해결되지 않으면 README_OPERATION_new.md 의 FAQ를 참고하세요.'
    Write-ToolkitLog -File 'pilot.log' -Level ERROR -Message ('pilot-start 실패: ' + $msg)
}
exit $exitCode
