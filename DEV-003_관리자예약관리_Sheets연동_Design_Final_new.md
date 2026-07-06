# DEV-003 — 관리자 예약관리(admin_reservations) Google Sheets Live 연동 설계 문서 (Final)

> 문서 유형: **PM 승인 완료 · 최종 설계 문서 (Design Only, 구현 코드 미포함)**
> 상태: **FINAL — 설계 종료.** 이후 구현(Implementation)은 별도 세션에서 진행.
> 이전 버전: v1(`DEV-003_관리자예약관리_Sheets연동_Design_new.md`), v2(`DEV-003_관리자예약관리_Sheets연동_Design_v2_new.md`) — 모두 보존
> 작성일: 2026-07-01
> 저장 위치: `99_임시보관_정리대기/CMC_Platform_new/`

## 개정 이력

| 버전 | 일자 | 변경 내용 |
|------|------|-----------|
| v1 | 2026-07-01 | 최초 설계 초안 |
| v2 | 2026-07-01 | PM 1차 검토 반영 — 범위 확정, Lock 정책 확정, Production Baseline·NFR 신설, 열린 항목 3건 도출 |
| **Final** | 2026-07-01 | PM 2차 승인으로 열린 항목 3건 전부 확정, **Impact Analysis**·**구현 순서** 신설. 설계 종료 |

---

## 1. PM 승인 확정 사항 (전체 확정 — 잔여 열린 항목 없음)

### ① 신규 파일 생성
- `admin_reservations_v2_new.html` 신규 생성 확정, 원본 `admin_reservations_new.html` 수정 금지, `_new` 규칙 유지

### ② DEV-003 범위 확정

**포함(In-Scope)**
| # | 기능 | 비고 |
|---|------|------|
| 1 | 예약목록 조회 | `list` 액션 |
| 2 | 예약검색 | 클라이언트 사이드 필터(기존 로직 유지) |
| 3 | 예약상세 조회 | 캐시 조회 우선, `get` 액션은 fallback |
| 4 | 예약상태 변경 | `updateStatus` 액션(Lock 필수) |
| 5 | 관리자 메모 저장 | `update` 액션, `note` 단일 필드 한정(Lock 필수) — **옵션 A 채택 확정** |
| 6 | Google Sheets Live 연동 | `CMC_SheetsServiceV2` + `sheets_api_v3_final.gs` |

**제외(Out-of-Scope)**
| 제외 항목 | 비고 |
|-----------|------|
| Dashboard / KPI / Summary / 통계 | STEP 3 별도 과제. 통계 카드는 Local 유지(7.1절) |
| Excel | 기존 CSV 다운로드 버튼 현행 유지 |
| Calendar | STEP 5 별도 과제 |
| Drag & Drop | 해당 없음 |
| 권한관리 | STEP 6 별도 과제 |
| 예약 수정 | 다중 필드 편집 UI 미포함(메모 저장과 구분 확정) |
| 예약 삭제 | 해당 없음 |

### ③ 로딩 처리
- 기존 UI(레이아웃·구성요소) 변경 금지, Spinner 등 신규 시각 요소 금지
- 허용 표현: 텍스트뿐 — `Loading...`, `Saving...`
- 표시 위치: 기존 빈 목록 안내 영역·토스트 영역 재사용

### ④ Lock 정책
| 동작 | Lock 사용 여부 |
|------|----------------|
| 조회(목록/상세) | 사용 안 함 |
| 상태 변경 | 필수 |
| 메모 저장 | 필수 |

### ⑤ 메모 저장 API 방식 — **확정: 옵션 A**
- 기존 `update` 액션을 재사용하되, payload는 `{note}` 단일 필드로 강제 한정.
- 프론트엔드 코드 레벨에서 `note` 외 다른 필드를 절대 전송하지 않도록 강제하여 "예약 수정 제외" 원칙과 충돌하지 않도록 설계.
- 백엔드 신규 액션(`updateNote`) 추가는 채택하지 않음(범위 최소화).

### ⑥ 메모 편집 UI 전환 — **확정: 허용**
- 상세 모달의 특이사항 표시 슬롯(`id="dNote"`)을 읽기 전용 `<span>`에서 편집 가능한 `<textarea>`로 전환하는 것을 승인함.
- 조건: 위치·크기·스타일(레이아웃)은 원본과 100% 동일하게 유지. 신규 요소 추가 없음(기존 요소의 상호작용 속성만 변경).

### ⑦ sheetName 값 정정 — **확정: DEV-003에 포함**
- `config_v2_new.js`의 `appsScript.sheetName` 기본값(`'예약현황'`)을 실제 배포 시트명(`'종합검진_예약대장'`)으로 정정하는 작업을 본 티켓에 포함.

---

## 2. Production Baseline

| 항목 | 값 |
|------|-----|
| Backend 스크립트 | `sheets_api_v3_final.gs` (실배포본, 독립형 스크립트 · `SPREADSHEET_ID` 고정 참조) |
| Google Sheets 문서 | `종합검진_예약대장` (시트명, 29컬럼) |
| 배포 상태 | Current Production Deployment (Web App `/exec`, STEP 0/1에서 검증됨) |
| Timezone | Asia/Seoul |
| 날짜/시간 포맷 | STEP 1.5.1 DateFix 적용됨 |

**Reservation API 현황**

| 그룹 | 액션 | Method | 현재 상태 | 본 티켓 사용 여부 |
|------|------|--------|-----------|--------------------|
| Reservation | `create` | POST | 구현·검증 완료(STEP 1) | 미사용 |
| Reservation | `get` | GET | 구현 완료 | 사용(상세조회 fallback) |
| Reservation | `list` | GET | 구현 완료 | 사용(목록조회) |
| Reservation | `summary` | GET | 구현 완료 | 미사용(통계 제외) |
| Admin | `list` / `get`(재사용) | GET | 구현 완료 | 사용 |
| Admin | `updateStatus`(Status) | POST | **Lock 보강 확정(본 티켓 범위, 3절)** | 사용 |
| Admin | `update`(Note, 단일필드) | POST | **Lock 보강 확정(본 티켓 범위, 3절)** | 사용(옵션 A) |

> 백엔드 변경 범위는 "Lock 로직 추가 + `note` 필드 한정 사용"에 한정하며, 액션명·응답 포맷·컬럼 구조·다른 액션 로직은 변경하지 않는다.

---

## 3. Architecture Diagram

### 3.1 기본 구조
```
Admin UI (admin_reservations_v2_new.html)
        ↓
CMC_SheetsServiceV2 (google_sheets_service_v2_new.js)
        ↓
Apps Script (sheets_api_v3_final.gs, Lock 보강)
        ↓
Google Sheets (종합검진_예약대장)
```

### 3.2 상세 구조 (모드 분기 포함)
```
[admin_reservations_v2_new.html]  ← 신규 파일, 원본 보존
        │  async + in-memory 캐시(AA.cache)
        ▼
[config_v2_new.js : CMC_CONFIG.dataSource]  (sheetName 값 정정 반영, ⑦)
        │
        ├─ 'local'  → [CMC_SheetsServiceV2 Mock] → [db_service_new.js : CMC_DB] → localStorage (롤백 경로)
        │
        └─ 'google' → [CMC_SheetsServiceV2 Live] → fetch(GET/POST)
                              ▼
                    [sheets_api_v3_final.gs]
                      doGet  → list / get
                      doPost → updateStatus(Lock) / update-note(Lock)
                              ▼
                    [Google Sheets : 종합검진_예약대장]
```
- 통계 카드(전체/접수/확정/완료/취소변경)는 본 경로와 무관하게 `CMC_Stats`/`CMC_DB` 그대로 유지(7.1절).

---

## 4. Sequence Diagram

### 4.1 예약목록 조회 (Lock 미사용)
```
사용자     admin_reservations_v2_new.html     CMC_SheetsServiceV2     Apps Script(v3_final)     Sheet
 │ 접속       │                                     │                        │                    │
 │ ─────────► │ init() [async]                      │                        │                    │
 │            │ "Loading..." 표시(기존 빈목록 슬롯) │                        │                    │
 │            │ ── await getAll() ─────────────────►│                        │                    │
 │            │                                      │── GET ?action=list ──►│                    │
 │            │                                      │                        │ getRange/getValues (Lock 없음) │
 │            │                                      │                        │◄───────────────────│
 │            │                                      │◄── {ok,data,count} ───│                    │
 │            │◄── {ok,data,source,count} ───────────│                        │                    │
 │            │ AA.cache = data                       │                        │                    │
 │            │ renderTable()/renderPagination()      │                        │                    │
 │◄───────────│ 목록 표시                              │                        │                    │
```
- 실패 시: 목록 영역에 "예약 목록을 불러오지 못했습니다." 표시(기존 슬롯 재사용), `AA.cache=[]`.

### 4.2 예약상태 변경 (Lock 필수)
```
사용자   상세 모달(admin_reservations_v2)    CMC_SheetsServiceV2    Apps Script(v3_final)         Sheet
 │ 상태 선택 후 저장 클릭  │                              │                              │              │
 │ ─────────────────────► │ saveStatus() [async]          │                              │              │
 │                         │ prevStatus 보관, 캐시 낙관적 갱신 │                            │              │
 │                         │ "Saving..." 표시(토스트 슬롯)   │                              │              │
 │                         │ ── await updateStatus(no,status) ──►│                        │              │
 │                         │                                │── POST updateStatus ───────►│              │
 │                         │                                │                              │ LockService.getScriptLock() 시도 │
 │                         │                                │                              │   실패→503 즉시 반환 │
 │                         │                                │                              │   성공→행탐색+상태값 setValue+부가타임스탬프 │
 │                         │                                │                              │   finally: releaseLock() │
 │                         │                                │◄── {ok,data} 또는 {ok:false,code:503} │
 │                         │◄── 응답 ───────────────────────│                              │              │
 │                         │ 실패 시 prevStatus 롤백 + 오류 문구 │                              │
```

### 4.3 관리자 메모 저장 (Lock 필수)
```
사용자   상세 모달(admin_reservations_v2)    CMC_SheetsServiceV2    Apps Script(v3_final)         Sheet
 │ 메모(textarea) 입력 후 저장 클릭(상태 저장과 동일 버튼) │                                        │
 │ ─────────────────────► │ saveStatus() 내부에서 메모 변경분 감지 │                              │
 │                         │ prevNote 보관, 캐시 낙관적 갱신        │                              │
 │                         │ "Saving..." 표시                       │                              │
 │                         │ ── await update(no, {note}) ──────────►│                              │
 │                         │                                │── POST update {no,data:{note}} ────►│              │
 │                         │                                │                              │ LockService 획득(동일 정책) │
 │                         │                                │                              │   특이사항(18번) setValue │
 │                         │                                │                              │   finally: releaseLock() │
 │                         │                                │◄── {ok,data} 또는 오류 ──────│              │
 │                         │◄── 응답 ───────────────────────│                              │              │
 │                         │ 실패 시 prevNote 롤백 + 오류 문구 │                              │
```
- 상태와 메모가 모두 변경된 경우: 상태 먼저 → 메모 다음 순서로 순차 호출, 각각 독립적으로 성공/실패 판정 및 롤백.

---

## 5. API Mapping Table

| UI Action | Apps Script Action | Method | Response |
|-----------|---------------------|--------|----------|
| 예약목록 조회 | `list` | GET | `{ok:true, data:[...], count:N}` |
| 예약검색 | (서버 액션 없음, 클라이언트 필터) | - | - |
| 예약상세 조회 | (캐시 조회) / fallback `get` | - / GET | - / `{ok:true, data:{...}}` |
| 예약상태 변경 | `updateStatus` | POST | `{ok:true, data:{reservationNo,status}, message}` / `{ok:false, error, code:503}` |
| 관리자 메모 저장 | `update`(payload: `{note}` 단일 필드) | POST | `{ok:true, data:{reservationNo}, message}` / `{ok:false, error, code:503}` |
| (내부 진단, 화면 비노출) | `ping` | GET | `{ok:true, message, sheetName, totalCols}` |

---

## 6. Non-Functional Requirements

| 항목 | 기준 |
|------|------|
| 응답시간 | 목록조회·상태변경·메모저장 각 API 호출 3초 이내 |
| 인코딩 | UTF-8 100% |
| 브라우저 지원 | Chrome 최신 버전 기준 |
| 반응형 | 기존 Responsive breakpoint·레이아웃 100% 유지 |
| 오류 처리 | Google Sheets/Apps Script 오류 시 자동 Retry 없이 오류 메시지 1회 표시 |

---

## 7. 상세 설계 결정 사항 (전부 확정)

### 7.1 통계 카드 처리 — 확정
- 통계 카드(전체/접수/확정/완료/취소변경)는 기존 `CMC_Stats`/`CMC_DB` 참조 로직을 그대로 유지(통계 제외 항목).
- Live 모드에서 통계 카드(Local)와 하단 목록(Sheets)의 데이터 출처가 다를 수 있음 — 알려진 제약사항으로 확정, 통합은 후속 KPI 티켓에서 진행.

### 7.2 메모 저장 API 방식 — 확정(옵션 A)
- `update` 액션 재사용, payload는 `{note}` 단일 필드로 강제. 다른 필드 전송 금지.

### 7.3 백엔드 Lock 정책 상세 설계 — 확정 (코드 미작성, 재배포 필요)
| 대상 함수 | 적용 방식(설계 수준 서술) |
|-----------|---------------------------|
| 상태변경 처리 경로 | 행 탐색 전 `LockService.getScriptLock()` 획득 시도(대기 한도 예: 10초). 실패 시 즉시 `{ok:false, code:503, error:'동시 요청이 많아 처리하지 못했습니다.'}` 반환. 성공 시 기존 로직 수행 후 반드시 `releaseLock()`. |
| 메모저장 처리 경로 | 동일한 획득/대기/실패응답/해제 패턴, 대상 컬럼은 특이사항(18번) 한 칸. |
- 액션명·응답 포맷·다른 액션(`create`/`list`/`get`/`summary`/`updateOps`) 로직은 변경하지 않음.
- Apps Script "새 버전" 재배포 필수(STEP 1.5.1의 배포 미반영 실수 재발 방지, QA에 재배포 확인 절차 포함).

### 7.4 로딩/저장 텍스트 처리 — 확정
- 목록 로딩: 기존 빈 상태 슬롯에 `"예약 목록을 불러오는 중입니다..."`
- 저장 중: 기존 토스트 슬롯에 `"저장 중입니다..."` → 완료 시 기존 성공 문구로 교체
- 실패 시: 동일 슬롯에 오류 문구(신규 스타일 없음)

### 7.5 메모 편집 UI 반영 방식 — 확정(허용)
- `dNote`를 읽기전용 `<span>`에서 편집 가능한 `<textarea>`로 전환. 위치·크기·스타일은 원본과 동일 유지.
- 저장 트리거는 신규 버튼 없이 기존 "💾 상태 저장" 버튼 재사용, 상태값과 메모 변경분을 함께 처리.

### 7.6 필터링 전략 — 확정
- 전체 목록 1회 조회 후 클라이언트 사이드 필터 유지(서버 쿼리 파라미터 연동은 범위 밖).

### 7.7 캐시 갱신 시점 — 확정
- 페이지 최초 진입, 상태변경/메모저장 성공 후, 수동 새로고침(F5) 시에만 갱신. 자동 폴링 없음.

### 7.8 sheetName 값 정정 — 확정(포함)
- `config_v2_new.js`의 `appsScript.sheetName` 기본값을 `'종합검진_예약대장'`으로 정정(표시용, API 동작에는 영향 없음).

---

## 8. Impact Analysis

### 8.1 영향받는 파일
| 구분 | 파일 | 영향 내용 |
|------|------|-----------|
| 신규 생성 | `app/pages/admin_reservations_v2_new.html` | 전체 신규. 원본 마크업 복제 + 데이터 계층 배선 |
| 변경(로직 보강, 액션/구조 불변) | `app/apps_script/sheets_api_v3_final.gs` | `updateStatus`/`update`(note) 경로에 LockService 추가 → **재배포 필요** |
| 변경(값 정정만) | `app/config_v2_new.js` | `appsScript.sheetName` 값만 정정, 구조·다른 필드 불변 |
| 무영향(원본 보존) | `app/pages/admin_reservations_new.html` | 무수정 |
| 무영향 | `app/services/db_service_new.js`, `app/services/stats_service_new.js` | 로직 무변경(Mock 위임/통계 카드 계속 사용) |
| 무영향 | `app/services/google_sheets_service_v2_new.js` | 어댑터 그대로 재사용, 액션 호환 확인됨 |
| 무영향 | `app/pages/reservation_v2_new.html`(STEP1), `admin_dashboard_*.html`(STEP2 이전 버전) | 별도 파일·별도 화면, 본 변경과 독립적 |

### 8.2 영향받는 사용자/업무
- **직접 영향**: 검진센터 관리자(예약관리 화면 사용자). 여러 담당자가 동일 예약 데이터를 실시간(수동 새로고침 기준) 공유하게 됨.
- **무영향**: 수검자(예약 신청자) — 예약신청 화면(`reservation_v2_new.html`)은 이미 STEP1에서 별도 전환 완료, 본 티켓과 독립.
- **운영 프로세스 영향**: 자동 폴링이 없으므로(7.7절) "다른 담당자의 변경사항은 새로고침 후 반영됨"을 관리자 교육/공지 사항으로 안내 필요.

### 8.3 데이터 영향
- 쓰기 대상 컬럼: 예약상태(15), 예약확정일(16, 조건부), 검진종료(22, 조건부), 특이사항(18) — 총 4개 컬럼 한정.
- 나머지 25개 컬럼은 본 화면에서 읽기만 발생, 쓰기 없음(예약 수정 제외 원칙과 정합).
- 기존 데이터(생년월일·희망검진일 등, STEP 1.5.1 DateFix 적용분) 형식·값에 영향 없음.

### 8.4 성능/트래픽 영향
- Apps Script 호출 빈도 증가: 화면 진입 시 GET 1회, 저장 동작 시 POST 1~2회(상태/메모). 관리 인원 소수(소규모 검진센터) 기준으로 quota 리스크는 낮음.
- Lock 도입으로 상태변경/메모저장 응답에 대기 시간이 소폭 추가될 수 있음(NFR 3초 기준 내 관리, 8절 리스크4 연계).

### 8.5 보안/개인정보 영향
- 신규로 노출되는 개인정보 필드 없음. 연락처 마스킹(`CMC.maskPhone`) 등 기존 처리 그대로 유지.
- Web App 액세스 권한('조직 내') 설정 원칙 재확인 필요(신규 조치 아님).

### 8.6 하위 호환성 영향
- 백엔드 응답 포맷(JSON 구조) 무변경 → STEP1(`reservation_v2_new.html`) 및 향후 STEP3(대시보드) 연동에 영향 없음.
- Lock 추가는 `_actionCreate`에 이미 적용된 패턴과 동일 구조 재사용 → 새로운 실패 모드는 "동시 요청 시 503" 1가지로 한정, 기존 성공 경로의 동작은 그대로 유지.

### 8.7 롤백 영향
- 프론트엔드 롤백(9절)은 백엔드에 영향 없음. 백엔드 Lock 보강은 응답 포맷을 바꾸지 않는 하위 호환 변경이라 프론트엔드만 되돌려도 정합성 문제 없음.
- 데이터 손실 위험 없음(모든 조치가 추가적 잠금/값 정정 수준).

---

## 9. Risk 분석

| # | 리스크 | 영향도 | 발생가능성 | 대응 방안 |
|---|--------|--------|------------|-----------|
| 1 | Lock 보강 배포가 반영되지 않은 채 QA 진행(STEP 1.5.1과 동일한 실수) | 중 | 중 | 배포 시 "새 버전" 선택 필수 절차를 QA·구현순서에 명시, 재배포 후 `?action=ping` 확인 |
| 2 | `update`(범용) 액션 재사용이 추후 다른 개발자에 의해 다중 필드 전송으로 확장되어 "예약 수정 제외" 원칙을 벗어날 가능성 | 중 | 낮음 | 프론트엔드 코드에서 payload를 `{note}` 한정 생성하는 단일 지점(헬퍼)으로 강제, 코드 리뷰 시 확인 |
| 3 | 통계 카드(Local)와 목록(Live) 데이터 출처 불일치로 사용자 혼선 | 낮음 | 확정적(구조적) | 8.2절/7.1절에 명시, 관리자 교육 시 안내 |
| 4 | Lock 적용으로 동시 요청 시 응답 지연 → 3초 NFR 기준 초과 가능 | 중 | 낮음 | Lock 대기 한도를 짧게 설정(예: 10초 내 실패 처리), 소규모 운영 환경 특성상 실제 동시성 낮음. QA에서 실측 |
| 5 | 개인정보 포함 응답 데이터 노출 | 높음(정보보호) | 낮음 | Web App 액세스 권한 '조직 내' 설정 재확인(기존 원칙) |

---

## 10. Rollback Plan

### 10.1 프론트엔드 롤백 (기본 경로)
```
admin_reservations_v2_new.html 제거
        ↓
기존 admin_reservations_new.html 사용
        ↓
Backend 변경 없음
```
- 프론트엔드 롤백은 백엔드에 영향을 주지 않음. Lock 보강은 응답 포맷을 바꾸지 않는 하위 호환 변경.

### 10.2 즉시 전환 롤백 (모드 스위치)
- `CMC_CONFIG.setDataSource('local'); location.reload();` → 즉시 localStorage 모드 복귀.

### 10.3 백엔드 자체 롤백
- Apps Script 배포 관리에서 Lock 보강 이전 버전으로 배포 버전만 되돌리는 것도 가능(프론트엔드 롤백과 별개 경로).

### 10.4 설정 오염 시
- localStorage 키 `cmc_config_v2` 삭제 후 새로고침 → 기본값(`local`) 복귀.

---

## 11. QA Checklist

**기능 검증**
- [ ] LOCAL 모드: 목록·검색·필터가 원본과 동일하게 동작하는가
- [ ] GOOGLE 모드: 페이지 진입 시 Sheet(`종합검진_예약대장`)의 실제 데이터가 목록에 표시되는가
- [ ] GOOGLE 모드: 상태변경 시 예약상태(15)/예약확정일(16)/검진종료(22) 컬럼이 정상 반영되는가
- [ ] GOOGLE 모드: 메모 저장 시 특이사항(18) 컬럼이 정상 반영되는가
- [ ] 상태+메모 동시 변경 후 저장 시 두 값 모두 정상 반영(순차 호출) 되는가
- [ ] API 실패 인위 재현 시 상태/메모 각각 낙관적 갱신이 정상 롤백되는가

**Lock/동시성 검증**
- [ ] 백엔드 재배포 시 "새 버전"으로 배포했는지 확인(`?action=ping`으로 최신 반영 확인)
- [ ] 두 세션에서 동일 예약번호 동시 상태변경 시, 하나는 성공·하나는 503으로 안전 처리되는가
- [ ] 503 발생 시 자동 재시도 없이 명확한 오류 문구가 표시되는가

**성능/NFR**
- [ ] 목록조회·상태변경·메모저장 각 API 응답 3초 이내(Network 탭 측정)
- [ ] 한글 데이터(성명·메모) 왕복 후 인코딩 깨짐 없음
- [ ] Chrome 최신 버전 정상 동작
- [ ] 모바일/태블릿 반응형 레이아웃 기존과 동일
- [ ] Sheets 응답 실패 강제 재현 시 자동 재시도 없이 오류 메시지 1회 표시

**UI 무결성 검증(추가)**
- [ ] `dNote` textarea 전환 후 레이아웃(위치/크기/스타일)이 원본과 동일한지 스크린샷 비교
- [ ] 그 외 화면 요소(통계 카드, 필터바, 테이블, 페이지네이션, CSV 버튼)에 시각적 변경이 없는지 확인

**회귀(Regression)**
- [ ] 원본 `admin_reservations_new.html` 무수정·정상 동작
- [ ] 통계 카드가 기존과 동일하게 `CMC_DB` 기준 표시(목록과 값 달라도 화면 정상)
- [ ] `reservation_v2_new.html`(STEP1) 예약 등록 흐름 정상 동작
- [ ] `config_v2_new.js` sheetName 값 정정이 다른 화면(연동설정 화면 등)에 부작용 없는지 확인

---

## 12. Definition of Done

1. `admin_reservations_v2_new.html` 신규 생성, 원본 무수정 보존 확인.
2. `sheets_api_v3_final.gs`에 Lock 보강 적용 및 "새 버전" 재배포 완료.
3. `config_v2_new.js`의 sheetName 값 정정 완료.
4. 11절 QA Checklist 전 항목(기능/Lock·동시성/성능·NFR/UI 무결성/회귀) 통과.
5. 롤백 경로(10절) 시연 완료.
6. 통계 카드가 본 티켓 범위 밖(Local 유지)임이 코드 리뷰로 확인됨.
7. 메모 저장이 `update` 액션에서 `note` 단일 필드만 전송함이 코드 리뷰로 확인됨.
8. 구현은 본 문서 승인 후 별도 세션에서 진행, 본 문서에는 구현 코드 미포함.

---

## 13. 구현 순서 (Implementation Plan — 별도 세션에서 수행)

> 아래 순서는 설계 문서 기준 작업 계획이며, 코드 작성은 포함하지 않는다. 실제 구현은 별도 세션에서 이 순서를 따라 진행한다.

| 순서 | 단계 | 목표 | 산출물 | 검증 체크포인트 |
|------|------|------|--------|------------------|
| 1 | 백엔드 Lock 보강 | `updateStatus`/`update`(note) 경로에 LockService 획득·해제 로직 추가(7.3절 설계 반영) | 수정된 `sheets_api_v3_final.gs`, "새 버전" 재배포 | `?action=ping` 정상 응답, 기존 단건 상태변경 정상 동작(회귀) |
| 2 | sheetName 값 정정 | `config_v2_new.js`의 `appsScript.sheetName`을 `'종합검진_예약대장'`으로 수정 | 수정된 `config_v2_new.js` | `ping()` 응답 메시지에 올바른 시트명 표시 |
| 3 | 신규 화면 뼈대 생성 | 원본 `admin_reservations_new.html` 전체를 `admin_reservations_v2_new.html`로 복제(마크업 100% 동일) | 신규 파일 | 원본과 시각적 diff 없음 확인 |
| 4 | 스크립트 로드 교체 | `db_service_new.js` 유지, `config_v2_new.js` + `google_sheets_service_v2_new.js` 로드 추가 | 스크립트 태그 구성 | 콘솔 오류 없이 로드 확인 |
| 5 | 목록조회 배선 | `init()` async 전환, `CMC_SheetsServiceV2.getAll()` 연동, `AA.cache` 도입, `getFiltered()`를 캐시 기반으로 전환 | 배선된 목록조회 로직 | LOCAL 모드에서 원본과 동일 목록 표시 |
| 6 | 로딩/에러 텍스트 적용 | 기존 빈 상태 슬롯에 Loading/오류 문구 적용(7.4절) | 텍스트 처리 로직 | 신규 시각 요소 없음, 문구만 상황별 교체 확인 |
| 7 | 메모 편집 요소 전환 | `dNote`를 `<span>`→`<textarea>`로 전환(7.5절), 위치·스타일 동일 유지 | 수정된 상세 모달 마크업 | 레이아웃 스크린샷 비교로 무변화 확인 |
| 8 | 상태변경 배선 | `saveStatus()` async 전환, `updateStatus()` 호출 + 낙관적 갱신/롤백 구현(4.2절) | 배선된 상태변경 로직 | LOCAL 모드 정상 동작, 실패 시나리오 롤백 확인 |
| 9 | 메모저장 배선 | 동일 `saveStatus()` 흐름 내 메모 변경분 감지 → `update({note})` 호출(옵션 A), 순차 처리(상태 먼저) | 배선된 메모저장 로직 | LOCAL 모드 정상 동작, 실패 시나리오 롤백 확인 |
| 10 | Live 통합 검증 | 실배포 URL로 `dataSource='google'` 전환 후 목록/상태/메모 각 API 실동작 확인 | QA 결과 기록 | 11절 QA Checklist "기능 검증(GOOGLE)" 전체 통과 |
| 11 | Lock/동시성 검증 | 두 세션 동시 상태변경 요청으로 503 처리 확인 | QA 결과 기록 | 11절 "Lock/동시성 검증" 전체 통과 |
| 12 | 성능/NFR 측정 | 각 API 응답시간, 인코딩, 브라우저, 반응형 확인 | 측정 결과 기록 | 11절 "성능/NFR" 전체 통과 |
| 13 | 회귀 검증 | 원본 화면, 대시보드, STEP1 예약신청 화면 무영향 확인 | 회귀 결과 기록 | 11절 "회귀" 전체 통과 |
| 14 | 최종 승인 | DoD(12절) 전 항목 충족 확인 후 PM 최종 승인 요청 | 구현 완료 보고 | DoD 8개 항목 체크 완료 |

---

## 14. 화면 요소 매핑 요약 (참고)

| 화면 요소 | 상태 |
|-----------|------|
| 통계 카드 5종 | 변경 없음(Local 유지) |
| 검색/필터 바 | 변경 없음(클라이언트 필터 유지) |
| 목록 테이블 | 데이터 소스만 Sheets로 전환, 마크업 무변경 |
| 상세 모달 - 특이사항(dNote) | `<span>` → `<textarea>` 전환 확정(⑥) |
| 상세 모달 - "💾 상태 저장" 버튼 | 문구·위치 무변경, 동작만 상태+메모 동시 처리로 확장 |
| CSV 다운로드 버튼 | 변경 없음(Excel 제외 항목) |

---

*본 문서는 설계 검토 전용이며 코드 변경을 포함하지 않는다. 설계는 본 문서로 종료되며, 구현은 별도 세션에서 진행한다. v1·v2 초안은 동일 폴더에 보존됨.*
