# DEV-003 v2 — 관리자 예약관리(admin_reservations) Google Sheets Live 연동 설계 문서

> 문서 유형: **PM 승인용 설계 문서 (Design Only, 구현 코드 미포함)**
> 버전: v2 (PM 검토 반영판) | 원본 초안: `DEV-003_관리자예약관리_Sheets연동_Design_new.md` (v1, 보존)
> 작성일: 2026-07-01
> 저장 위치: `99_임시보관_정리대기/CMC_Platform_new/`

## 개정 이력

| 버전 | 일자 | 변경 내용 |
|------|------|-----------|
| v1 | 2026-07-01 | 최초 설계 초안 (범위: 목록조회·검색·상태변경, 통계 카드 처리방안 포함) |
| v2 | 2026-07-01 | PM 검토 반영 — 범위 확정(관리자 메모저장 추가 / Dashboard·KPI·통계·Excel 등 명시 제외), Lock 정책 확정(상태변경·메모저장 필수), Production Baseline·NFR 절 신설, Rollback/QA/DoD를 PM 지정 형식으로 재구성 |

---

## 1. PM 승인 확정 사항

### ① 신규 파일 생성
- `admin_reservations_v2_new.html` 신규 생성으로 확정
- 원본 `admin_reservations_new.html` 수정 금지(그대로 보존)
- 파일명 `_new` 규칙 유지

### ② DEV-003 범위 확정

**포함(In-Scope)**
| # | 기능 | 비고 |
|---|------|------|
| 1 | 예약목록 조회 | `list` 액션 |
| 2 | 예약검색 | 클라이언트 사이드 필터(기존 로직 유지) |
| 3 | 예약상세 조회 | 캐시 조회 우선, `get` 액션은 예외 상황 대비 fallback |
| 4 | 예약상태 변경 | `updateStatus` 액션 |
| 5 | 관리자 메모 저장 | `update` 액션(payload를 note 단일 필드로 한정, 7.2절) |
| 6 | Google Sheets Live 연동 | `CMC_SheetsServiceV2` + `sheets_api_v3_final.gs` |

**제외(Out-of-Scope)**
| 제외 항목 | 비고 |
|-----------|------|
| Dashboard | STEP 3 별도 과제 |
| KPI | STEP 3 별도 과제 |
| Summary | 백엔드 `summary` 액션 존재하나 본 화면 미사용 |
| 통계 | 화면 상단 통계 카드는 현행 유지(7.1절) |
| Excel | 기존 CSV 다운로드 버튼은 현행 그대로 유지, 신규 설계 없음 |
| Calendar | STEP 5 별도 과제 |
| Drag & Drop | 해당 없음 |
| 권한관리 | STEP 6 별도 과제 |
| 예약 수정 | 성명·연락처·프로그램 등 다중 필드 편집 UI/기능 미포함(메모 저장과 구분) |
| 예약 삭제 | 해당 없음 |

### ③ 로딩 처리
- 기존 UI(레이아웃·구성요소) 변경 금지
- Spinner 등 신규 시각 요소 추가 금지
- 허용되는 표현은 텍스트뿐: `Loading...`, `Saving...`
- 표시 위치: 기존에 존재하는 텍스트 슬롯(빈 목록 안내 영역, 토스트 영역)을 재사용

### ④ Lock 정책
| 동작 | Lock 사용 여부 |
|------|----------------|
| 조회(목록/상세) | 사용 안 함 |
| 상태 변경 | 필수 |
| 메모 저장 | 필수 |

---

## 2. Production Baseline

현재 운영 기준을 아래와 같이 명시한다. (신규 배포·신규 스프레드시트 생성 없음, 기존 자산 그대로 사용)

| 항목 | 값 |
|------|-----|
| Backend 스크립트 | `sheets_api_v3_final.gs` (실배포본, 독립형 스크립트 · `SPREADSHEET_ID` 고정 참조) |
| Google Sheets 문서 | `종합검진_예약대장` (시트명, 29컬럼) |
| 배포 상태 | Current Production Deployment (Web App, `/exec` URL 발급 완료 — STEP 0/1에서 검증됨) |
| Timezone | Asia/Seoul |
| 날짜/시간 포맷 | STEP 1.5.1 DateFix 적용됨(생년월일·희망검진일 → `yyyy-MM-dd`, 희망시간 → `HH:mm`) |

**Reservation API 현황 (배포된 액션 목록)**

| 그룹 | 액션 | Method | 현재 상태 | 본 티켓 사용 여부 |
|------|------|--------|-----------|--------------------|
| Reservation | `create` | POST | 구현·검증 완료(STEP 1) | 미사용 |
| Reservation | `get` | GET | 구현 완료 | 사용(상세조회 fallback) |
| Reservation | `list` | GET | 구현 완료 | 사용(목록조회) |
| Reservation | `summary` | GET | 구현 완료 | 미사용(통계 제외) |
| Admin | `list`(재사용) | GET | 구현 완료 | 사용 |
| Admin | `get`(재사용) | GET | 구현 완료 | 사용(fallback) |
| Admin | `updateStatus` (Status) | POST | **Lock 미적용 — 본 티켓에서 보강 필요(7.3절)** | 사용 |
| Admin | `update` (Note) | POST | **Lock 미적용 — 본 티켓에서 보강 필요(7.3절)**, note 단일 필드 한정 사용 | 사용 |

> **중요**: v1 문서에서는 "Apps Script 백엔드 코드 수정 없음"을 Out-of-Scope로 명시했으나, PM 승인된 Lock 정책(④)을 만족하려면 `updateStatus`/`update`(note) 경로에 LockService 보강이 필요하다. 따라서 v2에서는 **백엔드 변경 범위를 "Lock 로직 추가에 한정"** 하는 것으로 재정의한다(액션명·응답 포맷·컬럼 구조·다른 액션 로직은 무변경).

---

## 3. Architecture Diagram

### 3.1 PM 지정 기본 구조
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
[config_v2_new.js : CMC_CONFIG.dataSource]
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
- 통계 카드(전체/접수/확정/완료/취소변경)는 본 다이어그램 경로와 무관하게 **기존 `CMC_Stats`/`CMC_DB` 그대로 유지**(7.1절, 통계 제외 항목).

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
- 실패 시: 목록 영역에 "예약 목록을 불러오지 못했습니다." 텍스트 표시(6.3절/기존 슬롯 재사용), `AA.cache=[]`.

### 4.2 예약상태 변경 (Lock 필수)
```
사용자   상세 모달(admin_reservations_v2)    CMC_SheetsServiceV2    Apps Script(v3_final)         Sheet
 │ 상태 선택 후 저장 클릭  │                              │                              │              │
 │ ─────────────────────► │ saveStatus() [async]          │                              │              │
 │                         │ prevStatus 보관, 캐시 낙관적 갱신 │                            │              │
 │                         │ "Saving..." 텍스트 표시(토스트 슬롯 재사용) │                  │              │
 │                         │ ── await updateStatus(no,status) ──►│                        │              │
 │                         │                                │── POST updateStatus ───────►│              │
 │                         │                                │                              │ LockService.getScriptLock() 시도 │
 │                         │                                │                              │   실패→503 즉시 반환(대기X) │
 │                         │                                │                              │   성공→행탐색+상태값 setValue+부가타임스탬프 │
 │                         │                                │                              │   finally: releaseLock() │
 │                         │                                │◄── {ok,data} 또는 {ok:false,code:503} │
 │                         │◄── 응답 ───────────────────────│                              │              │
 │                         │ 실패 시 prevStatus로 롤백 + 오류 텍스트("상태 변경에 실패했습니다") │            │
```

### 4.3 관리자 메모 저장 (Lock 필수, 신규 시퀀스)
```
사용자   상세 모달(admin_reservations_v2)    CMC_SheetsServiceV2    Apps Script(v3_final)         Sheet
 │ 메모 입력 후 저장 클릭(상태 저장과 동일 버튼, 7.4절) │                                          │
 │ ─────────────────────► │ saveStatus() 내부에서 메모 변경분 감지 │                              │
 │                         │ prevNote 보관, 캐시 낙관적 갱신        │                              │
 │                         │ "Saving..." 텍스트 표시                │                              │
 │                         │ ── await update(no, {note}) ──────────►│                              │
 │                         │                                │── POST update {no,data:{note}} ────►│              │
 │                         │                                │                              │ LockService 획득(동일 정책) │
 │                         │                                │                              │   특이사항(18번) setValue │
 │                         │                                │                              │   finally: releaseLock() │
 │                         │                                │◄── {ok,data} 또는 오류 ──────│              │
 │                         │◄── 응답 ───────────────────────│                              │              │
 │                         │ 실패 시 prevNote로 롤백 + 오류 텍스트 │                              │
```
- 상태와 메모가 모두 변경된 경우: **상태 먼저 → 메모 다음** 순서로 순차 호출(각각 독립적으로 성공/실패 판정 및 개별 롤백).

---

## 5. API Mapping Table

| UI Action | Apps Script Action | Method | Response |
|-----------|---------------------|--------|----------|
| 예약목록 조회 | `list` | GET | `{ok:true, data:[...], count:N}` |
| 예약검색 | (서버 액션 없음, 클라이언트 필터) | - | - |
| 예약상세 조회 | (캐시 조회, 서버 호출 없음) / fallback `get` | - / GET | - / `{ok:true, data:{...}}` |
| 예약상태 변경 | `updateStatus` | POST | `{ok:true, data:{reservationNo,status}, message}` 또는 `{ok:false, error, code:503}`(Lock 실패) |
| 관리자 메모 저장 | `update` (payload: `{note}` 단일 필드) | POST | `{ok:true, data:{reservationNo}, message}` 또는 `{ok:false, error, code:503}`(Lock 실패) |
| (내부 진단, 화면 비노출) | `ping` | GET | `{ok:true, message, sheetName, totalCols}` |

---

## 6. Non-Functional Requirements

| 항목 | 기준 |
|------|------|
| 응답시간 | 목록조회·상태변경·메모저장 각 API 호출 3초 이내 완료 |
| 인코딩 | UTF-8 100% (한글 성명·메모 등 왕복 시 깨짐 없음) |
| 브라우저 지원 | Chrome 최신 버전 기준(타 브라우저 검증은 본 티켓 범위 밖) |
| 반응형 | 기존 Responsive breakpoint 및 레이아웃 100% 유지 |
| 오류 처리 | Google Sheets/Apps Script 오류 발생 시 **자동 Retry 없이** 오류 메시지를 1회 표시하고 종료(사용자가 수동 재시도) |

---

## 7. 상세 설계 결정 사항

### 7.1 통계 카드 처리 (v1 대비 변경)
- v1에서는 통계 카드를 캐시 기반으로 재계산하는 방안을 제시했으나, PM이 "통계/KPI"를 명시적으로 Out-of-Scope로 확정함에 따라 **통계 카드(전체/접수/확정/완료/취소변경)는 기존 `CMC_Stats`/`CMC_DB` 참조 로직을 그대로 유지**한다.
- 결과적으로 Live 모드에서는 **통계 카드(Local 기준)와 하단 목록(Sheets 기준)의 데이터 출처가 다를 수 있음**을 알려진 제약사항으로 명시한다. 통합은 후속 KPI/통계 티켓에서 다룬다.

### 7.2 메모 저장 API 방식 (PM 확인 필요, 열린 항목)
백엔드에 메모 전용 액션이 없어 두 가지 방식 중 선택이 필요하다.

| 옵션 | 방식 | 장점 | 단점 |
|------|------|------|------|
| A (권장) | 기존 `update` 액션을 재사용하되 payload를 `{note}` 단일 필드로 제한 | 백엔드 신규 액션 불필요, Lock 보강만으로 충족 | "예약 수정 제외" 원칙과 문언상 경계가 모호 — 실제로는 note 1개 필드만 전송되므로 기능적으로는 "메모 저장"에 한정됨을 코드 레벨에서 강제 필요 |
| B | Apps Script에 `updateNote` 전용 액션 신규 추가 | 의미적으로 명확히 분리, "예약 수정"과 완전히 구분 | 백엔드 신규 액션 작성 필요(범위 확대) |

→ **권장: 옵션 A.** 프론트엔드에서 `update` 호출 시 payload에 `note` 외 다른 키를 절대 포함하지 않도록 강제(코드 레벨 단일 책임)하는 조건으로 진행. PM 승인 필요.

### 7.3 백엔드 Lock 정책 상세 설계 (변경 필요, 코드 미작성)
현재 `sheets_api_v3_final.gs`는 `_actionCreate`에만 LockService가 적용되어 있다. Lock 정책(④)을 만족하려면 아래 두 경로에 동일한 패턴을 확장해야 한다.

| 대상 함수 | 적용 방식(설계 수준 서술) |
|-----------|---------------------------|
| 상태변경 처리 경로 | 행 탐색을 시작하기 전 `LockService.getScriptLock()`을 획득 시도(대기 한도 예: 10초). 획득 실패 시 즉시 `{ok:false, code:503, error:'동시 요청이 많아 처리하지 못했습니다.'}` 반환. 획득 성공 시 기존 행탐색+상태값 설정+부가 타임스탬프 로직을 그대로 수행 후, 처리 결과와 무관하게 반드시 잠금 해제(`releaseLock`)까지 완료. |
| 메모저장 처리 경로(`update`, note 단일 필드) | 위와 동일한 획득/대기/실패응답/해제 패턴을 적용하되, 대상 컬럼은 특이사항(18번) 한 칸만 변경. |

- 액션명, 요청/응답 JSON 구조, 다른 컬럼·다른 액션(`create`/`list`/`get`/`summary`/`updateOps`)의 동작은 **일체 변경하지 않음**.
- 이 보강은 **Apps Script 재배포(새 버전)** 가 필요하며, STEP 1.5.1에서 겪었던 "배포 미반영" 실수(Code.gs 저장만으로는 `/exec` 버전이 갱신되지 않음)를 재발하지 않도록 QA 절차에 재배포 확인 항목을 포함한다(9절).

### 7.4 로딩/저장 텍스트 처리 (기존 슬롯 재사용)
- 목록 로딩: 기존 "조회된 예약이 없습니다" 빈 상태 텍스트 슬롯을 `"예약 목록을 불러오는 중입니다..."`로 교체 표시.
- 상태/메모 저장 중: 기존 토스트(`AA.toast()`) 슬롯에 `"저장 중입니다..."` 표시 → 완료 시 기존 성공 문구로 교체.
- 실패 시: 동일 토스트 슬롯에 오류 문구 표시(신규 색상/스타일 추가 없음).

### 7.5 메모 편집 UI 반영 방식 (PM 확인 필요, 열린 항목)
- 현재 상세 모달의 특이사항(`id="dNote"`)은 읽기 전용 `<span>`이며 편집 기능이 없다.
- 메모 저장 기능을 구현하려면 이 슬롯을 **동일한 위치·크기·스타일을 유지한 채 편집 가능한 입력 요소로 전환**해야 한다. 이는 신규 요소 추가가 아니라 기존 요소의 편집 가능 여부만 바꾸는 최소 변경이나, "기존 UI 변경 금지" 원칙과 접점이 있어 명시적으로 승인 요청한다.
- 저장 트리거는 신규 버튼을 추가하지 않고 **기존 "💾 상태 저장" 버튼을 재사용**하여 상태값과 메모 변경분을 함께 처리한다(4.3절 시퀀스).

### 7.6 필터링 전략
- v1과 동일하게 유지: 전체 목록 1회 조회 후 클라이언트 사이드에서 기존 검색/필터 로직 그대로 적용(서버 쿼리 파라미터 연동은 범위 밖).

### 7.7 캐시 갱신 시점
- 페이지 최초 진입, 상태변경/메모저장 성공 후, 수동 새로고침(F5) 시에만 갱신. 자동 폴링 없음(범위 밖).

### 7.8 Production Baseline 부수 확인 사항
- `config_v2_new.js`의 `appsScript.sheetName` 기본값(`'예약현황'`)이 실제 배포 시트명(`'종합검진_예약대장'`)과 다름. API 동작에는 영향 없으나(표시용) 운영 혼선 방지를 위해 값 정정 여부 확인 필요(부수 작업, 별도 코드 1줄 변경).

---

## 8. Risk 분석

| # | 리스크 | 영향도 | 발생가능성 | 대응 방안 |
|---|--------|--------|------------|-----------|
| 1 | Lock 보강 배포가 반영되지 않은 채(STEP 1.5.1과 동일한 실수) QA를 진행 | 중 | 중 | 배포 시 "새 버전" 선택 필수 절차를 QA 체크리스트에 명시(9절), 재배포 후 `?action=ping` 확인 |
| 2 | 메모 저장에 `update`(범용) 액션을 재사용함에 따라 "예약 수정 제외" 원칙과 범위 해석 충돌 가능 | 중 | 중 | 7.2절 옵션 A/B 명시 후 PM 승인 획득, 프론트엔드에서 note 외 필드 전송 금지 강제 |
| 3 | 통계 카드(Local)와 목록(Live)의 데이터 출처 불일치로 사용자 혼선 | 낮음 | 확정적(구조적) | 7.1절 명시적 제약사항 문서화, 필요 시 후속 통계 티켓에서 통합 |
| 4 | 두 액션(상태변경/메모저장)에 Lock 적용 시 대기시간 증가로 3초 NFR 기준 초과 가능 | 중 | 낮음 | Lock 대기 한도를 짧게 설정(예: 10초 내 실패 처리)하고, 실제 동시 요청 빈도가 낮은 소규모 운영 환경임을 감안. NFR 측정 QA 항목 포함 |
| 5 | 메모 편집 슬롯 전환(7.5절)이 "기존 UI 변경 금지"에 저촉된다고 판단될 경우 기능 자체 재설계 필요 | 중 | 중 | PM 사전 승인 필수 항목으로 별도 확인(13절) |
| 6 | 개인정보 포함 응답 데이터 노출 | 높음(정보보호) | 낮음 | Web App 액세스 권한 '조직 내' 설정 기존 원칙 재확인(신규 조치 아님) |

---

## 9. Rollback Plan

### 9.1 프론트엔드 롤백 (기본 경로)
```
admin_reservations_v2_new.html 제거
        ↓
기존 admin_reservations_new.html 사용
        ↓
Backend 변경 없음
```
- 프론트엔드 롤백은 백엔드에 영향을 주지 않는다. Lock 정책 보강은 응답 포맷을 바꾸지 않는 하위 호환 변경이므로, 원본 화면으로 되돌아가도 백엔드를 별도로 되돌릴 필요가 없다.

### 9.2 즉시 전환 롤백 (모드 스위치)
- Live 모드 오류 발생 시: `CMC_CONFIG.setDataSource('local'); location.reload();` → 즉시 localStorage 모드 복귀.

### 9.3 백엔드 자체 롤백 (Lock 보강 결함 발견 시)
- Apps Script 배포 관리에서 Lock 보강 이전 버전으로 배포 버전만 되돌리는 것도 가능(9.1절 프론트엔드 롤백과는 별개 경로).

### 9.4 설정 오염 시
- localStorage 키 `cmc_config_v2` 삭제 후 새로고침 → 기본값(`local`) 복귀.

---

## 10. QA Checklist

**기능 검증**
- [ ] LOCAL 모드: 목록·검색·필터가 원본 `admin_reservations_new.html`과 동일하게 동작하는가
- [ ] GOOGLE 모드: 페이지 진입 시 Sheet(`종합검진_예약대장`)의 실제 데이터가 목록에 표시되는가
- [ ] GOOGLE 모드: 상태변경 시 예약상태(15번) 컬럼이 실제로 갱신되는가('예약확정'→16번, '검진완료'→22번 자동기록 포함)
- [ ] GOOGLE 모드: 메모 저장 시 특이사항(18번) 컬럼이 실제로 갱신되는가
- [ ] 상태+메모를 동시에 변경 후 저장 시 두 값 모두 정상 반영되는가(순차 호출 확인)
- [ ] 상태변경/메모저장 API 실패를 인위 재현 시 낙관적 갱신이 각각 정상 롤백되는가

**Lock/동시성 검증**
- [ ] 백엔드 재배포 시 "새 버전"으로 배포했는지 확인(`?action=ping` 응답의 배포 버전 확인)
- [ ] 두 브라우저 탭에서 동일 예약번호에 대해 거의 동시에 상태변경 요청 시, 하나는 성공하고 다른 하나는 503 오류로 안전하게 처리되는지 확인
- [ ] 503 오류 발생 시 사용자에게 명확한 오류 문구가 표시되는지(자동 재시도 없음, NFR 5절)

**성능/NFR**
- [ ] 목록조회·상태변경·메모저장 각 API 응답이 3초 이내인지 개발자도구 Network 탭으로 측정
- [ ] 한글 데이터(성명·메모) 왕복 후 인코딩 깨짐이 없는지 확인
- [ ] Chrome 최신 버전에서 정상 동작 확인
- [ ] 모바일/태블릿 반응형 레이아웃이 기존과 동일하게 유지되는지 확인
- [ ] Google Sheets 응답 실패(예: 잘못된 URL)를 강제 재현 시, 자동 재시도 없이 오류 메시지가 1회만 표시되는지 확인

**회귀(Regression)**
- [ ] 원본 `admin_reservations_new.html`이 변경 없이 정상 동작하는가
- [ ] 통계 카드가 기존과 동일하게 `CMC_DB` 기준으로 표시되는가(목록과 값이 달라도 화면 깨짐 없음)
- [ ] `reservation_v2_new.html`(STEP1 산출물) 예약 등록 흐름이 본 변경과 무관하게 정상 동작하는가

---

## 11. Definition of Done

1. `admin_reservations_v2_new.html` 신규 생성, 원본 `admin_reservations_new.html` 무수정 보존 확인.
2. `sheets_api_v3_final.gs`에 상태변경·메모저장 경로 Lock 보강이 적용되고 "새 버전"으로 재배포 완료.
3. 10절 QA Checklist 전 항목(기능/Lock·동시성/성능·NFR/회귀) 통과.
4. `dataSource='local'` 즉시 롤백 및 원본 파일 교체 롤백(9절) 시연 완료.
5. 통계 카드가 본 티켓 범위 밖(Local 유지)임이 코드 리뷰로 확인됨.
6. 메모 저장이 `update` 액션에서 `note` 단일 필드만 전송함이 코드 리뷰로 확인됨(7.2절 옵션 A 채택 시).
7. 13절 "잔여 확인 필요 사항" 전 항목에 대한 PM 서면 회신 확보.
8. 구현은 본 문서 승인 후 별도 세션에서 진행하며, 본 문서에는 구현 코드가 포함되지 않음.

---

## 12. 화면 요소 매핑 요약 (참고)

| 화면 요소 | v1 대비 상태 |
|-----------|--------------|
| 통계 카드 5종 | 변경 없음(Local 유지, 7.1절) |
| 검색/필터 바 | 변경 없음(클라이언트 필터 유지) |
| 목록 테이블 | 데이터 소스만 Sheets로 전환, 마크업 무변경 |
| 상세 모달 - 특이사항(dNote) | **읽기전용 → 편집가능 전환 필요**(7.5절, PM 확인 필요) |
| 상세 모달 - "💾 상태 저장" 버튼 | 문구·위치 무변경, 동작만 상태+메모 동시 처리로 확장 |
| CSV 다운로드 버튼 | 변경 없음(Excel 제외 항목, 현행 유지) |

---

## 13. 잔여 확인 필요 사항 (PM 승인 요청)

1. **메모 저장 API 방식**: 7.2절 옵션 A(`update` 재사용, note 단일 필드 한정) 채택 여부. 옵션 B(전용 `updateNote` 액션 신규) 선호 시 백엔드 범위 확대 승인 필요.
2. **메모 편집 UI 전환**: 7.5절 — 특이사항 표시 슬롯을 읽기전용에서 편집가능으로 전환하는 것이 "기존 UI 변경 금지" 원칙의 허용 범위인지 확인.
3. **백엔드 Lock 보강 승인**: Production Baseline(2절)에 명시한 대로, 이번 티켓이 프론트엔드 신규 파일 생성뿐 아니라 `sheets_api_v3_final.gs`의 Lock 로직 보강(재배포 포함)까지 포함하는 것에 동의하는지 확인.
4. **`config_v2_new.js` sheetName 값 정정**(7.8절, 부수 작업): 이번 티켓에서 함께 처리할지, 별도 항목으로 분리할지 확인.

---

*본 문서는 설계 검토 전용이며 코드 변경을 포함하지 않음. v1 초안은 동일 폴더에 보존됨.*
