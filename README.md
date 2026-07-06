# CMC Platform (CSHSP)

**천안의료원 건강검진센터 AI 예약 컨시어지 플랫폼**
Cheonan Medical Center — AI Health Screening Concierge Platform

**버전**: v0.9.0-pilot
**상태**: Architecture Freeze 완료 / Pilot 준비 중 (자세한 내용은 [CLAUDE.md](CLAUDE.md), [PROJECT_STATUS.md](PROJECT_STATUS.md) 참조)
**라이선스**: 천안의료원 내부 전용 ([LICENSE](LICENSE))

---

## 1. 프로젝트 소개

CMC Platform은 천안의료원 건강검진센터의 예약·운영·상담 업무를 지원하는 플랫폼이다. 수검자는 웹에서 검진 예약을 신청하고 AI 채팅으로 프로그램 추천·상담을 받을 수 있으며, 직원은 관리자 콘솔에서 예약 승인·문진 검토·운영 통계를 확인한다.

초기 버전은 localStorage 기반 정적 페이지로 시작해, Google Sheets/Apps Script 연동을 거쳐 현재는 Python(FastAPI) 백엔드 기반의 20-Entity 데이터 계층, 상태머신을 갖춘 예약 엔진, 규칙 기반+Claude API 하이브리드 AI 에이전트로 확장되었다.

## 2. 주요 기능

- **예약 신청/관리**: 수검자용 예약 신청 화면, 상태머신 기반 승인 흐름(PENDING_APPROVAL → CONFIRMED/REJECTED → COMPLETED/CANCELLED), 감사로그 기록
- **관리자 콘솔**: 예약 목록/상세/승인, 문진 검토, Slot·일정 관리, 감사로그 조회 (RBAC 기반, ROLE-STAFF만 승인 가능)
- **AI 채팅 컨시어지**: SSE 스트리밍 채팅 위젯, 예약 신청·프로그램 추천·문진 안내·상담원 연결. 35개 금지응답 카테고리 차단 + AI는 예약을 직접 확정할 수 없음(3중 방어)
- **운영 대시보드**: 실시간 KPI(6종), 검사실 현황(8종), AI 상담 통계
- **Google Sheets 연동**: Apps Script Web App을 통한 예약 원장 기록 (OAuth 불필요)
- **보안/개인정보**: Rate Limit, PII 마스킹 로그, 세션에 대화 원문 미저장

## 3. 구조 (아키텍처 요약)

세 개의 실행 영역으로 구성된다.

1. **Frontend** — 정적 HTML/CSS/Vanilla JS (`app/`, `admin/`, `chat/`)
2. **Backend (Python)** — FastAPI REST API + AI 에이전트 오케스트레이션 (`src/`)
3. **Backend (Google Apps Script)** — Google Sheets를 예약 원장으로 사용하는 별도 백엔드 (`app/apps_script/`)

두 백엔드는 독립적으로 존재하며 자동 동기화되지 않는다. 상세 구조와 데이터 흐름은 **[ARCHITECTURE.md](ARCHITECTURE.md)**를 참조한다.

## 4. 실행 방법

### 사전 준비

```bash
# Python 의존성 설치 (Python 3.9+, 운영 권장 3.14)
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일을 열어 CSHSP_DATA_DIR 등 값 채우기 (ANTHROPIC_API_KEY는 선택)
```

### API 서버 실행 (포트 8600)

```bash
python -m uvicorn src.api.api_server:app --host 127.0.0.1 --port 8600
```

Health check: `http://127.0.0.1:8600/api/health`

### 정적 프론트엔드 서버 실행 (포트 4000)

```bash
npx serve -p 4000 .
# 또는: python -m http.server 4000
```

### Google Apps Script 연동 설정 (예약 화면 사용 시 필수)

1. `app/apps_script/sheets_api_v3_final.gs`를 Google Apps Script 프로젝트에 배포 (웹 앱, "새 버전"으로 배포)
2. 발급된 배포 URL을 `app/config_v2_new.js`의 `appsScript.webAppUrl`에 입력
3. `SPREADSHEET_ID`, `SHEET_NAME`은 운영 시트에 맞게 `.gs` 파일에서 직접 수정

### 테스트 실행

```bash
python tests/run_sprint_a_tests.py
python tests/run_sprint_b_tests.py
python tests/run_sprint_d_tests.py
python tests/run_sprint_e_tests.py
python tests/run_sprint_f_tests.py
python tests/run_sprint_g_tests.py
python tests/run_sprint_h_tests.py
python tests/run_sprint_i_quality_gate.py
```

운영 배포 절차 전체는 `src/deploy/production_checklist.md`, `src/deploy/process_manager.md`를 참조한다.

## 5. 폴더 구조

```
CMC_Platform_new/
├── app/            프론트엔드(예약 UI, 대시보드) + Apps Script 백엔드
├── admin/          관리자 콘솔 (Sprint C)
├── chat/           AI 채팅 위젯 (Sprint E/F)
├── src/            Python 백엔드
│   ├── core/         Core Data Layer (Sprint A)
│   ├── reservation/   예약 엔진 (Sprint B)
│   ├── questionnaire/ 문진 처리 (Sprint C)
│   ├── api/          FastAPI REST 서버 (Sprint D)
│   ├── agents/        AI 에이전트 오케스트레이터 (Sprint E~G)
│   ├── dashboard/     AI 상담 통계 (Sprint G)
│   ├── security/       Rate Limit, PII 마스킹
│   ├── workers/        알림 발송 워커
│   └── deploy/         운영 절차 문서
├── data/           20 Entity JSON 데이터 (개인정보 포함, 버전관리 제외)
├── docs/           Sprint 산출 문서, 운영 매뉴얼
├── tests/          Sprint별 테스트 스크립트
├── CLAUDE.md         작업 지침 (SSOT)
├── ARCHITECTURE.md   시스템 구조 (SSOT)
├── ROADMAP.md        이력 및 계획 (SSOT)
├── DECISIONS.md      아키텍처 의사결정 기록 (SSOT)
├── PROJECT_STATUS.md 현재 상태 스냅샷 (SSOT)
├── CHANGELOG.md      버전별 변경 이력
└── RELEASE_NOTES_v0.9.0-pilot.md  릴리스 노트
```

상세 구조는 [ARCHITECTURE.md](ARCHITECTURE.md) §2 참조.

## 6. 로드맵

- Sprint A~I, Sprint 2까지 개발 완료, Architecture Freeze(Sprint 0) 완료 (2026-07-04)
- **Pilot Ready 전제조건 (Sprint J 착수 전 필수 해결)**: STEP1.5 DateFix 배포, DEV-003(관리자 예약관리 Sheets연동) 구현, 더미 데이터/계정 정리
- 이후 계획: LLM 기반 의도 분류 전환 검토, 관리자 인증 구현, HTTPS 적용, SQLite 마이그레이션 검토, 파일럿 운영, Go-Live

전체 로드맵은 **[ROADMAP.md](ROADMAP.md)**를 참조한다.

## 7. 관련 문서

| 문서 | 용도 |
|---|---|
| [CLAUDE.md](CLAUDE.md) | 작업 지침 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 시스템 구조 |
| [ROADMAP.md](ROADMAP.md) | 이력 + 향후 계획 |
| [DECISIONS.md](DECISIONS.md) | 아키텍처 의사결정 기록(ADR) |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | 현재 상태 스냅샷 |
| [CHANGELOG.md](CHANGELOG.md) | 버전별 변경 이력 |
| [RELEASE_NOTES_v0.9.0-pilot.md](RELEASE_NOTES_v0.9.0-pilot.md) | v0.9.0-pilot 릴리스 노트 |
| [PILOT_READINESS_REVIEW.md](PILOT_READINESS_REVIEW.md) | Pilot 운영 시작 전 최종 검토 보고서 |

## 8. 개인정보 취급 주의

`data/patients.json`, `data/reservations.json`, `data/businesses.json` 등은 개인정보(PII)를 포함한다. 외부 공유용 산출물에는 이름·생년월일·전화번호·주민등록번호 등을 제거 또는 마스킹한다. 상세 원칙은 [CLAUDE.md](CLAUDE.md) 참조.
