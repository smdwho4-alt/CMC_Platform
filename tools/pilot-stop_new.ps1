# =====================================================================
#  CSHSP Operation Toolkit v1.0 - pilot-stop_new.ps1
#  Pilot 자동 종료 (pilot-stop_new.bat 더블클릭으로 실행됨)
#  Port 8600(API), 4000(Frontend)을 점유한 python 프로세스만 정리한다.
# =====================================================================
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'settings_new.ps1')
Initialize-Toolkit

$exitCode = 0
try {
    Write-Banner 'CSHSP Pilot 종료 (pilot-stop)'
    Write-ToolkitLog -File 'pilot.log' -Level INFO -Message '=== pilot-stop 시작 ==='

    $targets = @(
        @{ Name = 'API 서버';      Port = $Settings.ApiPort },
        @{ Name = 'Frontend 서버'; Port = $Settings.FrontendPort }
    )
    $stopped = 0

    foreach ($t in $targets) {
        $pids = Get-PortOwnerPids -Port $t.Port
        if ($pids.Count -eq 0) {
            Write-Step '--' ('{0} (Port {1}): 실행 중이 아님' -f $t.Name, $t.Port) 'DarkGray'
            continue
        }
        foreach ($procId in $pids) {
            try {
                $proc = Get-Process -Id $procId -ErrorAction Stop
                # 안전장치: 예상 프로세스(python/uvicorn 계열)만 종료
                if ($proc.ProcessName -notmatch '^(python|pythonw|uvicorn)') {
                    Write-Step '!!' ('{0} (Port {1}): 예상 밖 프로세스 [{2}] PID {3} — 종료하지 않음. 직접 확인 필요.' -f $t.Name, $t.Port, $proc.ProcessName, $procId) 'Yellow'
                    Write-ToolkitLog -File 'pilot.log' -Level WARN -Message ('Port {0} 점유 프로세스 {1}(PID {2})는 python이 아니어서 건너뜀' -f $t.Port, $proc.ProcessName, $procId)
                    continue
                }
                # 정상 종료 시도 후 확인 (콘솔 앱이라 CloseMainWindow 불가 → Stop-Process 사용)
                Stop-Process -Id $procId -ErrorAction Stop
                Start-Sleep -Milliseconds 500
                if (Get-Process -Id $procId -ErrorAction SilentlyContinue) {
                    Stop-Process -Id $procId -Force -ErrorAction Stop   # 마지막 수단
                }
                $stopped++
                Write-Step 'OK' ('{0} 종료 완료 (PID {1})' -f $t.Name, $procId) 'Green'
                Write-ToolkitLog -File 'pilot.log' -Level OK -Message ('{0} 종료 PID={1}' -f $t.Name, $procId)
            } catch {
                Write-Step '!!' ('{0} 종료 실패 (PID {1}): {2}' -f $t.Name, $procId, $_.Exception.Message) 'Red'
                Write-ToolkitLog -File 'pilot.log' -Level ERROR -Message ('{0} 종료 실패 PID={1}: {2}' -f $t.Name, $procId, $_.Exception.Message)
                $exitCode = 1
            }
        }
    }

    Write-Host ''
    if ($stopped -gt 0) {
        Write-Host ('  Pilot 종료 완료 (프로세스 {0}개 정리)' -f $stopped) -ForegroundColor Green
    } else {
        Write-Host '  종료할 Pilot 프로세스가 없습니다. (이미 꺼져 있음)' -ForegroundColor Yellow
    }
    Write-ToolkitLog -File 'pilot.log' -Level OK -Message ('=== pilot-stop 완료 (정리 {0}개) ===' -f $stopped)
}
catch {
    $exitCode = 1
    Write-Host ('  [오류] ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('  로그 확인: ' + (Join-Path $Settings.LogFolder 'error.log')) -ForegroundColor Yellow
    Write-ToolkitLog -File 'pilot.log' -Level ERROR -Message ('pilot-stop 실패: ' + $_.Exception.Message)
}
exit $exitCode
