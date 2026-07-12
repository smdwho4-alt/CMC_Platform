# =====================================================================
#  CSHSP Operation Toolkit v1.0 - backup-db_new.ps1
#  자동 백업: data / logs / config / reports → tools\backup\Backup_날짜.zip
#  30일(설정값) 지난 백업 자동 삭제. 기존 파일은 절대 수정하지 않는다.
# =====================================================================
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'settings_new.ps1')
Initialize-Toolkit

$exitCode = 0
try {
    Write-Banner 'CSHSP 자동 백업 (backup-db)'
    Write-ToolkitLog -File 'backup.log' -Level INFO -Message '=== backup-db 시작 ==='

    # [1/4] 백업 대상 수집 ------------------------------------------------
    $stamp   = Get-Date -Format 'yyyyMMdd_HHmmss'
    $zipPath = Join-Path $Settings.BackupFolder ('Backup_{0}.zip' -f $stamp)
    $staging = Join-Path $env:TEMP ('cshsp_backup_{0}' -f $stamp)
    New-Item -ItemType Directory -Path $staging -Force | Out-Null

    $included = @()
    $skipped  = @()
    $i = 0
    foreach ($target in $Settings.BackupTargets) {
        $i++
        Write-Progress -Activity '백업 대상 복사' -Status $target -PercentComplete ([int]($i / $Settings.BackupTargets.Count * 100))
        $src = Join-Path $ProjectRoot $target
        if (-not (Test-Path -LiteralPath $src)) { $skipped += $target; continue }
        $destName = ($target -replace '[\\/]', '_')
        $dest = Join-Path $staging $destName
        if (Test-Path -LiteralPath $src -PathType Container) {
            Copy-Item -LiteralPath $src -Destination $dest -Recurse -Force
        } else {
            Copy-Item -LiteralPath $src -Destination $dest -Force
        }
        $included += $target
    }
    Write-Progress -Activity '백업 대상 복사' -Completed
    if ($included.Count -eq 0) { throw '백업할 대상이 하나도 없습니다. settings_new.ps1 의 BackupTargets를 확인하세요.' }
    Write-Step '1/4' ('대상 수집 완료: {0}개 포함, {1}개 없음(생략)' -f $included.Count, $skipped.Count)

    # [2/4] ZIP 생성 ---------------------------------------------------------
    Write-Step '2/4' ('압축 생성 중... ' + (Split-Path $zipPath -Leaf))
    Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $zipPath -CompressionLevel Optimal -Force
    Remove-Item -LiteralPath $staging -Recurse -Force
    $zipInfo = Get-Item -LiteralPath $zipPath
    Write-Step 'OK ' ('백업 완료: {0} ({1:N2} MB)' -f $zipInfo.Name, ($zipInfo.Length / 1MB)) 'Green'
    Write-ToolkitLog -File 'backup.log' -Level OK -Message ('백업 생성: {0} ({1:N2} MB) 포함=[{2}] 생략=[{3}]' -f $zipInfo.Name, ($zipInfo.Length / 1MB), ($included -join ', '), ($skipped -join ', '))

    # [3/4] 보관기한 초과 백업 삭제 -------------------------------------------
    $cutoff = (Get-Date).AddDays(-1 * $Settings.BackupRetentionDays)
    $old = @(Get-ChildItem -LiteralPath $Settings.BackupFolder -Filter 'Backup_*.zip' | Where-Object { $_.LastWriteTime -lt $cutoff })
    foreach ($f in $old) {
        Remove-Item -LiteralPath $f.FullName -Force
        Write-ToolkitLog -File 'backup.log' -Level INFO -Message ('보관기한({0}일) 초과 백업 삭제: {1}' -f $Settings.BackupRetentionDays, $f.Name)
    }
    Write-Step '3/4' ('보관기한 {0}일 초과 백업 정리: {1}개 삭제' -f $Settings.BackupRetentionDays, $old.Count)

    # [4/4] 현황 요약 ------------------------------------------------------------
    $all = @(Get-ChildItem -LiteralPath $Settings.BackupFolder -Filter 'Backup_*.zip')
    $totalMB = ($all | Measure-Object Length -Sum).Sum / 1MB
    Write-Step '4/4' ('현재 보관 중인 백업: {0}개, 총 {1:N1} MB' -f $all.Count, $totalMB)
    Write-Host ''
    Write-Host ('  백업 폴더: ' + $Settings.BackupFolder) -ForegroundColor Gray
    Write-ToolkitLog -File 'backup.log' -Level OK -Message ('=== backup-db 완료 (보관 {0}개) ===' -f $all.Count)
}
catch {
    $exitCode = 1
    Write-Host ('  [오류] 백업 실패: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host '  → 디스크 공간과 폴더 권한을 확인한 뒤 다시 실행하세요.' -ForegroundColor Yellow
    Write-ToolkitLog -File 'backup.log' -Level ERROR -Message ('backup-db 실패: ' + $_.Exception.Message)
}
exit $exitCode
