# CSHSP Operation Toolkit v1.0 — 운영 매뉴얼

천안의료원 건강검진센터 CSHSP(v1.0.0-pilot) **운영 자동화 도구** 매뉴얼입니다.
기존 프로그램(app / src / data / API / Dashboard / Apps Script)은 **일절 수정하지 않으며**, 이 폴더(`tools/`)의 도구만으로 Pilot을 시작·종료·점검·백업·보고합니다.

- 대상 환경: Windows 11, Windows PowerShell 5.1 또는 PowerShell 7 (둘 다 지원, 자동 선택)
- 관리자 권한: **불필요**
- 경로: 모두 상대경로 기반 — `CMC_Platform_new` 폴더를 통째로 옮겨도 동작

---

## 1. 구성 파일

| 파일 | 용도 | 사용 방법 |
|---|---|---|
| `pilot-start_new.bat` | Pilot 시작 (API 8600 + Frontend 4000 + 브라우저 오픈) | **더블클릭** |
| `pilot-stop_new.bat` | Pilot 종료 (두 서버 정리) | **더블클릭** |
| `pilot-check_new.bat` | 11개 항목 자동 점검 (색상 콘솔) | **더블클릭** |
| `backup-db_new.ps1` | data/logs/config/reports ZIP 백업 (+30일 초과분 자동 삭제) | 우클릭 → PowerShell로 실행 |
| `generate-report_new.ps1` | 일일 점검 HTML 보고서 생성 (A4 인쇄 가능) | 우클릭 → PowerShell로 실행 |
| `settings_new.ps1` | **모든 설정의 단일 관리 지점** + 공용 함수 | 설정 변경 시에만 편집 |
| `logs/` `reports/` `backup/` | 로그 / 보고서 / 백업 저장소 (자동 생성) | — |

`pilot-start_new.ps1`, `pilot-stop_new.ps1`, `pilot-check_new.ps1`은 bat이 호출하는 실제 로직입니다(직접 실행해도 됩니다). bat은 ExecutionPolicy를 자동 처리하므로 `Set-ExecutionPolicy` 입력이 필요 없고, 결과 확인 후 아무 키나 누르면 창이 닫힙니다.
※ `pilot-start.bat`(구버전, `_new` 없는 파일)은 이전 버전 보존용입니다. **`_new`가 붙은 파일을 사용하세요.**

---

## 2. 설치 방법

별도 설치가 없습니다. 조건만 확인하세요.

1. Python 설치 확인: 명령 프롬프트에서 `python --version` (3.10 이상 권장)
2. 의존성 설치(최초 1회): 프로젝트 루트에서 `pip install -r requirements.txt`
3. `tools` 폴더가 `CMC_Platform_new` 바로 아래에 있는지 확인

---

## 3. 일상 운영 절차 (Daily)

### 아침 — 시작
1. `tools\pilot-start_new.bat` **더블클릭**
2. "Pilot 시작 완료!" 메시지와 함께 Dashboard·예약 페이지가 브라우저에 열리면 정상
3. 이미 실행 중이면 "중복 실행하지 않습니다"라고 알려주고 그대로 사용 가능

### 일과 중 — 점검 (Daily Check)
1. `tools\pilot-check_new.bat` **더블클릭** → 자동 점검 → 종합 결과 확인 (PASS/WARN/FAIL)
2. 보고서가 필요하면 `generate-report_new.ps1` 실행 → `reports\Daily_Check_날짜.html` 생성 (인쇄 = 브라우저에서 Ctrl+P, A4 세로)

### 퇴근 전 — 백업 · 종료
1. `backup-db_new.ps1` 실행 → `backup\Backup_날짜_시각.zip` 생성 확인
2. `tools\pilot-stop_new.bat` **더블클릭** → "Pilot 종료 완료" 확인

---

## 4. 점검 항목 (pilot-check)

Git 상태 / Python / Port 8600 / Port 4000 / API Health / Dashboard 페이지 / 예약 페이지 / Apps Script URL / Google Sheets 연결(ping) / 백업 최신 여부 / 로그 폴더 쓰기 — 총 11개.

- **PASS**(초록) 정상 · **WARN**(노랑) 운영 가능하나 확인 권장 · **FAIL**(빨강) 조치 필요
- 외부망 항목(Apps Script, Sheets)은 병원 방화벽 때문에 실패할 수 있어 FAIL 대신 WARN으로 처리합니다.
- 종합 결과: FAIL 1개라도 있으면 FAIL, WARN만 있으면 WARN, 모두 정상이면 PASS

## 5. 백업 · 복원 (Backup / Restore)

- **백업**: `backup-db_new.ps1` 실행. 대상 = `data`, `tools\logs`, `tools\reports`, config 파일(존재하는 것만). 30일 지난 ZIP은 자동 삭제(보관일수는 `settings_new.ps1`의 `BackupRetentionDays`).
- **복원**:
  1. `pilot-stop_new.bat`으로 Pilot 종료
  2. `backup\Backup_날짜.zip`을 임시 폴더에 압축 해제
  3. 압축 안의 `data` 폴더 내용을 확인 후, 프로젝트의 `data\`에 필요한 파일만 복사 (원본은 먼저 다른 이름으로 보존 권장)
  4. `pilot-start_new.bat`으로 재시작 → `pilot-check_new.ps1`로 확인

## 6. 설정 변경

**`settings_new.ps1` 한 파일만** 수정합니다 (포트, URL, 백업 보관일수, 타임아웃 등).
예: 대시보드 파일이 바뀌면 `DashboardUrl` 값만 교체 → 모든 도구에 자동 반영.

## 7. 작업 스케줄러 등록 (선택)

매일 자동 백업을 원하면 명령 프롬프트에서 (관리자 권한 불필요, 현재 사용자 계정으로 등록):

```
schtasks /Create /TN "CSHSP_DailyBackup" /TR "powershell -NoProfile -ExecutionPolicy Bypass -File \"C:\Users\cmcsh\건강검진\99_임시보관_정리대기\CMC_Platform_new\tools\backup-db_new.ps1\"" /SC DAILY /ST 17:30
```

해제: `schtasks /Delete /TN "CSHSP_DailyBackup" /F`

## 8. 오류 해결 · FAQ

| 증상 | 원인/조치 |
|---|---|
| "Python을 찾을 수 없습니다" | Python 미설치 또는 PATH 누락. 재설치 시 "Add python to PATH" 체크 |
| API Health 응답 없음 | `logs\api_server.err.log` 확인. 대부분 `pip install -r requirements.txt` 미실행이 원인 |
| 페이지가 안 열림 (FAIL) | `pilot-stop_new.bat` → `pilot-start_new.bat` 재시작 후 재점검 |
| 포트 점유했는데 python이 아님 | pilot-stop이 안전상 종료하지 않음. 작업 관리자에서 해당 PID 확인 후 직접 처리 |
| Apps Script / Sheets WARN | 인터넷·방화벽 확인. 내부 기능(API/Dashboard)은 영향 없음 |
| 한글이 깨져 보임 | bat/ps1에 `chcp 65001`을 **넣지 마세요**(v1.0.1에서 제거 — 한글 Windows에서 오히려 깨짐의 원인). 그래도 깨지면 콘솔 속성에서 글꼴을 '굴림체' 또는 'D2Coding'으로 변경 |
| 보고서가 안 만들어짐 | `logs\error.log` 확인. reports 폴더 쓰기 권한 확인 |
| 스크립트 실행 차단 | bat 파일 사용(내부에서 ExecutionPolicy Bypass 처리) — 시스템 설정 변경 불필요 |

- 모든 동작 로그: `logs\pilot.log`(시작·종료·보고서) / `logs\health.log`(점검) / `logs\backup.log`(백업) / `logs\error.log`(오류만 모음)
- git 커밋 시 `tools/logs` `tools/backup` `tools/reports`는 제외(.gitignore 등록)를 권장합니다.

---
CSHSP Operation Toolkit v1.0 · 2026-07-12 · Architecture Freeze 준수(기존 소스 무수정)
