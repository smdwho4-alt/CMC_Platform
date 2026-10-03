# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — Replay 차단 격리 실측: 서버 측 요청 예산 가드(로컬 미러)

gas_candidate/ServerBudgetGuard_new.gs와 동일한 제어 흐름. 카운터·시작시각은
PropertiesService(의 로컬 시뮬레이션)를 쓴다 — CacheService가 아니다(그
파일 상단 주석과 동일한 이유: 안전장치 자체가 비영속 저장소 때문에
조용히 리셋되면 안 되므로).

한계 명시(그 파일과 동일): 이 가드는 서명 검증을 통과한 "인증된" 요청만
센다. 비인증 요청이 공개 endpoint의 실행 quota를 소모하는 것까지는
막지 못한다.
"""
from __future__ import annotations

from dataclasses import dataclass

from sim_script_lock import ScriptLockSim
from sim_properties_service import ScriptPropertiesSim

EXPERIMENT_DEADLINE_SECONDS = 900
EXPERIMENT_REQUEST_CAP = 80
LOCK_WAIT_TIMEOUT_MS = 5000


@dataclass
class BudgetOutcome:
    outcome: str  # "WITHIN_BUDGET" | "BUDGET_EXCEEDED" | "EXPERIMENT_EXPIRED" | "BLOCKED_STORE_ERROR"
    request_count: int
    elapsed_seconds: float


def check_and_consume_request_budget(
    now_epoch_seconds: float, *, lock: ScriptLockSim, props: ScriptPropertiesSim,
    deadline_seconds: float = EXPERIMENT_DEADLINE_SECONDS, request_cap: int = EXPERIMENT_REQUEST_CAP,
    lock_timeout_ms: int = LOCK_WAIT_TIMEOUT_MS,
) -> BudgetOutcome:
    acquired = lock.try_lock(lock_timeout_ms)
    if not acquired:
        return BudgetOutcome(outcome="BLOCKED_STORE_ERROR", request_count=-1, elapsed_seconds=-1)
    try:
        start_raw = props.get_property("experiment_start_time")
        if start_raw is None:
            start_time = now_epoch_seconds
            props.set_property("experiment_start_time", str(start_time))
        else:
            start_time = float(start_raw)

        elapsed = now_epoch_seconds - start_time
        if elapsed > deadline_seconds:
            return BudgetOutcome(outcome="EXPERIMENT_EXPIRED", request_count=-1, elapsed_seconds=elapsed)

        count_raw = props.get_property("experiment_request_count")
        count = 0 if count_raw is None else int(count_raw)

        if count + 1 > request_cap:
            return BudgetOutcome(outcome="BUDGET_EXCEEDED", request_count=count, elapsed_seconds=elapsed)

        count += 1
        props.set_property("experiment_request_count", str(count))
        return BudgetOutcome(outcome="WITHIN_BUDGET", request_count=count, elapsed_seconds=elapsed)
    except Exception:
        return BudgetOutcome(outcome="BLOCKED_STORE_ERROR", request_count=-1, elapsed_seconds=-1)
    finally:
        lock.release_lock()


def admin_reset_experiment_budget(props: ScriptPropertiesSim) -> None:
    """편집기 전용 수동 초기화의 로컬 대응 — 어떤 HTTP 라우트에도 연결하지 않는다."""
    props.delete_property("experiment_start_time")
    props.delete_property("experiment_request_count")
