# STEP 0~1 — 예약신청 쓰기 경로 Live 배선 & 검증 절차

> 목표: `reservation` 화면의 예약 1건이 Google Sheets에 저장되는 것만 검증
> 원칙: 원본 무수정·삭제 금지 / 대시보드·관리자 화면 미변경 / `dataSource='local'` 즉시 롤백
> 작성: 2026-07-01

---

## 1. 변경 요약

- **수정한 기존 파일: 없음** (원본 `reservation_new.html` 그대로 보존)
- **추가한 파일: 1개** — `app/pages/reservation_v2_new.html`
  - 원본 UI/폼 100% 동일, 하단 `<script>` 저장 로직만 배선
  - `config_v2_new.js` + `google_sheets_service_v2_new.js` 스크립트 로드 추가
  - `dataSource='local'` → 기존 localStorage 방식 그대로 / `='google'` → Apps Script 저장

> ⚠️ 주의: `CMC_CONFIG`/`CMC_SheetsServiceV2`는 `const` 전역이라 `window.` 접두어로 접근되지 않음.
> 코드에서 반드시 bare 참조(`typeof CMC_CONFIG !== 'undefined'`)로 접근. (검증 중 실제로 이 함정 발견·수정함)

---

## 2. STEP 0 — Apps Script 백엔드 배포 준비 점검 결과

| 점검 항목 | 결과 |
|-----------|------|
| `apps_script/sheets_api_v2_new.gs` 존재·완성 | ✅ 29컬럼 CRUD 완성 |
| 지원 action (doGet) | `list` / `get` / `summary` / `ping` |
| 지원 action (doPost) | `create` / `updateStatus` / `updateOps` / `update` |
| create → Sheets append 가능 | ✅ `_actionCreate` → `sheet.appendRow(row)`, 서버 채번(`_generateNo`) |
| health check | ✅ `?action=ping` → `{ok:true, message:'CMC Sheets API v2 정상', ...}` |
| 헤더 초기화 | ✅ `_initHeader` 최초 1회 실행 시 29컬럼 자동 생성 |

→ **백엔드는 코드 수정 불필요. 배포만 하면 됨.**

### 배포 수동 작업 (사용자 진행 — Google 계정 필요)
1. Google Sheets 새 문서 생성 (예: "CMC_예약현황")
2. 확장 → Apps Script → `sheets_api_v2_new.gs` 전체 내용 붙여넣기 → 저장
3. 편집기에서 `_initHeader`는 자동 생성되므로, 함수 목록에서 `doGet` 대신 아무 함수나 1회 실행해 권한 승인
   (또는 시트 최초 접근 시 자동 생성됨)
4. 배포 → 새 배포 → 유형: **웹 앱**
   - 실행 계정: 나
   - 액세스: **조직 내부** (또는 테스트 시 '모든 사용자')
5. 배포 후 **웹 앱 URL 복사** (형식: `https://script.google.com/macros/s/●●●/exec`)
6. 브라우저에서 `URL?action=ping` 접속 → `{"ok":true,...}` 확인

---

## 3. Web App URL 입력 위치 & 모드 전환

### 방법 A — 설정 파일에 직접 입력 (권장, 영구)
`app/config_v2_new.js`
```js
dataSource: 'local',          // ← 'google' 로 바꾸면 Live
appsScript: {
  webAppUrl: '',              // ← 여기에 배포 URL 붙여넣기
  sheetName: '예약현황',
  ...
}
```
> 파일 수정 시에도 원칙상 원본 보존이 필요하면 `config_v3_new.js` 사본을 만들고 페이지 로드 태그를 교체.
> 현재 STEP1에서는 config_v2를 그대로 사용.

### 방법 B — 브라우저 콘솔에서 임시 전환 (테스트용, localStorage 저장)
```js
CMC_CONFIG.appsScript.webAppUrl = 'https://script.google.com/macros/s/●●●/exec';
CMC_CONFIG.setDataSource('google');   // persist() 로 localStorage 저장됨
location.reload();
```
롤백:
```js
CMC_CONFIG.setDataSource('local');    // 다시 localStorage 모드
location.reload();
```

---

## 4. 검증 결과 (자동 테스트 완료)

미리보기 서버(`http://localhost:4000/app/pages/reservation_v2_new.html`)에서 검증함.

### 4-1. LOCAL 모드 (기본·롤백 상태) — ✅ 통과
| 항목 | 결과 |
|------|------|
| 저장 전/후 건수 | 40 → 41 (+1) |
| 예약번호 발급 | `20260701-0001` (클라이언트 채번) |
| 성공화면 표시 | block |
| 저장 데이터 | name=검증테스트, program=SMART, status=예약접수 정상 |

### 4-2. LIVE 모드 안전차단 (google + URL 미설정) — ✅ 통과
- `_isLive()=true`, DB 변화 없음, 성공화면 미표시
- alert: "Live 모드이지만 Apps Script Web App URL이 설정되지 않았습니다."

### 4-3. LIVE 모드 저장 경로 (google + URL + 어댑터 stub) — ✅ 통과
- 성공화면에 **서버 채번번호** `20260715-0007` 반영
- 클라이언트가 예약번호를 서버로 보내지 않음(서버 채번 확인)
- 로컬 localStorage 미사용(Live는 Sheets로 저장)

> 4-3은 실제 배포 URL 없이 어댑터를 stub하여 **배선 로직**을 검증한 것.
> 실제 Sheets 저장은 아래 5절(배포 후 수동 검증)에서 확인.

---

## 5. 실 배포 후 최종 검증 절차 (사용자 진행)

1. 3절 방법으로 `webAppUrl` 입력 + `dataSource='google'` 전환 후 페이지 새로고침
2. 콘솔에 `저장 모드: LIVE (Google Sheets)` 초록색 로그 확인
3. 예약 폼 작성 → **예약 신청하기** 클릭
4. 성공화면 예약번호 확인 (예: `20260701-0001`)
5. **Google Sheets '예약현황' 시트에 해당 행이 생겼는지 확인** ← 핵심 검증
6. 콘솔 `[예약저장:LIVE] 응답 →` 로그에서 `{ok:true}` 확인

---

## 6. 롤백 방법

| 상황 | 조치 |
|------|------|
| Live 저장 실패/오류 | 콘솔에서 `CMC_CONFIG.setDataSource('local'); location.reload();` |
| 새 파일 자체 롤백 | `reservation_v2_new.html` 대신 원본 `reservation_new.html` 링크 사용 (원본 무손상) |
| config 오염 | localStorage 키 `cmc_config_v2` 삭제 후 새로고침 (기본값 local 복귀) |

→ 원본 파일·기존 데이터는 전혀 변경되지 않았으므로 **완전 롤백 가능**.

---

## 7. 주의사항 & STEP 2 진행 전 확인사항

**아직 필요한 수동 작업**
- [ ] Apps Script 배포 및 `webAppUrl` 확보 (2·3절)
- [ ] `?action=ping` 응답 확인
- [ ] 실 배포 URL로 5절 최종 검증 (Sheets 행 생성 확인)

**보안 (운영 전 필수, 아직 미적용)**
- 웹앱 액세스 범위 '조직 내'로 제한 (개인정보 포함)
- 관리자 인증 부재 상태 — STEP 6에서 처리 예정

**STEP 2 진행 전 확정 필요**
- STEP 1 실 배포 검증이 성공해야 STEP 2(관리자 목록/상태변경 Live 배선) 착수
- 관리자 화면도 동일하게 `admin_reservations_v2_new.html` 사본 + 배선 방식으로 진행 예정
- 대시보드(`dashboard_service_v2` 순수함수화)는 STEP 3에서 별도 진행

---

*본 STEP은 예약 쓰기 경로 배선·검증만 수행. 원본·데이터 무변경. 저장: CMC_Platform_new/*
