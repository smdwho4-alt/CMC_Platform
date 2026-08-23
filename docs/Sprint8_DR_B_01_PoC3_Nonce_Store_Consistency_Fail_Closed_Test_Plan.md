# Sprint8 DR-B-01 PoC#3 — Nonce 이중저장소 정합성 불일치 Fail-Closed 처리 실행계획

> **상태**: 실행계획 초안(Draft). harness 작성·실행 없음. 실제 측정 결과 없음. Commit 없음.
> **작성일**: 2026-08-23(Sprint8 Pre-G1-B-F)
> **기준선**: `main`/`origin/main` = `b97d2ed7721cdc8fe73adf7ddbade07605e12029`

---

## 1. 목적과 범위

ADR-017 §29 PoC#3("양쪽 저장소 간 정합성이 어긋나는 경우의 처리 로직 검증")을 Production 코드와 분리된 로컬 Pre-Implementation Harness로 실행하기 위한 **실행계획**을 작성한다. 이 문서는 계획 작성까지만 수행하며, 실제 harness 작성·실행은 포함하지 않는다.

**범위**: FastAPI SQLite 1차 Nonce 저장소와 GAS CacheService 2차 저장소의 판단 조합(NEW/EXISTING/ERROR/UNKNOWN)에 따른 **Fail-Closed 결정 로직**의 검증. 이 harness는 실제 GAS CacheService 구현이나 Production 통합을 검증하는 것이 아니라, **저장소 판단 조합에 따른 Fail-Closed 결정 로직만** 검증한다.

**제외 범위**(§7에서 재확인): Canonical String/HMAC 형식 정합성(별도 Gap, Security Test Plan §5/§8 Gap #2), `service_hmac.py` 수정, GAS HMAC 구현, timestamp 허용 초값 결정, Nonce/Idempotency TTL·CAS 정책 확정, 실제 GAS CacheService eviction·동시성 검증(PoC#2 범위), DR-B-02 Phase 1/Phase 2, Commit8-3b/8-3d 구현.

## 2. 기준선 Commit

`b97d2ed7721cdc8fe73adf7ddbade07605e12029`(HEAD=main=origin/main, Sprint8 PoC#2 완료·PROJECT_STATUS.md §2-2 반영 직후 시점).

## 3. 근거 문서·코드

| 문서/코드 | 확인 내용(직접 인용) |
|---|---|
| `ADR-017_FastAPI_Proxy_and_Signed_GAS_Operations.md` §13 | "채택: CacheService(GAS, TTL 300초, 2차 방어)와 FastAPI 측 영속 저장소(...1차 방어)의 이중 구조... 저장 실패 시 Fail-Closed(양쪽 저장소 중 어느 한쪽이라도 기록에 실패하면 해당 요청을 진행하지 않음)... 원자성: GAS측은 Nonce 존재확인~기록 구간을 LockService로 감쌈, FastAPI측은 SQLite UNIQUE 제약으로 원자성 확보" |
| `ADR-017_FastAPI_Proxy_and_Signed_GAS_Operations.md` §29 | PoC#3 정의(Commit8-3a STEP2-C §6 원문): "3. 양쪽 저장소 간 정합성이 어긋나는 경우(FastAPI는 신규로 판단했으나 GAS Cache에 이미 존재하는 극단적 사례)의 처리 로직 검증" — Pre-Implementation Harness 조건 |
| `ADR-017_FastAPI_Proxy_and_Signed_GAS_Operations.md` §36 | 2026-08-18 PM 승인: "§29를 Pre-Implementation Harness(사전 검증)와 Integrated Implementation(Commit8-3b 정식 구현)의 2단계로 명확화... GAS를 실제 사용하는 PoC(§29 항목2)는 별도 PM 승인·격리된 테스트 환경 전 착수 금지를 명시" — PoC#3(항목3)은 GAS 실사용 항목이 아니므로 이 별도 승인 요건 대상이 아님을 재확인 |
| `docs/Sprint8_Security_Architecture_Design.md` §20 | "Pre-Implementation Harness와 Integrated Implementation 구분(PM 결정)... Commit8-3b 착수 전 사전 Gate는 Pre-Implementation Harness(격리된 최소 harness, Commit8-3b Production 코드와 별개 산출물)를 통한 Preliminary Validation을 가리키며, Commit8-3b Production 코드 자체의 완성을 의미하지 않는다" |
| `docs/Sprint8_Security_Architecture_Design.md` §23 | "DR-B-01 PoC 3건... (3) 양쪽 저장소 정합성 불일치 시나리오 처리 검증. 3건 전부 Pre-Implementation Harness(Commit8-3b Production 코드와 별개)로 수행하며, 항목(2)는 GAS를 실제 사용하므로 별도 PM 승인과 격리된 테스트 환경... 확보 전에는 착수하지 않는다" — 항목(3)=PoC#3은 이 GAS 실사용 승인요건에 해당하지 않음 |
| `docs/Sprint8_Security_Test_and_Deployment_Gate_Plan.md` §40 | "Pre-G1(보조 Gate)... DR-B-01 harness PoC 3건... Pass 시 효력: Commit8-3b 정식 착수의 설계·판단 근거로만 사용. G6 Pass나 배포 승인을 대체하지 않는다" / 추적표: "DR-B-01 \| PoC 3건(SQLite UNIQUE 원자성/CacheService eviction 시뮬레이션/양쪽 저장소 정합성 불일치 처리) \| ... \| DEFERRED" |
| `docs/Sprint8_Security_Test_and_Deployment_Gate_Plan.md` §42-1 | `REPLAY-02`: "nonce 재사용·replay 거부... FastAPI SQLite+GAS Cache 이중검사... 결과 `NONCE_REPLAYED`... ADR-017 §13... **REQUIRES POC(DR-B-01)**" — 이 PoC#3이 입력자료를 제공하는 대상 Test ID |
| `docs/Sprint8_DR_B_01_PoC1_SQLite_Atomicity_Report.md` §1/§17 | "GAS CacheService(PoC#2), 저장소 정합성 불일치(PoC#3)... 이 보고서의 범위 밖이다" — PoC#1이 SQLite 원자성만 검증했고 이중저장소 정합성은 미검증임을 재확인 |
| `docs/Sprint8_DR_B_01_PoC2_GAS_CacheService_Test_Plan.md` §28 | "PoC#3(양쪽 저장소 정합성 불일치 처리 검증)은 PoC#2 결과(특히 P2-10 Fail-Closed 입력자료)에 일부 의존할 수 있으나, 이 문서는 PoC#3을 설계하지 않으며 별도 STEP으로 남긴다" |
| `docs/Sprint8_DR_B_01_PoC2_GAS_CacheService_Result_Report.md` §6.1/§13 | P2-10 결과: "P2-07/P2-08 결과 2건을 근거자료로 산출. Fail-Closed 정책 자체를 확정한 것이 아님" — 이 PoC#3이 참고할 수 있는 선행 근거자료(정책 미확정 상태) |
| `PROJECT_STATUS.md` §2-2 | "DR-B-01 PoC#3 \| ⬜ 미착수 \| 별도 범위·착수 승인 필요" — 현재 상태 재확인 |
| `src/auth/service_hmac.py` | `verify_signature()` docstring: "Nonce 재사용(Replay) 방지는 이 함수 범위 밖이다 — 호출부가 별도의 Nonce 저장소(예: 짧은 TTL 캐시)로 이미 사용된 Nonce인지 확인해야 한다(Commit8-3 설계 대상, 이번 Commit에서는 저장소를 구현하지 않는다)" — Nonce 이중저장소 자체가 **NOT IMPLEMENTED** 재확인. `canonical_string()`은 5필드(`method/action/timestamp/nonce/body_hash`) 구조로 ADR-017 §12 8줄 형식과 다르나, 이는 §7에서 명시하는 별도 Gap이며 이 PoC#3 범위 밖 |
| `app/apps_script/*.gs`(3개 파일) | `CacheService`/`HMAC` 관련 코드 전수 검색 결과 **0건** — GAS 측 Nonce 2차 저장소·서명 검증 모두 미구현 재확인 |

## 4. 공식 목적 — 검증 대상 보안 불변조건

이 PoC는 다음 불변조건이 harness 수준에서 성립하는지 검증한다(어느 것 하나라도 위반되면 FAIL, §6).

1. **단일 판단 조합에서 ALLOW 후보는 Primary NEW / Secondary NEW 조합뿐이다.** P3-09의 첫 요청과 P3-10의 각 독립 nonce 요청은 이 동일한 NEW/NEW 조합을 시퀀스 안에서 재사용하는 것일 뿐이며, 별도의 예외적 허용 규칙이 아니다.
2. 어느 한쪽이라도 **EXISTING**이면 요청을 **거부(DENY)**한다.
3. 어느 한쪽이라도 **ERROR/UNAVAILABLE**이면 요청을 **거부(DENY)**한다(불확실을 신규로 낙관 처리하지 않음).
4. 두 저장소의 판단이 **불일치**하면 요청을 거부한다.
5. 판단이 **불명확**(스키마 밖 값·UNKNOWN)하면 요청을 거부한다.
6. Fail-Closed는 **요청 허용 여부에 대한 원칙**이며, 실패 후 1차 저장소 record를 유지할지 rollback할지에 대한 정책은 **이 PoC가 임의로 확정하지 않는다**(관측값으로만 기록, §6/§7).

**용어 제한**: 이 문서에서 "ALLOW"는 harness의 결정값(정상 처리 후보로 판단됨)을 가리키는 용어일 뿐, Production 업무처리의 최종 승인을 의미하지 않는다. 이 PoC 결과를 Production 구현·배포 적합성으로 확대 해석하지 않는다.

## 5. 실행환경 및 harness 설계 원칙

- Production 코드와 완전히 분리된 **로컬 Pre-Implementation Harness**로 설계한다(신규 파일, 기존 코드 import 없음).
- **Python 표준 라이브러리만 사용**(`sqlite3`, `tempfile`, `os`, `json`, `uuid`, `datetime` 등), 외부 의존성 설치 없음.
- **1차 저장소**: 임시 SQLite(OS 임시 디렉터리, PoC#1과 동일한 격리 원칙 재사용 — `tempfile.mkdtemp()` 하위).
- **2차 저장소**: 실제 GAS CacheService를 호출하지 않고, 그 판단 결과(NEW/EXISTING/ERROR/UNKNOWN)를 **재현하는 deterministic in-memory adapter**로 대체한다(dict 기반, 시나리오별로 사전 주입된 응답만 반환).
- GAS·Google Sheets·외부 네트워크 접근 전혀 없음.
- 모든 nonce·request ID는 **synthetic**(예: `poc3-<uuid>`, `poc3-req-<n>` 형식)만 사용, 실 예약번호·PII·실 nonce 미사용.
- 실행 종료 후 임시 SQLite 파일(및 `-wal`/`-shm` 보조파일)·로그·in-memory cache adapter 상태를 정리한다(§8 cleanup 계획).
- **명시**: 이 harness는 실제 GAS CacheService 구현이나 Production 통합을 검증하는 것이 아니라, **저장소 판단 조합에 따른 Fail-Closed 결정 로직만** 검증한다. 결정 로직 자체도 이 PoC를 위해 harness 내부에 새로 작성하는 참조 구현이며, Commit8-3b Production 코드가 아니다.

## 6. 최소 시나리오 (P3-01~P3-12)

| Test ID | Input(설명) | Primary(1차 SQLite) 결과 | Secondary(2차 Cache adapter) 결과 | Expected decision | Pass criteria | Evidence |
|---|---|---|---|---|---|---|
| P3-01 | 정상 synthetic nonce 1건, 양쪽 최초 조회 | NEW | NEW | ALLOW(정상 처리 후보) | ALLOW 반환. 이후 실제 예약 처리·record 저장 로직 시뮬레이션은 이 PoC 범위 밖(§7) | 실행 로그 |
| P3-02 | 동일 nonce, 두 저장소 판단 불일치(**공식 PoC#3 핵심 극단 사례**: FastAPI는 신규로 판단했으나 GAS Cache에 이미 존재) | NEW | EXISTING | DENY | 반드시 DENY. ALLOW 발생 시 즉시 중단(§8) | 실행 로그 |
| P3-03 | 반대 방향 불일치 | EXISTING | NEW | DENY | 반드시 DENY | 실행 로그 |
| P3-04 | 양쪽 모두 기존 값 존재(정상 Replay 탐지) | EXISTING | EXISTING | DENY | 반드시 DENY | 실행 로그 |
| P3-05 | 1차 저장소 오류, 2차는 신규 판단 | ERROR | NEW | DENY | 반드시 DENY(ERROR를 NEW로 낙관 변환 금지) | 실행 로그 |
| P3-06 | 1차는 신규 판단, 2차 저장소 오류 | NEW | ERROR | DENY | 반드시 DENY | 실행 로그 |
| P3-07 | 양쪽 모두 오류/불가용 | ERROR | ERROR | DENY | 반드시 DENY | 실행 로그 |
| P3-08 | 2차 결과가 스키마 밖 값(UNKNOWN/비정상값), 1차는 NEW | NEW | UNKNOWN | DENY | UNKNOWN을 NEW로 임의 변환하지 않고 DENY | 실행 로그 |
| P3-09 | 동일 nonce 반복 호출(1차 ALLOW 후보 처리 이후 동일 nonce 재호출) | 1차 호출: NEW / 2차 호출: EXISTING(자기 자신이 방금 기록한 값) | 1차 호출: NEW / 2차 호출: EXISTING | 첫 요청 ALLOW 후보 → 동일 nonce 재호출 DENY | 최초 호출은 NEW/NEW 조합이므로 ALLOW 후보, 재호출은 EXISTING이 섞이므로 반드시 DENY | 실행 로그 + 호출 순서 기록 |
| P3-10 | 서로 다른 synthetic nonce 2개 이상을 교차 호출 | nonce별 독립 값(각 NEW) | nonce별 독립 값(각 NEW) | 서로 다른 nonce 각각 ALLOW 후보, 상태 교차오염 없음 | 각 nonce가 독립적으로 NEW/NEW 조합이므로 각각 ALLOW 후보이며, 한 nonce의 판정·상태가 다른 nonce의 판정에 영향을 주지 않음(상태 교차오염 없음) | 실행 로그 |
| P3-11 | 판단 로직 실행 중 어댑터가 강제 예외를 발생시키는 경우 | 예외 발생(강제) | 호출되지 않거나 무관 | DENY | 예외 발생 시 default allow 없음(fail-open 금지), 오류 메시지에 Secret·원문 nonce·내부 경로 미노출, 안전하게 분류된 오류 사유만 기록 | 실행 로그 + 오류 분류 |
| P3-12 | 전체 시나리오 실행 종료 후 정리 확인 | 해당없음 | 해당없음 | DECISION_NOT_APPLICABLE(cleanup 검증) | 임시 SQLite 파일(및 `-wal`/`-shm`)·in-memory cache adapter 상태·로그 파일 중 저장소 밖에 남아야 할 것 외 잔존 0건 | 정리 전후 스냅샷 |

**ALLOW 후보는 시나리오 ID가 아니라 판단 조합(Primary NEW / Secondary NEW)으로 결정된다.** P3-01은 단일 요청에서 이 조합이 나타나는 기본 사례이고, P3-09의 첫 요청과 P3-10의 각 독립 nonce 요청도 시퀀스 안에서 동일한 NEW/NEW 조합을 재사용하므로 ALLOW 후보가 된다 — 이는 예외 규칙이 아니라 같은 원칙의 반복 적용이다. NEW/NEW가 아닌 모든 조합(EXISTING·ERROR·UNKNOWN이 하나라도 섞인 경우)과 동일 nonce의 재호출은 항상 DENY다.

## 7. 이번 PoC#3 범위에서 반드시 분리할 항목

다음은 이번 PoC#3의 검증 대상이 **아니며**, 별도 항목·별도 승인으로 관리한다.

- **Canonical String 5필드↔8줄 형식 Gap**(`service_hmac.py`의 `method\naction\ntimestamp\nnonce\nbody_hash` vs ADR-017 §12의 `CMC-HMAC-SHA256\n1\n<Method>\n<operation>\n<timestamp>\n<nonce>\n<idempotencyKey>\n<payloadHash>`)은 Security Test Plan §5/§8 Gap #2로 이미 별도 추적 중이며, 이번 PoC#3 범위 밖이다.
- `service_hmac.py` 수정 없음.
- GAS 측 HMAC 서명 검증 구현 없음.
- timestamp 허용 오차 초값(REPLAY-01) 결정 없음.
- Nonce TTL·Idempotency TTL·CAS 정책 확정 없음(ADR-017 §14, DR-B-02 대상).
- 실제 GAS CacheService eviction·동시성 검증 없음(PoC#2가 이미 별도로 다룸, 이 PoC#3은 그 결과를 in-memory adapter 응답 설계의 참고자료로만 사용할 수 있음).
- DR-B-02 Phase 1(예비 부하검증)·Phase 2(G6 최종검증)를 대체하지 않는다.

## 8. 성공·실패·중단·증적

### 8.1 판정 기준

- **PASS**: 모든 Primary/Secondary NEW/NEW 판단이 ALLOW 후보로 처리되고, 그 외 모든 조합(EXISTING·ERROR·UNKNOWN이 하나라도 섞인 경우)은 예외 없이 DENY이며, 반복된 동일 nonce 요청(재호출)은 DENY이고, 서로 다른 nonce는 서로 독립적으로 처리되며(교차오염 없음), 예외 발생 시 default deny가 유지되고, P3-12 cleanup이 완료된 경우.
- **PASS WITH CONDITIONS**: 위 PASS 기준(ALLOW/DENY 오분류 0건)은 전부 충족했으나, 정리 단계에서 경미한 잔존이 있었거나 일부 시나리오가 harness 제약으로 완전히 재현되지 못한 경우(예: 실제 동시성 재현 불가 — 이 harness는 단일 실행 순차 판단만 검증).
- **FAIL**: 다음 중 하나라도 해당하면 FAIL이다.
  - mismatch·EXISTING·ERROR·UNKNOWN이 하나라도 섞인 판단 조합에서 ALLOW가 한 건이라도 나온 경우
  - P3-09의 두 번째(동일 nonce 재호출) 요청이 DENY가 아닌 경우
  - P3-10의 독립 nonce 중 정상 NEW/NEW 요청이 DENY되거나, 서로 다른 nonce 간 상태가 교차오염된 경우
  - ERROR/UNKNOWN이 NEW로 변환된 경우
  - 예외 발생 후 default allow가 관측된 경우
  - P3-12 cleanup이 실패한 경우

### 8.2 중단 기준

- **예상 밖 ALLOW 발생 시 즉시 중단**하고 나머지 시나리오를 진행하지 않는다(안전 우선).
- 무한 retry를 설계하지 않는다.
- timeout·반복 횟수는 harness 설계 시 **PROPOSED INITIAL VALUE**로만 표시하며 이 계획서에서 확정하지 않는다.

### 8.3 결과 JSON 구조(제안)

각 시나리오 결과는 최소 다음 필드를 가진 object로 반환하도록 harness를 설계할 것을 제안한다(PoC#1/#2와 동일한 관행 재사용):

```
{
  "scenario": "P3-02",
  "primaryResult": "NEW",
  "secondaryResult": "EXISTING",
  "decision": "DENY",
  "expectedDecision": "DENY",
  "pass": true,
  "recordRetainedNote": "관측값일 뿐 정책 확정 아님",
  "errorType": null,
  "errorMessageSafe": null,
  "notes": []
}
```

`recordRetainedNote`는 DENY 이후 1차 저장소 record를 유지했는지/rollback했는지의 **관측값**을 기록하는 필드이며, 이 계획서는 그 정책을 확정하지 않는다(§4 항목6).

### 8.4 최종 결과보고서 예정 경로

`docs/Sprint8_DR_B_01_PoC3_Nonce_Store_Consistency_Fail_Closed_Result_Report.md`(이번 STEP에서 작성하지 않음, 실행 승인·실행 완료 후 별도 STEP).

### 8.5 Secret·PII 보호

모든 nonce·request ID는 synthetic 문자열만 사용(§5). 실제 HMAC Secret, 실제 예약자 정보, 실제 운영 URL을 이 PoC의 어떤 단계에도 포함하지 않는다. 오류 메시지는 안전하게 분류된 사유만 기록하고 원문·Secret을 노출하지 않는다(P3-11).

### 8.6 Cleanup 계획

각 시나리오 실행 후, 그리고 전체 실행 종료 후 임시 SQLite 파일(및 `-wal`/`-shm`)과 in-memory cache adapter 상태를 정리하고, 정리 전후 스냅샷을 P3-12로 기록한다(PoC#1의 `tearDown()` 관행 재사용 제안).

### 8.7 실행 전 승인 Gate

| 항목 | 현재 상태 | 필요 승인 |
|---|---|---|
| harness 작성 | 미착수(이 문서는 계획만) | PM/실행자 승인 후 별도 STEP |
| harness 실행 | 미착수 | 작성 완료 후 별도 승인 |
| Canonical String Gap(§7) | 별도 항목으로 분리 유지 | 이 PoC#3과 별도로 결정 |
| PoC#2 결과 참고 여부 | P2-10 근거자료 활용 가능(§3) | 참고만, 재실행 승인 불요 |

## 9. PoC#1/#2·DR-B-02·Commit8-3b와의 관계

PoC#1(SQLite UNIQUE 원자성)은 완료·Push됨(PASS, Commit `6ffc5cf`). PoC#2(GAS CacheService eviction)도 완료·Push됨(PASS WITH CONDITIONS, Commit `b97d2ed`). 이 PoC#3은 두 결과와 독립적으로 수행 가능하나, in-memory adapter의 응답 설계 시 PoC#2의 P2-10 근거자료(Fail-Closed 입력자료, 정책 미확정)를 참고할 수 있다. DR-B-02(Idempotency 부하검증) Phase 1/Phase 2는 이 PoC#3과 별개의 검증 대상이며 대체되지 않는다. 이 PoC#3의 결과는 Commit8-3b 정식 착수의 설계·판단 근거 중 하나일 뿐이며, G6 통과나 Production 배포 승인을 대체하지 않는다(ADR-017 §29 원칙).

## 10. 한계

- 이 harness는 저장소 판단 조합에 대한 **결정 로직**만 검증하며, 실제 SQLite/CacheService 통합 동작, 실제 동시 요청 경합, 실제 GAS 네트워크 지연은 재현하지 않는다.
- P3-09(반복 호출)·P3-10(교차 nonce)은 단일 실행 내 순차 호출로만 검증되며, 실제 동시 요청 상황의 race condition은 이 PoC 범위 밖이다.
- 1차 저장소 record 유지/rollback 정책(§4 항목6)은 이 PoC에서 관측만 하며 확정하지 않는다.

## 11. 결론

이 문서는 ADR-017 §29 PoC#3(양쪽 저장소 정합성 불일치 처리 검증)을 Production 코드와 분리된 로컬 harness로 실행하기 위한 계획을 12개 시나리오(P3-01~P3-12)로 구체화했다. 검증 대상은 저장소 판단 조합(NEW/EXISTING/ERROR/UNKNOWN)에 대한 Fail-Closed 결정 로직이며, GAS·Google Sheets 실접근이나 Canonical String/HMAC 형식 정합성(별도 Gap)은 범위에서 명시적으로 제외했다. ALLOW 후보는 P3-01뿐이며 나머지 전 시나리오는 DENY가 기대값이다. 실제 harness 작성·실행은 이 문서 승인과 별개로 §8.7의 Gate를 충족해야 한다.

---

**완료 조건 준수 확인**: 이 문서 작성 중 harness를 작성하거나 실행하지 않았다. 테스트를 실행하지 않았다. GAS·Google Sheets에 접근하지 않았다. 의존성을 설치하지 않았다. Production 코드(`service_hmac.py`, `app/apps_script/*.gs` 등)를 수정하지 않았다. 기존 문서를 수정하지 않았다. 실제 Secret·Token·Nonce·PII·운영 URL을 포함하지 않았다. Git add/commit/push 없음. PoC#2 격리 GAS 프로젝트를 삭제하지 않았다.
