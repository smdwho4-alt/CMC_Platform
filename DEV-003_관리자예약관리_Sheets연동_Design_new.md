# DEV-003 — 관리자 예약관리(admin_reservations) Google Sheets 연동 전환 설계 문서

> 문서 유형: **PM 승인용 설계 문서 (Design Only, 구현 코드 미포함)**
> 대응 범위: CMC Platform 운영 전환 Migration Plan의 **STEP 2 — 관리자 읽기/상태변경 전환**
> 원칙: 기존 UI 변경 금지 · Version 1.0 범위 유지 · 원본 파일 무수정 · 즉시 롤백 가능
> 작성일: 2026-07-01 | 작성 대상 폴더: `99_임시보관_정리대기/CMC_Platform_new/`
> 선행 문서: `CMC_Platform_운영전환분석_Migration_20260701_new.md`, `STEP0-1_예약쓰기검증_배포절차_new.md`, `STEP1.5.1_DateFix_QA_new.md`

---

## 0. 개요

### 0.1 목적
관리자 예약관리 화면(`admin_reservations_new.html`)이 현재 localStorage(`CMC_DB`)만 사용하는 구조를, 이미 완성된 Google Sheets 연동 계층(`CMC_SheetsServiceV2` + Apps Script)에 배선하여 **여러 담당자가 동일한 예약 데이터를 실시간 공유**할 수 있도록 전환한다.

### 0.2 배경
- STEP 1(예약신청 화면)에서 쓰기 경로 배선 검증 완료(`reservation_v2_new.html`).
- STEP 1.5에서 날짜 포맷 결함(DateFix)을 수정한 최종 백엔드 `sheets_api_v3_final.gs`가 실배포됨.
- 관리자 화면(목록 조회·상태변경)은 아직 `CMC_DB`(localStorage, 단말 고정)만 사용 — 담당자 간 데이터 미공유 상태.

### 0.3 승인 요청 사항 (PM 확인 필요)
1. 본 설계대로 신규 파일 `admin_reservations_v2_new.html` 생성을 승인하는가 (원본 미수정).
2. 통계 카드 계산 로직을 화면 내부로 이전(3.5절)하는 방식에 이견이 없는가.
3. "목록 로딩 중" 텍스트를 기존 빈 목록 안내 영역에 표시하는 것을 UI 변경으로 볼 것인지, 데이터 상태 표시(허용)로 볼 것인지 확인.
4. 백엔드 동시성(LockService) 미적용 잔여 리스크(6.3절)를 v1.0에서 수용할지, 이번 티켓 범위에 포함할지 결정.

---

## 1. 범위 정의

### In-Scope
- `admin_reservations_new.html`을 원본으로 하는 신규 파일 `admin_reservations_v2_new.html` 생성
- 목록 조회 로직을 `CMC_DB.getAll()` → `CMC_SheetsServiceV2.getAll()`로 전환
- 상태변경 로직을 `CMC_DB.update()` → `CMC_SheetsServiceV2.updateStatus()`로 전환
- 동기(sync) 렌더링 → 비동기(async) 렌더링 구조 전환
- `dataSource` 스위치(local/google) 기반 즉시 롤백 체계 유지
- 목록 캐시(in-memory) 도입 및 필터/검색의 클라이언트 사이드 유지

### Out-of-Scope (본 티켓에서 다루지 않음)
- 화면 레이아웃/CSS/문구 변경 (기존 UI 100% 동일 유지)
- 실시간 자동 폴링(주기적 재조회) — v1.0 범위 밖, 별도 티켓으로 제안
- 관리자 로그인/인증 (STEP 6 별도 과제)
- 대시보드(`admin_dashboard_v3_new.html`) 전환 (STEP 3 별도 과제)
- 알림 서버화(이메일/캘린더, STEP 5 별도 과제)
- Apps Script 백엔드 코드 수정 (`sheets_api_v3_final.gs`는 배포된 그대로 사용, 액션 추가 없음)

---

## 2. Architecture Diagram

### 2.1 현재 구조 (AS-IS)
```
[admin_reservations_new.html]
        │  동기 호출 (sync)
        ▼
[db_service_new.js : CMC_DB]  ───► localStorage("cheonan_reservations_v1")
        ▲
[stats_service_new.js : CMC_Stats]  (통계 카드 계산, CMC_DB 직접 참조)
```
- 단일 브라우저/단말에 데이터 고정. 다른 PC의 담당자는 동일 예약을 볼 수 없음.

### 2.2 전환 후 구조 (TO-BE, DEV-003)
```
[admin_reservations_v2_new.html]   ← 신규 파일 (원본 admin_reservations_new.html 보존)
        │  비동기 호출 (async) + in-memory 캐시(AA.cache)
        ▼
[config_v2_new.js : CMC_CONFIG.dataSource]
        │
        ├─ 'local'  ──► [google_sheets_service_v2_new.js : CMC_SheetsServiceV2 Mock 경로]
        │                        │
        │                        ▼
        │                [db_service_new.js : CMC_DB] ──► localStorage (변경 없음, 롤백 경로)
        │
        └─ 'google' ──► [google_sheets_service_v2_new.js : CMC_SheetsServiceV2 Live 경로]
                                 │  fetch (GET query / POST text-plain JSON)
                                 ▼
                        [Apps Script Web App : sheets_api_v3_final.gs]
                          doGet  → list / get / summary / ping
                          doPost → updateStatus / update / updateOps / create
                                 │
                                 ▼
                        [Google Sheets : "종합검진_예약대장" (29컬럼)]
```

**핵심 설계 결정**
- 통계 카드(전체/접수/확정/완료/취소변경)는 `CMC_Stats`(CMC_DB 직접 의존) 호출을 제거하고, 화면이 이미 확보한 `AA.cache` 배열에서 **직접 계산**하도록 변경한다. (3.5절 상세)
  - 사유: `CMC_Stats.statusCounts()`는 내부적으로 `CMC_DB.getAll()`을 하드코딩 호출하므로, Live 모드에서도 항상 localStorage 값을 보여주는 오류가 발생함. 공용 서비스 파일(`stats_service_new.js`)은 대시보드 등 다른 화면이 계속 사용 중이므로 **수정하지 않고**, 신규 화면 내부에 로컬 계산 함수를 추가하는 방식으로 격리한다.
- 대상 백엔드는 `sheets_api_v2_new.gs`가 아니라 **실배포본 `sheets_api_v3_final.gs`** 로 명시한다(6.1절 근거). 클라이언트 어댑터(`CMC_SheetsServiceV2`)의 액션명·요청 포맷은 두 버전 간 동일하여 어댑터 코드 변경은 불필요함.

---

## 3. Sequence Diagram

### 3.1 페이지 진입 → 목록 조회
```
사용자        admin_reservations_v2_new.html      CMC_SheetsServiceV2        Apps Script(v3_final)      Sheet
 │  접속            │                                     │                          │                    │
 │ ───────────────► │ init() [async]                      │                          │                    │
 │                  │ 로딩 표시(테이블 영역에 "불러오는 중…")│                          │                    │
 │                  │ ─── await getAll() ─────────────────►│                          │                    │
 │                  │                                      │ ── GET ?action=list ────►│                    │
 │                  │                                      │                          │ getRange().getValues()
 │                  │                                      │                          │◄───────────────────│
 │                  │                                      │◄── {ok:true,data,count} ─│                    │
 │                  │◄── {ok, data, source, count} ────────│                          │                    │
 │                  │ AA.cache = data                       │                          │                    │
 │                  │ renderStats()/renderTable()/render    │                          │                    │
 │                  │  Pagination() (cache 기준 동기 계산)  │                          │                    │
 │◄─────────────────│ 목록/통계 표시                        │                          │                    │
```
- 실패 시(`ok:false` 또는 네트워크 예외): 테이블 영역에 기존 "조회된 예약이 없습니다" 슬롯을 재사용해 오류 메시지 표시, `AA.cache = []`로 안전 처리. 통계 카드는 0으로 표시.

### 3.2 상태 변경 (낙관적 갱신 + 실패 롤백)
```
사용자      상세 모달(admin_reservations_v2)      CMC_SheetsServiceV2       Apps Script(v3_final)     Sheet
 │ 상태 선택 후 "저장"클릭 │                                │                          │                  │
 │ ───────────────────►  │ saveStatus() [async]           │                          │                  │
 │                        │ prevStatus = cache[i].status   │                          │                  │
 │                        │ cache[i].status = 신규값 (낙관적 적용, 화면 즉시 갱신)      │                  │
 │                        │ 모달 닫기 + 토스트("변경되었습니다") 즉시 표시              │                  │
 │                        │ ── await updateStatus(no,status) ──►│                     │                  │
 │                        │                                 │ ── POST updateStatus ──►│                  │
 │                        │                                 │                          │ 상태값 setValue  │
 │                        │                                 │                          │ (예약확정/검진완료 시 부가 타임스탬프)│
 │                        │                                 │◄── {ok:true,data} ───────│                  │
 │                        │◄── {ok, data, source} ──────────│                          │                  │
 │                        │ if !ok: cache[i].status = prevStatus (롤백) + 오류 토스트   │                  │
 │                        │         (모달은 이미 닫힌 상태 → 재오픈 유도 alert)          │                  │
 │                        │ re-render (성공 시 서버 응답 data로 캐시 항목 갱신)          │                  │
```
- 낙관적 갱신을 택한 이유: Live 모드는 Mock(400ms) 대비 왕복 지연이 더 클 수 있어(실측 필요) 즉각적 UX를 유지하기 위함. 단, 실패 시 반드시 원복 + 명시적 오류 알림 필요.

---

## 4. API Mapping

| # | 화면 동작 | 페이지 함수(AA) | CMC_SheetsServiceV2 메서드 | HTTP | Apps Script action | 영향 컬럼(Sheet, 29컬럼 기준) |
|---|-----------|------------------|------------------------------|------|---------------------|-------------------------------|
| 1 | 페이지 진입/명시적 새로고침 | `refreshCache()` (신규) | `getAll()` | GET | `list` | 읽기 전용, 전체 29컬럼 |
| 2 | 상세 모달 열기 | `openModal(no)` | 없음(캐시 조회) | - | - | - |
| 3 | 상태 저장 | `saveStatus()` | `updateStatus(no, status)` | POST | `updateStatus` | 예약상태(15) 필수, 예약확정일(16)/접수시간(20)/검진시작(21)/검진종료(22) 조건부 |
| 4 | 검색/필터 입력 | `getFiltered()` | 없음(캐시 필터, 클라이언트 사이드) | - | - | - |
| 5 | CSV 다운로드 | `downloadCSV()` | 없음(캐시 기반) | - | - | - |
| 6 | 페이지네이션 이동 | `goPage(n)` | 없음(캐시 슬라이스) | - | - | - |
| 7 | (내부 진단용, 화면 노출 없음) | `init()` 내 optional | `ping()` | GET | `ping` | - |

**상태값별 서버 부가 동작 (참고, `_actionUpdateStatus` 고정 로직)**

| 선택 상태 | 서버 자동 처리 |
|-----------|---------------|
| 예약확정 | `예약확정일` 컬럼에 현재시각 자동 기록 |
| 검진완료 | `검진종료` 컬럼에 현재시각 자동 기록 |
| 검진중 | `접수시간`, `검진시작` 자동 기록 (**단, 본 화면의 상태 드롭다운에는 '검진중' 옵션이 없어 이 화면에서는 발생하지 않음** — 정보 공유용, 수정 불필요) |
| 예약접수 / 일정변경 / 예약취소 | 부가 타임스탬프 없음, 상태값만 변경 |

---

## 5. 신규/변경 파일 목록

| 구분 | 파일 | 조치 |
|------|------|------|
| 신규 | `app/pages/admin_reservations_v2_new.html` | 원본 전체 복제 후 하단 `<script>` 블록만 배선 로직 교체. HTML 마크업(`<head>`~`</main>`, 모달 구조)은 원본과 100% 동일 |
| 변경 없음(원본 보존) | `app/pages/admin_reservations_new.html` | 무수정, 롤백 시 즉시 사용 가능 |
| 변경 없음 | `app/services/db_service_new.js` | Mock 경로 내부 위임 대상으로만 계속 사용 |
| 변경 없음 | `app/services/stats_service_new.js` | 다른 화면(대시보드) 호환 위해 무수정 |
| 변경 없음 | `app/services/google_sheets_service_v2_new.js` | 어댑터 그대로 재사용 (액션명 v3_final과 호환 확인됨) |
| 변경 없음 | `app/config_v2_new.js` | `dataSource` 스위치만 활용, 필드 추가 없음 |
| 참고(배포 대상 확인용) | `app/apps_script/sheets_api_v3_final.gs` | 코드 미수정. "이 버전이 실제 배포본"임을 문서화(6.1절) |

**스크립트 로드 순서 (`admin_reservations_v2_new.html` 하단)**
```
programs_data_new.js → sample_data_new.js → db_service_new.js
→ config_v2_new.js → google_sheets_service_v2_new.js
→ nav_new.js
```
- `stats_service_new.js`는 로드하지 않음(3.5절 사유로 화면 내부 계산으로 대체).

---

## 6. 상세 설계 결정 사항

### 6.1 대상 백엔드 버전 확정 (중요)
- Migration Plan 문서상 명목은 `sheets_api_v2_new.gs`이나, STEP 1.5에서 이미 `sheets_api_v3_final.gs`(LockService 일부 적용 + DateFix + 고정 `SPREADSHEET_ID` + 독립형 스크립트 구조)로 **실제 배포가 갱신됨**.
- 두 파일의 `SHEET_NAME`이 다름: v2는 `'예약현황'`, v3_final은 `'종합검진_예약대장'`.
- **본 설계는 실배포본인 `sheets_api_v3_final.gs`를 대상으로 한다.** 액션명·요청/응답 포맷(list/get/updateStatus/update, JSON 구조)이 v2와 동일하므로 클라이언트 어댑터 코드 변경은 불필요.
- 확인 필요: `config_v2_new.js`의 `appsScript.sheetName` 기본값(`'예약현황'`)이 실제 시트명과 다름. 이 값은 `ping()` 응답 메시지 표시에만 쓰이고 API 동작에는 영향 없으나, 운영 혼선 방지를 위해 값 정정 여부를 PM/운영팀 확인 필요(코드 1줄 값 변경, 이번 티켓 부수 작업으로 제안).

### 6.2 필터링 전략: 서버 필터 vs 클라이언트 필터
- Apps Script `list` 액션은 `status`/`dateFrom`/`dateTo`/`doctor`/`examRoom`/`paymentStatus` 서버 필터를 이미 지원.
- 그러나 화면의 통합검색(성명·연락처·예약번호·사업장·프로그램 텍스트 매칭)은 서버 미지원.
- **설계 결정**: v1.0에서는 최소 변경 원칙에 따라 **전체 목록을 1회 조회 후 클라이언트에서 기존과 동일한 필터 로직을 그대로 적용**한다. 서버 사이드 쿼리 파라미터 연동은 향후 데이터량 증가 시 별도 개선 과제로 분리(Out-of-Scope 명시).

### 6.3 동시성(Concurrency) 잔여 리스크
- `_actionUpdateStatus`/`_actionUpdate`는 `_actionCreate`와 달리 `LockService`가 적용되어 있지 않음(행 탐색 후 `setValue`까지 원자적이지 않음).
- 두 담당자가 **동일 예약번호**를 동시에 상태변경 시도하는 극단적 케이스에서 마지막 쓰기가 이전 쓰기를 덮어쓸 수 있음(Last-Write-Wins).
- 실제 운영 규모(소규모 검진센터, 동시 접속 관리자 소수)를 고려하면 발생 확률은 낮음으로 판단되나, **백엔드 코드 변경 없이는 완전 해소 불가**하므로 본 티켓 범위 밖 리스크로 문서화하고 PM 승인 시 수용 여부를 확정한다(9절 QA 체크리스트에도 반영).

### 6.4 로딩/에러 상태 표시 방식
- 신규 UI 요소(배지, 아이콘, 버튼) 추가 없이, 기존에 존재하던 "조회된 예약이 없습니다" 빈 상태 텍스트 슬롯을 상황별 메시지로 교체하는 방식만 사용:
  - 로딩 중: "예약 목록을 불러오는 중입니다…"
  - 조회 실패: "예약 목록을 불러오지 못했습니다. 새로고침 후 다시 시도해 주세요."
  - 정상, 결과 0건: 기존 문구 유지
- 상태 변경 실패 시: 기존 `toast()` 함수를 재사용하되 배경색 등 스타일 변경 없이 텍스트만 오류 메시지로 전달(예: `"상태 변경에 실패했습니다. 다시 시도해 주세요."`).

### 6.5 캐시 갱신 시점 (자동 폴링 없음, Out-of-Scope 재확인)
- 캐시 갱신은 다음 3가지 이벤트에서만 발생: ① 페이지 최초 진입, ② 상태변경 성공 후 서버 응답 반영, ③ 브라우저 수동 새로고침(F5).
- 다른 담당자의 변경사항은 내가 새로고침하기 전까지 화면에 반영되지 않음 — 이는 v1.0 범위의 명시적 제약이며, 실시간 반영이 필요하면 후속 티켓(자동 폴링 또는 서버 푸시)에서 다룬다.

---

## 7. Risk 분석

| # | 리스크 | 영향도 | 발생가능성 | 대응 방안 |
|---|--------|--------|------------|-----------|
| 1 | 대상 백엔드가 `sheets_api_v2_new.gs`가 아닌 `sheets_api_v3_final.gs`인 것을 인지하지 못하고 잘못된 시트명 가정으로 확인 작업을 진행 | 중 | 중 | 6.1절 명시, 구현 착수 전 실제 배포 URL의 `?action=ping` 응답과 시트명 재확인 |
| 2 | `CMC_Stats`가 여전히 `CMC_DB`만 참조 — 실수로 v2 화면에서 재사용 시 Live 모드에서도 localStorage 값이 표시됨 | 높음 | 중 | `stats_service_new.js` 미사용, 화면 내부 캐시 기반 계산 함수로 대체(3절/6절) |
| 3 | Live 모드 응답 지연으로 목록 로딩 체감 저하 | 낮음 | 중 | 로딩 상태 텍스트 표시(6.4절), 캐시 1회 조회 후 필터는 클라이언트 처리로 재조회 최소화 |
| 4 | 동시 상태변경 시 Last-Write-Wins(LockService 미적용) | 중 | 낮음 | 6.3절 문서화, PM 수용 여부 결정 후 필요 시 별도 백엔드 하드닝 티켓 발행 |
| 5 | `config_v2_new.js`의 `webAppUrl` 미설정 상태에서 `dataSource='google'`로 전환 시 매 호출마다 예외 발생 | 낮음 | 낮음 | `CMC_SheetsServiceV2.ping()`에서 URL 미설정을 사전 감지하는 기존 로직 재사용, 실패 메시지를 6.4절 방식으로 노출 |
| 6 | 개인정보(연락처·생년월일 등) 포함 데이터가 Web App 응답에 그대로 노출 | 높음(정보보호) | 낮음(액세스 조직 내 제한 시) | 기배포 시 액세스 권한 '조직 내' 설정 여부를 STEP 0 체크리스트로 재확인(신규 조치 아님, 기존 원칙 재확인) |
| 7 | Mock(local) 모드는 `confirmedAt` 등 부가 타임스탬프를 저장하지 않아 Live 모드와 데이터 형태가 미세하게 다름 | 낮음 | 확정적(구조적 차이) | 화면 표시 로직은 두 모드 모두 필드 존재 여부와 무관하게 안전 출력(`||'-'`) 되어 있음을 확인, 별도 조치 불필요 |

---

## 8. Rollback Plan

| 상황 | 조치 | 소요 시간 |
|------|------|-----------|
| Live 모드 조회/저장 오류 발생 | 브라우저 콘솔에서 `CMC_CONFIG.setDataSource('local'); location.reload();` 실행 → 즉시 localStorage 모드로 복귀 | 즉시 |
| 신규 화면 자체에 결함 발견 | `admin_reservations_v2_new.html` 링크 대신 원본 `admin_reservations_new.html`로 되돌림(네비게이션 링크 원복) | 즉시 (원본 무손상 보존) |
| `config_v2_new.js` 설정 오염 | localStorage 키 `cmc_config_v2` 삭제 후 새로고침 → 기본값(`local`)으로 복귀 | 즉시 |
| 배포 서버(Apps Script) 자체 장애 | `dataSource='local'` 유지 상태에서는 영향 없음(Mock 경로는 Apps Script 미의존) | 해당 없음 |

- 모든 롤백 경로는 **원본 파일 삭제·수정이 발생하지 않는 구조**이므로 데이터 손실 없이 즉시 복귀 가능.

---

## 9. QA Checklist

**기능 검증**
- [ ] LOCAL 모드: 목록이 기존 `admin_reservations_new.html`과 동일하게 표시되는가
- [ ] LOCAL 모드: 검색/필터(성명·연락처·예약번호·사업장, 상태, 프로그램, 기간)가 기존과 동일하게 동작하는가
- [ ] LOCAL 모드: 상태 저장 시 토스트 표시 및 통계 카드 즉시 갱신되는가
- [ ] LOCAL 모드: CSV 다운로드 결과가 기존과 동일한 컬럼/인코딩(UTF-8 BOM)으로 생성되는가
- [ ] GOOGLE 모드(URL 미설정): 안전하게 오류 메시지가 표시되고 화면이 깨지지 않는가
- [ ] GOOGLE 모드(정상 배포 URL): 페이지 진입 시 Sheet의 실제 데이터가 목록에 표시되는가
- [ ] GOOGLE 모드: 상태변경 시 Sheet의 예약상태 컬럼(15번)이 실제로 갱신되는가
- [ ] GOOGLE 모드: '예약확정'으로 변경 시 예약확정일(16번) 컬럼이 자동 기록되는가
- [ ] GOOGLE 모드: '검진완료'로 변경 시 검진종료(22번) 컬럼이 자동 기록되는가
- [ ] GOOGLE 모드: 상태변경 API 실패(예: 네트워크 차단)를 인위 재현 시, 낙관적 갱신이 정상 롤백되는가

**회귀(Regression) 검증**
- [ ] 원본 `admin_reservations_new.html`이 변경 없이 그대로 정상 동작하는가
- [ ] 대시보드(`admin_dashboard_v3_new.html`)가 `stats_service_new.js`를 통해 기존과 동일하게 동작하는가(본 티켓의 영향을 받지 않는지 확인)
- [ ] `reservation_v2_new.html`(STEP1 산출물)의 예약 등록 흐름이 본 변경과 무관하게 정상 동작하는가

**성능/UX**
- [ ] Live 모드 첫 목록 로딩 시간이 체감상 과도하게 느리지 않은가(참고 기준: 3초 이내)
- [ ] 로딩/오류 문구가 기존 빈 상태 문구와 스타일 일관성을 유지하는가(신규 시각 요소 없음 확인)

**보안**
- [ ] Web App 배포 액세스 권한이 '조직 내'로 설정되어 있는가(신규 확인 아님, 재확인)
- [ ] 화면에 노출되는 연락처가 기존과 동일하게 마스킹(`CMC.maskPhone`) 처리되는가

---

## 10. Definition of Done

1. `admin_reservations_v2_new.html`이 신규 생성되고, 원본 `admin_reservations_new.html`은 무수정 상태로 보존됨이 확인됨.
2. LOCAL 모드에서 9절 QA Checklist의 "기능 검증(LOCAL)" 및 "회귀 검증" 항목 전체 통과.
3. GOOGLE 모드에서 실제 배포된 `sheets_api_v3_final.gs` 대상으로 9절 QA Checklist의 "기능 검증(GOOGLE)" 항목 전체 통과(Sheet 행 변경 실제 확인 포함).
4. `dataSource='local'` 전환만으로 즉시 롤백되는 것이 시연됨(8절 Rollback Plan 재현 확인).
5. 통계 카드가 `CMC_Stats`/`CMC_DB`에 의존하지 않고 화면 자체 캐시로 계산됨이 코드 리뷰로 확인됨.
6. 6.3절 동시성 리스크 및 6.1절 백엔드 버전 확인 사항에 대해 PM 서면(또는 채팅) 승인 획득.
7. 본 문서의 "0.3 승인 요청 사항" 4개 항목에 대한 PM 회신이 기록됨.
8. 실제 구현 착수는 본 문서 승인 후 별도 구현 티켓/세션에서 진행하며, 이 문서 자체에는 구현 코드가 포함되지 않음.

---

*본 문서는 설계 검토 전용이며 코드 변경을 포함하지 않음. 저장 위치: `99_임시보관_정리대기/CMC_Platform_new/`*
