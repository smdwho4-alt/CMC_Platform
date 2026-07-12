# CSHSP Operation Toolkit v1.0 — QA · Regression · Operation Test 결과

- 일시: 2026-07-12 15:10~15:13
- 환경: Windows 11, Windows PowerShell 5.1, Python 3.14.2, CSHSP v1.0.0-pilot (Pilot 실환경)
- 원칙 확인: 기존 소스 무수정(tools/ 신규 추가만), Architecture Freeze 유지

## 1. Operation Test (실환경 실행)

| # | 테스트 | 기대 결과 | 실제 결과 | 판정 |
|---|---|---|---|---|
| 1 | pilot-check (서버 정지 직전 상태) | 항목별 상태 검출·색상 출력·종합 판정 | 11항목 출력, 종합 WARN(백업없음·git변경) — FAIL 검출 로직 정상 | PASS |
| 2 | pilot-stop (서버 2개 실행 중) | python 프로세스만 안전 종료 | API(PID 2968)·Frontend(PID 28256) 정상 종료 | PASS |
| 3 | pilot-start (미기동 상태) | 기동→Health 대기→페이지 오픈 | 8단계 완료, Health HTTP 200, 브라우저 오픈 | PASS |
| 4 | pilot-start 재실행 | 중복 실행 금지 | "이미 실행 중 — 중복 실행하지 않습니다" 출력, 프로세스 추가 생성 없음 | PASS |
| 5 | backup-db | ZIP 생성·30일 초과분 정리 | Backup_20260712_151206.zip 생성(5개 대상 포함), 정리 0건 | PASS |
| 6 | generate-report | Daily_Check HTML 생성 | Daily_Check_20260712.html 생성, 11항목·요약카드·A4 인쇄 CSS 포함 | PASS |
| 7 | PS 5.1 호환(bat 호출 경로) | powershell.exe -File 로 정상 동작 | pilot-check 정상 완료 (PASS 10/WARN 1/FAIL 0) | PASS |
| 8 | 로그 생성 | pilot/health/backup 로그 + 서버 stdout/err | logs\ 에 7개 로그 파일 생성 확인 | PASS |

## 2. Regression Check

- git status 확인 결과 기존 추적 파일 변경 없음(신규 tools/ 및 기존 미커밋 문서만 존재) → **기존 소스 무수정 확인**
- API Health `HTTP 200 {"status":"ok","version":"sprint-d-1.0"}` — 기존 서비스 동작 불변
- Dashboard·예약 페이지 HTTP 200, Apps Script HTTP 200, Sheets action=ping 정상 → **Regression Zero**

## 3. 코드 리뷰 반영 사항 (Self QA)

- StrictMode 하에서 빈 배열 반환 시 unroll로 `.Count` 실패 → `Get-PortOwnerPids`가 단항 콤마로 배열째 반환하도록 수정 후 재검증 (테스트 #1~#7 통과)
- PS5.1 한글 호환을 위해 모든 .ps1을 UTF-8(BOM)로 저장, bat은 ASCII+`chcp 65001`
- pilot-stop 안전장치: 포트 점유 프로세스가 python 계열이 아니면 종료하지 않고 경고만 출력
- 같은 날 보고서 재생성 시 덮어쓰기 금지 → 시각(HHmmss) 접미사로 새 파일 저장
- 외부망 점검(Apps Script/Sheets)은 병원 방화벽 고려 시 FAIL 대신 WARN 처리

## 4. 종합 판정

**Operation Toolkit v1.0 — Release 승인 (전 항목 PASS)**

잔여 권고: ① `tools/logs·backup·reports`를 .gitignore에 추가(사용자 승인 필요) ② 매일 17:30 자동 백업 스케줄러 등록은 README §7 절차 참고
