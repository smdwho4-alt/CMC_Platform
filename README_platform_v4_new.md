# CMC Health Screening Platform v1.0 — Phase 4.5 README

> **Phase 4.5**: Google Sheets 예약 DB를 병원 운영 DB로 확장  
> Phase 1 · 2 · 3 · 4 파일은 모두 유지됨 — 기존 파일 삭제 없음

---

## Phase 4.5 신규 파일

| 파일 | 설명 |
|------|------|
| `app/apps_script/sheets_api_v2_new.gs` | Apps Script v2 — 29컬럼 운영 DB 확장판 |
| `app/docs/erd_new.html` | ERD (Database Schema) — 브라우저에서 열기 |
| `app/docs/workflow_new.html` | Workflow Diagram — 수영레인·상태전이·API 흐름 |
| `app/docs/sheets_structure_new.html` | Google Sheets 구조도 — 컬럼 미리보기·상세 정의 |
| `README_platform_v4_new.md` | 이 문서 |

---

## 컬럼 확장 내역

### 기존 18개 컬럼 (Phase 4 유지)

| 열 | 컬럼명 | 영문 필드 | 비고 |
|----|--------|-----------|------|
| A | 예약번호 | reservationNo | PK, 자동생성 YYYYMMDD-NNNN |
| B | 접수일시 | createdAt | 자동 타임스탬프 |
| C | 성명 | name | 필수, 개인정보 |
| D | 생년월일 | birth | 필수, 개인정보 |
| E | 연락처 | phone | 필수, 개인정보 |
| F | 성별 | gender | 남/여 |
| G | 검진프로그램 | program | BASIC·SMART·VIP·PREMIUM·YOUNG·온김에 |
| H | 희망검진일 | wishDate | YYYY-MM-DD |
| I | 희망시간 | wishTime | HH:mm |
| J | 수면 | sleep | 수면선택/미선택 |
| K | 선택검사 | optionalTests | 콤마 구분 |
| L | 사업장 | company | 선택 |
| M | 예약경로 | route | 온라인·전화·방문·협약 |
| N | 담당자 | manager | 예약 처리 직원 |
| O | 예약상태 | status | 6가지 상태 |
| P | 예약확정일 | confirmedAt | 자동 |
| Q | 문자발송 | smsSent | Y/N |
| R | 특이사항 | note | 자유 메모 |

### 추가 11개 컬럼 (Phase 4.5 신규)

| 열 | 컬럼명 | 영문 필드 | 기본값 | 입력주체 |
|----|--------|-----------|--------|--------|
| S | 검진예정시간 | scheduledTime | — | 행정 |
| T | 접수시간 | checkinTime | — | 자동(상태→검진중) |
| U | 검진시작 | examStart | — | 자동(상태→검진중) |
| V | 검진종료 | examEnd | — | 자동(상태→검진완료) |
| W | 검진실 | examRoom | — | 행정 |
| X | 문진의사 | doctor | — | 행정 |
| Y | 담당간호사 | nurse | — | 행정 |
| Z | 예상비용 | estimatedCost | — | 행정 |
| AA | 결제상태 | paymentStatus | 미결제 | 시스템/행정 |
| AB | 결과발송 | resultStatus | 미발송 | 시스템/행정 |
| AC | 재예약여부 | revisit | 해당없음 | 행정 |

---

## 전체 파일 구조 (Phase 1~4.5 누적)

```
CMC_Platform_new/
├── index.html
├── app/
│   ├── config_new.js                               ← [Phase 3] 보존
│   ├── config_v2_new.js                            ← [Phase 4] 보존
│   ├── apps_script/
│   │   ├── sheets_api_new.gs                       ← [Phase 4] 18컬럼 (보존)
│   │   └── sheets_api_v2_new.gs                    ← [Phase 4.5] 29컬럼 ★
│   ├── docs/
│   │   ├── erd_new.html                            ← [Phase 4.5] ERD ★
│   │   ├── workflow_new.html                       ← [Phase 4.5] Workflow ★
│   │   └── sheets_structure_new.html               ← [Phase 4.5] Sheets 구조도 ★
│   ├── pages/
│   │   ├── admin_dashboard_new.html                ← [Phase 2] 보존
│   │   ├── admin_dashboard_v2_new.html             ← [Phase 3] 보존
│   │   ├── reservation_new.html
│   │   └── admin_reservations_new.html
│   ├── components/
│   │   └── nav_new.js
│   ├── services/
│   │   ├── db_service_new.js
│   │   ├── stats_service_new.js
│   │   ├── google_sheets_service_new.js            ← [Phase 3] 보존
│   │   ├── google_sheets_service_v2_new.js         ← [Phase 4] 보존
│   │   ├── calendar_service_new.js
│   │   └── gmail_service_new.js
│   ├── data/
│   │   ├── programs_data_new.js
│   │   └── sample_data_new.js
│   └── styles/
│       ├── main_style_new.css
│       └── dashboard_style_new.css
├── README_platform_new.md       ← [Phase 2] 보존
├── README_platform_v2_new.md    ← [Phase 3] 보존
├── README_platform_v3_new.md    ← [Phase 4] 보존
└── README_platform_v4_new.md    ← [Phase 4.5] 이 문서
```

---

## Apps Script v2 배포 방법

### 기존 Phase 4 스크립트에서 업그레이드하는 경우

```
1. https://script.google.com 접속 → 기존 프로젝트 열기
2. 기존 sheets_api_new.gs 내용을 sheets_api_v2_new.gs 내용으로 교체
3. [저장] (Ctrl+S)
4. [배포] → [배포 관리] → [수정] → 버전: 새 버전 → [배포]
5. 기존 Web App URL은 그대로 유지됨 (URL 변경 없음)
```

### 신규 배포하는 경우

```
1. https://script.google.com → [새 프로젝트]
2. sheets_api_v2_new.gs 내용 전체 붙여넣기
3. [배포] → [새 배포] → 웹 앱
4. 다음 사용자로 실행: 나
5. 액세스: 조직 내부 사용자 (운영) 또는 모든 사람 (테스트)
6. [배포] → URL 복사 → config_v2_new.js 의 appsScript.webAppUrl 에 입력
```

### 시트 헤더 초기화 (최초 1회)

```
Apps Script 편집기에서 _initHeader 함수 실행
→ '예약현황' 시트 자동 생성 및 29개 헤더 설정
→ 기존 컬럼(A~R) 파란색, 추가 컬럼(S~AC) 초록색으로 구분 표시
```

---

## Phase 4.5 신규 API 엔드포인트

### doGet — summary (당일 운영 요약)

```
GET ?action=summary[&date=YYYY-MM-DD]

응답:
{
  "ok": true,
  "data": {
    "date": "2026-07-01",
    "total": 12,
    "byStatus":  { "예약확정": 5, "검진중": 3, "검진완료": 4 },
    "byRoom":    { "1검진실": 6, "2검진실": 6 },
    "byPayment": { "미결제": 5, "결제완료": 7 },
    "byDoctor":  { "이의사": 7, "최의사": 5 },
    "totalEstimatedCost": 4320000
  }
}
```

### doPost — updateOps (운영 정보 업데이트)

```javascript
// 요청
{
  "action": "updateOps",
  "no": "20260701-0001",
  "data": {
    "scheduledTime": "09:00",
    "examRoom": "1검진실",
    "doctor": "이의사",
    "nurse": "박간호사",
    "estimatedCost": 450000,
    "paymentStatus": "결제완료",
    "resultStatus": "발송완료",
    "revisit": "해당없음"
  }
}

// 응답
{ "ok": true, "data": { "reservationNo": "20260701-0001" }, "message": "운영 정보 업데이트 완료" }
```

### 자동 타임스탬프 동작

| 상태 변경 | 자동 기록 컬럼 |
|-----------|--------------|
| `예약확정` | P열(예약확정일) |
| `검진중` | T열(접수시간), U열(검진시작) |
| `검진완료` | V열(검진종료) |

---

## 다이어그램 파일 열기

```
app/docs/erd_new.html           → 브라우저로 열기 (DB Schema, 29개 컬럼 상세)
app/docs/workflow_new.html      → 브라우저로 열기 (수영레인, 상태전이, API 흐름)
app/docs/sheets_structure_new.html → 브라우저로 열기 (시트 미리보기, 운영 팁)
```

---

## 개인정보 운영 전 주의사항

| 항목 | 위험 | 권장 조치 |
|------|------|----------|
| 의료·진료 관련 필드 추가 시 | 민감 의료정보 해당 가능 | 의료법·개인정보보호법 검토 필요 |
| 검진시작·종료 타임스탬프 | 개인 활동 증적 | 보존 기간 정책 수립 |
| 문진의사·담당간호사 | 의료진 개인정보 | 내부 식별코드 사용 권장 |
| 예상비용 컬럼 | 청구 관련 민감 정보 | 회계·청구 시스템과 분리 관리 권장 |
| Apps Script Web App URL | 노출 시 무단 접근 | 액세스 권한 '조직 내'로 제한 |

---

## Phase 로드맵

| Phase | 내용 | 상태 |
|-------|------|------|
| Phase 1 | 기본 예약·관리 HTML/JS (localStorage) | ✅ 완료 |
| Phase 2 | 플랫폼 구조 리팩터링, 대시보드 신설 | ✅ 완료 |
| Phase 3 | Google Workspace 어댑터, 데이터소스 전환 | ✅ 완료 |
| Phase 4 | Apps Script Web App 연동 구조 | ✅ 완료 |
| **Phase 4.5** | **운영 DB 컬럼 확장 (29개), ERD·Workflow·구조도** | ✅ 완료 |
| Phase 5 | 실 배포·인증, HIS 연동, 카카오 알림톡, 통계 고도화 | 예정 |

---

*CMC Health Screening Platform v1.0 Phase 4.5 | 2026-07-01 | 천안의료원 건강검진센터*
