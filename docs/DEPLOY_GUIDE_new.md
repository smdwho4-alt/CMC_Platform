# CMC Health Screening Platform — 운영 배포 가이드

작성일: 2026-07-07 | **현행화: Sprint7 Commit7-4(2026-07-29)** | 대상: 초보자도 따라할 수 있는 단계별 절차

> **Sprint7 Commit7-4 현행화 안내**: 이 문서는 Sprint2~6(Admin Portal, FastAPI 예약 승인/Slot/Policy, Legacy Guard) 반영 전(Sprint H 무렵) 작성됐다. 이번 갱신에서 실제 코드와 대조해 파일명·버전 표기 오류를 바로잡고, FastAPI/Regression/Rollback 관련 절차를 추가했다. Netlify 배포·GAS 배포 버튼 조작 절차 자체(§2/§4)는 여전히 유효해 그대로 유지한다.

---

## 목차

1. [사전 준비 체크리스트](#1-사전-준비-체크리스트)
2. [Google Apps Script 배포 절차](#2-google-apps-script-배포-절차)
3. [FastAPI Backend 운영 환경](#3-fastapi-backend-운영-환경)
4. [대시보드/Portal URL 연결 방법](#4-대시보드portal-url-연결-방법)
5. [Netlify 운영 환경 배포](#5-netlify-운영-환경-배포)
6. [배포 후 검증(Smoke Test·Regression)](#6-배포-후-검증smoke-testregression)
7. [Pilot 테스트 절차](#7-pilot-테스트-절차)
8. [오류 발생 시 중단 기준 및 Rollback](#8-오류-발생-시-중단-기준-및-rollback)
9. [배포 완료 보고 형식](#9-배포-완료-보고-형식)
10. [트러블슈팅](#10-트러블슈팅)

---

## 0. 배포 단계 구분(중요)

아래 5단계는 **서로 다른 승인·위험 수준**을 갖는다. 혼동하지 않도록 항상 구분해서 진행한다.

| 단계 | 내용 | 필요 승인 |
|---|---|---|
| **로컬 검증** | 자신의 PC/개발 서버에서 코드 동작 확인, Regression 실행 | 불필요(단, 운영 데이터 접근 시 주의) |
| **Git Push** | `git push`로 원격 저장소 반영 | **PM 명시적 승인 필수**(ADR-012) |
| **Netlify Deploy** | 정적 파일(Portal HTML/JS) 배포 | PM 승인 필수 |
| **GAS Deploy** | Apps Script 새 버전 배포(Google Sheets 연동) | PM 승인 필수, Google 계정 인증 필요(에이전트가 대신 수행 불가) |
| **운영 데이터 확인** | 실제 Google Sheets 데이터 조회/검증 | 조회만 가능, 수정은 별도 승인 필요 |

---

## 1. 사전 준비 체크리스트

배포 전 아래 항목을 모두 확인하세요.

| # | 항목 | 확인 |
|---|------|------|
| 1 | Google 계정 로그인 상태 (병원 계정 권장) | ☐ |
| 2 | Google Sheets 예약대장 파일 열기 가능 | ☐ |
| 3 | Netlify 계정 생성 완료 (netlify.com) | ☐ |
| 4 | GitHub 계정 및 저장소 접근 가능 | ☐ |
| 5 | 배포 대상 Apps Script 파일 확인(§2-0 참조 — 두 개의 파일 중 어느 것을 쓸지 확인) | ☐ |
| 6 | FastAPI 운영 서버 실행 환경 확보(§3 참조) | ☐ |
| 7 | 공식 Baseline Commit 확인(`production_checklist.md` ① 참조) | ☐ |

---

## 2. Google Apps Script 배포 절차

### 2-0. ⚠ 배포 대상 파일 확인(중요, Sprint7 Commit7-4에서 정정)

저장소에는 GAS 파일이 **두 개** 존재한다.

| 파일 | 상태 |
|---|---|
| `app/apps_script/sheets_api_v3_final.gs` | **실제 현재 운영 배포본으로 확인됨**(`ARCHITECTURE.md` "현재 배포본" 명시, Sprint4~7 전체 작업이 이 파일 기준) |
| `app/apps_script/sheets_api_v4_deploy_new.gs` | v3와 핵심 로직은 동일(파일 자체 헤더에 "v3와 동일, 변경 없음"으로 명시)하나 CONFIG 블록 재구성 등 배포 편의 기능 추가된 별도 버전. **실제 배포에 쓰였는지 이 세션에서 확인되지 않음** |

**이 가이드의 이전 버전은 v4를 기준으로 작성돼 있었으나, 실제 운영 중인 파일은 v3다.** 아래 절차는 **v3 기준으로 정정**했다. v4로 전환할지 여부는 이번 현행화 범위 밖의 별도 결정 사항이다(Decision Required — GAS 코드 변경은 이번 Commit 절대 금지 항목).

### 2-1. Apps Script 프로젝트 열기

1. Google Sheets 예약대장 열기(URL은 운영 환경변수/내부 문서로 별도 관리 — 이 가이드에 기록하지 않음)
2. 상단 메뉴 → **확장 프로그램** → **Apps Script** 클릭
3. Apps Script 편집기가 새 탭에서 열림

> **또는** 기존 독립형 스크립트가 있는 경우: [script.google.com](https://script.google.com) → 기존 프로젝트 선택

---

### 2-2. 코드 붙여넣기

1. 편집기 좌측에 `Code.gs` 파일이 보임
2. `Code.gs` 클릭 → 기존 코드 **전체 선택(Ctrl+A)** → **삭제**
3. `app/apps_script/sheets_api_v3_final.gs` 파일 내용 **전체 복사**(§2-0 확인 후 v3 사용을 권장)
4. 편집기에 **붙여넣기(Ctrl+V)**
5. **Ctrl+S** 또는 상단 💾 아이콘 클릭 → 저장

---

### 2-3. CONFIG 블록 확인

`sheets_api_v3_final.gs` 상단 근처에서 아래 값을 확인한다(실제 값은 이 문서에 기록하지 않음 — 변수명만 표기).

- `SPREADSHEET_ID` — Google Sheets URL에서 `/d/`와 `/edit` 사이 문자열. **실제 값을 문서/커밋 메시지/채팅에 남기지 않는다.**
- `SHEET_NAME` — 시트 하단 탭 이름과 정확히 일치해야 함(현재 확인된 값: `종합검진_예약대장`)
- 개인정보 포함 여부 관련 설정 — 목록 조회 응답에 연락처·생년월일이 포함되지 않도록 유지(FastAPI 측 `pii_mask.py`와 별개로 GAS 자체에서도 확인)

---

### 2-4. 웹 앱 배포

**이 단계가 가장 중요합니다. 순서를 정확히 따르세요.**

1. Apps Script 편집기 상단 → **배포** 버튼 클릭
2. **새 배포** 선택(⚠ **기존 배포 편집이 아니라 반드시 "새 버전"** — 과거 "기존 버전 재사용"으로 STEP1.5 DateFix 수정이 실제 반영되지 않은 사고가 있었다, `PROJECT_STATUS.md` §2 참조)
3. **유형 선택** → 톱니바퀴 아이콘 클릭 → **웹 앱** 선택
4. 설명 입력(예: "CMC Platform API 운영배포 — 배포일자·변경요약 기재")
5. 설정값 입력:

   | 항목 | 값 |
   |------|-----|
   | 다음 사용자로 실행 | **나(본인 Google 계정)** |
   | 액세스 권한 | **⛔ 반드시 "조직 내" 또는 "나만"으로 설정** — "모든 사용자"로 설정 시 URL을 아는 누구나 예약 데이터를 조회·수정할 수 있다(GAS `doGet`/`doPost`에 자체 인증이 없음, `production_checklist.md` ⑤ 참조). 내부망 운영 원칙과 맞지 않으면 반드시 재검토 |

6. **배포** 버튼 클릭
7. **권한 부여** 팝업이 뜨면: **권한 검토** → 본인 Google 계정 선택 → **고급** → **'안전하지 않은 페이지'로 이동**(정상 메시지) → **허용**
8. 배포 완료 후 **웹 앱 URL**을 복사해 **서버 환경변수(`CSHSP_GAS_WEBAPP_URL`)로만 저장** — 문서·커밋·채팅에 URL 원문을 남기지 않는다

---

### 2-5. 배포 확인 (ping 테스트)

브라우저 주소창에 `[웹앱URL]?action=ping` 입력. **정상 응답(v3 기준, 실제 코드로 확인)**:

```json
{
  "ok": true,
  "data": {
    "message": "CMC Sheets API v3 정상",
    "sheetName": "종합검진_예약대장",
    "totalCols": 29
  }
}
```

이 응답이 보이면 배포 성공입니다.

---

## 3. FastAPI Backend 운영 환경

이전 버전 가이드에는 이 섹션이 없었다(Admin Portal/예약 승인 API 도입 이전 작성). Sprint4~6에서 신설된 FastAPI 기반 예약 승인/Slot/Policy 기능을 운영하려면 아래를 갖춰야 한다.

### 3-1. 서버 기동

`process_manager.md` 참조 — `python -m uvicorn src.api.api_server:app --host 127.0.0.1 --port 8600`, Windows에서는 NSSM으로 서비스 등록 권장.

### 3-2. 필수 환경변수

| 변수 | 필수 | 설명 |
|---|:---:|---|
| `CSHSP_GAS_WEBAPP_URL` | **필수**(승인/거절 API가 이 값 없이는 503 반환) | §2-4에서 배포한 GAS Web App URL. **실제 값은 서버 환경변수로만 설정, 문서 기록 금지** |
| `CSHSP_DATA_DIR` | 권장 | 로컬 JSON 데이터 폴더(`Patient`/`CRM`/`AuditLog` 등 Reservation 외 Entity, ADR-013) |
| `ANTHROPIC_API_KEY` | 선택 | AI 채팅 기능용, 값 기록 금지(기존 `process_manager.md` 원칙 그대로 유지) |

### 3-3. Health Check

`GET /api/admin-portal/health` — Sheets 연동 상태(`connected`/`not_configured`/`error`) 확인. `not_configured`면 `CSHSP_GAS_WEBAPP_URL` 미설정을 의심한다.

---

## 4. 대시보드/Portal URL 연결 방법

### 4-1. Admin Portal(현재 서비스 중)

`app/pages/admin_portal_new.html`은 `?api=` 쿼리 파라미터로 API 서버 주소를 지정한다(기본값 `http://localhost:8600`). 별도 파일 수정 없이 `admin_portal_new.html?api=https://your-api-domain` 형태로 접속하면 된다(코드로 확인, `API_ROOT` 변수).

### 4-2. Reservation Portal / Legacy Portal(config_v2_new.js 경유)

`reservation_v3_new.html`(수검자 예약 폼)과 `admin_reservations_v2_new.html`(Legacy Portal)은 `app/config_v2_new.js`에서 GAS 연동을 설정한다.

```javascript
const CMC_CONFIG = {
  dataSource: 'google',          // 'local' → 'google' 으로 변경 시 Sheets 연동
  appsScript: {
    webAppUrl: '[여기에 실제 URL — 문서에는 기록하지 않음]',
  },
};
```

> **주의**: 이 파일은 Reservation Portal과 Legacy Portal이 **함께 사용**한다(코드로 확인) — 수정 시 두 화면 모두에 영향을 준다.
> **⚠ `dataSource: 'google'`로 설정하고 실제 운영 URL을 넣으면, 이 파일이 커밋된 저장소를 통해 URL이 노출될 수 있다** — 저장소 접근 권한을 반드시 확인할 것(§8, `production_checklist.md` ⑤ 참조).

### 4-3. (참고, 레거시) admin_dashboard_new_v2.html

이 화면은 `app/services/dashboard_sheets_service_new.js`를 통해 별도로 Sheets에 연동하는 **더 오래된 대시보드**다. 현재 운영 중인 화면은 §4-1의 **Admin Portal(`admin_portal_new.html`)**이며, `admin_dashboard_new_v2.html`은 Sprint2(Dashboard v3) 트랙의 산물로 여전히 파일은 존재하나 이 가이드의 주 대상이 아니다. 두 화면을 혼동하지 않는다.

---

## 5. Netlify 운영 환경 배포

### 5-1. 현재 netlify.toml 확인 (Commit8-2d에서 Publish Boundary 도입, 정정)

**저장소 전체(`publish="."`)를 게시하던 이전 방식은 Commit8-2d에서 폐기됐다** —
`src/`(백엔드 인증 소스), `tests/`, `docs/`, `tools/`, ADR·Threat Model 등 내부
문서까지 정적 게시 대상에 포함되는 구조적 노출 위험이 있었기 때문이다(상세:
Commit8-2c/8-2d 감사 이력). 현재는 `build_public_new.py`(저장소 루트)가 운영에
필요하다고 확인된 파일만 명시적으로 `public/`에 복사하는 **허용목록(Allowlist)
방식**이며, `public/`만 게시된다.

프로젝트 루트의 `netlify.toml`:

```toml
[build]
  command = "python3 build_public_new.py"
  publish = "public"

[[redirects]]
  from = "/"
  to = "/pages/admin_dashboard_new.html"
  status = 302
```

`app/apps_script/`(GAS 소스), `app/docs/`(내부 참고문서)는 `build_public_new.py`의
허용목록에 없어 애초에 `public/`에 복사되지 않는다 — 별도 차단 규칙에 의존하지
않는다. `src/`, `tests/`, `docs/`, `tools/`, `data/` 등도 동일한 이유로 게시되지
않는다. 허용목록 상세와 설계 근거는 Commit8-2d STEP1/STEP2 기록을 참조.

### 5-2. GitHub 연동 배포(권장)

1. **GitHub 저장소 준비**(⛔ PM 승인 후에만 push): `git push -u origin main`
2. **Netlify 사이트 생성**: netlify.com 로그인 → **Add new site** → **Import an existing project** → GitHub 저장소 선택 → Build 설정(Base directory 비움, Build command `python3 build_public_new.py`, Publish directory `public`) → **Deploy site**
3. **배포 완료 확인**: Netlify가 자동 URL 발급, 이후 GitHub main 브랜치 push 시 자동 재배포(단, Auto Publishing이 Locked 상태면 Push만으로는 실제 게시되지 않으며 PM 등 권한자가 관리화면에서 수동으로 Publish를 승인해야 한다)
4. **Deploy Preview vs Production**: PR/브랜치 기반 Deploy Preview는 운영 URL과 분리된 별도 URL로 생성되어 운영에 영향을 주지 않는다. Production Deploy(운영 URL 반영)는 이와 별개로, Auto Publishing Locked 상태에서는 PM의 수동 승인 없이는 발생하지 않는다.

### 5-3. webAppUrl을 운영 환경에 반영하는 방법

**방법 A(권장)**: `app/config_v2_new.js`를 직접 수정 후 `git push` — 단, §4-2의 경고대로 저장소를 **Private**으로 설정.
**방법 B**: Netlify 환경변수 사용(URL을 소스에 노출하지 않을 경우) — 정적 사이트라 별도 빌드 도구 없이는 주입이 번거로움, 방법 A가 더 간단함이 이미 확인됨.

### 5-4. CORS 확인

```
GET 요청(URLSearchParams): simple request → CORS 불필요 → 정상 동작
POST 요청(Content-Type 미설정): simple request → CORS 불필요 → 정상 동작
POST 요청(Content-Type: application/json): preflight → GAS 미지원 → 실패
```

기존 서비스 파일(`google_sheets_service_v2_new.js` 등)은 이미 GET+URLSearchParams 또는 Content-Type 미설정 방식을 사용하므로 추가 CORS 설정 불필요(코드로 확인).

---

## 6. 배포 후 검증(Smoke Test·Regression)

이전 버전 가이드에는 Backend Regression 절차가 없었다(FastAPI 예약 승인 기능 도입 이전 작성). 아래를 배포 직후 반드시 수행한다.

1. **Smoke Test**: §2-5(GAS ping), §3-3(FastAPI health) 둘 다 정상 확인
2. **Regression**: `production_checklist.md` ②에 나열된 스위트 재실행, 전부 PASS 확인(코드/설정을 바꾸지 않았다면 배포 전 로컬에서 이미 확인된 결과를 인용해도 되나, GAS를 재배포했다면 반드시 재확인)
3. **Admin Portal 실사용 확인**: `production_checklist.md` ③ 체크리스트 수행
4. **Legacy Portal 확인**: 동일 문서 ④ — 특히 "예약확정 차단"이 여전히 동작하는지(GAS 재배포 시 회귀 가능성 있음, 클라이언트 가드는 GAS와 무관하지만 GAS 응답 형식이 바뀌면 영향 가능)

---

## 7. Pilot 테스트 절차

### 7-1. 테스트 환경 설정

| 항목 | 설정값 |
|------|--------|
| 테스트 시트 | 기존 `종합검진_예약대장` 시트에 테스트 데이터 입력 |
| 테스트 브라우저 | Chrome(시크릿 창 권장) |
| 개인정보 | 실제 환자 정보 사용 금지 — 가상 데이터만 사용 |

### 7-2. 단계별 테스트 시나리오

1. GAS API 연결 확인(§2-5)
2. 예약 등록 → Sheets 저장 확인: **`reservation_v3_new.html`**(현재 서비스 중인 예약 폼, 과거 `reservation_form_new.html`은 저장소에 존재하지 않는 파일명이었음 — 이번에 정정)에서 가상 데이터 입력 → 제출 → Sheets 행 추가 확인
3. Admin Portal에서 방금 등록한 예약이 조회되는지 확인
4. Admin Portal에서 승인 → Slot 점유 확인 → Legacy Portal에서 예약확정 재선택 시도 → 차단 확인(§2-0/`production_checklist.md` ④)

### 7-3. 테스트 완료 기준(Go/No-Go)

| # | 항목 | 기준 |
|---|------|------|
| 1 | GAS ping 응답 | `ok: true` |
| 2 | 예약 등록 → Sheets 저장 | 예약번호 채번 정상 |
| 3 | FastAPI Health | `connected` |
| 4 | Admin Portal 승인/거절 | 정상 동작, 오류 메시지 정상 표시 |
| 5 | Legacy Portal 예약확정 차단 | 차단 확인 |
| 6 | 개인정보 보호 | 목록 응답에 phone·birth 미노출 |

모든 항목 Pass 시 → **운영 배포 승인**(단, PM 최종 승인 별도 필요)

### 7-4. 테스트 데이터 정리

Pilot 테스트 완료 후 Sheets에서 테스트 데이터 행 삭제 — 예약번호가 테스트 날짜로 시작하는 행 선택 후 삭제(⚠ 이 작업은 운영 Sheets 데이터 변경이므로 별도 승인 절차를 따른다).

---

## 8. 오류 발생 시 중단 기준 및 Rollback

| 상황 | 중단 기준 | 대응 |
|---|---|---|
| GAS ping 실패 | 즉시 중단 | §2 재확인, 재배포하지 않고 원인 파악 우선 |
| FastAPI Health `error` | 즉시 중단 | §3-2 환경변수 재확인 |
| Regression FAIL 발생 | 즉시 중단, 배포하지 않음 | 실패 원인 분석, 회귀 여부 확인 |
| 배포 후 Admin Portal 승인 실패 다발 | 배포 중단, 이전 상태로 Rollback 검토 | GAS 재배포 이력 확인(이전 버전으로 재배포 가능한지) |

**⛔ 독립된 Rollback 절차 문서는 아직 없다**(Sprint7 Commit7-5에서 작성 예정, `Operation_Readiness_Assessment_v1.0.md` Gap #5). 현재 가능한 조치: Git 커밋 되돌리기(코드), GAS "배포 관리"에서 이전 버전으로 재배포(수동, Google 계정 인증 필요). Sheets 데이터 자체의 Rollback 절차는 문서화되지 않았다 — Commit7-5까지는 신중히 접근하고 사전에 Sheets 데이터를 확인해 둘 것을 권장한다.

---

## 9. 배포 완료 보고 형식

배포 담당자는 아래 형식으로 기록을 남긴다(양식 신설, 이전 버전에는 없었음).

```
배포일시:
배포자:
공식 Baseline Commit:
변경 요약(무엇이 바뀌었는지, Release Note 링크):
GAS 재배포 여부(했다면 새 버전 번호):
Smoke Test 결과(§6):
Regression 결과(PASS/FAIL 건수):
이상 발생 여부:
PM 승인자:
```

---

## 10. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| ping 응답 없음 | GAS 미배포 또는 URL 오류 | §2 재배포, URL 재확인(단, URL을 문서에 남기지 않는다) |
| `{"ok":false}` | 스프레드시트 접근 권한 없음 | Sheets 공유 설정에서 '편집자' 추가 |
| FastAPI Health `not_configured` | `CSHSP_GAS_WEBAPP_URL` 미설정 | §3-2 확인 |
| Admin Portal 오류 메시지가 부정확 | Portal Error Contract 문제 가능성 | `parseApiError()` 관련 회귀 여부 확인(Commit5-3.1/5-3.2) |
| 콘솔에 CORS 에러 | POST에 `Content-Type: application/json` 설정됨 | fetch body 전송 시 Content-Type 헤더 제거 |
| 예약번호 중복 | 동시 등록 충돌 | GAS LockService가 자동 처리(503 → 재시도) |
| Netlify 404 | publish directory 설정 오류 | `netlify.toml`의 publish를 `.`으로 설정 |
| Legacy Portal에서 "예약확정" 차단이 안 됨 | `admin_reservations_v2_new.html` 회귀 가능성 | Commit6-1 가드 코드(`approvalBlocked`) 존재 여부 확인 |

---

## 부록 — 파일 역할 요약(Sprint7 Commit7-4에서 정정)

| 파일 | 역할 | 비고 |
|------|------|------|
| `app/apps_script/sheets_api_v3_final.gs` | **실제 운영 배포본**(GAS) | ARCHITECTURE.md에서 확인됨 |
| `app/apps_script/sheets_api_v4_deploy_new.gs` | v3와 핵심 로직 동일한 별도 패키징(실사용 여부 미확인) | §2-0 참조 |
| `app/config_v2_new.js` | Reservation Portal·Legacy Portal의 webAppUrl/dataSource 설정 공유 | §4-2 |
| `app/services/google_sheets_service_v2_new.js` | Reservation/Legacy Portal이 사용하는 Sheets 어댑터 | 현재 서비스 중 |
| `app/services/dashboard_sheets_service_new.js` | 구 대시보드(`admin_dashboard_new_v2.html`) 전용 어댑터 | 레거시, §4-3 |
| `app/pages/admin_portal_new.html` | **현재 서비스 중인 Single Admin Portal** | §4-1 |
| `app/pages/reservation_v3_new.html` | **현재 서비스 중인 수검자 예약 폼** | 과거 문서의 `reservation_form_new.html`은 존재하지 않는 파일명이었음(정정) |
| `app/pages/admin_reservations_v2_new.html` | Legacy Portal(예약변경/취소/검진완료 담당, 예약확정은 차단됨) | §4-2 |
| `netlify.toml` | Netlify 배포 설정 | §5 |

---

*이 가이드로 해결되지 않는 문제는 `docs/CSHSP_Failure_Response_Manual.md` 참조.*
