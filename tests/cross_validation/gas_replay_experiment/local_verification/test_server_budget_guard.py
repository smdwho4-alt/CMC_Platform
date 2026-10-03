# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — Replay 차단 격리 실측: 서버 측 요청 예산 가드 단위 테스트

요청사항 1 "상한 집계는 동시 요청에서도 원자적으로 처리한다"를 직접
실제 스레드로 검증한다(같은 실행 내 반복호출이 아니다).
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from server_budget_guard import check_and_consume_request_budget, admin_reset_experiment_budget  # noqa: E402
from sim_script_lock import ScriptLockSim  # noqa: E402
from sim_properties_service import ScriptPropertiesSim  # noqa: E402


def test_budget_allows_within_cap_and_blocks_over_cap_sequentially():
    lock = ScriptLockSim()
    props = ScriptPropertiesSim()
    now = time.time()
    cap = 5
    results = []
    for i in range(cap + 3):
        r = check_and_consume_request_budget(now + i, lock=lock, props=props, request_cap=cap)
        results.append(r.outcome)
    assert results[:cap] == ["WITHIN_BUDGET"] * cap
    assert results[cap:] == ["BUDGET_EXCEEDED"] * 3


def test_budget_cap_enforced_atomically_under_real_concurrency():
    """실제 threading.Thread(동시 소켓 통신은 아니지만 진짜 OS 스레드
    경쟁)로 cap을 초과하는 수의 요청을 동시에 던져도, WITHIN_BUDGET으로
    통과하는 수가 **정확히 cap과 같아야** 한다(초과 통과 없음)."""
    lock = ScriptLockSim()
    props = ScriptPropertiesSim()
    cap = 10
    n_threads = 40
    barrier = threading.Barrier(n_threads)
    outcomes = []
    outcomes_lock = threading.Lock()

    def worker():
        barrier.wait()
        now = time.time()
        r = check_and_consume_request_budget(now, lock=lock, props=props, request_cap=cap)
        with outcomes_lock:
            outcomes.append(r.outcome)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    within = sum(1 for o in outcomes if o == "WITHIN_BUDGET")
    exceeded = sum(1 for o in outcomes if o == "BUDGET_EXCEEDED")
    assert within == cap, f"cap={cap}인데 WITHIN_BUDGET이 {within}건 나옴(원자성 위반 가능성)"
    assert exceeded == n_threads - cap


def test_experiment_expired_after_deadline():
    lock = ScriptLockSim()
    props = ScriptPropertiesSim()
    t0 = time.time()
    first = check_and_consume_request_budget(t0, lock=lock, props=props, deadline_seconds=100)
    assert first.outcome == "WITHIN_BUDGET"

    later = check_and_consume_request_budget(t0 + 101, lock=lock, props=props, deadline_seconds=100)
    assert later.outcome == "EXPERIMENT_EXPIRED"


def test_admin_reset_clears_budget_state():
    lock = ScriptLockSim()
    props = ScriptPropertiesSim()
    now = time.time()
    check_and_consume_request_budget(now, lock=lock, props=props, request_cap=1)
    exhausted = check_and_consume_request_budget(now, lock=lock, props=props, request_cap=1)
    assert exhausted.outcome == "BUDGET_EXCEEDED"

    admin_reset_experiment_budget(props)  # 편집기 전용 수동 초기화의 로컬 대응

    fresh = check_and_consume_request_budget(now, lock=lock, props=props, request_cap=1)
    assert fresh.outcome == "WITHIN_BUDGET"
