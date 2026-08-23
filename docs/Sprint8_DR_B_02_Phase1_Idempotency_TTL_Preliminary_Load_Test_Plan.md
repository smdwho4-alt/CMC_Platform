# Sprint8 DR-B-02 Phase 1 — Idempotency TTL 예비 부하검증(Preliminary Validation) 실행계획

> **상태**: 실행계획 초안(Draft). harness 작성·실행 없음. 실제 측정 결과 없음. Commit 없음.
> **작성일**: 2026-08-23(Sprint8 Pre-G1-B-G)
> **기준선**: `main`/`origin/main` = `6652ee8762836114ecb3b7537150741c4c1a3813`

---

## 1. 목적과 범위

ADR-017 §29 DR-B-02("Idempotency TTL 5개값에 대한 실측 트래픽/재시도 패턴 기반 부하검증")의 **Phase 1(Preliminary Validation)**을 로컬 Pre-Implementation Harness로 실행하기 위한 **실행계획**을 작성한다. 이 문서는 계획 작성까지만 수행하며, 실제 harness 작성·실행은 포함하지 않는다.

**범위**: FastAPI Idempotency 상태기계(ADR-017 §14, 5상태·TTL)의 만료 경계 동작과 동시 요청 처리 로직을 결정론적 로컬 harness로 검증한다.

**제외 범위**(§12에서 재확인): 실제 Production RPS·성능·확장성·TTL 적합성 입증, 외부 부하도구(locust/k6/jmeter 등) 사용, 신규 패키지 설치, 실제 48시간 대기, Canonical String/HMAC Gap, GAS 실접근, Phase 2(G6), TTL 최종 확정, Commit8-3b 착수 승인.

## 2. 기준선 Commit

`6652ee8762836114ecb3b7537150741c4c1a3813`(HEAD=main=origin/main, Sprint8 DR-B-01 PoC 3건 완료 직후 시점).

## 3. 근거 문서·코드

| 문서/코드 | 확인 내용(직접 인용) |
|---|---|
| `ADR-017_FastAPI_Proxy_and_Signed_GAS_Operations.md` §14 | Idempotency 5상태·TTL(`IN_PROGRESS` 60초/`SUCCEEDED` 900초/`FAILED_RETRYABLE` 300초/`FAILED_FINAL` 900초/`UNKNOWN` 48시간). "§29의 부하검증이 완료되기 전까지 위 TTL은 '구현 확정값'이 아니라 '설계 확정값'으로만 간주한다." |
| `ADR-017_FastAPI_Proxy_and_Signed_GAS_Operations.md` §29 | "§14의 Idempotency TTL·저장구조에 대한 부하검증(DR-B-02)은 2단계로 구분한다... Phase 1(Preliminary Validation) — Pre-Implementation Harness 기반... 결과는 TTL·저장방식·동시성 설계의 잠정 선택 근거로만 사용하며, Production 적합성이나 최종 성능을 보증하지 않는다." |
| `docs/Sprint8_Security_Architecture_Design.md` §23 | "DR-B-02 부하검증... Phase 1(Preliminary Validation) — Pre-Implementation Harness 기반 예비 부하검증, 결과는 TTL·저장방식·동시성 설계의 잠정 선택 근거일 뿐 Production 적합성을 보증하지 않음." |
| `docs/Sprint8_Security_Test_and_Deployment_Gate_Plan.md` §40 | Pre-G1 추적표: "DR-B-02 \| Idempotency TTL 부하검증 \| ... \| Phase 1: harness 기반 예비 부하검증(잠정 선택 근거) \| Phase 2: 통합 구현 기준 최종 부하검증(TTL 확정 근거) \| DEFERRED" |
| `docs/Sprint8_Security_Test_and_Deployment_Gate_Plan.md` §21 | "IDEM-01~05... 저장 로직이 없으므로 전부 EXECUTABLE AFTER IMPLEMENTATION, TTL 수치 자체의 타당성 검증은 **REQUIRES LOAD VALIDATION**(DR-B-02)." |
| `docs/Sprint8_Security_Test_and_Deployment_Gate_Plan.md` §32(G6) | "Pass criteria: 이 문서에서 정의하지 않음 — 실측 데이터 부재로 Pass 기준 자체가 REQUIRES LOAD VALIDATION 상태... Phase 1(예비검증) 결과만으로는 G6 Pass 판정을 내리지 않는다." |
| `docs/Sprint8_Admin_Operations_API_Contract.md` §21(재확인) | TTL 5값을 "PROPOSED, REQUIRES LOAD TEST — DR-B-02"로 인용, "현재 저장소에 Idempotency 저장 로직은 **NOT IMPLEMENTED**"(grep 재확인). |
| 저장소 전수 검색(이번 STEP 이전 조사) | Idempotency 저장·상태전이 실 구현 코드 **0건**. 실측 트래픽/재시도 패턴(RPS/TPS/percentile) 데이터 **0건**. 전용 부하도구(locust/k6/jmeter 등) 의존성 **0건**. `concurrent.futures.ThreadPoolExecutor`는 PoC#1 harness·`run_sprint4_commit3a_slot_hardening_qa.py`·`run_sprint_d_tests.py` 3곳에서 이미 "정확히 1건만 성공" 패턴에 사용된 선례 확인. `import unittest`/`from unittest`는 PoC#1·PoC#3 harness 2개뿐. |
| `docs/Sprint8_DR_B_01_PoC1_SQLite_Atomicity_Report.md` | PASS, Commit `6ffc5cf` — 이 문서와 별개, `ThreadPoolExecutor` 패턴 재사용 근거만 참고. |
| `docs/Sprint8_DR_B_01_PoC2_GAS_CacheService_Result_Report.md` | PASS WITH CONDITIONS, Commit `b97d2ed` — TTL 300초를 PROPOSED INITIAL VALUE로 취급한 관행을 이 문서도 동일하게 따른다. |
| `docs/Sprint8_DR_B_01_PoC3_Nonce_Store_Consistency_Fail_Closed_Result_Report.md` | PASS — FAIL-CLOSED DECISION LOGIC VERIFIED, Commit `6652ee8` — 이중 저장소/Fail-Closed 결정 로직 검증 패턴(§9 record 관측·정책 미확정 원칙)을 이 문서도 계승한다. |

## 4. Pre-G1·이중 판정 구조

이 문서는 `Sprint8_Security_Test_and_Deployment_Gate_Plan.md` §40이 정의하는 **Pre-G1(보조 Gate)** 중 DR-B-02 **Phase 1**에 해당한다. Pre-G1 통과는 G6 진입이나 통과를 대체하지 않으며(§32 재확인), Phase 1 결과는 "TTL·저장방식·동시성 설계의 잠정 선택 근거"일 뿐이다.

이 계획은 판정을 **두 축으로 분리**한다:

- **A. HARNESS TECHNICAL RESULT** — `PASS` / `PASS WITH CONDITIONS` / `FAIL`. harness 코드가 설계대로 동작했는지(TTL 경계 판정, 동시성 원자성, cleanup)만 평가한다.
- **B. OFFICIAL PHASE 1 GATE** — `BLOCKED INPUT` 또는 `완료`. 계획서 §5가 명시하는 대로 **실측 트래픽·재시도 패턴 데이터가 저장소에 존재하지 않으므로**, A가 전부 PASS이더라도 B는 **`BLOCKED INPUT`으로 고정**된다. B가 "완료"로 바뀌려면 이 harness 결과와는 별도로 실측 데이터(운영자 재시도 행동 패턴 등, ADR-017 Commit8-3a STEP2-C §7 재인용)가 PM/실행자에 의해 별도로 확보되어야 한다.

## 5. TTL 5값(PROPOSED) 및 Production 구현 상태

| 상태 | TTL(계획값) | 표기 |
|---|---|---|
| `IN_PROGRESS` | 60초 | PROPOSED |
| `SUCCEEDED` | 900초 | PROPOSED |
| `FAILED_RETRYABLE` | 300초 | PROPOSED |
| `FAILED_FINAL` | 900초 | PROPOSED |
| `UNKNOWN` | 48시간(172800초) | PROPOSED |

위 5개 값 전부 ADR-017 §14의 **설계 확정값**일 뿐 **구현 확정값이 아니다**(§29 원문 재인용). 이 harness는 이 값들을 그대로 사용하되 **PROPOSED**로만 취급하며, 이 계획서로 최종 확정하지 않는다.

**BLOCKED INPUT / LIMITATION(명시)**: Production Idempotency 저장 로직은 **NOT IMPLEMENTED**이며(§3 재확인), 저장소에는 DR-B-02가 요구하는 실측 트래픽·재시도 패턴 데이터가 **존재하지 않는다**. 이 두 사실 자체가 §4의 "B. OFFICIAL PHASE 1 GATE = BLOCKED INPUT" 고정 사유다.

## 6. 실행환경 및 harness 설계 원칙

- **Python 표준 라이브러리만 사용**(`sqlite3`, `unittest`, `concurrent.futures.ThreadPoolExecutor`, `tempfile`, `uuid`, `datetime` 등), 외부 부하도구(locust/k6/jmeter 등)·신규 패키지 설치 없음.
- 저장소: 임시 SQLite(OS 임시 디렉터리, PoC#1/#3과 동일 격리 원칙).
- **injectable clock**: 실제 시간 경과(특히 48시간)를 기다리지 않고, harness 내부에서 "현재 시각"을 주입 가능한 `Clock` 컴포넌트(고정 시각 반환 + 명시적 `advance(seconds)`)로 대체해 TTL 만료 전/경계/만료 후를 결정론적으로 재현한다. `time.sleep()`으로 실제 대기하지 않는다.
- 동시성 재현: `concurrent.futures.ThreadPoolExecutor` + `threading.Barrier`(PoC#1과 동일 관행).
- 재시도·burst 패턴은 **합성(synthetic) 패턴**만 사용하며, 실제 운영 트래픽을 관측·재현한 것이 아님을 결과에 명시한다(§9).
- GAS·Google Sheets·외부 네트워크 접근 없음. 모든 idempotency key·nonce는 `dr-b-02-<uuid>` 형식의 synthetic 값만 사용.
- 실행 종료 후 임시 SQLite 파일(및 `-wal`/`-shm`)과 임시 디렉터리를 정리한다.

## 7. 시나리오 (B2-01~B2-12)

| ID | 목적 | 입력·부하 프로파일 | 검증방법 | 측정값 | 예상결과 | 판정기준 |
|---|---|---|---|---|---|---|
| B2-01 | TTL 5상태·초값 매핑 자체의 단위 검증 | 상태 5종 × PROPOSED TTL 값 1세트 | 상태→TTL 매핑 테이블을 harness 상수로 재현 후 단위 비교 | 매핑 일치 건수/5 | 5/5 일치 | 5/5 불일치 시 FAIL |
| B2-02 | `IN_PROGRESS`(60초) 만료 전/경계/만료 후 | key 1건, injectable clock으로 59초/60초/61초 시점 조회 | 각 시점에서 상태 조회 함수 호출 | 만료 전·경계·만료 후 각 판정값 | 59초=유효, 60초=경계(정책값 그대로 관측), 61초=만료(UNKNOWN/RECONCILIATION 후보 전이) | 경계 처리 로직이 예외 없이 결정론적이면 PASS |
| B2-03 | `SUCCEEDED`(900초) 만료 전/경계/만료 후 | key 1건, clock으로 899초/900초/901초 | B2-02와 동일 방법 | 상동 | 상동(TTL 값만 900초로 치환) | 상동 |
| B2-04 | `FAILED_RETRYABLE`(300초) 만료 전/경계/만료 후 | key 1건, clock으로 299초/300초/301초 | B2-02와 동일 방법 | 상동 | 상동(TTL 값만 300초로 치환) | 상동 |
| B2-05 | `FAILED_FINAL`(900초) 만료 전/경계/만료 후 | key 1건, clock으로 899초/900초/901초 | B2-02와 동일 방법 | 상동 | 상동 | 상동 |
| B2-06 | `UNKNOWN`(48시간=172800초) 만료 전/경계/만료 후 | key 1건, clock으로 172799초/172800초/172801초(실제 대기 없음) | B2-02와 동일 방법(injectable clock으로만 경과 재현) | 상동 | 상동(TTL 값만 172800초로 치환) | 상동 |
| B2-07 | 동일 idempotency key 동시 요청 — 정확히 1건만 최초 생성 | 동일 key 1개에 대해 `ThreadPoolExecutor`(WORKER_COUNT, PoC#1과 동일 보수적 값 재사용 제안)로 동시 생성 시도 | `threading.Barrier`로 시작 동기화 후 동시 INSERT/생성 시도 | 요청 수, 최초 생성 성공 수, 중복 차단 수, 오류 수 | 성공 정확히 1건, 나머지 전부 중복 차단(오류 0건) | 성공≠1 또는 오류>0이면 FAIL |
| B2-08 | 서로 다른 key 동시 요청 — 상태 교차오염 없음 | 서로 다른 synthetic key N개(PoC#1 WORKER_COUNT와 동일 규모 제안)를 동시 생성 | 동시 실행 후 각 key의 최종 상태를 개별 조회 | 요청 수, unique key 수, 성공 수, 오류 수 | 전 key 성공, 서로의 상태에 영향 없음 | 성공 수≠unique key 수 또는 교차오염 관측 시 FAIL |
| B2-09 | 합성 정상 재시도 패턴 | 1개 key에 대해 `FAILED_RETRYABLE` 전이 후 새 nonce로 순차 재시도(합성 간격, 실측 아님) 3~5회(PROPOSED) | 순차 호출 후 최종 상태·재시도 횟수 확인 | 요청 수, retry 수, 최종 상태, elapsed time | 재시도마다 새 nonce로 독립 처리, 최종적으로 SUCCEEDED 또는 FAILED_FINAL 후보로 수렴 | 재시도 간 상태 오염·중복 성공 발생 시 FAIL |
| B2-10 | 합성 burst/retry-storm 패턴 | 동일 key에 짧은 간격으로 다수(PROPOSED 초기값, 예: 20~50건) 합성 요청 집중 투입 — **실제 운영 트래픽 재현 아님** | `ThreadPoolExecutor`로 짧은 시간창에 집중 투입 | 요청 수, 성공 수, 차단 수, 오류 수, elapsed time, throughput(로컬 관측값) | 성공은 정확히 1건, 나머지는 차단 또는 `IN_PROGRESS` 대기 응답 | 성공>1 또는 예상 밖 오류 발생 시 FAIL |
| B2-11 | 시간·작업량 guard 및 부분결과 보존·cleanup | 의도적으로 매우 작은 시간/횟수 guard를 부여해 강제 조기 중단 유발(PoC#2의 P2-11 자기검증과 동일 원칙) | 강제 guard 조건에서 실행 후 중단 시점까지의 부분결과 확인 | 처리된 요청 수, 중단 시점, 부분결과 보존 여부 | 조기 중단 후 부분결과가 안전하게 보존되고 무한 재시도 없음 | 무한 루프·부분결과 유실 시 FAIL |
| B2-12 | 반복 재현성·잔존 리소스 최종 검증 | B2-02~B2-10 패턴을 3회(PROPOSED, PoC#1 REPEAT_COUNT 축소값 참고) 반복 | 반복 간 결과 분산 확인 + 최종 cleanup 실행 | 반복 횟수, 반복 간 결과 편차, cleanup 후 remaining 수 | 반복 간 판정 결과 편차 0, cleanup 후 remaining=0 | 반복 간 결과가 매번 다르거나 remaining>0이면 FAIL |

## 8. 측정 항목(§7 표의 "측정값" 열 공통 정의)

- 요청 수, unique key 수, retry 수
- 최초 생성 성공 수, 중복 차단 수
- 오류·timeout 수
- elapsed time(harness 실행 시간, 초 단위)
- **throughput은 이 로컬 harness의 관측값으로만 표시**하며 Production 처리량 추정치로 사용하지 않는다
- latency min/median/p95/max(harness 내부 함수 호출 기준, 실제 네트워크 왕복 없음)
- 상태별 만료 전·경계·만료 후 판정 결과(B2-02~B2-06)
- cleanup 후 remaining 수(SQLite 잔여 행, 임시 파일·디렉터리)
- 반복 실행 간 결과 편차(B2-12)

## 9. 판정 기준

### 9.1 A. HARNESS TECHNICAL RESULT

- **PASS**: B2-01~B2-12 전 시나리오가 §7의 예상결과와 일치하고, cleanup이 완료된 경우.
- **PASS WITH CONDITIONS**: 판정 로직 자체는 기대대로 동작했으나, 정리 단계에서 경미한 잔존이 있었거나 일부 시나리오가 harness 제약(예: 실제 다중 프로세스 부하 미재현)으로 완전히 재현되지 못한 경우.
- **FAIL**: TTL 경계 판정 오류, 동시 요청에서 성공 건수 오분류, 교차오염 관측, 무한 루프·무한 재시도 관측, 또는 cleanup 실패.

### 9.2 B. OFFICIAL PHASE 1 GATE

- **BLOCKED INPUT**(이 계획서 승인 시점 기준 확정 상태) — §5가 명시하는 대로 실측 트래픽·재시도 패턴 데이터가 저장소에 없으므로, **A의 결과와 무관하게** 고정된다.
- **완료**로 전환되려면: (a) A가 PASS 또는 PASS WITH CONDITIONS이고, (b) 이 harness 결과와는 별도로 실측 데이터(운영자 재시도 행동 패턴 등)가 PM/실행자에 의해 확보되어야 한다. 이 문서는 (b)를 스스로 생성하지 않는다.

### 9.3 중단·재시도 금지 기준

- 예상 밖 무한 루프·무한 재시도가 관측되면 즉시 중단한다.
- B2-10(burst) 규모, B2-11 guard 값, B2-12 반복 횟수는 전부 **PROPOSED INITIAL VALUE**로만 표시하며 이 계획서에서 확정하지 않는다.
- 이 harness는 실제 48시간을 대기하지 않는다(§6 injectable clock).

## 10. Cleanup 계획

각 시나리오 실행 후, 그리고 전체 실행 종료 후 임시 SQLite 파일(및 `-wal`/`-shm`)과 임시 디렉터리를 정리하고, 정리 전후 스냅샷을 B2-12로 기록한다(PoC#1/#3의 `tearDown()` 관행 재사용 제안).

## 11. 실행 전 승인 Gate

| 항목 | 현재 상태 | 필요 승인 |
|---|---|---|
| harness 작성 | 미착수(이 문서는 계획만) | PM/실행자 승인 후 별도 STEP |
| harness 실행 | 미착수 | 작성 완료 후 별도 승인 |
| B. OFFICIAL PHASE 1 GATE 전환(BLOCKED INPUT 해소) | 실측 데이터 없음 | 이 harness와 별도로 PM/실행자가 실측 데이터 확보 후 결정 |
| B2-10 burst 규모·B2-11 guard·B2-12 반복 횟수 최종값 | PROPOSED만 존재 | PM 확정 필요 |

## 12. 범위에서 반드시 제외할 항목

- 실제 Production RPS·성능·확장성·TTL 적합성 입증(이 계획·harness 결과로 입증한다고 표현하지 않는다).
- 외부 부하도구(locust/k6/jmeter 등) 및 신규 패키지 설치.
- 실제 48시간(또는 다른 TTL 실초) 대기.
- Canonical String/HMAC 형식 Gap(별도 Gap, Security Test Plan §5/§8 Gap #2) — PoC#3과 동일 원칙 재확인.
- 운영 GAS·Google Sheets 실접근.
- Phase 2(G6 Final Validation), TTL 최종 확정, Commit8-3b/8-3d 착수 승인, Production 배포 승인.

## 13. PoC#1/#2/#3·G6·Commit8-3b와의 관계

PoC#1(SQLite 원자성, PASS, `6ffc5cf`)·PoC#2(GAS CacheService eviction, PASS WITH CONDITIONS, `b97d2ed`)·PoC#3(Nonce 이중저장소 Fail-Closed, PASS, `6652ee8`)은 이미 완료·Push되었다. 이 DR-B-02 Phase 1은 그 결과들과 독립적으로 계획되었으나, PoC#1의 SQLite 원자성 harness 패턴과 PoC#3의 이중 판정(관측 vs 정책 미확정) 원칙을 그대로 계승한다. G6(Final Validation)은 Commit8-3b 통합 구현 완료 후에만 진입하며 이 Phase 1과는 별개의 Gate다(Gate Plan §32). 이 계획·결과는 Commit8-3b 정식 착수 승인이나 G6 통과를 대체하지 않는다.

## 14. 한계

- injectable clock 기반 검증은 실제 시스템 시계·NTP 드리프트·서버 재시작 등 실운영 조건의 시간 관련 이상 상황을 재현하지 않는다.
- B2-10(burst)·B2-09(재시도)는 **합성 패턴**이며 실제 운영자 재시도 행동 패턴을 관측한 결과가 아니다(§9 원칙 그대로).
- 단일 로컬 프로세스·`ThreadPoolExecutor` 기반 동시성은 실제 다중 서버·다중 프로세스 환경의 경합을 완전히 재현하지 않는다.
- 이 문서의 "B. OFFICIAL PHASE 1 GATE = BLOCKED INPUT"은 이 문서 작성 시점의 저장소 상태를 근거로 하며, 향후 실측 데이터가 확보되면 재평가가 필요하다.

## 15. 결론

이 문서는 ADR-017 §29 DR-B-02 Phase 1(Idempotency TTL 예비 부하검증)을 로컬 Pre-Implementation Harness로 실행하기 위한 계획을 12개 시나리오(B2-01~B2-12)로 구체화했다. TTL 5값은 전부 PROPOSED로 취급했고, Production Idempotency 저장 로직이 NOT IMPLEMENTED임을 명시했다. 판정은 A(HARNESS TECHNICAL RESULT)와 B(OFFICIAL PHASE 1 GATE)로 분리했으며, 실측 트래픽·재시도 데이터 부재로 인해 B는 A의 결과와 무관하게 **BLOCKED INPUT**으로 고정된다. 실제 harness 작성·실행은 이 문서 승인과 별개로 §11의 Gate를 충족해야 한다.

---

**완료 조건 준수 확인**: 이 문서 작성 중 harness를 작성하거나 실행하지 않았다. 의존성을 설치하지 않았다. GAS·Google Sheets·외부 네트워크에 접근하지 않았다. Production 코드나 기존 문서를 수정하지 않았다. 실제 Secret·Token·PII·운영 URL을 포함하지 않았다. 실측 데이터가 없다는 사실을 과장 없이 BLOCKED INPUT으로 명시했으며 Production RPS·성능·TTL 적합성을 입증한다고 표현하지 않았다. Git add/commit/push 없음.
