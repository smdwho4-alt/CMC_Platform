# CMC Health Screening Platform v1.0 — Phase 3 README

> **Phase 3**: Google Workspace 연동 어댑터 추가  
> Phase 1 · 2 파일은 모두 유지됨 — 기존 파일 삭제 없음

---

## Phase 3 신규 파일

| 파일 | 설명 |
|------|------|
| `app/config_new.js` | Google Workspace 통합 설정 (SheetID, CalendarID, Timezone 등) |
| `app/services/google_sheets_service_new.js` | Google Sheets API v4 어댑터 (Mock + Live 인터페이스) |
| `app/services/calendar_service_new.js` | Google Calendar API v3 어댑터 (Mock + Live 인터페이스) |
| `app/services/gmail_service_new.js` | Gmail API v1 어댑터 (Mock + Live 인터페이스) |
| `app/pages/admin_dashboard_v2_new.html` | Phase 3 대시보드 (데이터 소스 전환 스위치 포함) |
| `README_platform_v2_new.md` | 이 문서 |

---

## 전체 파일 구조 (Phase 1~3 누적)

```
CMC_Platform_new/
├── index.html                              ← 진입점 (대시보드 리다이렉트)
├── app/
│   ├── config_new.js                       ← [Phase 3] GWS 설정
│   ├── pages/
│   │   ├── admin_dashboard_new.html        ← [Phase 2] 기본 대시보드 (보존)
│   │   ├── admin_dashboard_v2_new.html     ← [Phase 3] GWS 전환 스위치 포함 ★
│   │   ├── reservation_new.html            ← [Phase 2] 예약 신청
│   │   └── admin_reservations_new.html     ← [Phase 2] 예약 관리
│   ├── components/
│   │   └── nav_new.js                      ← [Phase 2] 공통 네비게이션
│   ├── services/
│   │   ├── db_service_new.js               ← [Phase 2] localStorage CRUD
│   │   ├── stats_service_new.js            ← [Phase 2] KPI 산출
│   │   ├── google_sheets_service_new.js    ← [Phase 3] Sheets 어댑터
│   │   ├── calendar_service_new.js         ← [Phase 3] Calendar 어댑터
│   │   └── gmail_service_new.js            ← [Phase 3] Gmail 어댑터
│   ├── data/
│   │   ├── programs_data_new.js            ← [Phase 2] 상수·유틸
│   │   └── sample_data_new.js              ← [Phase 2] 샘플 데이터 40건
│   └── styles/
│       ├── main_style_new.css              ← [Phase 2] 공통 스타일
│       └── dashboard_style_new.css         ← [Phase 2] 대시보드 스타일
└── README_platform_new.md                  ← [Phase 2] README (보존)
    README_platform_v2_new.md               ← [Phase 3] 이 문서
```

---

## 데이터 소스 전환 스위치

`admin_dashboard_v2_new.html` 상단에 **데이터 소스 전환 바**가 추가되었습니다.

| 모드 | 표시 | 동작 |
|------|------|------|
| **Local** | 💾 Local (localStorage) | Phase 1~2와 동일한 localStorage 기반 |
| **Google Workspace** | Google Workspace | GWS API 어댑터 경유 (Mock 시 localStorage 폴백) |

- 선택한 모드는 `localStorage(cmc_config_v1)`에 저장되어 새로고침 후에도 유지
- Mock 모드에서 GWS를 선택해도 데이터는 동일하게 표시됨 (API 호출 시뮬레이션)
- 최근 예약목록 테이블에 `GWS` / `Local` 출처 뱃지 표시

---

## Google Workspace 연동 절차

### 1단계 — Google Cloud 프로젝트 설정

```
Google Cloud Console → 새 프로젝트 생성
→ API 및 서비스 → 라이브러리에서 아래 3개 활성화:
  ① Google Sheets API v4
  ② Google Calendar API v3
  ③ Gmail API v1
```

### 2단계 — OAuth 2.0 클라이언트 ID 생성

```
API 및 서비스 → 사용자 인증 정보
→ 사용자 인증 정보 만들기 → OAuth 2.0 클라이언트 ID
→ 웹 애플리케이션 선택
→ 승인된 JavaScript 원본: https://your-domain.com
→ 생성 후 클라이언트 ID 복사
```

### 3단계 — Google Sheets 준비

```
Google Sheets에서 새 스프레드시트 생성
→ 시트 이름: Sheet1 (또는 원하는 이름)
→ 1행에 헤더 입력:
  예약번호 | 접수일시 | 수정일시 | 상태 | 성명 | 생년월일 | 연락처 | 성별
  프로그램 | 희망검진일 | 희망시간 | 수면여부 | 선택검사 | 사업장 | 특이사항
→ URL에서 Spreadsheet ID 복사:
  https://docs.google.com/spreadsheets/d/[여기가-ID]/edit
```

### 4단계 — Google Calendar 준비

```
Google Calendar → 새 캘린더 생성 ('건강검진 예약' 등)
→ 설정 → 캘린더 통합 → 캘린더 ID 복사
  (형식: abc123...@group.calendar.google.com)
```

### 5단계 — 대시보드 v2에서 설정 입력

```
admin_dashboard_v2_new.html 접속
→ 데이터 소스를 [Google Workspace]로 전환
→ GWS 설정 패널에서:
  - Spreadsheet ID 입력
  - Calendar ID 입력
  - 발신 이메일 입력
  - Client ID 입력
→ [설정 저장] 클릭
→ [전체 테스트] 클릭하여 연결 확인
```

### 6단계 — OAuth 인증 (운영 환경)

```
[중요] 클라이언트사이드 OAuth는 운영 환경에서 보안 위험이 있습니다.
아래 중 하나를 선택하세요:

(권장) 서버사이드 방식:
  - Google Apps Script Web App으로 Sheets/Calendar/Gmail 처리
  - 클라이언트는 Apps Script 엔드포인트로 POST 요청
  - Apps Script에서 서비스 계정으로 API 호출

(대안) Google Identity Services:
  - GIS 라이브러리 로드 후 팝업 인증
  - 사용자가 직접 Google 계정으로 로그인
  - 획득한 access_token을 각 서비스에 주입
```

### Apps Script 연동 예시 (권장 방식)

```javascript
// Google Apps Script (doPost 함수)
function doPost(e) {
  const data = JSON.parse(e.postData.contents);
  const action = data.action;

  if (action === 'getReservations') {
    const sheet = SpreadsheetApp.openById(SHEET_ID).getActiveSheet();
    const values = sheet.getDataRange().getValues();
    return ContentService.createTextOutput(
      JSON.stringify({ ok: true, data: values })
    ).setMimeType(ContentService.MimeType.JSON);
  }
  // ... 다른 액션 처리
}
```

---

## 서비스 어댑터 인터페이스

### CMC_SheetsService

```javascript
await CMC_SheetsService.getAll()          // 전체 예약 조회
await CMC_SheetsService.append(reservation) // 예약 추가
await CMC_SheetsService.updateStatus(no, status) // 상태 변경
await CMC_SheetsService.update(no, patch)  // 전체 업데이트
await CMC_SheetsService.ping()            // 연결 테스트
```

### CMC_CalendarService

```javascript
await CMC_CalendarService.createEvent(reservation) // 이벤트 생성
await CMC_CalendarService.deleteEvent(eventId)     // 이벤트 삭제
await CMC_CalendarService.listWeek()               // 이번주 이벤트
await CMC_CalendarService.listToday()              // 오늘 이벤트
await CMC_CalendarService.ping()                   // 연결 테스트
```

### CMC_GmailService

```javascript
await CMC_GmailService.sendReceived(r, email)   // 접수 확인 메일
await CMC_GmailService.sendConfirmed(r, email)  // 확정 안내 메일
await CMC_GmailService.sendCancelled(r, email)  // 취소 안내 메일
await CMC_GmailService.sendRescheduled(r, email, date, time) // 일정변경
CMC_GmailService.getLog()                        // 발송 로그 조회
await CMC_GmailService.ping()                    // 연결 테스트
```

### CMC_CONFIG

```javascript
CMC_CONFIG.dataSource         // 'local' | 'google'
CMC_CONFIG.setDataSource('google')  // 모드 전환 + 저장
CMC_CONFIG.isGoogle()         // boolean
CMC_CONFIG.isLocal()          // boolean
CMC_CONFIG.load()             // localStorage에서 설정 로드
CMC_CONFIG.persist()          // localStorage에 설정 저장
```

---

## 보안 주의사항

| 항목 | 상태 | 권장 조치 |
|------|------|----------|
| API Key | 코드에 직접 입력 금지 | 서버 환경변수 또는 Secret Manager |
| OAuth Token | 클라이언트사이드 위험 | Apps Script 서버사이드 처리 |
| 수검자 개인정보 | 민감 데이터 | HTTPS 필수, 접근권한 관리 |
| Sheets ID 노출 | URL에서 추출 가능 | Sheets 공유 설정 '제한됨' 유지 |

---

## Phase 로드맵

| Phase | 내용 | 상태 |
|-------|------|------|
| Phase 1 | 기본 예약·관리 HTML/JS (localStorage) | ✅ 완료 |
| Phase 2 | 플랫폼 구조 리팩터링, 대시보드 신설 | ✅ 완료 |
| **Phase 3** | **Google Workspace 어댑터, 데이터소스 전환** | ✅ 완료 |
| Phase 4 | Apps Script 서버 구현, 실 운동 OAuth | 예정 |
| Phase 5 | HIS 연동, 카카오 알림톡, 통계 고도화 | 예정 |

---

*CMC Health Screening Platform v1.0 Phase 3 | 2026-07-01 | 천안의료원 건강검진센터*
