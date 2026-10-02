# Sprint8 DR-B-02 Phase 1 — Idempotency TTL 예비 부하검증(Preliminary Validation) 실행 결과 보고서

> **상태**: candidate 기반 로컬 합성 harness 1회 실행 완료(2026-10-02, 2회차에서 PASS). 이 문서는 그 결과만 보고하며, 저장소 반영(harness/로그 사본)은 이 문서 작성과 별개의 PM 승인 절차를 거친다.
> **작성일**: 2026-10-03
> **기준 계획서**: [docs/Sprint8_DR_B_02_Phase1_Idempotency_TTL_Preliminary_Load_Test_Plan.md](Sprint8_DR_B_02_Phase1_Idempotency_TTL_Preliminary_Load_Test_Plan.md)
> **기준선 commit**: `cadf055dd27ee6967a89f8ac4725b0a933ef60ff`(HEAD=main=origin/main, 이 보고서 작성 시점)

---

## 1. 목적과 범위

이 문서는 ADR-017 §29 DR-B-02 Phase 1(Idempotency TTL 예비 부하검증)을 로컬 Pre-Implementation harness로 1회 실행한 결과를 보고한다. harness는 계획서가 정의한 B2-01~B2-12 시나리오(총 12개 ID, B2-09는 SUCCEEDED/FAILED_FINAL 두 수렴 경로로 분리해 15개 `test_` 메서드로 구현)를 다룬다.

이 문서가 보고하는 것은 **A. HARNESS TECHNICAL RESULT**(harness 코드가 설계대로 동작했는가)뿐이며, **B. OFFICIAL PHASE 1 GATE**는 계획서 §4·§5·§9.2가 명시한 대로 실측 트래픽·재시도 패턴 데이터 부재를 이유로 이 보고서와 무관하게 **BLOCKED INPUT**으로 고정된다(§12 재확인).

## 2. 실행 환경

| 항목 | 값 |
|---|---|
| Python 버전 | 3.14.2 |
| 표준 라이브러리만 사용 | `os, sqlite3, sys, tempfile, threading, time, math, unittest, uuid, concurrent.futures, pathlib, typing` |
| 외부 네트워크·운영 GAS·Google Sheets 접근 | 없음(설계·실행 양쪽 모두 확인) |
| 저장소 | OS 임시 디렉터리의 SQLite 파일(`tempfile.mkdtemp`), 실행 종료 시 정리 |
| harness 위치(실행 시점) | 저장소 밖 scratchpad — `sprint8_dr_b_02_phase1_idempotency_ttl_harness_candidate.py` |
| harness 위치(저장소 반영본) | [tests/pre_g1/test_dr_b_02_phase1_idempotency_ttl_preliminary_validation.py](../tests/pre_g1/test_dr_b_02_phase1_idempotency_ttl_preliminary_validation.py) — 실행된 candidate와 바이트 단위로 동일 |
| **실행한 harness SHA-256** | `6db18c2a8c44e4741116b631d78b82287273b26dcbdc7eb3fee13b99b320ea7e` |
| 실행 횟수 | 2회(1차 FAIL/ERROR → 코드 수정 → 2차 전부 PASS). 자세한 이력은 §8 참조 |

## 3. 실행 명령과 결과 요약(2차 실행 — 최종 결과)

```
명령: python3 -X utf8 -m unittest -v sprint8_dr_b_02_phase1_idempotency_ttl_harness_candidate
종료코드: 0
Ran 15 tests in 10.285s
OK
```

| 구분 | 수 |
|---|---|
| 실행된 테스트 수 | 15 |
| PASS | 15 |
| FAIL | 0 |
| ERROR | 0 |
| SKIP | 0 |

## 4. 시나리오별 실행 결과(B2-01~B2-12, 2차 실행 로그 실측값 그대로 인용)

| ID | 결과 | 측정값(로그 원문) |
|---|---|---|
| B2-01 | PASS | `match_count=5/5 mapping={'IN_PROGRESS': 60, 'SUCCEEDED': 900, 'FAILED_RETRYABLE': 300, 'FAILED_FINAL': 900, 'UNKNOWN': 172800}` |
| B2-02 | PASS | `[TTL=60s state=IN_PROGRESS] before=IN_PROGRESS boundary=IN_PROGRESS after=UNKNOWN` latency(min/median/p95/max)=0.004576/0.005598/0.008668/0.009009s, n=3. 경로 A/B 상세는 §5 |
| B2-03 | PASS | `[TTL=900s state=SUCCEEDED] before=SUCCEEDED boundary=SUCCEEDED after=EXPIRED` |
| B2-04 | PASS | `[TTL=300s state=FAILED_RETRYABLE] before=FAILED_RETRYABLE boundary=FAILED_RETRYABLE after=EXPIRED` |
| B2-05 | PASS | `[TTL=900s state=FAILED_FINAL] before=FAILED_FINAL boundary=FAILED_FINAL after=EXPIRED` |
| B2-06 | PASS | `[TTL=172800s state=UNKNOWN] before=UNKNOWN boundary=UNKNOWN after=EXPIRED`(48시간, 숫자 연산만, 실제 대기 없음) |
| B2-07 | PASS | `workers=8 CREATED=1 DUPLICATE_BLOCKED=7 errors=0 row_count=1 elapsed_sec=0.167160 throughput_ops_per_sec=47.858 latency(min/median/p95/max)=0.00959/0.05946/0.15260/0.16493s n=8` |
| B2-08 | PASS | `distinct_keys=8 CREATED=8 total_rows=8 unique_keys_in_db=8 elapsed_sec=0.161971 throughput_ops_per_sec=49.391` |
| B2-09 | PASS(양쪽 경로) | 상세는 §6 |
| B2-10 | PASS | `burst_count=30 CREATED=1 DUPLICATE_BLOCKED=29 errors=0 elapsed_sec=1.986160 throughput_ops_per_sec=15.105 latency p95=1.811s max=1.978s n=30` |
| B2-11 | PASS | `guard_max=3 total_requested=10 processed=3 aborted_early=True row_count_after_abort=3 elapsed_sec=0.023701 throughput_ops_per_sec=126.578` |
| B2-12 | PASS | 상세는 §7 |

**정책 미확정 보조 검증**(공식 B2-ID 아님, §9 참조): `test_policy_unresolved_states_block_without_mutation` — PASS.

## 5. B2-02 — 두 호출 경로(IN_PROGRESS 만료 → UNKNOWN 전이·재실행 차단·행 보존)

ADR-017 §14/§16/§23은 IN_PROGRESS가 TTL(60초)을 초과하면 삭제가 아니라 자동으로 `UNKNOWN`/`RECONCILIATION_REQUIRED`로 전이하고, 이후 자동 재실행을 절대 금지한다고 명시한다. 이 결과가 **호출 순서와 무관하게 동일**한지 두 경로로 각각 검증했다(로그 원문 인용):

| 경로 | 설명 | 결과 |
|---|---|---|
| A(직접 호출) | `read_state()`를 거치지 않고, 아직 원시 state가 `IN_PROGRESS`인 행에 `try_create()`를 직접 호출 | `retry_result=('RECONCILIATION_REQUIRED_BLOCKED', 'UNKNOWN') row_count=1 state_after=UNKNOWN` |
| B(read_state 선행) | `read_state()`가 먼저 호출되어 이미 `UNKNOWN`으로 전이된 뒤 `try_create()` 호출 | `retry_result=('RECONCILIATION_REQUIRED_BLOCKED', 'UNKNOWN') row_count=1 state_after=UNKNOWN` |

양쪽 경로 모두 **UNKNOWN 전이, CREATED=0(신규 생성 없음), 기존 행 보존(row_count=1)**을 만족했다 — 1차 실행에서 경로 B가 `DUPLICATE_BLOCKED`를 반환해 FAIL이었던 결함(§8)이 해소되었음을 2차 실행이 실측으로 확인했다.

## 6. B2-09 — 두 수렴 경로(최초 1회 + 재시도 4회 = 총 5회)

이번 합성 예비검증의 B2-09 설정(운영 정책 확정 아님, 로컬 검증 설정으로 기록):

- 최초 요청(`initial_request_count`) = **1**
- 재시도 횟수(`retry_count`, `RETRY_ATTEMPTS`) = **4**
- 총 요청 수(`total_request_count`) = 최초 1 + 재시도 4 = **5**
- 고유 nonce 수 = **5**(모든 요청이 서로 다른 nonce 사용)
- 마지막 재시도에서 `SUCCEEDED` 또는 `FAILED_FINAL`로 수렴

| | B2-09a(SUCCEEDED 경로) | B2-09b(FAILED_FINAL 경로) |
|---|---|---|
| initial_request_count | 1 | 1 |
| retry_count | 4 | 4 |
| total_request_count | 5 | 5 |
| unique_nonces | 5 | 5 |
| row_counts(매 단계) | [1, 1, 1, 1, 1] | [1, 1, 1, 1, 1] |
| terminal | SUCCEEDED | FAILED_FINAL |
| elapsed_sec | 0.041365 | 0.039319 |
| throughput_ops_per_sec | 120.876 | 127.166 |

양쪽 경로 모두 중복 행 없음(row_count 매 단계 1), 동일 key 유지(UPDATE 전용 SQL 구조로 보장), 지정한 최종 상태로 정확히 수렴했다.

**잔여 모호성(해결하지 않고 보고)**: 계획서 §7 B2-09 행의 "3~5회"가 마지막 수렴 시도 자체를 포함하는지(이번 harness의 해석), 아니면 FAILED_RETRYABLE 재시도만 가리키고 수렴 시도가 그 이후 별도로 추가되는 것인지는 계획서 원문만으로 완전히 확정되지 않는다. 이 harness는 전자(마지막 재시도=수렴 시도)로 일관되게 구현했다.

## 7. B2-12 — 3회 반복(B2-02~B2-10 전체 패턴)과 cleanup

```
[B2-12] repeats=3 distinct_outcome_patterns=1 row_counts_before_cleanup=[17, 17, 17]
cleanup_flags=[True, True, True] elapsed_sec_total=7.490863 ops_measured=216
throughput_ops_per_sec=28.835 latency_sec_min=0.001807 latency_sec_median=0.049576
latency_sec_p95=1.633585 latency_sec_max=2.092920 n=216
(observation only, not a pass/fail criterion - plan section 8)
```

- 3회 반복 모두 **동일한 결정론적 결과 패턴**(`distinct_outcome_patterns=1`, 편차 0건).
- 반복마다 cleanup 전 행 수 17건(TTL 5상태 + B2-07 1건 + B2-08 8건 + B2-09 SUCCEEDED 1건 + B2-09 FAILED_FINAL 1건 + B2-10 1건)으로 **반복 간 완전히 일치**.
- `cleanup_flags=[True, True, True]` — 3회 전부 cleanup 성공(임시 SQLite 파일·`-wal`/`-shm`·임시 디렉터리 전부 제거 확인).
- latency/throughput은 §8 공통 측정값을 관측값으로만 출력했으며, 합격 기준으로 쓰지 않았다(계획서에 없는 성능 기준 추가 없음).

## 8. 1차 실행 실패와 수정 내역, 2차 실행 통과 이력

**1차 실행**(candidate SHA-256 `9ee266afb1998cce8eaa879a2834118d1d401b37492701946db3c176a30a1e14`, `python3 -m unittest -v`, 종료코드 1): `Ran 14 tests in 10.149s`, `FAILED (failures=3, errors=1)`.

| 결함 | 증상 | 원인 | 조치 |
|---|---|---|---|
| B2-02 | `DUPLICATE_BLOCKED` ≠ 기대값 `RECONCILIATION_REQUIRED_BLOCKED` | `read_state()`가 먼저 `IN_PROGRESS`→`UNKNOWN` 전이를 수행한 뒤 `try_create()`가 호출되면, 이미 `UNKNOWN`으로 바뀐 "살아있는" 행을 만나 일반 `DUPLICATE_BLOCKED` 경로로 빠짐(호출 순서 의존성) | `try_create()`를 우선순위 기반으로 재작성 — 원시 state가 `IN_PROGRESS`로 만료됐든, 이미 `UNKNOWN`으로 전이됐든 48시간 이내면 **항상** `RECONCILIATION_REQUIRED_BLOCKED` 반환하도록 통일. 경로 A/B 양쪽을 검증하는 테스트 추가(§5) |
| B2-09a/09b | `nonces=5 != 기대값 4` | 테스트가 "총 요청 수"와 "재시도 횟수"를 혼동 — 계획서 §7 B2-09 측정값 칸은 "요청 수"와 "retry 수"를 구분하므로 최초 1회 + 재시도 4회 = 5가 맞는 값이었음 | `_run_retry_convergence()`에 `initial_request_count`/`retry_count`/`total_request_count`를 분리 도입하고, 테스트 기대값을 계획서 정의(총 요청 = 최초+재시도)에 맞춰 수정 |
| B2-12 | `UnicodeEncodeError: 'cp949' codec can't encode character '—'` | Windows 콘솔 기본 코드페이지(cp949)가 요약 `print()` 안의 em dash(—)를 인코딩하지 못함 | 해당 `print()`를 ASCII 전용 문자열로 재작성, 검증 assert를 `print()`보다 먼저 수행하도록 순서 변경, `sys.stdout`/`sys.stderr` UTF-8 `reconfigure()` 방어 코드 추가 |

**2차 실행**(candidate SHA-256 `6db18c2a8c44e4741116b631d78b82287273b26dcbdc7eb3fee13b99b320ea7e`, `python3 -X utf8 -m unittest -v`, 종료코드 0): `Ran 15 tests in 10.285s`, `OK` — 15/15 전부 PASS(§3~§7).

두 실행 모두 실제 stdout/stderr 전문이 로그로 보존되어 있다(§13 증적 참조).

## 9. 정책 미확정(POLICY UNRESOLVED) 4개 상태 — 관측 결과

SUCCEEDED/FAILED_RETRYABLE/FAILED_FINAL/UNKNOWN의 만료 후 전이 대상은 ADR-017 §14/§16/§23 어디에도 명시되어 있지 않다. 이 harness는 그 불확실성을 추측으로 메우지 않고, `try_create()`가 이 4개 상태의 만료 행에 대해 **어떤 조치도 취하지 않음**을 실측으로 확인했다(로그 원문):

```
[policy-unresolved] state=SUCCEEDED try_create_result=('POLICY_UNRESOLVED_BLOCKED', 'SUCCEEDED') row_count_for_key=1 raw_state_after=SUCCEEDED
[policy-unresolved] state=FAILED_RETRYABLE try_create_result=('POLICY_UNRESOLVED_BLOCKED', 'FAILED_RETRYABLE') row_count_for_key=1 raw_state_after=FAILED_RETRYABLE
[policy-unresolved] state=FAILED_FINAL try_create_result=('POLICY_UNRESOLVED_BLOCKED', 'FAILED_FINAL') row_count_for_key=1 raw_state_after=FAILED_FINAL
[policy-unresolved] state=UNKNOWN try_create_result=('POLICY_UNRESOLVED_BLOCKED', 'UNKNOWN') row_count_for_key=1 raw_state_after=UNKNOWN
```

4개 상태 전부 삭제·재생성·state 변경 없이 보존되었다. **이것은 "운영 정책이 확정되었다"는 의미가 아니라, 이번 harness가 범위를 "TTL 경과 감지"로 제한하고 정책이 불명확한 영역에서는 아무 조치도 취하지 않도록 설계되었음이 실제로 지켜졌다는 의미일 뿐이다.** 4개 상태의 올바른 만료 후 운영 정책은 여전히 PM/ADR 확인이 필요한 **POLICY UNRESOLVED** 항목으로 남는다.

## 10. 반드시 구분할 한계

- **실측 트래픽·재시도 패턴 데이터가 없다.** 이 harness의 모든 key·nonce·재시도 패턴은 `dr-b-02-<uuid>` 형식의 synthetic 값이며, 실제 운영자 재시도 행동이나 실제 요청 분포를 관측·재현한 것이 아니다.
- **이 결과를 Production RPS·성능·확장성 추정에 사용할 수 없다.** elapsed/throughput/latency는 로컬 단일 프로세스(`ThreadPoolExecutor`)의 관측값일 뿐이며, 실제 다중 서버·다중 프로세스 환경의 경합이나 네트워크 왕복을 전혀 포함하지 않는다.
- B2-10(burst)·B2-09(재시도)는 합성 패턴이며 실측 운영 트래픽이 아니다.
- injectable 가상 Clock 기반 검증은 실제 시스템 시계 드리프트·서버 재시작 등 운영 환경의 시간 관련 이상 상황을 재현하지 않는다.
- **이 실행 결과는 Production Idempotency 저장 로직의 구현 완료, Commit8-3b 착수 승인, G6(Final Validation) 통과, 또는 Production 배포 승인을 의미하지 않는다.**
- 4개 상태(SUCCEEDED/FAILED_RETRYABLE/FAILED_FINAL/UNKNOWN)의 만료 후 운영 정책은 이 실행으로 확정되지 않았다(§9).
- 임시 리소스 잔존: 2회 실행 전부 사후 확인 결과 OS 임시 디렉터리에 `cshsp_pre_g1_*` 패턴의 잔존 파일·디렉터리 **0건**.
- 외부 네트워크·운영 GAS·Google Sheets 접근: 설계·실행 양쪽 모두 **없음**(표준 라이브러리만 사용, 로컬 SQLite만 생성).

## 11. PoC#1~#3·계획서·G6·Commit8-3b와의 관계

이 Phase 1 결과는 PoC#1(SQLite 원자성, PASS, `6ffc5cf`)·PoC#2(GAS CacheService, PASS WITH CONDITIONS, `b97d2ed`)·PoC#3(Nonce 이중저장소 Fail-Closed, PASS, `6652ee8`)과 독립적으로 수행되었으나, PoC#1의 `ThreadPoolExecutor`+`Barrier` 동시성 패턴과 PoC#3의 이원 판정(기술 검증 vs 정책 확정 분리) 원칙을 그대로 계승한다. G6(Final Validation)은 Commit8-3b 정식 통합 구현 완료 후에만 진입하며 이 Phase 1과는 별개의 Gate다(계획서 §4, §13; Gate Plan §32). 이 결과는 Commit8-3b 정식 착수 승인이나 G6 통과를 대체하지 않는다.

## 12. 최종 판정

### 12.1 A. HARNESS TECHNICAL RESULT

**PASS — LOCAL SYNTHETIC ONLY**

B2-01~B2-12 전 시나리오(B2-09는 양쪽 수렴 경로 포함 15개 `test_` 메서드)가 2차 실행에서 설계된 예상 결과와 일치했고(§3~§7), 3회 반복 간 결과 편차 0건, cleanup 전부 성공(§7), 임시 리소스 잔존 0건(§10)을 확인했다. 단, 이 PASS는 **로컬 합성(synthetic) 데이터 기반 harness의 기술적 동작 검증 결과일 뿐**이며, Production 적합성·실측 트래픽 기반 검증을 의미하지 않는다(§10 한계 재확인).

### 12.2 B. OFFICIAL PHASE 1 GATE

**BLOCKED INPUT**(변동 없음)

계획서 §4·§5·§9.2가 명시한 대로, 실측 트래픽·재시도 패턴 데이터가 저장소에 존재하지 않으므로 A의 결과(PASS)와 **무관하게** BLOCKED INPUT으로 고정된다. BLOCKED INPUT이 "완료"로 전환되려면 (a) A가 PASS 또는 PASS WITH CONDITIONS이고(충족), (b) 이 harness 결과와는 별도로 실측 데이터(운영자 재시도 행동 패턴 등)가 PM/실행자에 의해 확보되어야 한다(계획서 §9.2). 이 문서는 (b)를 스스로 생성하지 않는다.

## 13. 증적(실행 로그)

- 1차 실행 원본 로그(FAIL, 2026-10-02, candidate SHA-256 `9ee266af...`): 저장소 밖 scratchpad에 원본 그대로 보존(cp949 인코딩, 109줄). 저장소에는 반영하지 않는다.
- 2차 실행 원본 로그(PASS, 2026-10-02, candidate SHA-256 `6db18c2a...`): 저장소 밖 scratchpad에 원본 그대로 보존(UTF-8 인코딩, 49줄). 저장소에는 반영하지 않는다.
- 두 로그의 절대 로컬 경로·사용자명을 `<SCRATCHPAD>`로 비식별화한 사본만 저장소에 반영했다(원본은 수정하지 않음, 내용은 경로 치환 외 동일 — 줄 수 일치로 확인):
  - [tests/pre_g1/dr_b_02_phase1_run1_fail_log_sanitized.txt](../tests/pre_g1/dr_b_02_phase1_run1_fail_log_sanitized.txt) — SHA-256 `cd497386f861b96c7f5970e0454573d66b8bf170f4ea97e375935e1c2ed33bf5`
  - [tests/pre_g1/dr_b_02_phase1_run2_pass_log_sanitized.txt](../tests/pre_g1/dr_b_02_phase1_run2_pass_log_sanitized.txt) — SHA-256 `0ab3646616355592d67d6317b4cd8215012e724abac9d84767cd3e6db5d70e5a`

---

**완료 조건 준수 확인**: 이 문서 작성 중 harness를 추가로 실행하지 않았다(2차 실행 로그만 인용). GAS·Google Sheets·외부 네트워크에 접근하지 않았다. Production 코드나 기존 SSOT 문서를 수정하지 않았다(PROJECT_STATUS.md 수정은 별도 candidate로 작성해 이 문서와 분리했다). 실제 계정·Secret·Token·PII·운영 URL을 포함하지 않았다. 실측 데이터가 없다는 사실을 과장 없이 BLOCKED INPUT으로 명시했으며 Production RPS·성능·배포 승인을 입증한다고 표현하지 않았다. Git add/commit/push를 수행하지 않았다.
