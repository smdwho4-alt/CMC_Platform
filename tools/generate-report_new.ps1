# =====================================================================
#  CSHSP Operation Toolkit v1.0 - generate-report_new.ps1
#  일일 점검 HTML 보고서 생성: tools\reports\Daily_Check_YYYYMMDD.html
#  pilot-check_new.ps1 를 실행해 결과를 수집한 뒤 인쇄 가능한(A4) 보고서를 만든다.
#  사용:  .\generate-report_new.ps1          # 보고서 생성
#         .\generate-report_new.ps1 -Open    # 생성 후 브라우저로 열기
# =====================================================================
param([switch]$Open)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'settings_new.ps1')
Initialize-Toolkit

$exitCode = 0
try {
    Write-Banner 'CSHSP 일일 점검 보고서 (generate-report)'
    Write-ToolkitLog -File 'pilot.log' -Level INFO -Message '=== generate-report 시작 ==='

    # [1/3] 점검 실행 -----------------------------------------------------
    Write-Step '1/3' '자동 점검 실행 중...'
    $check = & (Join-Path $PSScriptRoot 'pilot-check_new.ps1') -PassThru -Quiet

    # [2/3] HTML 생성 -------------------------------------------------------
    Write-Step '2/3' 'HTML 보고서 생성 중...'
    $dateStr = Get-Date -Format 'yyyyMMdd'
    $outPath = Join-Path $Settings.ReportFolder ('Daily_Check_{0}.html' -f $dateStr)
    if (Test-Path -LiteralPath $outPath) {
        # 기존 파일 덮어쓰기 금지 → 시각을 붙여 새 파일로 저장
        $outPath = Join-Path $Settings.ReportFolder ('Daily_Check_{0}_{1}.html' -f $dateStr, (Get-Date -Format 'HHmmss'))
    }

    $badge = @{ PASS = 'badge-pass'; WARN = 'badge-warn'; FAIL = 'badge-fail' }
    $rowsSb = New-Object System.Text.StringBuilder
    $no = 0
    foreach ($item in $check.Items) {
        $no++
        $detailHtml = [System.Net.WebUtility]::HtmlEncode($item.Detail)
        $nameHtml   = [System.Net.WebUtility]::HtmlEncode($item.Name)
        [void]$rowsSb.AppendLine(('<tr><td>{0}</td><td>{1}</td><td><span class="badge {2}">{3}</span></td><td>{4}</td></tr>' -f $no, $nameHtml, $badge[$item.Status], $item.Status, $detailHtml))
    }
    $passCnt = @($check.Items | Where-Object { $_.Status -eq 'PASS' }).Count
    $warnCnt = @($check.Items | Where-Object { $_.Status -eq 'WARN' }).Count
    $failCnt = @($check.Items | Where-Object { $_.Status -eq 'FAIL' }).Count
    $overallClass = $badge[$check.Overall]
    $checkedAt = $check.CheckedAt.ToString('yyyy-MM-dd HH:mm:ss')

    # Bootstrap 5 스타일(오프라인 사용을 위해 핵심 스타일 인라인 포함)
    $html = @"
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CSHSP 일일 점검 보고서 $dateStr</title>
<style>
  /* Bootstrap 스타일 발췌(오프라인 대응 인라인) + A4 인쇄 대응 */
  * { box-sizing: border-box; }
  body { font-family: 'Malgun Gothic','Segoe UI',sans-serif; margin: 0; background: #f5f6f8; color: #212529; }
  .container { max-width: 900px; margin: 24px auto; background: #fff; border-radius: 12px;
               box-shadow: 0 2px 10px rgba(0,0,0,.08); padding: 32px 40px; }
  h1 { font-size: 1.5rem; margin: 0 0 4px; color: #0d6efd; }
  .subtitle { color: #6c757d; font-size: .9rem; margin-bottom: 24px; }
  .summary { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }
  .card { flex: 1 1 140px; border: 1px solid #dee2e6; border-radius: 8px; padding: 14px 18px; text-align: center; }
  .card .num { font-size: 1.6rem; font-weight: 700; }
  .card .lbl { font-size: .8rem; color: #6c757d; }
  .num-pass { color: #198754; } .num-warn { color: #cc9a06; } .num-fail { color: #dc3545; }
  table { width: 100%; border-collapse: collapse; font-size: .9rem; }
  th, td { border-bottom: 1px solid #dee2e6; padding: 9px 10px; text-align: left; vertical-align: top; }
  th { background: #f8f9fa; border-top: 2px solid #0d6efd; white-space: nowrap; }
  tr:nth-child(even) td { background: #fbfcfd; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: .75rem; font-weight: 700; color: #fff; }
  .badge-pass { background: #198754; } .badge-warn { background: #ffc107; color: #212529; } .badge-fail { background: #dc3545; }
  .overall { font-size: 1rem; padding: 8px 22px; }
  .footer { margin-top: 28px; padding-top: 12px; border-top: 1px solid #dee2e6; color: #6c757d; font-size: .78rem; }
  @media print {
    body { background: #fff; }
    .container { box-shadow: none; margin: 0; max-width: 100%; padding: 10mm; border-radius: 0; }
    @page { size: A4 portrait; margin: 12mm; }
  }
</style>
</head>
<body>
<div class="container">
  <h1>CSHSP Pilot 일일 점검 보고서</h1>
  <div class="subtitle">천안의료원 건강검진센터 · CSHSP Operation Toolkit v1.0 · 점검시간: $checkedAt</div>

  <div class="summary">
    <div class="card"><div class="num"><span class="badge overall $overallClass">$($check.Overall)</span></div><div class="lbl">종합 결과</div></div>
    <div class="card"><div class="num num-pass">$passCnt</div><div class="lbl">PASS</div></div>
    <div class="card"><div class="num num-warn">$warnCnt</div><div class="lbl">WARNING</div></div>
    <div class="card"><div class="num num-fail">$failCnt</div><div class="lbl">FAIL</div></div>
  </div>

  <table>
    <thead><tr><th style="width:36px">#</th><th style="width:190px">점검 항목</th><th style="width:80px">상태</th><th>상세</th></tr></thead>
    <tbody>
$($rowsSb.ToString())    </tbody>
  </table>

  <div class="footer">
    본 보고서는 generate-report_new.ps1 이 자동 생성했습니다 ·
    Dashboard: $($Settings.DashboardUrl) ·
    점검 로그: tools\logs\health.log
  </div>
</div>
</body>
</html>
"@

    [System.IO.File]::WriteAllText($outPath, $html, [System.Text.UTF8Encoding]::new($true))
    Write-Step 'OK ' ('보고서 저장: ' + $outPath) 'Green'
    Write-ToolkitLog -File 'pilot.log' -Level OK -Message ('보고서 생성: {0} (종합 {1})' -f $outPath, $check.Overall)

    # [3/3] 열기(옵션) -------------------------------------------------------
    if ($Open) {
        Write-Step '3/3' '브라우저로 열기'
        Start-Process $outPath
    } else {
        Write-Step '3/3' '완료 (브라우저로 보려면 -Open 옵션 사용)'
    }
    Write-Host ''
    $ocolor = switch ($check.Overall) { 'PASS' { 'Green' } 'WARN' { 'Yellow' } default { 'Red' } }
    Write-Host ('  종합 결과: ' + $check.Overall) -ForegroundColor $ocolor
}
catch {
    $exitCode = 1
    Write-Host ('  [오류] 보고서 생성 실패: ' + $_.Exception.Message) -ForegroundColor Red
    Write-ToolkitLog -File 'pilot.log' -Level ERROR -Message ('generate-report 실패: ' + $_.Exception.Message)
}
exit $exitCode
