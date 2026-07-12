# CHANGELOG — CSHSP Operation Toolkit

## v1.0.2 (2026-07-12) — pilot-check 더블클릭 지원

### 추가 (Added)
- `pilot-check_new.bat` — 더블클릭 한 번으로 자동 점검 실행
  - ExecutionPolicy 자동 처리(`-ExecutionPolicy Bypass`) — 사용자가 `Set-ExecutionPolicy`를 입력할 필요 없음
  - 결과 확인 후 닫히도록 `pause` 유지(창 자동 종료 금지)
  - pwsh(PS7) 우선, 없으면 Windows PowerShell 5.1 자동 선택 — 기존 start/stop bat과 동일 패턴
  - v1.0.1 원칙 유지: `chcp 65001` 미사용, bat은 순수 ASCII
- README 사용법 갱신(점검 = 더블클릭)

### QA (Regression Zero 확인)
- bat 실제 실행: 11항목 점검 정상(PASS 10/WARN 1/FAIL 0, WARN=git 미커밋 변경), 한글 출력 정상, 종료코드 0
- 기존 파일 로직 무변경(README·CHANGELOG 문서만 갱신)

## v1.0.1 (2026-07-12) — HotFix: bat 실행 시 한글 출력 깨짐

### 수정 (Fixed)
- `pilot-start_new.bat` / `pilot-stop_new.bat`에서 `chcp 65001 >nul` 제거
- README FAQ의 한글 깨짐 항목을 실제 원인·조치로 교정

### 변경 이유 (Root Cause)
- 점검 결과 파일 인코딩은 모두 정상이었다: .ps1 = UTF-8(BOM) → PS 5.1/7 모두 한글 리터럴 정상 파싱, .bat = 순수 ASCII(비ASCII 0바이트) → 코드페이지 무관.
- 깨짐의 원인은 `chcp 65001` 자체: 한글 Windows 콘솔(conhost)에서 코드페이지를 65001로 바꾸면 한글 지원 글꼴 매핑이 깨지고, Windows PowerShell 5.1의 CP65001 호환 문제와 겹쳐 한글이 깨져 보인다.
- bat은 한글을 직접 출력하지 않고, PowerShell의 Write-Host는 코드페이지와 무관한 유니코드 콘솔 API로 출력하므로 기본 코드페이지(CP949)에서 한글이 정상 표시된다. 따라서 chcp 제거가 가장 안정적인 해법이다.

### QA (Regression Zero 확인)
- 수정된 bat 실제 실행: pilot-stop(서버 2개 정상 종료) → pilot-start(기동·Health 200·페이지 오픈) 모두 정상, 한글 출력 정상
- bat 비ASCII 바이트 0 유지, 로직 변경 없음(주석만 추가) — 기존 기능 변경 없음

## v1.0 (2026-07-12) — 최초 Release

### 추가 (Added)
- `pilot-start_new.bat` / `pilot-start_new.ps1` — Pilot 원클릭 시작
  - Python·프로젝트 확인 → API(uvicorn, :8600)·Frontend(http.server, :4000) 기동 → Health 대기(진행률 표시) → Dashboard·예약 페이지 자동 오픈
  - 포트 점유 감지로 **중복 실행 방지**, 서버는 숨김 창으로 실행되고 출력은 `logs\*.out.log / *.err.log`에 기록
- `pilot-stop_new.bat` / `pilot-stop_new.ps1` — Pilot 원클릭 종료
  - 포트 8600/4000 점유 프로세스 중 **python 계열만** 종료(안전장치), 정상 종료 우선·강제 종료 최소화
- `pilot-check_new.ps1` — 11개 항목 자동 점검(색상 출력, `-PassThru` 지원)
  - Git / Python / Port 8600·4000 / API Health / Dashboard / 예약 페이지 / Apps Script / Sheets(ping) / Backup / Logs + 종합 PASS·WARN·FAIL
- `backup-db_new.ps1` — data·logs·config·reports ZIP 백업, `Backup_YYYYMMDD_HHMMSS.zip`, 30일 초과분 자동 삭제
- `generate-report_new.ps1` — `reports\Daily_Check_YYYYMMDD.html` 생성(Bootstrap 스타일 인라인, A4 인쇄 대응, 같은 날 재실행 시 시각 접미사로 새 파일)
- `settings_new.ps1` — 단일 설정 지점(포트·URL·보관일수·타임아웃) + 공용 함수(로그·포트·HTTP 점검)
- `README_OPERATION_new.md` — 설치·운영·백업/복원·스케줄러·FAQ
- `logs/` `reports/` `backup/` 자동 생성, `pilot.log`·`health.log`·`backup.log`·`error.log` 타임스탬프 로깅

### 원칙 (Principles)
- Architecture Freeze 준수: 기존 소스(app/src/data 등) **무수정**, tools/ 추가만 — Regression Zero
- Windows 11 · PowerShell 5.1/7 겸용, UTF-8(BOM)·한글 경로 지원, 상대경로, 관리자 권한 불필요, StrictMode + try/catch

### QA (2026-07-12, Pilot 실환경)
| 테스트 | 결과 |
|---|---|
| pilot-check (서버 정지 상태 → FAIL 검출) | PASS |
| pilot-stop (실행 중 서버 2개 정상 종료) | PASS |
| pilot-start (신규 기동 → Health OK → 페이지 오픈) | PASS |
| pilot-start 재실행 (중복 실행 방지) | PASS |
| backup-db (ZIP 생성·보관정리) | PASS |
| generate-report (HTML 생성, 11항목) | PASS |
| PowerShell 5.1 경로(bat 호출 방식) 검증 | PASS |

상세: `reports\OPERATION_QA_20260712_new.md`
