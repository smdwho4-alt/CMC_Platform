# CMC Health Screening Platform v1.0 — Phase 4 README

> **Phase 4**: Google Apps Script 방식 실제 연동 구조 추가  
> Phase 1 · 2 · 3 파일은 모두 유지됨 — 기존 파일 삭제 없음

---

## Phase 4 신규 파일

| 파일 | 설명 |
|------|------|
| `app/apps_script/sheets_api_new.gs` | Google Apps Script — Sheets Web App API 서버 |
| `app/services/google_sheets_service_v2_new.js` | Sheets 어댑터 v2 (Apps Script URL 방식) |
| `app/config_v2_new.js` | 설정 v2 (Apps Script Web App URL 항목 추가) |
| `README_platform_v3_new.md` | 이 문서 |

---

## 전체 파일 구조 (Phase 1~4 누적)

```
CMC_Platform_new/
├── index.html
├── app/
│   ├── config_new.js                           ← [Phase 3] GWS 직접 API 설정 (보존)
│   ├── config_v2_new.js                        ← [Phase 4] Apps Script 설정 ★
│   ├── apps_script/
│   │   └── sheets_api_new.gs                   ← [Phase 4] Apps Script 서버 ★
│   ├── pages/
│   │   ├── admin_dashboard_new.html            ← [Phase 2] 보존
│   │   ├── admin_dashboard_v2_new.html         ← [Phase 3] GWS 전환 포함 (보존)
│   │   ├── reservation_new.html
│   │   └── admin_reservations_new.html
│   ├── components/
│   │   └── nav_new.js
│   ├── services/
│   │   ├── db_service_new.js
│   │   ├── stats_service_new.js
│   │   ├── google_sheets_service_new.js        ← [Phase 3] 직접 API 방식 (보존)
│   │   ├── google_sheets_service_v2_new.js     ← [Phase 4] Apps Script 방식 ★
│   │   ├── calendar_service_new.js
│   │   └── gmail_service_new.js
│   ├── data/
│   │   ├── programs_data_new.js
│   │   └── sample_data_new.js
│   └── styles/
│       ├── main_style_new.css
│       └── dashboard_style_new.css
├── README_platform_new.md                      ← [Phase 2] 보존
├── README_platform_v2_new.md                   ← [Phase 3] 보존
└── README_platform_v3_new.md                   ← [Phase 4] 이 문서
```

---

## Google Sheets 연동 구조 (Phase 4)

```
브라우저 (JS)
    │
    │  fetch POST/GET
    ▼
Apps Script Web App (sheets_api_new.gs)
    │
    │  SpreadsheetApp API
    ▼
Google Sheets — '예약현황' 시트
```

Phase 3의 직접 Sheets API v4 방식과 달리, 클라이언트에서 OAuth 토큰이 불필요.  
Apps Script가 서비스 계정 권한으로 Sheets에 접근하므로 보안 측면에서 권장.

---

## Google Apps Script 배포 방법

### 1단계 — 스크립트 프로젝트 생성

```
1. https://script.google.com 접속
2. [새 프로젝트] 클릭
3. 프로젝트 이름: "CMC 예약관리 API" 등으로 설정
4. sheets_api_new.gs 내용 전체를 편집기에 붙여넣기
5. [저장] (Ctrl+S)
```

### 2단계 — Sheets 연결

```
1. Apps Script 편집기에서 [서비스] → [+] → Google Sheets API 추가
   (대부분의 경우 SpreadsheetApp은 별도 추가 불필요)
2. 스크립트 파일 상단 SHEET_NAME = '예약현황' 확인
3. 연결할 Google Sheets를 미리 생성 (시트명: 예약현황)
4. 스크립트를 해당 Sheets에서 열면 자동 바인딩됨:
   Google Sheets > 확장 프로그램 > Apps Script
```

### 3단계 — 웹 앱 배포 및 URL 발급

```
Apps Script 편집기 > [배포] > [새 배포]
→ 유형 선택: 웹 앱
→ 설명: "CMC 예약 API v1"
→ 다음 사용자로 실행: 나 (또는 서비스 계정)
→ 액세스 권한:
    ▶ 개발·테스트: 모든 사람 (익명 포함)
    ▶ 운영:        조직 내부 사용자 또는 나만  ← 권장
→ [배포] 클릭
→ 웹 앱 URL 복사 (형식: https://script.google.com/macros/s/.../exec)
```

> **중요**: URL을 외부에 노출하지 말 것.  
> URL만 알면 누구나 데이터 접근 가능(액세스 권한이 '모든 사람'인 경우).

### 4단계 — 헤더 행 초기화 (최초 1회)

```
Apps Script 편집기에서 아래 함수를 직접 실행:
→ 함수 선택: _initHeader
→ [실행] 클릭

또는 doGet?action=ping 으로 첫 요청 시 자동 초기화
```

### 5단계 — Google Sheets 컬럼 구조 확인

시트 `예약현황` 의 1행(헤더):

| A | B | C | D | E | F | G | H | I | J | K | L | M | N | O | P | Q | R |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 예약번호 | 접수일시 | 성명 | 생년월일 | 연락처 | 성별 | 검진프로그램 | 희망검진일 | 희망시간 | 수면 | 선택검사 | 사업장 | 예약경로 | 담당자 | 예약상태 | 예약확정일 | 문자발송 | 특이사항 |

---

## Web App URL 연결 방법

### config_v2_new.js 에 URL 입력

```javascript
const CMC_CONFIG = {
  appsScript: {
    webAppUrl: 'https://script.google.com/macros/s/[SCRIPT_ID]/exec',
    sheetName: '예약현황',
    timezone:  'Asia/Seoul',
  },
  // ...
};
```

> 실제 운영 시 URL을 코드에 직접 입력하지 않고,  
> 서버사이드 환경변수 또는 별도 설정 파일(gitignore 대상)로 관리할 것.

### HTML 페이지에서 스크립트 로드 순서

```html
<!-- 기존 스크립트 이후 추가 -->
<script src="../config_v2_new.js"></script>
<script src="../services/google_sheets_service_v2_new.js"></script>
```

---

## 테스트 방법

### A. Apps Script URL 직접 테스트 (브라우저)

```
# 연결 확인
https://script.google.com/macros/s/[SCRIPT_ID]/exec?action=ping

# 예약 목록 조회
https://script.google.com/macros/s/[SCRIPT_ID]/exec?action=list

# 상태 필터 조회
https://script.google.com/macros/s/[SCRIPT_ID]/exec?action=list&status=예약접수
```

### B. 브라우저 콘솔에서 테스트

```javascript
// 1. config 설정 (URL 입력 후)
CMC_CONFIG.load();
CMC_CONFIG.appsScript.webAppUrl = 'https://script.google.com/macros/s/.../exec';

// 2. 연결 테스트
await CMC_SheetsServiceV2.ping();
// → { ok: true, mode: 'live', message: 'Apps Script 연결 성공 ...' }

// 3. 전체 목록 조회
const result = await CMC_SheetsServiceV2.getAll();
console.log(result.data.length + '건 조회');

// 4. 예약 등록
await CMC_SheetsServiceV2.create({
  name: '홍길동', birth: '1980-01-01', phone: '010-0000-0000',
  gender: '남', program: 'BASIC', wishDate: '2026-07-15',
  wishTime: '09:00', sleep: '미선택', status: '예약접수',
});

// 5. 상태 변경
await CMC_SheetsServiceV2.updateStatus('20260701-0001', '예약확정');
```

### C. Mock 모드 테스트 (Apps Script URL 없이)

```javascript
// dataSource가 'local'이면 Mock 동작
CMC_CONFIG.dataSource = 'local';
const r = await CMC_SheetsServiceV2.getAll();
// → Mock: localStorage에서 조회
```

---

## 개인정보 운영 전 주의사항

| 항목 | 위험 | 권장 조치 |
|------|------|----------|
| **Apps Script Web App URL** | URL 노출 시 무단 접근 가능 | 액세스 권한 '조직 내' 제한, URL gitignore 처리 |
| **연락처·생년월일** | Sheets에 평문 저장 | Sheets 공유 설정 '제한됨' (특정 계정만), HTTPS 필수 |
| **문자 발송 여부** | 문자발송 컬럼 자동 기록 | 발송 결과는 담당자만 확인 가능하도록 접근 제어 |
| **예약확정일 자동 기록** | 타임스탬프가 개인 활동 증적 | 보존 기간 정책 수립 (개인정보처리방침 반영) |
| **localStorage** | 시제품 — 브라우저에 데이터 잔존 | 운영 시 세션 종료 후 localStorage 정리 로직 추가 |
| **관리자 접근** | 현재 로그인 없음 | 운영 전 관리자 인증(Google 계정 또는 자체 로그인) 필수 |

> **v1.0은 시제품입니다.**  
> 실제 수검자 개인정보를 다루는 운영 환경에서는 반드시:  
> 1. HTTPS 적용  
> 2. 관리자 인증 구현  
> 3. 개인정보처리방침 수립 및 고지  
> 4. 데이터 보존 기간 설정  
> 5. 보안 담당자 지정

---

## 예약번호 자동 생성 규칙

```
형식: YYYYMMDD-NNNN
예시: 20260701-0001

- Apps Script 서버에서 당일 기존 예약번호를 조회 후 최대값 +1
- 일자가 변경되면 순번이 0001부터 재시작
- 동시 등록 시 중복 방지: AppScript의 단일 스레드 특성 활용
```

---

## Phase 로드맵

| Phase | 내용 | 상태 |
|-------|------|------|
| Phase 1 | 기본 예약·관리 HTML/JS (localStorage) | ✅ 완료 |
| Phase 2 | 플랫폼 구조 리팩터링, 대시보드 신설 | ✅ 완료 |
| Phase 3 | Google Workspace 어댑터, 데이터소스 전환 | ✅ 완료 |
| **Phase 4** | **Apps Script Web App 연동 구조** | ✅ 완료 |
| Phase 5 | 실제 배포·인증, HIS 연동, 카카오 알림톡 | 예정 |

---

*CMC Health Screening Platform v1.0 Phase 4 | 2026-07-01 | 천안의료원 건강검진센터*
