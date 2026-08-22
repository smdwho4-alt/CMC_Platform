# Sprint8 DR-B-01 PoC#2 — GAS CacheService Eviction 격리 실행계획

> **상태**: 실행계획 초안(Draft). GAS 접속·실행·배포 없음. 실제 측정 결과 없음. 수치는 PROPOSED INITIAL VALUE 또는 EXECUTION-TIME OFFICIAL VERIFICATION REQUIRED로만 표시한다. Commit 없음.
> **작성일**: 2026-08-22(Sprint8 Pre-G1-B-D)
> **기준선**: `main`/`origin/main` = `6ffc5cf3dab48268816dd38e9923b8f3353e538e`

---

## 1. 목적

ADR-017 §29 PoC#2("GAS CacheService의 실제 eviction 빈도를 이 시스템의 예상 트래픽 규모로 시뮬레이션")를 운영 GAS·Google Sheets와 완전히 분리된 격리 환경에서 실행하기 위한 **실행계획**을 작성한다. 이 문서는 계획 작성 및 정적 검증까지만 수행하며, 실제 GAS 접속·Apps Script 작성·실행은 포함하지 않는다.

## 2. 범위·제외 범위

**범위**: PoC#2(GAS CacheService eviction 시뮬레이션) 실행을 위한 격리 환경 요구사항, 시나리오 12건, 측정항목, 성공·중단·실패 기준, 승인 Gate 정의.

**제외 범위**: PoC#1(SQLite, 완료·Push됨 — `docs/Sprint8_DR_B_01_PoC1_SQLite_Atomicity_Report.md`), PoC#3(저장소 정합성 불일치 처리 검증), DR-B-02(Idempotency 부하검증), Commit8-3b 실제 구현, 실제 GAS 프로젝트 생성·배포, Google Sheets 접근, Apps Script 코드 작성, 실제 PoC#2 실행.

## 3. 기준선 Commit

`6ffc5cf3dab48268816dd38e9923b8f3353e538e`(HEAD=main=origin/main, Pre-G1-A-P 완료 시점).

## 4. 근거 문서·코드

| 문서/코드 | 확인 내용 |
|---|---|
| `ADR-017_FastAPI_Proxy_and_Signed_GAS_Operations.md` §13 | Nonce 이중저장 구조에서 GAS CacheService(TTL 300초)를 2차 방어로 채택, "CacheService 단독 사용은 채택하지 않는다"(공식 확인된 1,000항목 상한·비영속성 근거) |
| `ADR-017_FastAPI_Proxy_and_Signed_GAS_Operations.md` §29 | PoC#2 정의: "GAS CacheService의 실제 eviction 빈도를 이 시스템의 예상 트래픽 규모로 시뮬레이션" — GAS 실사용이므로 별도 PM 승인·격리환경 확보 전 착수 금지(Commit8-3a STEP3-G 보완) |
| `docs/Sprint8_Security_Architecture_Design.md` §23 | DR-B-01 PoC 3건이 Pre-Implementation Harness로 수행되며, 항목(2)는 별도 PM 승인·격리 테스트 환경 필요 |
| `docs/Sprint8_Security_Test_and_Deployment_Gate_Plan.md` §16/§40 | REPLAY 영역 Test ID(REPLAY-01~03)와 Pre-G1 보조 Gate의 PoC#2 승인 경계 정의 |
| `docs/Sprint8_DR_B_01_PoC1_SQLite_Atomicity_Report.md` | PoC#1(SQLite UNIQUE 원자성) 완료 결과 — PASS, PoC#2·#3·DR-B-02 미착수로 명시(§17) |
| `src/auth/service_hmac.py` | Nonce 저장소 관련 코드 없음(docstring상 "Commit8-3 설계 대상") — Production nonce 구현 부재 재확인 |
| `app/apps_script/sheets_api_v3_final.gs`(운영본), `sheets_api_v3_new.gs`, `sheets_api_v4_deploy_new.gs`(미사용 후보) | `LockService.getScriptLock()` 3개 파일 전부에서 사용 확인(예약 생성·상태변경 동시성 보호). **`CacheService`/`PropertiesService` 사용 0건**(grep 전수 재확인) |
| `docs/DEPLOY_GUIDE_new.md` | `script.google.com` 링크는 신규 GAS 프로젝트 생성 안내용 일반 링크일 뿐, 기존 테스트용 프로젝트를 가리키지 않음(재확인) |
| 저장소 전체 grep(`scriptId`/`testProject`/전용 테스트 GAS 스크립트) | **격리된 테스트용 GAS 프로젝트·script ID가 현재 저장소에 존재하지 않음**(재확인, `tests/*.gs` 0건) |

## 5. AS-IS CacheService 사용 현황

**CacheService는 현재 Production GAS 코드 어디에도 사용되지 않는다**(grep 전수 재확인, `app/apps_script/*.gs` 3개 파일 전부 0건). `LockService.getScriptLock()`만 예약 생성(`_actionCreate`)과 상태변경(`_actionUpdateStatus`) 3곳에서 사용된다(§4 근거). 즉 CacheService 기반 Nonce 2차 방어(ADR-017 §13)는 **설계만 존재하며 GAS 코드로 구현된 바 없다**.

## 6. Production nonce 구현 상태

**NOT IMPLEMENTED**(PoC#1 보고서 §3에서 이미 확인된 사실 재인용, 이번 조사로도 동일 결론 재확인). FastAPI 측(`src/auth/service_hmac.py`)에도 GAS 측에도 Nonce 저장 로직이 없다.

## 7. 검증 가설

ADR-017 §13이 전제하는 "CacheService 단독으로는 Replay 차단을 보장할 수 없다"(1,000항목 상한·비영속성 근거)는 명제를, 이 시스템이 예상하는 트래픽 규모의 key 투입량 하에서 **실제로 eviction이 관측되는지, 관측된다면 어느 투입 규모에서부터인지**를 격리 환경에서 실측 확인하는 것을 가설로 한다. 이 가설의 성립 여부가 FastAPI 측 SQLite 1차 저장소(PoC#1로 원자성 확인됨)의 필요성 근거를 보강한다.

## 8. 격리 테스트 환경 요구사항

- 운영 GAS Web App(`sheets_api_v3_final.gs` 배포본)과 **완전히 별개인** 신규 GAS 프로젝트.
- 운영 Google Sheets(`종합검진_예약대장`)에 연결하지 않음 — PoC#2는 Sheets 자체를 필요로 하지 않는다(§10 재확인, CacheService는 Spreadsheet 바인딩 없이도 단독 Apps Script 프로젝트에서 동작 가능).
- 사용 Google 계정: **PM/병원전산담당이 결정할 사항**(§7 Gate 표, 임의 지정하지 않음).
- 웹앱 공개 배포는 원칙적으로 불필요(§5 원칙 재확인) — 테스트는 Apps Script 편집기 내 함수 직접 실행 또는 시간 기반 트리거만으로 충분할 것으로 예상되나, 필요성이 발생하면 별도 PM 승인 필요.

## 9. 테스트용 GAS 프로젝트 요구사항

| 항목 | 요구사항 |
|---|---|
| 프로젝트 유형 | 독립형 스크립트(Standalone script) — Spreadsheet 미바인딩 |
| 소스 코드 | 이 PoC 전용 신규 `.gs` 파일(운영 `sheets_api_v3_final.gs`의 어떤 코드도 재사용·복사하지 않음, 신규 작성) |
| 배포 | 원칙적으로 불필요(§8). 필요 시 "테스트" 라벨의 별도 배포, 운영 배포와 URL 공유 금지 |
| 접근 권한 | 실행 계정 본인만(공개 배포 금지 원칙 유지) |
| 존재 여부 | **현재 없음**(§4 재확인) — 이 계획 승인 후 별도 생성 필요 |

## 10. 운영 GAS·Sheets 분리 원칙

- 신규 격리 테스트용 GAS 프로젝트만 사용, 운영 GAS script ID 사용 금지.
- 운영 배포본(`sheets_api_v3_final.gs`) 수정 금지.
- 운영 Google Sheets 연결 금지.
- 실제 예약·수검자 데이터 사용 금지.
- 실제 HMAC Secret 사용 금지.
- 합성 nonce·가상 데이터만 사용(예: `poc2-<uuid>` 형식의 무의미 문자열).
- 웹앱 공개 배포는 원칙적으로 불필요, 필요성이 확인되면 별도 PM 승인 후 진행.
- 실행 로그에 Secret·식별정보 저장 금지.
- PoC 종료 후 테스트 cache·properties·trigger 정리(§25).
- 테스트 프로젝트 삭제 여부는 실행 승인 단계에서 별도 결정(이 문서에서 확정하지 않음).

## 11. 테스트 데이터 원칙

모든 key/value는 합성 문자열만 사용한다(PoC#1과 동일 원칙, `docs/Sprint8_DR_B_01_PoC1_SQLite_Atomicity_Report.md` §11 재인용). 실제 병원·수검자·직원 정보, 실제 예약번호 형식(YYYYMMDD-NNNN)을 흉내 내지 않는다(혼동 방지).

## 12. CacheService 종류 선정 근거

GAS는 `CacheService.getScriptCache()`(스크립트 전역 공유), `getUserCache()`(사용자별), `getDocumentCache()`(문서별, Spreadsheet 바인딩 필요) 3종을 제공한다(ADR-017 §13/§10 공식 확인 재인용). ADR-017 §13이 채택한 것은 **Script Cache**다 — Nonce는 특정 사용자나 문서가 아니라 스크립트(=Web App) 전체에서 공유되어야 재사용 탐지가 가능하기 때문이다(모든 호출자가 동일한 Nonce 네임스페이스를 공유해야 함). 이 PoC도 동일하게 **Script Cache**만을 대상으로 한다. `getDocumentCache()`는 Spreadsheet 바인딩이 필요해 §8의 "Sheets 미연결" 원칙과 충돌하므로 이 PoC의 대상에서 제외한다.

## 13. LockService 사용 여부

P2-09에서 LockService 적용/미적용을 비교 대상으로 포함한다(§19). ADR-017 §13은 "GAS측은 Nonce 존재확인~기록 구간을 LockService로 감쌈"을 설계 원칙으로 명시했으므로, 이 PoC는 `LockService.getScriptLock()`으로 감싼 CacheService 접근과 감싸지 않은 접근의 동작 차이(특히 동시 접근 시 값 일관성)를 관측 대상에 포함한다. LockService 자체의 원자성은 Production GAS(`_actionCreate` 등)에서 이미 사용 중인 기능이므로 이 PoC의 신규 검증 대상이 아니다 — 이 PoC는 "CacheService+LockService 조합"의 동작만 관측한다.

## 14. TTL 후보

ADR-017 §13은 GAS CacheService TTL을 **300초**로 채택했다(companion — DR-B-01 확정 조건부). 이 PoC는 이 값을 **PROPOSED INITIAL VALUE**로 사용하며, GAS `CacheService.put()`이 지원하는 공식 TTL 범위(1~21600초, ADR-017 §10 인용 근거) 자체는 이 계획 단계에서 **EXECUTION-TIME OFFICIAL VERIFICATION REQUIRED**로 표시한다 — 실행 시점에 최신 공식 문서를 재확인 없이 그대로 신뢰하지 않는다.

## 15. eviction 관측 정의

"Eviction"은 `put()` 성공 후 설정된 TTL이 아직 경과하지 않았음에도 `get()`이 `null`을 반환하는 경우로 정의한다(TTL 자연만료와 구분, §16). 관측 방법: 각 key의 `put()` 직후 시각과 `get()` 시각·TTL 설정값을 함께 기록해, "TTL 미경과 시점의 null 반환"만 eviction으로 집계한다.

## 16. cache miss와 eviction 구분 한계

GAS 공식 문서는 CacheService의 항목이 TTL 만료 전에도 사양상 사라질 수 있음을 명시하되("반드시 null을 받을 준비를 해야 한다", ADR-017 §13 인용), 개별 miss가 "TTL 자연만료"인지 "용량 압박에 의한 조기 축출"인지 GAS API 자체가 구분해 알려주지 않는다. 따라서 이 PoC는 **TTL 미경과 시점의 miss만** eviction으로 판정하며, TTL 경과 후 miss는 정상 만료로 분류해 통계에서 별도 집계한다(§19 P2-04/P2-05가 이 구분의 기준선을 제공).

## 17. 반복·부하 수준

PoC#1(`WORKER_COUNT=8`, `REPEAT_COUNT=20`)과 동일한 "로컬에서 무리 없는 보수적 값" 원칙을 따르되, GAS는 실행시간·quota 제약이 SQLite와 다르므로 별도 값이 필요하다. 이 문서는 최종값을 확정하지 않으며 다음을 **PROPOSED INITIAL VALUE**로만 제안한다: 1회 실행당 key 투입 수 50~200개 구간(공식 1,000항목 상한 대비 5~20%), 반복 실행 3~5회(SQLite PoC의 20회 대비 대폭 축소 — GAS 실행시간 상한과 수동/트리거 기반 실행의 운영 부담을 고려). 최종 확정은 실행 승인 단계에서 별도 결정.

## 18. 실행시간과 quota 고려

GAS 공식 문서가 명시하는 스크립트 실행시간 상한(6분/실행, ADR-017 §10 인용)과 일일 실행시간·트리거 quota는 계정 유형(개인/Workspace)에 따라 달라질 수 있어 이 문서에서 확정값으로 기재하지 않는다 — **EXECUTION-TIME OFFICIAL VERIFICATION REQUIRED**. P2-11(quota/실행시간 제한 발생 시 중단)이 이 불확실성에 대한 안전장치로 설계에 포함되어 있다.

## 19. 필수 시나리오

| Scenario | Purpose | Input scale | Method | Measurement | Expected observation | Pass criteria | Stop condition | Evidence |
|---|---|---|---|---|---|---|---|---|
| P2-01 | put 후 즉시 get 기본 동작 확인 | key 1개 | `put(key,value)` → 즉시 `get(key)` | 반환값 일치 여부 | 저장한 값 그대로 반환 | 값 일치 | 없음 | 실행 로그 |
| P2-02 | 동일 key overwrite 동작 확인 | key 1개, value 2회 갱신 | 동일 key로 `put()` 2회 | 두 번째 `get()` 결과 | 최신 값으로 덮어써짐 | 최신 값 반환 | 없음 | 실행 로그 |
| P2-03 | remove 후 miss 확인 | key 1개 | `put()` → `remove()` → `get()` | `get()` 결과 | `null` 반환 | null 확인 | 없음 | 실행 로그 |
| P2-04 | 설정 TTL 이전 조회(정상 보존 기준선) | key 1개, TTL=PROPOSED INITIAL VALUE(§14) | `put(key,value,ttl)` → TTL 경과 전 `get()` | 반환값 | 값 보존됨(정상) | 값 일치 | 없음 | 실행 로그 |
| P2-05 | 설정 TTL 이후 조회(정상 만료 기준선) | 상동 | `put()` → TTL 경과 후 `get()` | 반환값 | `null`(정상 만료) | null 확인, §16 "정상 만료"로 분류 | 없음 | 실행 로그 |
| P2-06 | 다수 key 입력 후 잔존율 측정 | §17 PROPOSED INITIAL VALUE 규모 | 순차 `put()` N개 → 즉시 전수 `get()` | 잔존 key 수/N | TTL 미경과 구간이므로 원칙상 100% 잔존 예상, 실측 편차 자체가 관측 대상 | 사전 규정 없음(실측 기록 목적) | quota 초과 시 중단(P2-11) | 실행 로그, 집계표 |
| P2-07 | 용량 압박 조건에서 조기 eviction 관측 | 공식 상한(§14 EXECUTION-TIME 재확인 대상) 근접 규모 | 대량 key 투입 후 초기 투입 key 재조회 | 초기 key의 TTL 미경과 시점 miss 여부 | eviction 발생 가능성 관측(발생 여부 자체가 미지) | 사전 규정 없음(실측 기록 목적) | quota/실행시간 초과 시 중단 | 실행 로그, 집계표 |
| P2-08 | 반복 실행별 잔존율 편차 | §17 반복 횟수(PROPOSED INITIAL VALUE) | P2-06/P2-07 패턴을 반복 실행 | 반복 간 잔존율 분산 | 편차의 크기 자체가 관측 대상(사전 예단 없음) | 사전 규정 없음 | 상동 | 실행 로그, 반복별 집계 |
| P2-09 | LockService 적용·미적용 비교 | key 소수(≤10) | 동일 시나리오를 Lock 有/無로 각각 실행 | 값 일관성 차이 | Lock 적용 시 더 높은 일관성 예상(가설, 확정 아님) | 사전 규정 없음 | 없음 | 실행 로그 |
| P2-10 | cache miss 시 Fail-Closed 처리 입력자료 산출 | P2-07/P2-08 결과 활용 | miss 발생 시나리오의 발생 빈도·조건 정리 | miss 발생률, 발생 조건 패턴 | ADR-017 §13 Fail-Closed 설계의 근거자료 산출(정책 자체는 확정 아님) | 해당없음(자료 산출용) | 없음 | 집계표 |
| P2-11 | quota·실행시간 제한 발생 시 중단 | 해당없음 | 공식 오류(quota exceeded 등) 발생 시 즉시 실행 중단 절차 확인 | 중단 절차 작동 여부 | 정상 중단, 부분 결과 보존 | 중단 후 데이터 손상 없음 | **이 시나리오 자체가 중단 트리거** | 오류 로그 |
| P2-12 | 테스트 리소스 정리 확인 | 해당없음 | 전체 실행 종료 후 `removeAll()` 등으로 정리 | 정리 후 잔여 key 수 | 0건 | 잔여 0건 | 없음 | 정리 전후 스냅샷 |

**실측 전이므로 위 "Expected observation"·"Pass criteria" 열은 가설/기준일 뿐 실제 결과가 아니다.**

## 20. 측정항목

put/get 성공·실패 건수, eviction 판정 건수(§15 정의), 정상 TTL 만료 건수(§16 구분), 반복 간 잔존율 분산, LockService 유/무 조건별 값 일관성, quota/실행시간 오류 발생 여부와 발생 시점, 실행 소요시간.

## 21. 사전 성공 기준

- **PASS**: 모든 시나리오가 예상 밖 오류 없이 실행 완료, eviction 판정 로직이 §15/§16 기준대로 정확히 동작함이 확인됨(eviction이 실제로 관측되었는지 여부와는 무관 — "관측 체계가 유효한가"가 판정 대상), 테스트 리소스 완전 정리(P2-12).
- **PASS WITH CONDITIONS**: 관측 체계는 유효하나 quota/실행시간 제약으로 목표 투입 규모(§17)에 도달하지 못했거나, 결과가 실행 계정 유형에 따라 달라질 수 있음이 확인된 경우.
- **FAIL**: eviction과 정상 만료를 구분할 수 없는 방식으로 설계되었음이 실행 중 드러나거나, 테스트 리소스가 정리되지 않거나, 운영 GAS·Sheets에 의도치 않게 접근한 경우.

이 기준은 **실행 계획**에 대한 사전 판정 기준이며, 실제 실행 결과가 없는 이 문서 자체에는 적용하지 않는다(§30).

## 22. 중단 기준

quota 초과, 실행시간 제한 도달, 예상 밖 오류(GAS API 변경 등), 운영 GAS·Sheets에 대한 의도치 않은 접근 징후 발견 시 즉시 중단한다(P2-11). 무한 재시도를 설계하지 않는다.

## 23. 실패 분류

| 분류 | 정의 |
|---|---|
| ENVIRONMENT_LIMIT | quota·실행시간 등 GAS 플랫폼 제약으로 중단 |
| OBSERVATION_LOGIC_FAILURE | eviction/정상만료 구분 로직 자체가 오작동 |
| ISOLATION_BREACH | 운영 GAS·Sheets·실 데이터에 접근한 징후 |
| UNEXPECTED_API_BEHAVIOR | 공식 문서와 다른 GAS API 동작 관측(재확인 필요) |
| CLEANUP_FAILURE | 테스트 리소스 정리 실패 |

## 24. 증적 수집방식

각 시나리오 실행 로그(Apps Script 실행 기록, `Logger` 또는 유사 메커니즘)를 시간순으로 저장하고, 이 PoC 전용 결과 보고서(PoC#1과 동일하게 `docs/Sprint8_DR_B_01_PoC2_GAS_CacheService_Result_Report.md` 형식 제안, 이 문서에서 신규 작성하지 않음)에 실측값만 기록한다. Secret·식별정보는 로그에 포함하지 않는다(§26).

## 25. 임시 리소스 정리

PoC 종료 후 다음을 정리한다: 테스트 Script Cache의 잔여 key(`removeAll()` 또는 TTL 자연만료 대기), 사용한 `PropertiesService` 값(사용했다면), 설정한 트리거(시간 기반 트리거를 사용했다면 삭제). 테스트 GAS 프로젝트 자체의 삭제 여부는 이 문서에서 확정하지 않으며 실행 승인 단계에서 별도 결정한다(§10 재인용).

## 26. Secret·PII 보호

실제 HMAC Secret, 실제 예약자 정보, 실제 운영 URL을 이 PoC의 어떤 단계(코드/로그/보고서)에도 포함하지 않는다. 합성 데이터만 사용(§11). 실행 계정 정보(이메일 등)는 보고서에 기록하지 않는다.

## 27. 실행권한과 승인경계

| Requirement | Current status | Required evidence | Approval needed | Blocking |
|---|---|---|---|---|
| 격리 GAS 프로젝트 | 없음(§9) | 신규 생성 완료 확인 | **예(PM)** | 예 |
| 사용 Google 계정 | 미지정 | PM/병원전산담당 결정 | **예(PM/병원전산담당)** | 예 |
| 운영환경과 분리 확인 | 원칙만 정의(§10) | 신규 프로젝트가 운영 script ID와 다름을 실행 전 재확인 | **예(실행자 자체 확인 + PM 승인)** | 예 |
| 공식 quota·제한 재확인 | 미확인(§14/§18 EXECUTION-TIME 표시) | 실행 시점 공식 문서 재조회 결과 | 실행자 책임(별도 PM 승인 불요) | 예(재확인 없이는 실행 불가) |
| 합성 테스트 데이터 | 원칙 정의됨(§11) | 실제 데이터 미사용 자체 점검 | 실행자 자체 확인 | 예 |
| 실행 횟수·입력 규모 | PROPOSED INITIAL VALUE만(§17) | 최종값 확정 | **예(PM)** | 예 |
| 예상 실행시간 | 미산정(§18) | 실행 전 추정치 산출 | 실행자 자체 산출 | 아니오(참고용) |
| 로그·증적 저장 위치 | 미정 | 저장 경로 결정 | **예(PM)** | 아니오(권장) |
| 테스트 리소스 정리 방법 | 원칙 정의됨(§25) | 정리 완료 확인 절차 | 실행자 자체 확인 | 예 |
| 외부 접근 승인 | 없음 | GAS 접속·실행 자체에 대한 승인 | **예(PM)** | 예 |
| 실행 중단조건 | 정의됨(§22) | 해당없음 | 없음(이미 정의) | 아니오 |

승인권자·사용 계정은 이 문서에서 임의 지정하지 않는다.

## 28. PoC#1·#3 관계

PoC#1(SQLite UNIQUE 원자성)은 **완료·Push됨**(PASS, `docs/Sprint8_DR_B_01_PoC1_SQLite_Atomicity_Report.md`, Commit `6ffc5cf`) — 이 결과를 PoC#2 결과로 확대 해석하지 않는다. PoC#3(양쪽 저장소 정합성 불일치 처리 검증)은 PoC#2 결과(특히 P2-10 Fail-Closed 입력자료)에 일부 의존할 수 있으나, 이 문서는 PoC#3을 설계하지 않으며 별도 STEP으로 남긴다.

## 29. DR-B-02 Phase 1 관계

DR-B-02(Idempotency TTL 부하검증)의 Phase 1(Preliminary Validation, ADR-017 §29/Security Test Plan §40 재인용)은 이 PoC#2와 별개의 검증 대상(Idempotency 상태기계)이다. 이 문서는 DR-B-02를 설계하지 않으며, PoC#2의 eviction 관측 결과가 향후 DR-B-02 Phase 1 설계 시 참고자료가 될 수 있음을 언급할 뿐이다(§18 quota 데이터 등).

## 30. 한계

- 이 문서는 계획일 뿐이며 실제 실행 결과를 포함하지 않는다.
- GAS CacheService의 공식 제약(quota, 항목 수 상한, 실행시간)은 계정 유형과 시점에 따라 달라질 수 있어 이 계획의 PROPOSED INITIAL VALUE가 실행 시점에도 유효하다고 보증하지 않는다(§14/§17/§18).
- eviction과 GAS 플랫폼 자체 오류(네트워크 지연 등)를 완전히 구분하는 것은 이 PoC의 관측 방법(§15/§16)만으로는 한계가 있을 수 있다.
- 단일 계정·단일 실행 세션 기준의 관측이며, 여러 계정·여러 스크립트 간 Cache 격리 특성(Script Cache가 스크립트 단위로 격리됨)까지는 별도로 검증하지 않는다.

## 31. 실행 전 체크리스트

1. §27 Gate 표의 "Approval needed=예" 항목 전부 PM 승인 확보
2. 격리 GAS 프로젝트 생성 완료(운영 script ID와 다름을 재확인)
3. 실행 시점 공식 quota·제한 재조회(§14/§18, EXECUTION-TIME OFFICIAL VERIFICATION REQUIRED 해소)
4. 실행 횟수·입력 규모 최종값 PM 확정(§17)
5. 로그·증적 저장 위치 확정
6. 합성 데이터만 사용함을 재확인
7. 중단 기준(§22)과 실패 분류(§23) 숙지

## 32. 후속 작업

- 이 계획서에 대한 PM 검토·승인.
- §27 승인 필요 항목(격리 GAS 프로젝트, 사용 계정, 실행 규모, 외부 접근) 확정.
- 승인 후 별도 STEP(가칭 Pre-G1-B)에서 실제 GAS 프로젝트 생성 및 PoC#2 실행.
- 실행 후 별도 결과 보고서 작성(PoC#1과 동일한 형식 제안).
- PoC#3 계획은 이 STEP에서 착수하지 않으며 별도 STEP으로 제안.

## 33. 결론

이 문서는 ADR-017 §29 PoC#2(GAS CacheService eviction 시뮬레이션)를 운영 GAS·Google Sheets와 완전히 분리된 환경에서 실행하기 위한 계획을 12개 시나리오(P2-01~P2-12)로 구체화했다. 현재 저장소에는 격리된 테스트용 GAS 프로젝트가 존재하지 않으며(§9), Production GAS 코드에는 CacheService 사용이 전무하다(§5). TTL·투입 규모·quota 등 핵심 수치는 전부 PROPOSED INITIAL VALUE 또는 EXECUTION-TIME OFFICIAL VERIFICATION REQUIRED로 표시했으며 이 문서에서 확정하지 않았다. 실행 승인권자·사용 계정도 임의 지정하지 않았다(§27). 실제 GAS 실행은 이 문서 승인과 별개로 §31의 체크리스트 충족 및 PM의 명시적 승인이 필요하다.

---

**완료 조건 준수 확인**: 이 문서 작성 중 GAS 프로젝트 생성·접속·수정·배포를 수행하지 않았다. Google Sheets에 접근하지 않았다. Apps Script 코드를 작성하지 않았다. 실제 PoC를 실행하지 않았다. 외부 API를 호출하지 않았다(웹 검색 포함). Production 코드를 수정하지 않았다. 실제 Secret·Token·Credential·PII·운영 script ID·운영 URL을 포함하지 않았다. 공식 quota·제한 수치를 확정값으로 기재하지 않고 EXECUTION-TIME OFFICIAL VERIFICATION REQUIRED로 표시했다. Production TTL·Idempotency TTL·Rate Limit·재시도 정책을 확정하지 않았다. Git add/commit/push 없음.
