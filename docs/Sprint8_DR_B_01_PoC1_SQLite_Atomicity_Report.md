# Sprint8 DR-B-01 PoC#1 — SQLite UNIQUE 동시요청 원자성 검증 결과

> **상태**: PoC 결과 보고서(Pre-Implementation Harness 실행 결과). Production 코드 구현이 아니다. GAS CacheService(PoC#2), 저장소 정합성 불일치(PoC#3), DR-B-02(부하검증), Commit8-3b 구현, Production 배포 가능 여부를 의미하지 않는다.
> **작성일**: 2026-08-18(Sprint8 Pre-G1-A)
> **기준선**: `main`/`origin/main` = `54dee947dfa5ff5cacbe90dd2ea35e0dccc55a12`

---

## 1. 목적과 범위

ADR-017 §13이 채택한 Nonce 이중저장 구조 중 "FastAPI 측 SQLite UNIQUE 제약으로 원자성 확보(별도 Lock 불필요)"라는 설계 전제가 실제로 성립하는지, 독립된 최소 harness로 검증한다. **범위는 SQLite 계층의 원자성 하나뿐**이며, GAS CacheService(PoC#2), 양쪽 저장소 정합성 불일치 처리(PoC#3), DR-B-02 부하검증, Commit8-3b 실제 구현은 이 보고서의 범위 밖이다(§17).

## 2. 기준선 Commit

`54dee947dfa5ff5cacbe90dd2ea35e0dccc55a12`(HEAD=main=origin/main).

## 3. 근거 문서·코드

| 문서/코드 | 확인 내용 |
|---|---|
| `ADR-017_FastAPI_Proxy_and_Signed_GAS_Operations.md` §13 | "FastAPI측은 SQLite UNIQUE 제약으로 원자성 확보(별도 Lock 불필요)" 설계 채택 문구 |
| `ADR-017_FastAPI_Proxy_and_Signed_GAS_Operations.md` §29 | PoC#1 정의: "FastAPI SQLite UNIQUE 제약이 실제 동시 요청에서 원자적으로 중복을 거부하는지 실측 검증" — Pre-Implementation Harness 조건(Commit8-3a STEP3-G 보완) |
| `docs/Sprint8_Security_Architecture_Design.md` §23 | DR-B-01 PoC 3건이 Pre-Implementation Harness로 수행됨을 재확인 |
| `docs/Sprint8_Security_Test_and_Deployment_Gate_Plan.md` §40 | Pre-G1(보조 Gate)의 목적·환경·효력 정의 |
| `src/auth/auth_store.py::connect()` | 기존 SQLite 연결 관행 확인(**읽기 전용 조사, import 없음**): `isolation_level=None`(수동 트랜잭션 제어), `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`, `PRAGMA foreign_keys=ON` |
| `src/auth/service_hmac.py` | Nonce 저장소 관련 코드 없음(docstring상 "Commit8-3 설계 대상"으로만 언급) — Production nonce 테이블 부재 재확인 |
| `tests/run_sprint4_commit3a_slot_hardening_qa.py` | 기존 동시성 테스트 관행 확인(참고용): `ThreadPoolExecutor`로 실동시성 재현, "정확히 하나만 성공" 불변조건 검증 패턴 |

## 4. 검증 환경

| 항목 | 값 |
|---|---|
| OS | Windows 11 (win32) |
| Python | 3.14.2 |
| sqlite3 모듈 연동 SQLite 버전 | 3.50.4 |
| 추가 의존성 설치 | 없음(Python 표준 라이브러리만 사용) |
| 네트워크 접근 | 없음 |
| GAS·Google Sheets 접근 | 없음 |
| Production DB 접근 | 없음(임시 DB만 사용) |

## 5. harness 구조

`tests/pre_g1/test_dr_b_01_poc1_sqlite_nonce_atomicity.py`(`unittest.TestCase` 기반, 8개 테스트 메서드 P1-01~P1-08). `setUp()`에서 `tempfile.mkdtemp(prefix="cshsp_pre_g1_a_")`로 임시 디렉터리를 생성하고 그 안에 SQLite 파일을 만들며, `tearDown()`에서 DB 파일과 WAL 보조파일(`-wal`/`-shm`)을 삭제 후 디렉터리를 제거한다. Production 코드는 import하지 않으며, `src/auth/auth_store.py`의 PRAGMA 관행만 값으로 독립 재구현했다.

## 6. 테이블 schema

```sql
CREATE TABLE nonce_store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nonce TEXT NOT NULL,
    inserted_at TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    UNIQUE(nonce)
);
```
`id`는 대리키(AUTOINCREMENT), `nonce` 컬럼에 명시적 `UNIQUE` 제약을 부여해 이번 PoC의 검증 대상을 정확히 반영했다.

## 7. transaction 방식

각 삽입 시도는 `BEGIN IMMEDIATE`(쓰기 락을 즉시 요청)로 시작해 `INSERT` 후 `COMMIT`한다. `sqlite3.IntegrityError`(UNIQUE 위반) 또는 `sqlite3.OperationalError`("database is locked" 포함) 발생 시 명시적으로 `ROLLBACK`한다. 무한 retry는 구현하지 않았다 — 각 워커는 정확히 1회만 시도한다.

## 8. 시나리오 P1-01~P1-08

| ID | 시나리오 |
|---|---|
| P1-01 | 단일 nonce 최초 삽입 성공 |
| P1-02 | 동일 nonce 순차 중복 삽입 UNIQUE 거부 |
| P1-03 | 동일 nonce 동시 삽입 경쟁(8 workers, Barrier 동기화) |
| P1-04 | 서로 다른 nonce 동시 삽입 전부 성공(8 workers) |
| P1-05 | 실패 transaction ROLLBACK 후 DB 정상 사용 가능 확인 |
| P1-06 | 독립 connection 2개 간 UNIQUE 제약 유지 확인 |
| P1-07 | 반복 실행(20회) 시 결과 안정성 |
| P1-08 | UNIQUE 거부와 database locked 결과 분류 확인(busy_timeout=5000ms 조건 하) |

## 9. 사전 성공 기준

§실행 전 harness docstring 및 이 보고서 상태 헤더에 고정 기재(변경 없이 그대로 인용):

- **PASS**: 동일 nonce 경쟁에서 최종 성공 1건, UNIQUE 거부가 예상대로 발생, 최종 행 수 1건, 데이터 손상 없음, 예상 밖 예외 없음, 임시 DB 정리 완료.
- **PASS WITH CONDITIONS**: 원자성은 확인됐지만 lock 오류·환경 의존성이 존재해 Production 설계에 추가 retry·timeout 기준이 필요.
- **FAIL**: 동일 nonce가 2건 이상 저장되거나, transaction 실패 후 DB 손상/사용불가, 예상 밖 오류로 검증 불가능, 결과가 반복 실행마다 불안정.

## 10. 실행 명령

```
python -m py_compile tests/pre_g1/test_dr_b_01_poc1_sqlite_nonce_atomicity.py
python -m unittest tests.pre_g1.test_dr_b_01_poc1_sqlite_nonce_atomicity -v
```
worker 수=8, 반복 횟수(P1-07)=20, `journal_mode=WAL`, `busy_timeout=5000ms`(§4·§11에 근거와 함께 기록).

## 11. 실행 결과

`python -m unittest ... -v` 실 출력(요약):

```
test_p1_01_single_insert_success ... ok
test_p1_02_sequential_duplicate_rejected ... ok
test_p1_03_concurrent_same_nonce_exactly_one_success ... ok
test_p1_04_concurrent_distinct_nonces_all_succeed ... ok
test_p1_05_rollback_then_db_still_usable ... ok
test_p1_06_unique_enforced_across_independent_connections ... ok
test_p1_07_repeated_execution_stability ... ok
test_p1_08_lock_vs_unique_conflict_classified_separately ... ok

Ran 8 tests in 4.207s

OK
```

실측 로그(각 테스트 내부 print 결과, 실제 값 그대로 기재):

```
[P1-01] status=OK row_count=1
[P1-02] first=OK second=UNIQUE row_count=1
[P1-03] workers=8 OK=1 UNIQUE=7 LOCKED=0 OTHER=0 final_row_count=1
[P1-04] distinct_nonces=8 OK=8 total_rows=8
[P1-05] first=OK rollback_trigger=UNIQUE after_insert=OK total_rows=2
[P1-06] 독립 connection(conn_a, conn_b) 간 UNIQUE 제약 유지 확인, row_count=1
[P1-07] repeats=20 distinct_ok_values={1} distinct_row_values={1} other_errors_total=0
[P1-08] busy_timeout_ms=5000 classification={'OK': 1, 'UNIQUE': 7, 'LOCKED': 0, 'OTHER': 0}
```

**환경 기록 사항**: Windows Git Bash 콘솔의 문자 인코딩(cp949 계열)으로 인해 P1-06의 한국어 print 문자열이 터미널 표시상 깨져 보이는 현상이 발생했다(콘솔 표시 문제, 테스트 판정 자체는 `unittest`가 "ok"로 정상 보고했으며 assertion도 전부 통과함 — §15에 한계로 기록).

## 12. 성공·중복거부·lock·기타 오류 집계

| 시나리오 | OK | UNIQUE(중복거부) | LOCKED | OTHER |
|---|---|---|---|---|
| P1-03(동일 nonce, 8 workers) | 1 | 7 | 0 | 0 |
| P1-04(서로 다른 nonce, 8 workers) | 8 | 0 | 0 | 0 |
| P1-08(동일 nonce, 8 workers, 분류확인용) | 1 | 7 | 0 | 0 |

이번 실행 규모(worker=8, 단일 로컬 머신)에서는 `database is locked`(OperationalError)가 **한 건도 관찰되지 않았다** — `BEGIN IMMEDIATE`가 요청한 쓰기 락이 짧은 트랜잭션 구간 안에서 `busy_timeout=5000ms` 이내에 순차적으로 해소되었기 때문으로 추정되나, 이 추정 자체를 확정값으로 기록하지 않는다(§15).

## 13. 반복 안정성

P1-07(20회 반복, 매회 신규 nonce): 20회 전부 `OK 건수=1`, `최종 행 수=1`, `OTHER 오류=0`으로 **완전히 안정적**이었다. `distinct_ok_values={1}`, `distinct_row_values={1}`(모든 반복에서 동일한 단일 값만 관찰됨).

## 14. 임시 DB 정리 결과

`glob.glob(tempfile.gettempdir() + '/cshsp_pre_g1_a_*')`로 실행 직후 재확인한 결과 잔여 임시 디렉터리 **0건**. `tearDown()`이 매 테스트마다 DB 파일·`-wal`·`-shm` 보조파일과 디렉터리를 정상적으로 정리했음을 확인했다.

## 15. 한계

- worker 수(8)와 반복 횟수(20)는 로컬 환경에서 무리 없는 보수적 값이며, Production 규모의 실제 동시 요청 수·트래픽 패턴을 대표하지 않는다.
- 이번 실행에서 `database is locked` 사례가 0건이었다는 것이 "Production에서도 항상 발생하지 않는다"는 것을 보증하지 않는다 — 단일 로컬 머신, 낮은 동시성 규모, 빠른 로컬 디스크(또는 메모리 캐시) 조건에서의 관찰값일 뿐이다.
- Windows Git Bash 콘솔의 문자 인코딩 문제로 일부 한국어 로그 출력이 터미널에서 깨져 표시되었다(§11) — 테스트 판정 로직(assertion)에는 영향이 없었으나, 향후 harness 재사용 시 로그를 ASCII로 제한하거나 파일로 저장하는 것을 고려할 수 있다.
- `BEGIN IMMEDIATE` + `busy_timeout` 조합이 아닌 다른 방식(예: `BEGIN EXCLUSIVE`, WAL 모드 미사용)에서의 동작은 검증하지 않았다.
- 이 harness는 Nonce "저장"의 원자성만 검증하며, ADR-017 §13이 요구하는 "GAS CacheService와의 이중 검사", "Fail-Closed 원칙", "지문(앞 8자)만 로그 기록" 등 나머지 설계 요소는 검증 범위 밖이다.

## 16. Production 적용 시 고려사항

- SQLite UNIQUE 제약이 동시 요청 상황에서 원자적으로 정확히 1건만 성공시킨다는 ADR-017 §13의 설계 전제는 **이번 PoC 규모 내에서는 확인되었다.**
- `BEGIN IMMEDIATE` 사용은 SQLite의 쓰기 락을 트랜잭션 시작 시점에 명시적으로 요청해 "읽기 후 쓰기" 사이의 경쟁 창을 최소화하는 방식이며, Production Nonce 저장 로직에서도 동일한 패턴 채택을 고려할 수 있다(단, 이 문서는 Production 설계를 확정하지 않는다).
- `busy_timeout` 값(5000ms)은 이번 PoC의 관찰 조건일 뿐이며 Production 값은 별도 결정 필요(DR-B-02 부하검증·정책결정 대상).
- `database is locked` 발생 시의 재시도 정책은 이번 PoC에서 관찰되지 않아 실측 근거가 없으며, ADR-017 §16(최대 3회, 지수 백오프+Jitter)의 기존 설계를 그대로 참조할 수 있으나 이 문서가 그 적정성을 검증하지는 않았다.

## 17. PoC#2·#3 및 DR-B-02와의 경계

이 보고서는 **PoC#1(SQLite UNIQUE 원자성)만** 다룬다. PoC#2(GAS CacheService eviction 시뮬레이션)는 GAS를 실제 사용하므로 별도 PM 승인과 격리된 테스트 환경 확보 전에는 착수하지 않았다(ADR-017 §29 재확인). PoC#3(양쪽 저장소 정합성 불일치 처리 검증)과 DR-B-02(Idempotency TTL 부하검증)도 이번 STEP에서 착수하지 않았다. Commit8-3b 구현에도 착수하지 않았다.

## 18. 후속 Gate 입력사항

- 이 결과는 `docs/Sprint8_Security_Test_and_Deployment_Gate_Plan.md` §40 Pre-G1의 DR-B-01 3건 중 **PoC#1 완료분**으로 참조될 수 있다(문서 갱신은 이 STEP에서 수행하지 않음, 별도 PM 승인 필요).
- Pre-G1 전체(PoC#1~#3 + DR-B-02 Phase 1) 완료를 의미하지 않으며, PoC#2·#3이 남아있다.
- Commit8-3b 착수 판단은 Pre-G1 전체 결과(이 PoC#1 포함)가 갖춰진 뒤 PM이 결정할 사항이다.

## 19. 결론

로컬 harness(worker=8, 20회 반복)에서 SQLite `UNIQUE` 제약은 동일 nonce에 대한 동시 삽입 요청 중 **정확히 1건만 성공시키고 나머지 전부를 원자적으로 거부**했다(8회 모두 최종 행 수 1, 20회 반복 전부 안정적). `database is locked` 오류는 이번 실행 규모에서 0건이었다. 데이터 손상, 예상 밖 예외, 반복 실행 간 불안정성은 관찰되지 않았으며, 임시 DB는 전부 정상 정리되었다. §9의 판정 기준에 따라 **PASS**로 판정한다. 이 결과는 SQLite 계층의 원자성에 대한 기술 검증일 뿐이며, GAS CacheService 검증(PoC#2), 저장소 정합성 검증(PoC#3), DR-B-02 부하검증, Commit8-3b 구현 완료, Production 배포 가능 여부를 의미하지 않는다.

---

**완료 조건 준수 확인**: 이 문서 작성 중 Production 코드·기존 테스트·설계문서를 수정하지 않았다(신규 파일 2건만 작성). 신규 harness는 Python 표준 라이브러리만 사용했고 저장소 다른 코드를 import하지 않았다. Production DB·운영 GAS·운영 Google Sheets에 접근하지 않았다. 실제 Secret·Token·PII를 사용하지 않았다. 임시 DB는 전부 정리되었다(재확인 완료). PoC#2·#3, DR-B-02, Commit8-3b·8-3d 구현을 수행하지 않았다. Git add/commit/push 없음.
