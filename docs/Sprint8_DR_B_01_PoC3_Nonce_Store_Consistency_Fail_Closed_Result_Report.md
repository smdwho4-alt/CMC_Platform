# Sprint8 DR-B-01 PoC#3 — Nonce 이중저장소 정합성 불일치 Fail-Closed 처리 실행 결과 보고서

> **상태**: 실행 완료(Pre-Implementation Harness, ADR-017 §29). Commit8-3b 정식 구현이 아니며, 이 결과는 Commit8-3b 착수 승인이나 G6 최종검증 통과를 의미하지 않는다.
> **작성일**: 2026-08-23(Sprint8 Pre-G1-B-F)
> **실행계획 원본**: `docs/Sprint8_DR_B_01_PoC3_Nonce_Store_Consistency_Fail_Closed_Test_Plan.md`
> **harness**: `tests/pre_g1/test_dr_b_01_poc3_nonce_store_consistency_fail_closed.py`

---

## 1. 목적과 범위

ADR-017 §29 PoC#3("양쪽 저장소 간 정합성이 어긋나는 경우의 처리 로직 검증")을 로컬 Pre-Implementation Harness로 실행한 결과를 기록한다. 검증 대상은 계획서 §4가 정의한 Fail-Closed 불변조건이며, 실제 GAS CacheService 구현이나 Production 통합을 검증하는 것이 아니라 저장소 판단 조합(NEW/EXISTING/ERROR/UNKNOWN)에 따른 **결정 로직만** 검증한다.

## 2. 실행 환경

- 1차 저장소: 임시 SQLite(`sqlite3`, OS 임시 디렉터리).
- 2차 저장소: 실제 GAS CacheService를 호출하지 않는 deterministic in-memory adapter(organic 상태 추적 + 시나리오별 1회성 override).
- Production 코드(`src/auth/service_hmac.py` 등) import 없음. 운영 GAS·Google Sheets·외부 네트워크 접근 없음. 모든 nonce는 `poc3-<uuid>` 형식의 synthetic 값만 사용.

## 3. 실행 명령과 결과 요약

```
PYTHONIOENCODING=utf-8 python -m unittest tests.pre_g1.test_dr_b_01_poc3_nonce_store_consistency_fail_closed -v
```

PoC#3 unittest 단독으로 **정확히 1회** 실행했다(전체 테스트 suite 실행 아님, 재시도 없음).

```
Ran 12 tests in 0.131s
OK
```

**failures=0, errors=0, skipped=0.**

## 4. 시나리오별 실행 결과(P3-01~P3-12, 각 1건)

| Test ID | Primary | Secondary | Decision | Expected | 결과 |
|---|---|---|---|---|---|
| P3-01 | NEW | NEW | ALLOW | ALLOW | PASS |
| P3-02 | NEW | EXISTING | DENY | DENY | PASS |
| P3-03 | EXISTING | NEW | DENY | DENY | PASS |
| P3-04 | EXISTING | EXISTING | DENY | DENY | PASS |
| P3-05 | ERROR | NEW | DENY | DENY | PASS |
| P3-06 | NEW | ERROR | DENY | DENY | PASS |
| P3-07 | ERROR | ERROR | DENY | DENY | PASS |
| P3-08 | NEW | GARBAGE_UNSCHEMA_VALUE(비정상값) | DENY | DENY | PASS |
| P3-09 | 첫 요청 NEW/NEW → ALLOW, 동일 nonce 재호출 EXISTING/EXISTING → DENY | — | ALLOW→DENY | ALLOW→DENY | PASS |
| P3-10 | 서로 다른 nonce(a, b) 각각 첫 요청 NEW/NEW → ALLOW, 각 재호출 EXISTING/EXISTING → DENY, 교차오염 없음 | — | 독립 ALLOW→DENY | 독립 ALLOW→DENY | PASS |
| P3-11 | NEW / (강제 예외) | DENY, `errorType=SECONDARY_EVALUATION_EXCEPTION`, `errorMessageSafe`는 안전하게 마스킹됨, default allow 0건 | DENY | DENY | PASS |
| P3-12 | in-memory adapter cleanup: `before={seen_count:3, pending_overrides:0}` → `after={seen_count:0, pending_overrides:0}` | — | DECISION_NOT_APPLICABLE | DECISION_NOT_APPLICABLE | PASS |

## 5. 핵심 극단 사례(P3-02) 상세

공식 PoC#3 정의(ADR-017 §29 항목3: "FastAPI는 신규로 판단했으나 GAS Cache에 이미 존재하는 극단적 사례")를 그대로 재현한 P3-02에서, Primary=NEW / Secondary=EXISTING 조합에 대해 harness는 **DENY**를 반환했다. §4 불변조건("어느 한쪽이라도 EXISTING이면 요청을 거부한다") 위반 0건.

## 6. 반복·교차오염 검증(P3-09/P3-10)

- P3-09: 최초 호출은 NEW/NEW로 ALLOW 후보가 되었고, 동일 nonce의 즉시 재호출은 Primary가 SQLite `IntegrityError`로 organic하게 EXISTING, Secondary도 organic하게 EXISTING이 되어 DENY로 정확히 전환되었다.
- P3-10: 서로 다른 synthetic nonce 2건(a, b)이 각각 독립적으로 첫 요청에서 ALLOW, 재호출에서 DENY를 기록했으며, a의 재호출이 b의 판정에 영향을 주거나 그 반대의 경우도 관측되지 않았다(상태 교차오염 0건).

## 7. 예외 처리 검증(P3-11)

Secondary 판단 도중 강제 예외(`RuntimeError`)를 주입한 결과, harness는 예외를 상위로 전파하거나 default allow로 넘어가지 않고 **DENY**로 귀결시켰다. `errorType=SECONDARY_EVALUATION_EXCEPTION`으로 안전하게 분류되었고, `errorMessageSafe`는 harness의 마스킹 로직에 의해 원문이 노출되지 않았다(테스트 assertion으로 nonce 원문·"Secret" 문자열 미포함을 직접 확인). fail-open(예외 시 임의 허용) 사례는 0건 관측되었다.

## 8. 정리(Cleanup) 검증(P3-12 및 실행 후 확인)

- in-memory adapter: `clear()` 호출 전 `seen_count=3, pending_overrides=0` → 호출 후 `seen_count=0, pending_overrides=0`으로 정상 정리됨.
- 임시 SQLite 파일 및 `-wal`/`-shm` 보조파일, 임시 디렉터리: 각 테스트의 `tearDown()`이 정리했으며, 실행 후 OS 임시 디렉터리(`cshsp_pre_g1_b_f_*`) 재확인 결과 **잔존 0건**.
- 실행으로 `tests/pre_g1/__pycache__/`가 신규 생성되었음을 실행 전 부재 확인과 대조해 확인한 뒤, 그 디렉터리만 삭제했다(다른 파일·캐시는 삭제하지 않음).
- Git 상태(staged/보호대상 2건/미추적 44건)는 실행 전후로 변화가 없었다.

## 9. Primary record 처리에 대한 관측(정책 미확정)

harness의 `evaluate_nonce_request()`는 **Primary(1차 SQLite) 판단을 먼저 수행해 record를 커밋한 뒤에** Secondary(2차 adapter) 판단을 수행하는 순서로 동작한다. 따라서 P3-02·P3-06·P3-08처럼 Primary가 NEW로 판단해 실제로 SQLite에 행을 커밋한 **이후에** Secondary가 EXISTING/ERROR/비정상값으로 판단되어 최종 결정이 DENY가 되는 경우, **Primary record는 이미 생성된 상태로 남는다**(harness가 자동으로 rollback하지 않음). 이는 이번 실행에서 실제로 관측된 harness 동작이며, 이 PoC는 그 record를 최종적으로 유지할지 별도 절차로 rollback할지에 대한 Production 정책을 **확정하지 않는다**(계획서 §4 항목6 재확인). harness의 이 순서·결과만으로 정책을 임의 결정하지 않았다.

## 10. 반드시 구분할 한계

- Production Nonce 저장소(FastAPI 1차/GAS Cache 2차)는 **아직 미구현**이며, 이 harness는 그 자리를 대신하는 격리된 재현물일 뿐이다.
- 실제 GAS CacheService를 호출하지 않았다 — Secondary는 deterministic in-memory adapter다.
- 실제 네트워크 지연, GAS 플랫폼 장애, 실제 동시 요청 경합, 실제 CacheService eviction은 이 PoC의 검증 대상이 아니다(eviction은 PoC#2 범위).
- §9에서 관측한 Primary record 유지/rollback 동작은 **정책으로 확정된 것이 아니라 관측사항**이다.
- Canonical String/HMAC 형식 Gap(`service_hmac.py` vs ADR-017 §12)은 이번 PoC#3 범위 밖이다(계획서 §7).
- Nonce/Idempotency TTL, CAS 정책은 이번 실행으로 확정되지 않았다.
- 이 결과는 DR-B-02 Phase 1(예비 부하검증)이나 Phase 2(G6 최종검증)를 대체하지 않는다.
- 이 결과는 Commit8-3b 정식 착수 승인, G6 Pass, Production 배포 승인을 의미하지 않는다(ADR-017 §29 원칙).

## 11. PoC#1·#2·DR-B-02·Commit8-3b와의 관계

PoC#1(SQLite UNIQUE 원자성, PASS, Commit `6ffc5cf`)과 PoC#2(GAS CacheService eviction, PASS WITH CONDITIONS, Commit `b97d2ed`)는 이미 완료·Push되었다. 이 PoC#3은 두 결과와 독립적으로 수행되었으며, Security Architecture Design §23과 Security Test and Deployment Gate Plan §40이 정의하는 Pre-G1(DR-B-01 harness PoC 3건) 중 마지막 항목을 완료한 것이다. DR-B-02 Phase 1/Phase 2는 이 결과와 별개의 검증 대상이며 대체되지 않는다. 이 결과는 Commit8-3b 정식 착수의 설계·판단 근거 중 하나일 뿐이다(PROJECT_STATUS.md §2-2는 이 결과를 반영해 별도 STEP에서 갱신될 수 있다).

## 12. 최종 판정

```
PASS — FAIL-CLOSED DECISION LOGIC VERIFIED
```

P3-01~P3-12 전 시나리오가 계획서 §6의 Expected decision과 정확히 일치했다(failures=0, errors=0, skipped=0). NEW/NEW 조합만 ALLOW 후보로 처리되었고, EXISTING·ERROR·비정상값이 하나라도 섞인 모든 조합과 동일 nonce 재호출은 예외 없이 DENY였다. 예외 발생 시 default allow는 관측되지 않았다(fail-open 0건). 정리(cleanup)는 in-memory adapter·임시 SQLite·임시 디렉터리 전부에서 완료 확인되었다. 이 판정은 **harness 수준의 결정 로직 검증 결과**이며, §10의 한계와 §9의 미확정 정책(Primary record 유지/rollback)을 벗어난 결론(Production 적합성 입증, Commit8-3b 착수·G6 통과 등)은 이 문서로 내려지지 않는다.

---

**완료 조건 준수 확인**: 이 문서 작성 중 GAS·Google Sheets에 접근하지 않았다. 추가 테스트를 실행하지 않았다(§3의 1회 실행 로그만 인용). Production 코드·기존 Gate 문서를 수정하지 않았다. 실제 계정 이메일·scriptId·URL·Token·PII를 포함하지 않았다. Git add/commit/push를 수행하지 않았다.
