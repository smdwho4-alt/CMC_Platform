# -*- coding: utf-8 -*-
"""
Sprint8 DR-B-02 Phase 1 — Idempotency TTL 예비 부하검증(Preliminary Validation) harness CANDIDATE (v4)

**이 파일은 candidate(초안) v4이며 아직 실행되지 않았다.** 저장소 밖 scratchpad에만
존재하고 CMC_Platform_new 저장소(cadf055 기준)에는 포함되지 않는다. git add/commit/
push 대상이 아니다.
- v1(SHA-256 8707ae878c7e650aa9434d6befc8818c37788f7bc4414c1a35a3c081126ebc0c):
  최초 candidate.
- v2(SHA-256 f28ab54d0c0a4bd00f57c8b5dc05ac9b4c35de83cd178430db1aad6e52d63dfa):
  v1 정적검증에서 발견된 §8 측정항목 미구현·B2-12 범위 축소·B2-09 수렴경로 편중을
  보완. 단, "정책 불명확/충돌" 서술이 저장소 1차 조사만으로 부정확했다.
- v3(SHA-256 02e5e2fa00ebd8b681cf083d91536094671d93dbf82ec69916c8104ef1e53e72):
  ADR-017 13/14/16/23절과 Gate Plan IDEM-03을 추가로 대조해 v2의 정책 서술을
  교정(IN_PROGRESS는 "불명확"이 아니라 **명시 정책과 상충** — POLICY
  CONTRADICTED로 재분류, 단 코드는 아직 고치지 않고 진단만 함). B2-12에 B2-09
  FAILED_FINAL 경로 누락분을 보완.
- v4(이 파일): (1) try_create()/read_state()를 실제로 ADR-017 14/16/23절에
  맞게 수정 — IN_PROGRESS 만료 시 삭제·재생성이 아니라 UNKNOWN으로 전이하고
  자동 재실행을 차단한다(POLICY CONTRADICTED를 코드 수정으로 해소). 나머지
  4개 상태(SUCCEEDED/FAILED_RETRYABLE/FAILED_FINAL/UNKNOWN)의 만료 후 삭제·
  재생성을 가정하던 코드는 전부 제거하고, "POLICY_UNRESOLVED_BLOCKED"를
  반환해 어떤 조치도 취하지 않도록 했다(정책 확정이 아니라 검증 범위 제한).
  (2) B2-12에 latency/throughput 관측값을 되돌림 — "§7 B2-12 행에 없다"는
  이유만으로 §8 적용 제외가 확정된다고 단정하지 않는다는 지적을 반영.
  (3) TTL 경계 테스트(PASS)와 만료 후 정책(POLICY FOUND/UNRESOLVED 구분)을
  별도 어서션으로 분리했다.

대응 계획서:
  docs/Sprint8_DR_B_02_Phase1_Idempotency_TTL_Preliminary_Load_Test_Plan.md (B2-01~B2-12)

## 가상시계(Clock) vs 실시계(perf_counter) 구분
- `Clock`(가상시계): TTL 만료 판정에만 쓰는 injectable 시계. `advance(seconds)`로만
  전진하며 실제 대기를 하지 않는다(48시간도 숫자 연산일 뿐). effective_state()/
  try_create()/transition_state()의 `now` 인자는 전부 이 가상시계 값이다.
- `time.perf_counter()`(실시계): §8이 요구하는 elapsed time·latency·throughput
  측정에만 쓰는 실제 벽시계. TTL 판정 로직에는 전혀 관여하지 않는다.
  이 둘은 완전히 분리되어 있으며 서로의 값을 공유하지 않는다.

## §8 성능 관측값 설계(세부 계산식은 _percentile/_latency_stats/_throughput 참조)
- 측정 대상: "harness 내부 함수 호출 1회"의 실제 경과시간(`time.perf_counter()`
  전/후 차이). 네트워크 왕복 없음(§8 원문 그대로).
- 단위: 초(sec). 출력 시 elapsed_sec는 소수점 6자리로 표기.
- 백분위수 계산법: 선형보간(linear interpolation, k=(n-1)*p 인덱스의 인접 두
  순위값을 보간). 표본이 극히 적은 시나리오(B2-02~06 n=3, B2-09 n=RETRY_ATTEMPTS)
  에서는 백분위수의 통계적 의미가 제한적임을 결과 해석 시 감안해야 하며, 이
  harness는 그 사실을 합격기준으로 쓰지 않는다.
- throughput 분모: "배치로 동시 제출된 요청 수" ÷ "배치 전체의 실제 벽시계
  경과시간"(개별 latency의 합이 아님). 분자는 성공 건수가 아니라 제출된 전체
  요청 수다. 로컬 관측값일 뿐 Production 처리량 추정치가 아니다(§8, §12).
- B2-01은 상수 비교일 뿐 I/O가 없어 latency/throughput 측정 대상에서 제외한다
  (의도적 범위 축소, 추측으로 메우지 않음).
- B2-12에도 §8 공통 측정값(elapsed time·latency·throughput)을 적용한다(v4,
  정정). v3에서는 "§7 표의 B2-12 행 측정값 칸에 elapsed/throughput이 없다"는
  이유로 제외했으나, §8이 "§7 표의 측정값 열 공통 정의"라고 명시한 이상 그
  칸에 없다는 사실 하나만으로 §8 적용 자체가 배제된다고 단정할 근거는 아니다.
  v4는 B2-02~10 하위패턴에서 이미 수집하던 latency(_timed_try_create,
  _run_retry_convergence의 latencies)를 그대로 재사용해 REPEAT_COUNT회 전체
  반복의 elapsed time(`time.perf_counter()` 기준)과 집계 latency/throughput을
  관측값으로만 출력한다(assert 대상 아님). 단, 반복 간 '결과 편차' PASS 판정
  (outcome 딕셔너리)에는 latency를 포함하지 않는다 — 실행시간은 반복마다
  자연히 달라지므로, 이를 편차 판정에 넣으면 타이밍 변동만으로 거짓 FAIL이
  발생할 수 있기 때문이다(§7 B2-12 행의 "반복 간 결과 편차"는 결정론적 분류
  결과를 뜻하는 것으로 해석).
- 계획서에 없는 성능 합격 기준(예: "p95 < N초")은 추가하지 않았다. 이 harness는
  latency/throughput을 관측·출력만 하며 assert 대상으로 쓰지 않는다.

## 정책 확인 결과(저장소 실측 조사, v2의 "정책 불명확/충돌" 서술을 교정함)
파일: ADR-017_FastAPI_Proxy_and_Signed_GAS_Operations.md(저장소 루트, 이 harness
파일과 별개의 기존 문서, 수정하지 않음).

1. IN_PROGRESS 만료 후 전이 대상은 명시적으로 확정되어 있다(POLICY FOUND).
   14절 표(111행) IN_PROGRESS 행 원문: "TTL 경과 후 만료삭제가 아니라 자동으로
   UNKNOWN/RECONCILIATION_REQUIRED로 전이". 23절(161행) 원문: "UNKNOWN/
   RECONCILIATION_REQUIRED는 자동 재실행을 절대 금지하고, 운영자의 Sheets
   직접 확인 후 수동으로 SUCCEEDED 또는 FAILED_FINAL로 전이시킨다(14절)."
   16절(125행)도 동일 원칙을 재시도 정책 맥락에서 재확인한다.
   docs/Sprint8_Security_Test_and_Deployment_Gate_Plan.md의 IDEM-03(318행)도
   "UNKNOWN/RECONCILIATION_REQUIRED 전이"를 테스트 항목으로 명시한다.
   -> v3까지의 candidate는 EXPIRED로 판정된 행을 삭제 후 즉시 새 IN_PROGRESS로
   재생성해 위 명시 정책과 상충했다(POLICY CONTRADICTED). **v4에서 코드를
   수정해 해소했다**: try_create()/read_state()가 이제 IN_PROGRESS 만료를
   감지하면 UNKNOWN으로 전이시키고(삭제 아님, `_auto_transition_in_progress_
   if_expired`) 자동 재실행을 차단한다(`RECONCILIATION_REQUIRED_BLOCKED`,
   CREATED 아님). `test_b2_02_in_progress_ttl_boundary`가 전이·레코드 보존·
   재실행 차단을 함께 검증한다 — 이 부분은 이제 POLICY FOUND + 코드 일치로
   정상 PASS 대상이다.

2. SUCCEEDED/FAILED_RETRYABLE/FAILED_FINAL의 만료 후 전이 대상은 어디에도
   명시되어 있지 않다(POLICY UNRESOLVED). 14절 표의 해당 3개 행은 TTL 설정
   취지만 설명할 뿐("응답유실 후 운영자가 화면 재확인·복귀하는 현실적 시간",
   "Nonce TTL과 동일하게 맞춤, 재시도는 새 Nonce로(16절)", "동일 키 재문의 시
   일관된 실패결과 반환") 만료 후 무엇으로 전이하는지는 14·16·23절 어디에도
   없다. 계획서 7절 표가 B2-03~06에 "상동"(B2-02와 동일 문구 "UNKNOWN/
   RECONCILIATION 후보 전이")을 재사용하는 것은 ADR 원문이 아니라 계획서
   저자의 재인용 관행이며, ADR-017은 이 3개 상태에 대해 그런 전이를 확정한
   적이 없다.

3. UNKNOWN 자신의 48시간 TTL이 "만료된 이후" 무엇이 되는지도 명시되어
   있지 않다(POLICY UNRESOLVED). 14절은 UNKNOWN을 "별도 상태로 보존"하며
   "자동 재실행하지 않고 조회·운영 확인 절차와 연결"한다고만 할 뿐, 48시간
   경과 후 삭제되는지·에스컬레이션되는지는 기술하지 않는다.

4. Nonce 저장소 Fail-Closed 원칙(13절)과 Idempotency TTL 정책(14절)은 서로
   다른 대상에 적용되므로 직접 비교할 수 없다(1차 보고의 비교가 부정확했음을
   교정). 13절(98행) 원문: "저장 실패 시 Fail-Closed(양쪽 저장소 중 어느
   한쪽이라도 기록에 실패하면 해당 요청을 진행하지 않음)" — 이는 Nonce
   발급 시점의 이중 저장소(FastAPI SQLite + GAS CacheService) "쓰기 실패"
   라는 좁은 대상에 적용되는 원칙이며, PoC#3(3절 재인용)이 검증한 것도 바로
   이 쓰기실패/불일치 시나리오다. 반면 이 harness의 Idempotency TTL 만료는
   이미 성공적으로 기록된 단일 FastAPI측 Idempotency 레코드의 시간 경과에
   따른 상태 전이 문제로, 저장소 구조·장애 시나리오·관련 ADR 절이 전혀
   다르다. 올바른 비교 대상은 13절이 아니라 14/16/23절이며, 위 1~3이 그
   결과다. "PoC#3의 Fail-Closed 원칙과 상충한다"던 v2 표현은 철회한다.

## POLICY CONTRADICTED(해소됨)/UNRESOLVED(여전히 유지) 처리 방식 — v4
- **IN_PROGRESS(POLICY CONTRADICTED → v4에서 코드 수정으로 해소)**: v3까지
  존재하던 `_policy_unresolved_demo_expired_row_recreation`(현재 구현이
  ADR과 상충함을 보여주던 진단 코드)은 **삭제했다** — 상충 자체가 더 이상
  존재하지 않기 때문이다. 대신 `test_b2_02_in_progress_ttl_boundary`가 (a)
  TTL 경계 감지(before/boundary/after=UNKNOWN 전이)와 (b) 전이 후 레코드
  보존 + try_create() 자동 재실행 차단(RECONCILIATION_REQUIRED_BLOCKED)을
  **구분된 두 블록**으로 모두 검증하는 정식 `test_` 메서드다(모두 합격
  집계에 포함되는 정상 PASS 대상).
- **SUCCEEDED/FAILED_RETRYABLE/FAILED_FINAL/UNKNOWN(POLICY UNRESOLVED,
  그대로 유지)**: 이 4개 상태의 만료 후 전이 대상은 여전히 ADR 어디에도
  없다. v4는 이 불확실성을 추측으로 메우는 대신, try_create()가 이 4개
  상태의 만료 행에 대해 **어떤 조치도 취하지 않도록**(POLICY_UNRESOLVED_
  BLOCKED, 삭제·재생성·state 변경 전부 없음) 코드를 수정했다. 이 "아무 것도
  하지 않음"이 실제로 지켜지는지는 `test_policy_unresolved_states_block_
  without_mutation`이 검증한다 — 이는 "운영 정책이 X로 확정되었다"가 아니라
  "이번 harness가 범위를 TTL 감지로 제한하기로 한 설계가 실제로 지켜진다"는
  것만 확인하는 테스트이므로, 정상 `test_` 메서드로 두고 합격 집계에
  포함한다. **최종 결과 해석 시 구분할 것**: TTL 경계 감지(B2-02~06의
  before/boundary/after) PASS ≠ "만료 후 올바른 정책이 무엇인지 확정됨".
  후자는 4개 상태 모두에 대해 여전히 PM/ADR 확인이 필요한 POLICY UNRESOLVED
  항목이다.

## 제외 범위(계획서 §12 재확인, 변경 없음)
실제 Production RPS·성능·확장성·TTL 적합성, 외부 부하도구, 실제 48시간 대기,
Canonical String/HMAC Gap, GAS·Google Sheets 실접근, Phase 2(G6), TTL 최종
확정, Commit8-3b 착수 승인. Python 표준 라이브러리만 사용(os, sqlite3,
tempfile, threading, time, math, unittest, uuid, concurrent.futures,
pathlib, typing). 저장소의 다른 코드를 import하지 않는다. 모든 key/nonce는
`dr-b-02-<uuid>` synthetic 값만 사용. GAS·Google Sheets·외부 네트워크 접근 없음.

## 판정(계획서 §9 재확인, 이 파일 자체는 판정을 내리지 않는다)
A. HARNESS TECHNICAL RESULT — 이 harness를 실행한 뒤 별도로 PASS/PASS WITH
   CONDITIONS/FAIL 판정.
B. OFFICIAL PHASE 1 GATE — 이 harness 결과와 무관하게 **BLOCKED INPUT**으로
   고정(계획서 §4, §5, §9.2). 이 파일의 실행 결과만으로 BLOCKED INPUT을
   해소하지 않는다.
"""
from __future__ import annotations

import math
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

# 1차 실행(run log 참고)에서 Windows 콘솔 기본 코드페이지(cp949)가 일부 특수
# 유니코드 문자(예: em dash)를 인코딩하지 못해 UnicodeEncodeError가 발생했다.
# 다음 실행을 대비해 stdout/stderr를 UTF-8로 재설정한다(가능한 경우에만,
# 실패해도 harness 동작 자체를 막지 않음). 이것과는 별개로 item 3에 따라
# 문제가 됐던 B2-12 요약 print 자체도 ASCII 전용 문자열로 바꿨다(이중 방어).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

# --- PROPOSED TTL 매핑(계획서 §5 원문 재인용, 구현 확정값 아님) -------------------
TTL_SECONDS = {
    "IN_PROGRESS": 60,
    "SUCCEEDED": 900,
    "FAILED_RETRYABLE": 300,
    "FAILED_FINAL": 900,
    "UNKNOWN": 172800,  # 48시간
}

# --- harness 설정값(이번 합성 예비검증에 사용, 운영 기준 아님. PM 지정값) -----------
WORKER_COUNT = 8                 # B2-07/08/12: PoC#1과 동일 보수적 값 재사용
BURST_COUNT = 30                 # B2-10/12
RETRY_ATTEMPTS = 4               # B2-09a/09b/12
GUARD_MAX_PROCESSED = 3          # B2-11
GUARD_TOTAL_REQUESTED = 10       # B2-11
REPEAT_COUNT = 3                 # B2-12

JOURNAL_MODE = "WAL"             # PoC#1과 동일 관행
BUSY_TIMEOUT_MS = 5000

_SCHEMA_SQL = """
CREATE TABLE idempotency_store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    nonce TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    UNIQUE(key)
);
"""


class Clock:
    """injectable 가상시계. 고정 시각에서 시작하며 advance(seconds)로만 전진한다.
    time.sleep()을 사용하지 않는다(계획서 §6). 성능 측정용 실시계(perf_counter)와는
    완전히 분리된 별개의 값이다."""

    def __init__(self, start: float = 0.0):
        self._now = float(start)

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> float:
        self._now += float(seconds)
        return self._now


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=BUSY_TIMEOUT_MS / 1000.0, isolation_level=None)
    conn.execute(f"PRAGMA journal_mode={JOURNAL_MODE}")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return conn


def _synthetic_key() -> str:
    return f"dr-b-02-{uuid.uuid4()}"


def _synthetic_nonce() -> str:
    return f"dr-b-02-{uuid.uuid4()}"


def effective_state(state: str, updated_at: float, now: float) -> str:
    """상태→TTL 매핑(TTL_SECONDS)과 updated_at 기준 경과시간(가상시계)으로 논리
    상태를 계산한다. elapsed <= TTL 이면 저장된 state 그대로("경계"는 유효로
    관측), elapsed > TTL이면 "EXPIRED"를 반환한다. "EXPIRED"는 5개 명명 상태 중
    하나가 아니라 이 harness가 도입한 중립 레이블이다(모듈 docstring "정책
    불명확" §1~2 참조 — 계획서가 만료 후 구체적 전이 대상을 확정하지 않음).
    DB를 변경하지 않는 read-time 판정(lazy expiry)이다."""
    ttl = TTL_SECONDS[state]
    elapsed = now - updated_at
    if elapsed <= ttl:
        return state
    return "EXPIRED"  # 명명 상태 아님 — 모듈 docstring "정책 확인 결과" §2/§3 참조(UNRESOLVED)


def seed_row(db_path: Path, key: str, state: str, at_time: float, worker_id: str = "seed") -> None:
    """B2-02~B2-06용 테스트 스캐폴딩: 지정 상태의 행을 직접 적재한다."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO idempotency_store (key, state, created_at, updated_at, nonce, worker_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (key, state, at_time, at_time, _synthetic_nonce(), worker_id),
        )
    finally:
        conn.close()


def _auto_transition_in_progress_if_expired(db_path: Path, key: str, now: float) -> None:
    """ADR-017 14/16/23절 원문대로, IN_PROGRESS 행이 TTL(60초)을 초과하면
    자동으로 state='UNKNOWN'으로 전이시킨다(삭제가 아니라 보존 + 상태전이).
    updated_at을 전이 시각(now)으로 갱신해 UNKNOWN의 48시간 TTL이 이 시점부터
    새로 계산되게 한다. 대상 행이 없거나 state가 IN_PROGRESS가 아니거나 아직
    만료되지 않았으면 아무 것도 하지 않는다(no-op). 다른 4개 상태(SUCCEEDED/
    FAILED_RETRYABLE/FAILED_FINAL/UNKNOWN)의 만료 후 전이 대상은 ADR 어디에도
    명시되어 있지 않으므로(POLICY UNRESOLVED) 이 함수는 그 상태들에는 관여하지
    않는다 — 이는 운영 정책을 확정하는 것이 아니라 이번 검증 범위를 "ADR이
    명시한 것만 구현"으로 제한한 것이다."""
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT state, updated_at FROM idempotency_store WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            return
        state, updated_at = row
        if state != "IN_PROGRESS" or (now - updated_at) <= TTL_SECONDS["IN_PROGRESS"]:
            conn.execute("ROLLBACK")
            return
        conn.execute(
            "UPDATE idempotency_store SET state = 'UNKNOWN', updated_at = ? WHERE key = ?",
            (now, key),
        )
        conn.execute("COMMIT")
    finally:
        conn.close()


def read_state(db_path: Path, key: str, now: float) -> str:
    """조회 시 IN_PROGRESS 만료를 감지하면 ADR-017 14/16/23절대로 자동으로
    UNKNOWN으로 전이시킨다(부작용 있음 — 삭제 아님, 명시 정책을 따른 상태전이,
    `_auto_transition_in_progress_if_expired` 참조). 다른 4개 상태의 만료는
    전이 대상이 ADR에 명시되어 있지 않으므로(POLICY UNRESOLVED) 상태를
    변경하지 않고 중립 레이블 'EXPIRED'만 반환한다(lazy, read-only)."""
    _auto_transition_in_progress_if_expired(db_path, key, now)
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT state, updated_at FROM idempotency_store WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return "ABSENT"
        state, updated_at = row
        return effective_state(state, updated_at, now)
    finally:
        conn.close()


def try_create(
    db_path: Path,
    key: str,
    worker_id: str,
    now: float,
    barrier: Optional[threading.Barrier] = None,
) -> tuple[str, str]:
    """동일 key에 대한 생성 시도. **기존 행이 전혀 없는 경우에만** 새 IN_PROGRESS
    행을 생성한다(1회만 시도, 무한 retry 없음). BEGIN IMMEDIATE로 PoC#1과 동일
    하게 원자성을 확보한다.

    POLICY 반영 — 분류 우선순위(모듈 docstring "정책 확인 결과" 참조, v5에서
    "UNKNOWN은 생성 경위·호출 순서와 무관하게 동일 분류" 요구사항 반영):

    1. 기존 행의 원시 state가 "IN_PROGRESS"이고 IN_PROGRESS TTL(60초)이
       지났으면 — 아직 read_state() 등으로 UNKNOWN 전이가 일어나지 않은
       "날것" 상태라도 — 이 자리에서 즉시 UNKNOWN으로 전이시키고(삭제 아님)
       "RECONCILIATION_REQUIRED_BLOCKED"를 반환한다(ADR-017 14/16/23절).
    2. 기존 행의 원시 state가 이미 "UNKNOWN"이면(read_state() 선행 호출로
       이미 전이됐거나, 테스트에서 직접 seed된 경우 등 생성 경위 무관) —
       그 UNKNOWN 자신의 48시간 TTL이 아직 지나지 않았으면 **동일하게**
       "RECONCILIATION_REQUIRED_BLOCKED"를 반환한다. §23 "자동 재실행
       절대 금지"는 전이 경로가 아니라 UNKNOWN이라는 상태 자체에 적용되는
       원칙이므로, 1번과 2번은 호출 순서와 무관하게 **항상 같은 결과**를
       낸다(item 1 요구사항 — v4까지는 1번 경로와 2번 경로가 서로 다른
       값(RECONCILIATION_REQUIRED_BLOCKED vs DUPLICATE_BLOCKED)을 반환해
       1차 실행에서 FAIL로 드러났다).
    3. 기존 행의 원시 state가 "UNKNOWN"이고 그 48시간 TTL마저 지났으면
       ("만료된 이후") 그 다음에 무엇을 해야 하는지 ADR 어디에도 없으므로
       (POLICY UNRESOLVED, 모듈 docstring 발견#3) "POLICY_UNRESOLVED_
       BLOCKED"를 반환한다 — 삭제·재생성·그 외 어떤 조치도 취하지 않는다.
    4. 기존 행이 SUCCEEDED/FAILED_RETRYABLE/FAILED_FINAL이고 아직 살아있으면
       "DUPLICATE_BLOCKED".
    5. 기존 행이 SUCCEEDED/FAILED_RETRYABLE/FAILED_FINAL이고 TTL이 지났으면,
       만료 후 전이 대상이 ADR 어디에도 없으므로(POLICY UNRESOLVED, 발견#2)
       3번과 동일하게 "POLICY_UNRESOLVED_BLOCKED"를 반환한다(삭제·재생성
       없음 — 운영 정책 확정이 아니라 이번 검증 범위를 TTL 감지로 제한).
    6. 기존 행이 전혀 없으면 새로 생성("CREATED").

    반환: (결과분류, 상세) — CREATED / DUPLICATE_BLOCKED /
    RECONCILIATION_REQUIRED_BLOCKED / POLICY_UNRESOLVED_BLOCKED /
    UNIQUE_RACE / LOCKED / OTHER 중 하나."""
    conn = _connect(db_path)
    try:
        if barrier is not None:
            barrier.wait()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT state, updated_at FROM idempotency_store WHERE key = ?", (key,)
            ).fetchone()
            if row is not None:
                state, updated_at = row
                # 우선순위 1: IN_PROGRESS가 아직 원시 상태로 만료된 경우 —
                # 지금 이 자리에서 UNKNOWN으로 전이시킨다.
                if state == "IN_PROGRESS" and effective_state(state, updated_at, now) == "EXPIRED":
                    conn.execute(
                        "UPDATE idempotency_store SET state = 'UNKNOWN', updated_at = ? WHERE key = ?",
                        (now, key),
                    )
                    conn.execute("COMMIT")
                    return ("RECONCILIATION_REQUIRED_BLOCKED", "UNKNOWN")
                # 우선순위 2/3: 이미 UNKNOWN인 경우 — 48시간 이내면 항상
                # RECONCILIATION_REQUIRED_BLOCKED(호출 순서 무관, 우선순위 1과
                # 동일 결과). 48시간마저 지났으면 POLICY UNRESOLVED.
                if state == "UNKNOWN":
                    conn.execute("ROLLBACK")
                    if effective_state(state, updated_at, now) == "UNKNOWN":
                        return ("RECONCILIATION_REQUIRED_BLOCKED", "UNKNOWN")
                    return ("POLICY_UNRESOLVED_BLOCKED", "UNKNOWN")
                # 우선순위 4/5: 나머지 3개 상태(SUCCEEDED/FAILED_RETRYABLE/
                # FAILED_FINAL) — 살아있으면 차단, 만료됐으면 POLICY UNRESOLVED.
                logical = effective_state(state, updated_at, now)
                if logical != "EXPIRED":
                    conn.execute("ROLLBACK")
                    return ("DUPLICATE_BLOCKED", logical)
                conn.execute("ROLLBACK")
                return ("POLICY_UNRESOLVED_BLOCKED", state)
            # 우선순위 6: 행이 전혀 없으면 새로 생성
            nonce = _synthetic_nonce()
            conn.execute(
                "INSERT INTO idempotency_store (key, state, created_at, updated_at, nonce, worker_id) "
                "VALUES (?, 'IN_PROGRESS', ?, ?, ?, ?)",
                (key, now, now, nonce, worker_id),
            )
            conn.execute("COMMIT")
            return ("CREATED", nonce)
        except sqlite3.IntegrityError as e:
            conn.execute("ROLLBACK")
            return ("UNIQUE_RACE", str(e))
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                return ("LOCKED", str(e))
            raise
    except Exception as e:  # noqa: BLE001 - 예상 밖 오류를 별도 분류
        return ("OTHER", f"{type(e).__name__}: {e}")
    finally:
        conn.close()


def transition_state(
    db_path: Path, key: str, new_state: str, now: float, nonce: Optional[str] = None
) -> None:
    """key의 상태(및 선택적으로 nonce)를 갱신한다. UPDATE만 수행하므로 구조적으로
    새 key를 만들거나 다른 key로 바꿀 수 없다(동일 key 유지가 SQL 구조로 보장됨)."""
    conn = _connect(db_path)
    try:
        if nonce is not None:
            conn.execute(
                "UPDATE idempotency_store SET state = ?, updated_at = ?, nonce = ? WHERE key = ?",
                (new_state, now, nonce, key),
            )
        else:
            conn.execute(
                "UPDATE idempotency_store SET state = ?, updated_at = ? WHERE key = ?",
                (new_state, now, key),
            )
    finally:
        conn.close()


def _count_rows(db_path: Path) -> int:
    """테이블 전체 행 수(여러 key가 섞여 있는 공유 DB에서 쓰임 — B2-12)."""
    conn = _connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM idempotency_store").fetchone()[0]
    finally:
        conn.close()


def _count_rows_for_key(db_path: Path, key: str) -> int:
    """특정 key에 대한 행 수(중복 행 방지 확인용 — B2-09a/09b)."""
    conn = _connect(db_path)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM idempotency_store WHERE key = ?", (key,)
        ).fetchone()[0]
    finally:
        conn.close()


def _raw_state(db_path: Path, key: str) -> str:
    """DB에 실제 저장된 state 컬럼 원본값(가공 없음). POLICY UNRESOLVED 상태의
    행이 try_create() 호출 후에도 임의로 변경되지 않았는지 확인하는 용도
    (read_state()의 'EXPIRED' 같은 계산된 레이블과는 다름)."""
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT state FROM idempotency_store WHERE key = ?", (key,)).fetchone()
        return row[0] if row is not None else "ABSENT"
    finally:
        conn.close()


def _distinct_keys(db_path: Path) -> set[str]:
    conn = _connect(db_path)
    try:
        return {row[0] for row in conn.execute("SELECT key FROM idempotency_store")}
    finally:
        conn.close()


# --- §8 성능 관측값(실시계 perf_counter 기반, TTL 가상시계와 무관) ------------------


def _percentile(values, p: float):
    """선형보간(linear interpolation) 방식 백분위수. p는 0.0~1.0. 인덱스
    k=(n-1)*p의 인접한 두 순위값을 보간한다. 표본이 적을수록(B2-02~06 n=3 등)
    통계적 의미가 제한적임을 결과 해석 시 감안해야 하며, 이 harness는 그
    사실을 합격기준으로 쓰지 않는다."""
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def _latency_stats(latencies_sec):
    """latencies_sec: time.perf_counter() 차이값(초)의 리스트. 측정 대상은
    '개별 함수 호출 1회의 실제 벽시계 경과시간'(§8 "harness 내부 함수 호출
    기준, 실제 네트워크 왕복 없음"). 단위는 초(sec)."""
    if not latencies_sec:
        return {"count": 0, "min": None, "median": None, "p95": None, "max": None}
    return {
        "count": len(latencies_sec),
        "min": min(latencies_sec),
        "median": _percentile(latencies_sec, 0.5),
        "p95": _percentile(latencies_sec, 0.95),
        "max": max(latencies_sec),
    }


def _throughput(op_count: int, wall_elapsed_sec: Optional[float]):
    """throughput(ops/sec) = 배치로 제출된 요청 수(op_count, 성공 여부 무관) ÷
    배치 전체의 실제 벽시계 경과시간(wall_elapsed_sec, 개별 latency의 합이
    아님). 로컬 관측값일 뿐 Production 처리량 추정치가 아니다(§8, §12)."""
    if wall_elapsed_sec is None or wall_elapsed_sec <= 0:
        return None
    return op_count / wall_elapsed_sec


def _timed(fn, *args, **kwargs):
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    t1 = time.perf_counter()
    return result, (t1 - t0)


def _timed_try_create(db_path, key, worker_id, now, barrier=None):
    """동시성 시나리오(B2-07/08/10/12)에서 스레드 내부 개별 호출 latency를
    측정하기 위한 래퍼."""
    t0 = time.perf_counter()
    result = try_create(db_path, key, worker_id, now, barrier)
    t1 = time.perf_counter()
    return result, (t1 - t0)


def _run_retry_convergence(db_path: Path, terminal_state: str, retry_attempts: int) -> dict:
    """B2-09a/09b 공통 로직(assert 없음, 관측 데이터만 반환). 동일 idempotency
    key를 고정한 채 매 시도 새 synthetic nonce로 전이하다 terminal_state
    (SUCCEEDED 또는 FAILED_FINAL)로 수렴시킨다. row_counts는 "이 key에 대한"
    행 수만 집계한다(공유 DB에서도 올바르게 동작하도록 _count_rows_for_key
    사용 — B2-12에서 재사용되므로 전체 테이블 카운트를 쓰면 틀린 판정이 됨).
    동일 key 유지는 UPDATE 전용 SQL 구조로 보장되며(transition_state는 새
    key를 만들 수 없음), row_counts가 매 단계 1로 유지되는지로 간접 확인한다.

    요청 수 용어 정리(계획서 §7 B2-09 행 재확인, item 2 — v5):
    계획서 측정값 칸이 "요청 수, retry 수, ..."로 **구분**되어 있고, 입력
    프로파일 칸은 "FAILED_RETRYABLE 전이 후 새 nonce로 순차 재시도... 3~5회"
    라고 되어 있다 — 즉 "3~5회"는 "최초 요청"이 아니라 그 뒤의 "재시도" 횟수를
    가리킨다. 이 함수는 그 해석에 따라 retry_attempts(RETRY_ATTEMPTS)를
    "재시도 횟수"로 취급하며, 최초 요청 1회(try_create)를 별도로 센다:
      initial_request_count = 1
      retry_count           = retry_attempts  (마지막 1회=terminal_state 수렴 포함)
      total_request_count   = initial_request_count + retry_count
    예: RETRY_ATTEMPTS=4 -> 최초 1 + 재시도 4 = 총 5개 nonce(1차 실행에서
    관측된 값과 일치 — 1차 실행 FAIL은 "총 요청 수"를 "재시도 횟수"와 혼동한
    테스트 측 기대값 오류였다).

    **잔여 모호성(코드로 임의 결정하지 않고 명시)**: "3~5회"의 마지막 1회가
    terminal_state로의 수렴 시도 자체를 포함하는지(이 함수의 해석), 아니면
    FAILED_RETRYABLE로만 재시도하는 횟수이고 수렴 시도는 그 **다음에 별도로
    추가**되는 것인지(그렇다면 총 요청 수 = 1 + retry_attempts + 1) 계획서
    원문만으로는 완전히 확정되지 않는다. 이 함수는 전자(마지막 재시도가 곧
    수렴 시도)로 일관되게 구현했다."""
    clock = Clock(start=0.0)
    key = _synthetic_key()
    wall_t0 = time.perf_counter()
    created, lat0 = _timed(try_create, db_path, key, "w0", clock.now())
    latencies = [lat0]
    nonces_used = [created[1]]
    row_counts = [_count_rows_for_key(db_path, key)]
    initial_request_count = 1
    retry_count = 0
    for _ in range(retry_attempts - 1):
        clock.advance(1.0)  # 합성 간격(실측 아님), TTL(FAILED_RETRYABLE=300초)보다 훨씬 작음
        new_nonce = _synthetic_nonce()
        _, lat = _timed(transition_state, db_path, key, "FAILED_RETRYABLE", clock.now(), new_nonce)
        latencies.append(lat)
        nonces_used.append(new_nonce)
        row_counts.append(_count_rows_for_key(db_path, key))
        retry_count += 1
    clock.advance(1.0)
    final_nonce = _synthetic_nonce()
    _, lat_final = _timed(transition_state, db_path, key, terminal_state, clock.now(), final_nonce)
    latencies.append(lat_final)
    nonces_used.append(final_nonce)
    row_counts.append(_count_rows_for_key(db_path, key))
    retry_count += 1
    wall_t1 = time.perf_counter()
    return {
        "created_status": created[0],
        "key": key,
        "terminal_state": terminal_state,
        "final_now": clock.now(),
        "nonces_used": nonces_used,
        "row_counts": row_counts,
        "latencies": latencies,
        "wall_elapsed": wall_t1 - wall_t0,
        "initial_request_count": initial_request_count,
        "retry_count": retry_count,
        "total_request_count": initial_request_count + retry_count,
    }


def _run_full_scenario_suite(run_id: int):
    """B2-12 전용: B2-02~B2-10 핵심 패턴을 하나의 묶음으로 독립 실행한다(반복마다
    독립된 임시 SQLite DB·독립된 synthetic key·독립된 가상시계 사용, 반복 간
    데이터 공유 없음). 반환되는 outcome은 '결정론적 분류 결과'만 담아 반복 간
    편차 판정에 쓴다. latency는 별도로 수집해 4번째 반환값으로 내보낸다(§8
    공통 측정값을 B2-12에도 적용 — v3에서는 "§7 B2-12 행에 없다"는 이유만으로
    제외했으나, 그 이유만으로 §8 적용 자체가 배제된다고 단정할 근거는 아니어서
    v4에서 되돌림). outcome 자체에는 latency를 넣지 않아 반복 간 '결과 편차'
    판정(완전히 결정론적이어야 함)이 실행시간 변동 때문에 깨지지 않게 한다.

    B2-02~06(TTL 5상태)에 더해, IN_PROGRESS는 ADR-017 14/16/23절대로 전이 후
    자동 재실행 차단까지 포함한다(v4, item 1). B2-09는 SUCCEEDED와
    FAILED_FINAL 두 수렴 경로를 모두 포함한다."""
    tmpdir = tempfile.mkdtemp(prefix=f"cshsp_pre_g1_b_dr_b_02_rep{run_id}_")
    db_path = Path(tmpdir) / "dr_b_02_idempotency_repeat.db"
    conn = _connect(db_path)
    try:
        conn.executescript(_SCHEMA_SQL)
    finally:
        conn.close()

    outcome: dict = {}
    latencies: list = []

    # B2-02~B2-06 하위패턴: 5개 상태 전부 TTL 경계 확인(상태별 독립 key·독립 가상시계)
    for state, ttl in TTL_SECONDS.items():
        local_clock = Clock(start=0.0)
        key = _synthetic_key()
        seed_row(db_path, key, state, at_time=local_clock.now())
        local_clock.advance(ttl - 1)
        before, lat_b = _timed(read_state, db_path, key, local_clock.now())
        local_clock.advance(1)
        boundary, lat_bd = _timed(read_state, db_path, key, local_clock.now())
        local_clock.advance(1)
        after, lat_a = _timed(read_state, db_path, key, local_clock.now())
        latencies.extend([lat_b, lat_bd, lat_a])
        if state == "IN_PROGRESS":
            # ADR-017 14/16/23절: 전이 후 자동 재실행 차단·레코드 보존까지 확인
            retry_result, lat_r = _timed(
                try_create, db_path, key, f"rep{run_id}_retry", local_clock.now()
            )
            latencies.append(lat_r)
            outcome[f"ttl_{state}"] = (
                before,
                boundary,
                after,
                retry_result[0],
                _count_rows_for_key(db_path, key),
            )
        else:
            outcome[f"ttl_{state}"] = (before, boundary, after)

    # B2-07 하위패턴: 동일 key 동시생성
    key07 = _synthetic_key()
    barrier07 = threading.Barrier(WORKER_COUNT)
    with ThreadPoolExecutor(max_workers=WORKER_COUNT) as ex:
        futs = [
            ex.submit(_timed_try_create, db_path, key07, f"rep{run_id}w{i}", 0.0, barrier07)
            for i in range(WORKER_COUNT)
        ]
        raw07 = [f.result() for f in futs]
    results07 = [r[0][0] for r in raw07]
    latencies.extend(r[1] for r in raw07)
    outcome["b2_07"] = (
        results07.count("CREATED"),
        results07.count("DUPLICATE_BLOCKED"),
        results07.count("OTHER") + results07.count("UNIQUE_RACE"),
    )

    # B2-08 하위패턴: 서로 다른 key 동시생성, 교차오염 없음
    keys08 = [_synthetic_key() for _ in range(WORKER_COUNT)]
    barrier08 = threading.Barrier(WORKER_COUNT)
    with ThreadPoolExecutor(max_workers=WORKER_COUNT) as ex:
        futs = [
            ex.submit(_timed_try_create, db_path, keys08[i], f"rep{run_id}w{i}", 0.0, barrier08)
            for i in range(WORKER_COUNT)
        ]
        raw08 = [f.result() for f in futs]
    results08 = [r[0][0] for r in raw08]
    latencies.extend(r[1] for r in raw08)
    outcome["b2_08"] = (
        results08.count("CREATED"),
        len(_distinct_keys(db_path) & set(keys08)),
    )

    # B2-09 하위패턴: SUCCEEDED/FAILED_FINAL 두 수렴 경로 모두 포함(독립 key)
    data09_succeeded = _run_retry_convergence(
        db_path, terminal_state="SUCCEEDED", retry_attempts=RETRY_ATTEMPTS
    )
    data09_failed_final = _run_retry_convergence(
        db_path, terminal_state="FAILED_FINAL", retry_attempts=RETRY_ATTEMPTS
    )
    latencies.extend(data09_succeeded["latencies"])
    latencies.extend(data09_failed_final["latencies"])
    outcome["b2_09_succeeded"] = (
        len(set(data09_succeeded["nonces_used"])),
        all(rc == 1 for rc in data09_succeeded["row_counts"]),
        data09_succeeded["terminal_state"],
    )
    outcome["b2_09_failed_final"] = (
        len(set(data09_failed_final["nonces_used"])),
        all(rc == 1 for rc in data09_failed_final["row_counts"]),
        data09_failed_final["terminal_state"],
    )

    # B2-10 하위패턴: burst/retry-storm
    key10 = _synthetic_key()
    barrier10 = threading.Barrier(BURST_COUNT)
    with ThreadPoolExecutor(max_workers=BURST_COUNT) as ex:
        futs = [
            ex.submit(_timed_try_create, db_path, key10, f"rep{run_id}b{i}", 0.0, barrier10)
            for i in range(BURST_COUNT)
        ]
        raw10 = [f.result() for f in futs]
    results10 = [r[0][0] for r in raw10]
    latencies.extend(r[1] for r in raw10)
    outcome["b2_10"] = (
        results10.count("CREATED"),
        results10.count("DUPLICATE_BLOCKED"),
        results10.count("OTHER") + results10.count("UNIQUE_RACE"),
    )

    row_count_before_cleanup = _count_rows(db_path)

    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()
    os.rmdir(tmpdir)

    cleanup_verified = (
        not Path(str(db_path)).exists()
        and not Path(str(db_path) + "-wal").exists()
        and not Path(str(db_path) + "-shm").exists()
        and not Path(tmpdir).exists()
    )

    return outcome, row_count_before_cleanup, cleanup_verified, latencies


class DrB02Phase1IdempotencyTtl(unittest.TestCase):
    """B2-01~B2-12(B2-09는 09a/09b 두 수렴 경로로 분리). 각 테스트는 자체 임시
    SQLite DB와 가상 Clock을 생성·정리한다."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="cshsp_pre_g1_b_dr_b_02_")
        self.db_path = Path(self._tmpdir) / "dr_b_02_idempotency.db"
        conn = _connect(self.db_path)
        try:
            conn.executescript(_SCHEMA_SQL)
        finally:
            conn.close()
        self.clock = Clock(start=0.0)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(self.db_path) + suffix)
            if p.exists():
                p.unlink()
        os.rmdir(self._tmpdir)

    def _row_count(self) -> int:
        return _count_rows(self.db_path)

    # B2-01 ----------------------------------------------------------------
    def test_b2_01_state_ttl_mapping_unit_check(self):
        # I/O 없는 상수 비교이므로 latency/throughput 측정 대상에서 제외한다
        # (모듈 docstring "§8 성능 관측값 설계" 참조, 의도적 범위 설정).
        expected = {
            "IN_PROGRESS": 60,
            "SUCCEEDED": 900,
            "FAILED_RETRYABLE": 300,
            "FAILED_FINAL": 900,
            "UNKNOWN": 172800,
        }
        match_count = sum(1 for k, v in expected.items() if TTL_SECONDS.get(k) == v)
        print(f"[B2-01] match_count={match_count}/5 mapping={TTL_SECONDS}")
        self.assertEqual(match_count, 5, f"TTL 매핑 불일치: {TTL_SECONDS} != {expected}")
        self.assertEqual(set(TTL_SECONDS.keys()), set(expected.keys()))

    # B2-02~B2-06 공통 구현 ---------------------------------------------------
    def _assert_ttl_boundary(self, state: str, ttl: int, expected_after: str = "EXPIRED"):
        """expected_after: IN_PROGRESS는 ADR-017 14/16/23절대로 "UNKNOWN"으로
        실제 전이되므로 호출부에서 "UNKNOWN"을 넘긴다. 나머지 4개 상태는
        전이 대상이 ADR에 명시되어 있지 않으므로(POLICY UNRESOLVED) 기본값
        "EXPIRED"(중립 레이블, 상태 변경 없음)를 그대로 쓴다."""
        key = _synthetic_key()
        seed_row(self.db_path, key, state, at_time=self.clock.now())

        targets = [ttl - 1, ttl, ttl + 1]
        labels = ["before", "boundary", "after"]
        results = {}
        latencies = []
        for label, target in zip(labels, targets):
            delta = target - self.clock.now()
            self.clock.advance(delta)
            value, elapsed = _timed(read_state, self.db_path, key, self.clock.now())
            results[label] = value
            latencies.append(elapsed)
        stats = _latency_stats(latencies)
        print(
            f"[TTL={ttl}s state={state}] before={results['before']} boundary={results['boundary']} "
            f"after={results['after']} latency_sec(min/median/p95/max)="
            f"{stats['min']}/{stats['median']}/{stats['p95']}/{stats['max']} n={stats['count']}"
        )
        self.assertEqual(results["before"], state, "만료 전 시점에 원래 상태가 관측되지 않음")
        self.assertEqual(results["boundary"], state, "경계 시점(TTL초)에 정책값 그대로 관측되지 않음")
        self.assertEqual(
            results["after"], expected_after, f"만료 후 시점에 {expected_after}로 전이되지 않음"
        )
        if expected_after == "EXPIRED":
            self.assertNotIn(
                results["after"], TTL_SECONDS.keys(), "EXPIRED가 5개 명명 상태 중 하나와 혼동됨"
            )
        return key, results, stats

    def _assert_reconciliation_blocked(self, key: str, now: float, path_label: str):
        """경로 A/B 공통 검증: try_create() 호출이 UNKNOWN/CREATED=0/행 보존을
        만족하는지 확인한다(item 1 — 호출 순서와 무관하게 동일 결과여야 함)."""
        retry_result = try_create(self.db_path, key, "w_retry", now=now)
        row_count = self._row_count()
        state_after = read_state(self.db_path, key, now=now)
        print(
            f"[B2-02-path-{path_label}] retry_result={retry_result} "
            f"row_count={row_count} state_after={state_after}"
        )
        self.assertEqual(
            retry_result[0],
            "RECONCILIATION_REQUIRED_BLOCKED",
            f"경로{path_label}: try_create()가 자동 재실행을 차단하지 못함",
        )
        self.assertNotEqual(retry_result[0], "CREATED", f"경로{path_label}: CREATED=0이어야 함")
        self.assertEqual(row_count, 1, f"경로{path_label}: 기존 행이 보존되어야 함(삭제·재생성 없음)")
        self.assertEqual(state_after, "UNKNOWN", f"경로{path_label}: 최종 상태는 UNKNOWN으로 유지되어야 함")

    def test_b2_02_in_progress_ttl_boundary(self):
        """TTL 경계 검증(PASS 대상) + ADR-017 14/16/23절 정책 검증(POLICY
        FOUND)을 **구분해서** 수행한다: 앞부분은 순수 TTL 경과 감지, 뒷부분은
        경로 B(read_state() 선행 호출 → try_create())를 검증한다. 경로 A
        (read_state() 없이 try_create() 직접 호출)는 test_b2_02b가 별도로
        검증한다 — v5: 두 경로가 항상 동일한 결과(RECONCILIATION_REQUIRED_
        BLOCKED)를 내는지 확인(1차 실행에서 경로 간 불일치가 FAIL로 발견됨)."""
        key, results, _ = self._assert_ttl_boundary(
            "IN_PROGRESS", TTL_SECONDS["IN_PROGRESS"], expected_after="UNKNOWN"
        )
        # --- 여기까지: TTL 경과 감지 PASS(before/boundary/after=UNKNOWN 전이) ---
        # --- 여기부터: 경로 B(_assert_ttl_boundary가 이미 read_state()를 3회
        # 호출해 IN_PROGRESS->UNKNOWN 전이를 완료시킨 상태) ---
        self.assertEqual(self._row_count(), 1, "UNKNOWN 전이 후 레코드가 삭제됨(ADR 위반)")
        self._assert_reconciliation_blocked(key, self.clock.now(), path_label="B(read_state 선행)")

    def test_b2_02b_in_progress_direct_try_create_path_a(self):
        """경로 A: read_state()를 전혀 호출하지 않고, 아직 원시 state가
        'IN_PROGRESS'인 행에 대해 try_create()를 직접 호출한다. 경로 B
        (test_b2_02)와 동일하게 RECONCILIATION_REQUIRED_BLOCKED/CREATED=0/
        행 보존이 나와야 한다 — 호출 순서(read_state 선행 여부)에 따라 결과가
        달라지지 않음을 확인한다(item 1 요구사항, 1차 실행 FAIL의 근본원인)."""
        key = _synthetic_key()
        seed_row(self.db_path, key, "IN_PROGRESS", at_time=0.0)
        now = TTL_SECONDS["IN_PROGRESS"] + 1
        self._assert_reconciliation_blocked(key, now, path_label="A(직접 호출)")

    def test_b2_03_succeeded_ttl_boundary(self):
        self._assert_ttl_boundary("SUCCEEDED", TTL_SECONDS["SUCCEEDED"])

    def test_b2_04_failed_retryable_ttl_boundary(self):
        self._assert_ttl_boundary("FAILED_RETRYABLE", TTL_SECONDS["FAILED_RETRYABLE"])

    def test_b2_05_failed_final_ttl_boundary(self):
        self._assert_ttl_boundary("FAILED_FINAL", TTL_SECONDS["FAILED_FINAL"])

    def test_b2_06_unknown_ttl_boundary_48h(self):
        # 실제 48시간을 대기하지 않는다 — Clock은 숫자 연산일 뿐이다(계획서 §6, §9.3).
        self._assert_ttl_boundary("UNKNOWN", TTL_SECONDS["UNKNOWN"])

    # 정책 미확정 범위 검증(공식 B2-ID 아님, 그러나 "범위를 TTL 감지로 제한한다"는
    # 의도적 설계 자체가 검증 대상이므로 정식 test_ 메서드로 둔다 — v3의 진단용
    # 메서드(POLICY CONTRADICTED를 보여주던 것)는 IN_PROGRESS 수정으로 폐기함) --
    def test_policy_unresolved_states_block_without_mutation(self):
        """SUCCEEDED/FAILED_RETRYABLE/FAILED_FINAL/UNKNOWN의 만료 후 전이
        대상은 ADR-017 어디에도 명시되어 있지 않다(POLICY UNRESOLVED, 모듈
        docstring 참조). 이 harness는 그 불확실성을 추측으로 메우지 않기
        위해 try_create()가 이 4개 상태의 만료된 행에 대해 **어떤 조치도
        취하지 않음**(삭제도, 재생성도, state 변경도 하지 않음)을 검증한다.
        이는 운영 정책을 확정하는 것이 아니라 이번 검증 범위를 제한한
        설계가 실제로 지켜지는지 확인하는 것이다."""
        for state in ("SUCCEEDED", "FAILED_RETRYABLE", "FAILED_FINAL", "UNKNOWN"):
            key = _synthetic_key()
            ttl = TTL_SECONDS[state]
            seed_row(self.db_path, key, state, at_time=0.0)
            result = try_create(self.db_path, key, "w_retry", now=ttl + 1)
            row_after = _count_rows_for_key(self.db_path, key)
            raw_state_after = _raw_state(self.db_path, key)
            print(
                f"[policy-unresolved] state={state} try_create_result={result} "
                f"row_count_for_key={row_after} raw_state_after={raw_state_after}"
            )
            self.assertEqual(
                result[0],
                "POLICY_UNRESOLVED_BLOCKED",
                f"{state} 만료 행에 조치를 취함(삭제·재생성 등) — 정책 미확정 상태에서는 금지",
            )
            self.assertEqual(
                row_after, 1, f"{state} 만료 행이 삭제됨(정책 미확정 상태에서는 보존해야 함)"
            )
            self.assertEqual(
                raw_state_after,
                state,
                f"{state} 만료 행의 저장된 state 컬럼 값이 임의로 변경됨(정책 미확정)",
            )

    # B2-07 ------------------------------------------------------------------
    def test_b2_07_concurrent_same_key_exactly_one_created(self):
        key = _synthetic_key()
        barrier = threading.Barrier(WORKER_COUNT)
        batch_t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=WORKER_COUNT) as ex:
            futs = [
                ex.submit(_timed_try_create, self.db_path, key, f"w{i}", 0.0, barrier)
                for i in range(WORKER_COUNT)
            ]
            raw = [f.result() for f in futs]
        wall_elapsed = time.perf_counter() - batch_t0
        results = [r[0] for r in raw]
        latencies = [r[1] for r in raw]
        classification = [r[0] for r in results]
        created = classification.count("CREATED")
        blocked = classification.count("DUPLICATE_BLOCKED")
        errors = classification.count("OTHER") + classification.count("UNIQUE_RACE")
        stats = _latency_stats(latencies)
        tput = _throughput(WORKER_COUNT, wall_elapsed)
        print(
            f"[B2-07] workers={WORKER_COUNT} CREATED={created} DUPLICATE_BLOCKED={blocked} "
            f"errors={errors} row_count={self._row_count()} elapsed_sec={wall_elapsed:.6f} "
            f"throughput_ops_per_sec={tput} latency_sec(min/median/p95/max)="
            f"{stats['min']}/{stats['median']}/{stats['p95']}/{stats['max']} n={stats['count']}"
        )
        self.assertEqual(created, 1, f"성공이 정확히 1건이 아님: {results}")
        self.assertEqual(errors, 0, f"예상 밖 오류 발생: {results}")
        self.assertEqual(blocked, WORKER_COUNT - 1)
        self.assertEqual(self._row_count(), 1)

    # B2-08 ------------------------------------------------------------------
    def test_b2_08_concurrent_distinct_keys_no_cross_contamination(self):
        keys = [_synthetic_key() for _ in range(WORKER_COUNT)]
        barrier = threading.Barrier(WORKER_COUNT)
        batch_t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=WORKER_COUNT) as ex:
            futs = [
                ex.submit(_timed_try_create, self.db_path, keys[i], f"w{i}", 0.0, barrier)
                for i in range(WORKER_COUNT)
            ]
            raw = [f.result() for f in futs]
        wall_elapsed = time.perf_counter() - batch_t0
        results = [r[0] for r in raw]
        latencies = [r[1] for r in raw]
        created = sum(1 for r in results if r[0] == "CREATED")
        total_rows = self._row_count()
        unique_keys_in_db = _distinct_keys(self.db_path)
        stats = _latency_stats(latencies)
        tput = _throughput(WORKER_COUNT, wall_elapsed)
        print(
            f"[B2-08] distinct_keys={WORKER_COUNT} CREATED={created} total_rows={total_rows} "
            f"unique_keys_in_db={len(unique_keys_in_db)} elapsed_sec={wall_elapsed:.6f} "
            f"throughput_ops_per_sec={tput} latency_sec(min/median/p95/max)="
            f"{stats['min']}/{stats['median']}/{stats['p95']}/{stats['max']} n={stats['count']}"
        )
        self.assertEqual(created, WORKER_COUNT, f"서로 다른 key 동시생성 중 일부 실패: {results}")
        self.assertEqual(total_rows, WORKER_COUNT)
        self.assertEqual(unique_keys_in_db, set(keys), "교차오염(다른 key가 섞임) 의심")

    # B2-09a/09b ---------------------------------------------------------------
    def _assert_retry_convergence(self, terminal_state: str, label: str):
        """B2-09a/09b 공통 assert. 요청 수 용어는 _run_retry_convergence
        docstring 및 계획서 §7 B2-09 행("요청 수"와 "retry 수"를 측정값에서
        구분)을 따른다(item 2, v5)."""
        data = _run_retry_convergence(self.db_path, terminal_state, RETRY_ATTEMPTS)
        stats = _latency_stats(data["latencies"])
        tput = _throughput(data["total_request_count"], data["wall_elapsed"])
        print(
            f"[{label}] key={data['key']} initial_request_count={data['initial_request_count']} "
            f"retry_count={data['retry_count']} total_request_count={data['total_request_count']} "
            f"unique_nonces={len(set(data['nonces_used']))} row_counts={data['row_counts']} "
            f"terminal={data['terminal_state']} elapsed_sec={data['wall_elapsed']:.6f} "
            f"throughput_ops_per_sec={tput} "
            f"latency_sec(min/median/p95/max)={stats['min']}/{stats['median']}/{stats['p95']}/{stats['max']} "
            f"n={stats['count']}"
        )
        self.assertEqual(data["created_status"], "CREATED")
        self.assertEqual(data["initial_request_count"], 1, "최초 요청은 1회여야 함")
        self.assertEqual(
            data["retry_count"], RETRY_ATTEMPTS, "재시도 횟수(retry_count)가 RETRY_ATTEMPTS와 다름"
        )
        self.assertEqual(
            data["total_request_count"],
            data["initial_request_count"] + RETRY_ATTEMPTS,
            "총 요청 수 = 최초 요청 1 + 재시도 횟수(RETRY_ATTEMPTS) 공식이 깨짐",
        )
        self.assertEqual(
            len(set(data["nonces_used"])),
            data["total_request_count"],
            "전체 요청(최초+재시도) 수만큼 고유 nonce가 생성되지 않음",
        )
        self.assertEqual(
            len(data["nonces_used"]),
            len(set(data["nonces_used"])),
            "nonce 목록에 중복이 존재함(모든 요청이 서로 다른 nonce를 써야 함)",
        )
        self.assertTrue(
            all(rc == 1 for rc in data["row_counts"]),
            "재시도 중 중복 행 생성 의심(동일 key 유지 위반 포함)",
        )
        final_observed = read_state(self.db_path, data["key"], now=data["final_now"])
        self.assertEqual(final_observed, terminal_state)

    def test_b2_09a_retry_convergence_to_succeeded(self):
        self._assert_retry_convergence("SUCCEEDED", "B2-09a")

    def test_b2_09b_retry_convergence_to_failed_final(self):
        self._assert_retry_convergence("FAILED_FINAL", "B2-09b")

    # B2-10 --------------------------------------------------------------------
    def test_b2_10_synthetic_burst_retry_storm(self):
        key = _synthetic_key()
        barrier = threading.Barrier(BURST_COUNT)
        batch_t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=BURST_COUNT) as ex:
            futs = [
                ex.submit(_timed_try_create, self.db_path, key, f"w{i}", 0.0, barrier)
                for i in range(BURST_COUNT)
            ]
            raw = [f.result() for f in futs]
        wall_elapsed = time.perf_counter() - batch_t0
        results = [r[0] for r in raw]
        latencies = [r[1] for r in raw]
        classification = [r[0] for r in results]
        created = classification.count("CREATED")
        blocked = classification.count("DUPLICATE_BLOCKED")
        errors = classification.count("OTHER") + classification.count("UNIQUE_RACE")
        stats = _latency_stats(latencies)
        tput = _throughput(BURST_COUNT, wall_elapsed)
        print(
            f"[B2-10] burst_count={BURST_COUNT} CREATED={created} DUPLICATE_BLOCKED={blocked} "
            f"errors={errors} elapsed_sec={wall_elapsed:.6f} throughput_ops_per_sec={tput} "
            f"latency_sec(min/median/p95/max)={stats['min']}/{stats['median']}/{stats['p95']}/{stats['max']} "
            f"n={stats['count']}"
        )
        self.assertEqual(created, 1, f"burst 상황에서 성공이 정확히 1건이 아님: {results}")
        self.assertEqual(errors, 0, f"예상 밖 오류 발생: {results}")
        self.assertEqual(blocked, BURST_COUNT - 1)

    # B2-11 ----------------------------------------------------------------------
    def test_b2_11_time_work_guard_partial_result_preserved(self):
        processed = []
        latencies = []
        aborted_early = False
        loop_t0 = time.perf_counter()
        for i in range(GUARD_TOTAL_REQUESTED):
            if len(processed) >= GUARD_MAX_PROCESSED:
                aborted_early = True
                break
            key = _synthetic_key()
            result, elapsed = _timed(try_create, self.db_path, key, f"guard{i}", float(i))
            latencies.append(elapsed)
            self.assertEqual(result[0], "CREATED")
            processed.append(key)
        wall_elapsed = time.perf_counter() - loop_t0
        remaining_unprocessed = GUARD_TOTAL_REQUESTED - len(processed)
        row_count_after_abort = self._row_count()
        stats = _latency_stats(latencies)
        tput = _throughput(len(processed), wall_elapsed)
        print(
            f"[B2-11] guard_max={GUARD_MAX_PROCESSED} total_requested={GUARD_TOTAL_REQUESTED} "
            f"processed={len(processed)} aborted_early={aborted_early} "
            f"row_count_after_abort={row_count_after_abort} elapsed_sec={wall_elapsed:.6f} "
            f"throughput_ops_per_sec={tput} latency_sec(min/median/p95/max)="
            f"{stats['min']}/{stats['median']}/{stats['p95']}/{stats['max']} n={stats['count']}"
        )
        self.assertTrue(aborted_early, "guard가 조기 중단을 유발하지 못함")
        self.assertEqual(len(processed), GUARD_MAX_PROCESSED)
        self.assertEqual(row_count_after_abort, GUARD_MAX_PROCESSED, "조기 중단 후 부분결과가 보존되지 않음")
        self.assertGreater(remaining_unprocessed, 0)
        # 무한 재시도 없음: 중단된 나머지 요청에 대해 추가 시도를 하지 않았음을
        # row_count가 GUARD_MAX_PROCESSED에서 변하지 않는지로 간접 확인한다.
        self.assertEqual(self._row_count(), GUARD_MAX_PROCESSED)

    # B2-12 ------------------------------------------------------------------------
    def test_b2_12_repeat_full_b2_02_to_b2_10_stability_and_cleanup(self):
        """Plan section 7, B2-12: repeat the B2-02~B2-10 patterns 3 times, as
        specified (history: v1 reduced scope to B2-07 only; v2 restored full
        B2-02~10; v2 included only the SUCCEEDED path of B2-09, v3 added
        FAILED_FINAL too; v3 excluded latency/throughput citing the B2-12 row
        of section 7, v4 restored them since that omission alone does not
        prove section 8 exclusion; v4 had a UnicodeEncodeError in this exact
        print statement on a cp949 console, fixed in v5 by using ASCII-only
        text here and by moving every assertion before this print call).
        Each repeat uses an independent temp DB, independent synthetic keys,
        and an independent virtual clock (see _run_full_scenario_suite).
        Pass/fail is based on deterministic outcome variance and cleanup;
        latency/throughput are observational only and are not included in
        the outcome dict used for the variance check, because wall-clock
        timing legitimately differs between repeats and must not cause a
        spurious failure there."""
        all_outcomes = []
        row_counts = []
        cleanup_flags = []
        all_latencies: list = []
        suite_wall_t0 = time.perf_counter()
        for rep in range(REPEAT_COUNT):
            outcome, row_count, cleanup_ok, latencies = _run_full_scenario_suite(run_id=rep)
            all_outcomes.append(outcome)
            row_counts.append(row_count)
            cleanup_flags.append(cleanup_ok)
            all_latencies.extend(latencies)
        suite_wall_elapsed = time.perf_counter() - suite_wall_t0

        normalized = [tuple(sorted(o.items())) for o in all_outcomes]
        distinct_patterns = set(normalized)

        # --- Assertions first (item 3): verification must happen before the
        # summary print, so a console-encoding failure in the print can never
        # mask or precede the actual pass/fail judgment. ---
        self.assertEqual(len(distinct_patterns), 1, f"repeat variance detected: {all_outcomes}")
        self.assertTrue(all(cleanup_flags), f"cleanup incomplete in some repeats: {cleanup_flags}")
        # 5 (TTL states) + 1 (B2-07) + WORKER_COUNT (B2-08) + 1 (B2-09 SUCCEEDED)
        # + 1 (B2-09 FAILED_FINAL) + 1 (B2-10). IN_PROGRESS->UNKNOWN transition
        # reuses the existing row and the blocked retry creates no new row, so
        # row count per repeat is unaffected.
        expected_rows_per_repeat = len(TTL_SECONDS) + 1 + WORKER_COUNT + 1 + 1 + 1
        self.assertTrue(
            all(rc == expected_rows_per_repeat for rc in row_counts),
            f"row_count before cleanup does not match expected "
            f"({expected_rows_per_repeat}): {row_counts}",
        )
        # This test's own fixture (self.db_path) is a separate temp DB from
        # _run_full_scenario_suite's and was never written to, so it must be 0
        # (a sanity check against accidental cross-use).
        self.assertEqual(self._row_count(), 0)

        # --- Summary print (ASCII-only, after all assertions pass; item 3) ---
        stats = _latency_stats(all_latencies)
        tput = _throughput(len(all_latencies), suite_wall_elapsed)
        print(
            f"[B2-12] repeats={REPEAT_COUNT} distinct_outcome_patterns={len(distinct_patterns)} "
            f"row_counts_before_cleanup={row_counts} cleanup_flags={cleanup_flags} "
            f"elapsed_sec_total={suite_wall_elapsed:.6f} ops_measured={len(all_latencies)} "
            f"throughput_ops_per_sec={tput} latency_sec_min={stats['min']} "
            f"latency_sec_median={stats['median']} latency_sec_p95={stats['p95']} "
            f"latency_sec_max={stats['max']} n={stats['count']} "
            f"(observation only, not a pass/fail criterion - plan section 8)"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
