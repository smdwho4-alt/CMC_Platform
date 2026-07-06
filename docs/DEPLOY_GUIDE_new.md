# CMC Health Screening Platform — 운영 배포 가이드

작성일: 2026-07-07 | 버전: v4.0 | 대상: 초보자도 따라할 수 있는 단계별 절차

---

## 목차

1. [사전 준비 체크리스트](#1-사전-준비-체크리스트)
2. [Google Apps Script 배포 절차](#2-google-apps-script-배포-절차)
3. [대시보드 URL 연결 방법](#3-대시보드-url-연결-방법)
4. [Netlify 운영 환경 배포](#4-netlify-운영-환경-배포)
5. [Pilot 테스트 절차](#5-pilot-테스트-절차)
6. [트러블슈팅](#6-트러블슈팅)

---

## 1. 사전 준비 체크리스트

배포 전 아래 항목을 모두 확인하세요.

| # | 항목 | 확인 |
|---|------|------|
| 1 | Google 계정 로그인 상태 (병원 계정 권장) | ☐ |
| 2 | Google Sheets 예약대장 파일 열기 가능 | ☐ |
| 3 | Netlify 계정 생성 완료 (netlify.com) | ☐ |
| 4 | GitHub 계정 및 저장소 접근 가능 | ☐ |
| 5 | `sheets_api_v4_deploy_new.gs` 파일 내용 복사 준비 | ☐ |

---

## 2. Google Apps Script 배포 절차

### 2-1. Apps Script 프로젝트 열기

1. [Google Sheets 예약대장](https://docs.google.com/spreadsheets/d/1WFnsyeBpHVhG5IgZ--3T00jCe-FPUMJdgWl4m120nuU/edit) 열기
2. 상단 메뉴 → **확장 프로그램** → **Apps Script** 클릭
3. Apps Script 편집기가 새 탭에서 열림

> **또는** 기존 독립형 스크립트가 있는 경우:
> [script.google.com](https://script.google.com) → 기존 프로젝트 선택

---

### 2-2. 코드 붙여넣기

1. 편집기 좌측에 `Code.gs` 파일이 보임
2. `Code.gs` 클릭 → 기존 코드 **전체 선택(Ctrl+A)** → **삭제**
3. `app/apps_script/sheets_api_v4_deploy_new.gs` 파일 내용 **전체 복사**
4. 편집기에 **붙여넣기(Ctrl+V)**
5. **Ctrl+S** 또는 상단 💾 아이콘 클릭 → 저장

---

### 2-3. CONFIG 블록 확인

코드 상단 CONFIG 블록(★★★ 표시 구간)에서 아래 3가지만 확인:

```javascript
const SPREADSHEET_ID     = '1WFnsyeBpHVhG5IgZ--3T00jCe-FPUMJdgWl4m120nuU'; // ← 현재 시트 ID
const SHEET_NAME         = '종합검진_예약대장';                               // ← 시트 탭 이름
const INCLUDE_PII_IN_LIST = false;                                           // ← 개인정보 포함 여부
```

- **SPREADSHEET_ID**: Google Sheets URL에서 `/d/` 와 `/edit` 사이의 긴 문자열
- **SHEET_NAME**: 시트 하단 탭에 표시된 이름과 정확히 일치해야 함
- **INCLUDE_PII_IN_LIST**: `false` 유지 (대시보드에 연락처·생년월일 미표시)

---

### 2-4. 웹 앱 배포

**이 단계가 가장 중요합니다. 순서를 정확히 따르세요.**

1. Apps Script 편집기 상단 → **배포** 버튼 클릭
2. **새 배포** 선택

   ![배포 메뉴](./assets/deploy_menu.png) ← (실제 화면 참고)

3. **유형 선택** → 톱니바퀴 아이콘 클릭 → **웹 앱** 선택

4. 설명 입력: `CMC Platform API v4.0 운영배포`

5. 설정값 입력:

   | 항목 | 값 |
   |------|-----|
   | 다음 사용자로 실행 | **나(본인 Google 계정)** |
   | 액세스 권한 | **모든 사용자** ← Netlify에서 호출하려면 필수 |

   > **보안 주의**: '모든 사용자' 설정 시 URL을 아는 누구나 API를 호출할 수 있습니다.
   > URL이 외부에 노출되지 않도록 관리하세요.
   > 내부망 전용이라면 '조직 내'로 설정하세요.

6. **배포** 버튼 클릭

7. **권한 부여** 팝업이 뜨면:
   - **권한 검토** 클릭
   - 본인 Google 계정 선택
   - **고급** 클릭 → **'안전하지 않은 페이지'로 이동** 클릭 ← (이 메시지는 정상)
   - **허용** 클릭

8. 배포 완료 후 **웹 앱 URL** 복사

   ```
   예시: https://script.google.com/macros/s/AKfycby.../exec
   ```

   이 URL을 안전한 곳에 보관하세요.

---

### 2-5. 배포 확인 (ping 테스트)

브라우저 주소창에 아래 URL 입력:

```
[웹앱URL]?action=ping
```

정상 응답:
```json
{
  "ok": true,
  "apiVersion": "4.0",
  "data": {
    "message": "CMC Sheets API v4.0 정상",
    "sheetName": "종합검진_예약대장",
    "totalCols": 29
  }
}
```

이 응답이 보이면 배포 성공입니다.

---

## 3. 대시보드 URL 연결 방법

### 3-1. config_v2_new.js에서 설정

파일 위치: `app/config_v2_new.js`

```javascript
const CMC_CONFIG = {
  dataSource: 'google',          // ← 'local' → 'google' 으로 변경
  appsScript: {
    webAppUrl: 'https://script.google.com/macros/s/[여기에_URL]/exec', // ← 복사한 URL 입력
  },
  // ...
};
```

> **주의**: `dataSource: 'google'`으로 변경해야 Sheets 데이터를 읽습니다.
> `'local'`이면 localStorage 데이터를 사용합니다 (테스트 모드).

---

### 3-2. 브라우저에서 URL 임시 설정 (파일 수정 없이 테스트)

`admin_dashboard_new_v2.html`을 브라우저에서 연 후 **F12(개발자 도구) → 콘솔** 에서 실행:

```javascript
// URL 설정 및 저장 (새로고침 후에도 유지)
CMC_CONFIG.load();
CMC_CONFIG.appsScript.webAppUrl = 'https://script.google.com/macros/s/[URL]/exec';
CMC_CONFIG.persist();
location.reload();
```

---

### 3-3. dashboard_sheets_service_new.js URL 적용 위치

파일 위치: `app/services/dashboard_sheets_service_new.js`

이 파일은 URL을 직접 가지지 않습니다. 아래 메서드가 `CMC_CONFIG`에서 자동으로 읽어옵니다:

```javascript
_url() {
  return (typeof CMC_CONFIG !== 'undefined' &&
          CMC_CONFIG.appsScript &&
          CMC_CONFIG.appsScript.webAppUrl) || '';
},
```

**즉, config_v2_new.js의 webAppUrl만 설정하면 dashboard_sheets_service_new.js는 자동으로 Sheets 모드로 전환됩니다.**

---

## 4. Netlify 운영 환경 배포

### 4-1. 현재 netlify.toml 확인

프로젝트 루트의 `netlify.toml`:

```toml
[build]
  publish = "."

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

이미 설정 완료 상태입니다.

---

### 4-2. GitHub 연동 배포 (권장)

1. **GitHub 저장소 준비**: 현재 저장소(main 브랜치)를 GitHub에 push

   ```bash
   git remote add origin https://github.com/[계정]/cmc-platform.git
   git push -u origin main
   ```

2. **Netlify 사이트 생성**:
   - [netlify.com](https://netlify.com) 로그인
   - **Add new site** → **Import an existing project**
   - **GitHub** 선택 → 저장소 선택
   - Build 설정:
     - Base directory: (비워두기)
     - Build command: (비워두기 — 정적 파일)
     - Publish directory: `.`
   - **Deploy site** 클릭

3. **배포 완료 확인**:
   - Netlify가 자동으로 URL 발급 (예: `https://cmc-platform.netlify.app`)
   - 이후 GitHub main 브랜치에 push 시 자동 재배포

---

### 4-3. webAppUrl을 운영 환경에 반영하는 방법

**방법 A: config_v2_new.js 직접 수정 후 git push** (권장)

```javascript
// app/config_v2_new.js
const CMC_CONFIG = {
  dataSource: 'google',
  appsScript: {
    webAppUrl: 'https://script.google.com/macros/s/[실제URL]/exec',
  },
};
```

수정 후:
```bash
git add app/config_v2_new.js
git commit -m "config: GAS webAppUrl 운영 설정"
git push
```

> Netlify가 자동으로 재배포됩니다.

**방법 B: Netlify 환경변수 사용** (URL을 소스에 노출하지 않을 경우)

1. Netlify 사이트 → **Site configuration** → **Environment variables**
2. 변수 추가: `VITE_GAS_URL` = `https://script.google.com/macros/s/[URL]/exec`
3. `config_v2_new.js`에서 환경변수 참조:
   ```javascript
   webAppUrl: window.__GAS_URL__ || '',
   ```
   그리고 `index.html`에 빌드 스크립트로 주입 (정적 사이트이므로 별도 빌드 도구 필요)

> 현재 프로젝트는 순수 정적 HTML이므로 **방법 A가 더 간단합니다.**
> 단, GAS URL이 GitHub에 공개되는 점을 감안해 저장소를 Private으로 설정하세요.

---

### 4-4. Netlify에서 GAS CORS 적용 확인

Netlify에서 호출 시 GAS CORS 처리:

```
Netlify 도메인: https://cmc-platform.netlify.app
GAS URL: https://script.google.com/...

→ 크로스 오리진 요청 발생
→ GET 요청(URLSearchParams): simple request → CORS 불필요 → 정상 동작 ✅
→ POST 요청(Content-Type 미설정): simple request → CORS 불필요 → 정상 동작 ✅
→ POST 요청(Content-Type: application/json): preflight → GAS 미지원 → 실패 ❌
```

**결론**: `dashboard_sheets_service_new.js`의 `_get()` 메서드는 이미 올바른 방식(GET + URLSearchParams)을 사용하므로 추가 CORS 설정 불필요합니다.

POST 예약 폼에서도 `Content-Type` 헤더를 설정하지 않으면 정상 동작합니다.

---

## 5. Pilot 테스트 절차

### 5-1. 테스트 환경 설정

| 항목 | 설정값 |
|------|--------|
| 테스트 시트 | 기존 `종합검진_예약대장` 시트에 테스트 데이터 입력 |
| 테스트 브라우저 | Chrome (시크릿 창 권장) |
| 테스트 URL | Netlify 발급 URL 또는 `file://` 로컬 |
| 개인정보 | 실제 환자 정보 사용 금지 — 가상 데이터 사용 |

---

### 5-2. 단계별 테스트 시나리오

#### STEP 1. GAS API 연결 확인

```
브라우저 주소창: [GAS_URL]?action=ping
기대 응답: {"ok":true,"apiVersion":"4.0",...}
```

#### STEP 2. 예약 등록 → Sheets 저장 확인

1. 예약 폼(`reservation_form_new.html`) 열기
2. 테스트 데이터 입력 (가상 이름, 임의 생년월일)
3. 제출 → 성공 메시지 확인
4. Google Sheets에서 행 추가 확인

#### STEP 3. 대시보드 실시간 데이터 확인

1. `admin_dashboard_new_v2.html` 열기
2. 브라우저 콘솔에서 확인:
   ```
   [Dashboard Sheets] Sheets 연동 성공 · 오늘 N건 / 이번주 M건 / 최근30일 K건
   ```
3. KPI 카드 숫자 확인:
   - 오늘 예약 / 예약접수 / 예약확정 / 검진완료 / 예약취소
4. 업데이트 표시: `📡 Sheets 실시간 · 업데이트: HH:MM:SS`

#### STEP 4. 오늘 일정 확인

1. Sheets에서 `희망검진일` = 오늘 날짜로 테스트 데이터 1건 추가
2. 대시보드 새로고침
3. '오늘 일정' 카드에 해당 예약 표시 확인

#### STEP 5. 이번주 예약 차트 확인

1. Sheets에 이번주 날짜로 3~5건 테스트 데이터 추가
2. 대시보드 새로고침
3. 요일별 막대 차트 숫자 일치 확인

#### STEP 6. 폴백(Fallback) 동작 확인

1. 브라우저 콘솔에서 webAppUrl 임시 삭제:
   ```javascript
   CMC_CONFIG.appsScript.webAppUrl = '';
   CMC_CONFIG.persist();
   location.reload();
   ```
2. 대시보드가 localStorage 데이터로 정상 표시되는지 확인
3. 업데이트 표시: `💾 로컬 데이터 · 업데이트: HH:MM:SS`

#### STEP 7. 1분 자동 갱신 확인

1. Sheets에 새 예약 1건 추가
2. 대시보드에서 60초 대기
3. KPI 숫자 자동 업데이트 확인

---

### 5-3. 테스트 완료 기준 (Go/No-Go)

| # | 항목 | 기준 |
|---|------|------|
| 1 | GAS ping 응답 | `ok: true`, `apiVersion: "4.0"` |
| 2 | 예약 등록 → Sheets 저장 | 5초 이내, 예약번호 채번 정상 |
| 3 | 대시보드 Sheets 연동 | 콘솔 에러 없음, 실시간 데이터 표시 |
| 4 | KPI 카드 숫자 | Sheets 집계값과 일치 |
| 5 | 폴백 동작 | URL 미설정 시 로컬 데이터로 정상 동작 |
| 6 | 자동 갱신 | 60초 주기 자동 업데이트 동작 |
| 7 | 개인정보 보호 | 대시보드 list 응답에 phone·birth 미표시 |

모든 항목 Pass 시 → **운영 배포 승인**

---

### 5-4. 테스트 데이터 정리

Pilot 테스트 완료 후 Sheets에서 테스트 데이터 행 삭제:
- `종합검진_예약대장` 시트 열기
- 예약번호가 테스트날짜(예: `20260707-`)로 시작하는 행 선택 후 삭제

---

## 6. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| ping 응답 없음 | GAS 미배포 또는 URL 오류 | 2-4 단계 재배포, URL 재확인 |
| `{"ok":false,"code":500}` | 스프레드시트 접근 권한 없음 | Sheets 공유 설정에서 '편집자' 추가 |
| 대시보드 KPI 0 표시 | webAppUrl 미설정 | 3-2 단계: 콘솔에서 URL 설정 |
| 콘솔에 CORS 에러 | POST에 Content-Type: application/json 설정됨 | fetch body 전송 시 Content-Type 헤더 제거 |
| 대시보드 `💾 로컬 데이터` 표시 | GAS 실패 → 폴백 동작 | 콘솔 에러 메시지 확인 후 GAS URL 재확인 |
| 예약번호 중복 | 동시 등록 충돌 | GAS LockService가 자동 처리함 (503 → 재시도) |
| Netlify 404 | publish directory 설정 오류 | netlify.toml의 publish를 `.`으로 설정 |
| 시트 자동 생성 안 됨 | SPREADSHEET_ID 오류 | Google Sheets URL에서 ID 재확인 |

---

## 부록 — 파일 역할 요약

| 파일 | 역할 |
|------|------|
| `app/apps_script/sheets_api_v4_deploy_new.gs` | Google Apps Script — 배포 코드 |
| `app/config_v2_new.js` | webAppUrl 설정, dataSource 전환 |
| `app/services/dashboard_sheets_service_new.js` | 대시보드 Sheets 데이터 서비스 |
| `app/pages/admin_dashboard_new_v2.html` | 관리자 대시보드 (Sheets 연동) |
| `netlify.toml` | Netlify 배포 설정 |

---

*이 가이드로 해결되지 않는 문제는 `docs/CSHSP_Failure_Response_Manual.md` 참조.*
