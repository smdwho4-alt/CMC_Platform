# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — Replay 차단 격리 실측: 로컬 검증 테스트

*** 합성 nonce·합성 키만 사용한다. 운영 예약자료·실제 서명 키는 쓰지
않는다. GAS 업로드·실행은 하지 않는다 — 전부 로컬 Python 시뮬레이션이다. ***

표기 원칙(요청사항 준수):
  - "동시성" 테스트는 실제 threading.Thread + threading.Barrier로 OS
    스레드를 동시에 기동한다. 같은 실행 안에서 반복 호출하는 것을
    동시성 실측이라고 표현하지 않는다.
  - CacheService 유실은 ScriptCacheSim.remove()로만 모사한다. 이를
    "실제 CacheService 조기 유실을 재현했다"고 표현하지 않고, 결과가
    FAIL인지 알려진 보안 한계(KNOWN_LIMITATION)인지 명시한다.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402

from replay_guard import (  # noqa: E402
    EXPERIMENT_MAX_SKEW_SECONDS,
    EXPERIMENT_NONCE_TTL_SECONDS_MIN,
    EXPERIMENT_NONCE_TTL_SECONDS_WITH_MARGIN,
    EXPERIMENT_TTL_MARGIN_SECONDS,
    check_and_record_nonce_variant_a_cache_lock,
    check_and_record_nonce_variant_b_properties_lock,
    verify_signature_real,
)
from nonce_ttl_boundary import (  # noqa: E402
    compute_nonce_ttl_seconds,
    compute_signature_allowed_end_time,
    assert_nonce_outlives_signature_window,
    NonceTtlConfigError,
    NonceTtlInvariantViolated,
)
from sim_cache_service import ScriptCacheSim  # noqa: E402
from sim_properties_service import ScriptPropertiesSim  # noqa: E402
from sim_script_lock import ScriptLockSim  # noqa: E402

from idempotency.signing_v2 import KeyRecord, KeyRegistry, sign_v2  # noqa: E402


TEST_SECRET = "synthetic-test-secret-only-not-production"  # 합성 키 — 운영 Secret 아님
TEST_KEY_ID = "synthetic-test-key-001"


def _build_registry() -> KeyRegistry:
    registry = KeyRegistry()
    registry.register(KeyRecord(key_id=TEST_KEY_ID, secret=TEST_SECRET, state="ACTIVE"))
    return registry


def _make_signed_envelope(*, nonce: str, timestamp: float, operation: str = "test.op") -> dict:
    payload = {"synthetic": True, "amount": 1}
    ts_str = str(timestamp)
    sig = sign_v2(
        secret=TEST_SECRET, method="POST", operation=operation, timestamp=ts_str,
        nonce=nonce, idempotency_key=f"idem-{nonce}", key_id=TEST_KEY_ID, payload=payload,
    )
    return {
        "method": "POST", "operation": operation, "timestamp": ts_str, "nonce": nonce,
        "idempotency_key": f"idem-{nonce}", "key_id": TEST_KEY_ID, "payload": payload, "signature": sig,
    }


# ---------------------------------------------------------------------------
# 요청사항 1(nonce 만료 경계 보완) 전용 단위 테스트 — 가드 전체 흐름과
# 별개로, NonceTtlBoundary_new.gs를 그대로 옮긴 nonce_ttl_boundary.py
# 자체의 계산·올림·불변식 검증을 직접 확인한다.
# ---------------------------------------------------------------------------

def test_ttl_boundary_rounds_up_fractional_remaining_time():
    """TTL을 올림(ceil)한다는 요구사항을 소수점 단위로 직접 확인한다."""
    ts = 100.0
    max_skew = 120.0
    now = 100.3  # remaining = (100+120) - 100.3 = 119.7
    margin = 0.5  # raw_ttl = 120.2 → ceil = 121
    ttl = compute_nonce_ttl_seconds(now, ts, max_skew, margin)
    assert ttl == 121, "119.7+0.5=120.2는 내림(120)이 아니라 올림(121)되어야 한다"


def test_ttl_boundary_signature_allowed_end_matches_formula():
    ts = 1_000_000.0
    max_skew = 120.0
    assert compute_signature_allowed_end_time(ts, max_skew) == ts + max_skew


def test_ttl_boundary_invariant_passes_for_guard_computed_ttl():
    """가드가 실제로 계산할 TTL이 불변식을 통과하는지 직접 재현."""
    ts = 1_700_000_000.0
    max_skew = EXPERIMENT_MAX_SKEW_SECONDS
    now = ts + max_skew  # 최초 처리 시각을 서명 허용 범위의 '먼 쪽' 경계로 둠
    ttl = compute_nonce_ttl_seconds(now, ts, max_skew, EXPERIMENT_TTL_MARGIN_SECONDS)
    allowed_end = compute_signature_allowed_end_time(ts, max_skew)
    assert_nonce_outlives_signature_window(now, ttl, allowed_end)  # 예외 없이 통과해야 함


def test_ttl_boundary_invariant_raises_when_ttl_insufficient():
    """불변식 검증 함수 자체가 실제로 위반을 감지하는지 확인(방어 코드가
    장식이 아니라 실제로 작동함을 증명)."""
    with pytest.raises(NonceTtlInvariantViolated):
        assert_nonce_outlives_signature_window(record_time=100.0, ttl_seconds=5, signature_allowed_end=200.0)


def test_ttl_boundary_config_error_on_negative_remaining():
    """서명이 이미 거부됐어야 할 시각에 대해 TTL을 계산하려 하면(호출
    순서 오류) 조용히 처리하지 않고 예외를 던진다."""
    ts = 1_000_000.0
    max_skew = 120.0
    now = ts + max_skew + 1  # 경계를 1초 넘김 — 이미 서명 자체가 거부됐어야 할 시점
    with pytest.raises(NonceTtlConfigError):
        compute_nonce_ttl_seconds(now, ts, max_skew, EXPERIMENT_TTL_MARGIN_SECONDS)


# ---------------------------------------------------------------------------
# 시나리오 1: 최초 nonce 허용, 재사용 거절
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("variant", ["A", "B"])
def test_scenario1_first_accept_replay_rejected(variant):
    lock = ScriptLockSim()
    now = time.time()
    nonce = f"syn-nonce-s1-{variant}"

    if variant == "A":
        store = ScriptCacheSim()
        guard = lambda: check_and_record_nonce_variant_a_cache_lock(nonce, now, now, lock=lock, cache=store)
    else:
        store = ScriptPropertiesSim()
        guard = lambda: check_and_record_nonce_variant_b_properties_lock(nonce, now, now, lock=lock, props=store)

    first = guard()
    assert first.outcome == "ACCEPTED"

    second = guard()
    assert second.outcome == "REJECTED_REPLAY"


# ---------------------------------------------------------------------------
# 시나리오 2: 동시 동일 nonce 요청 — 업무 실행권 정확히 1건
# (실제 threading.Thread + Barrier 기반. 같은 실행 내 순차 반복호출이 아님)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("variant", ["A", "B"])
def test_scenario2_concurrent_identical_nonce_exactly_one_execution(variant):
    lock = ScriptLockSim()
    nonce = f"syn-nonce-s2-{variant}"
    n_threads = 12
    barrier = threading.Barrier(n_threads)
    accepted_count = []
    accepted_lock = threading.Lock()

    if variant == "A":
        store = ScriptCacheSim()

        def guard(now):
            return check_and_record_nonce_variant_a_cache_lock(nonce, now, now, lock=lock, cache=store)
    else:
        store = ScriptPropertiesSim()

        def guard(now):
            return check_and_record_nonce_variant_b_properties_lock(nonce, now, now, lock=lock, props=store)

    def worker():
        barrier.wait()  # 모든 스레드가 동시에 출발하도록 강제
        now = time.time()
        result = guard(now)
        if result.outcome == "ACCEPTED":
            with accepted_lock:
                accepted_count.append(1)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(accepted_count) == 1, (
        f"variant={variant}: 동시 요청 {n_threads}건 중 업무 실행권이 "
        f"정확히 1건이어야 하는데 {len(accepted_count)}건이 나왔다"
    )


# ---------------------------------------------------------------------------
# 시나리오 3: 저장소 장애·잠금 timeout — 실행 0건
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("variant", ["A", "B"])
def test_scenario3a_lock_timeout_blocks_execution(variant):
    lock = ScriptLockSim()
    nonce = f"syn-nonce-s3a-{variant}"
    now = time.time()

    # 다른 스레드가 먼저 락을 잡고 오래 들고 있게 만든다.
    holder_ready = threading.Event()
    release_holder = threading.Event()

    def holder():
        lock.try_lock(5000)
        holder_ready.set()
        release_holder.wait(timeout=5)
        lock.release_lock()

    t = threading.Thread(target=holder)
    t.start()
    holder_ready.wait(timeout=2)

    if variant == "A":
        store = ScriptCacheSim()
        result = check_and_record_nonce_variant_a_cache_lock(
            nonce, now, now, lock=lock, cache=store, lock_timeout_ms=200
        )
    else:
        store = ScriptPropertiesSim()
        result = check_and_record_nonce_variant_b_properties_lock(
            nonce, now, now, lock=lock, props=store, lock_timeout_ms=200
        )

    release_holder.set()
    t.join(timeout=5)

    assert result.outcome == "BLOCKED_LOCK_TIMEOUT"


@pytest.mark.parametrize("variant", ["A", "B"])
def test_scenario3b_store_error_blocks_execution(variant, monkeypatch):
    lock = ScriptLockSim()
    nonce = f"syn-nonce-s3b-{variant}"
    now = time.time()

    if variant == "A":
        store = ScriptCacheSim()

        def boom(*a, **k):
            raise RuntimeError("synthetic CacheService put failure")

        monkeypatch.setattr(store, "put", boom)
        result = check_and_record_nonce_variant_a_cache_lock(nonce, now, now, lock=lock, cache=store)
    else:
        store = ScriptPropertiesSim()

        def boom(*a, **k):
            raise RuntimeError("synthetic PropertiesService setProperty failure")

        monkeypatch.setattr(store, "set_property", boom)
        result = check_and_record_nonce_variant_b_properties_lock(nonce, now, now, lock=lock, props=store)

    assert result.outcome == "BLOCKED_STORE_ERROR"
    assert lock.has_lock() is False  # finally에서 반드시 해제됨


# ---------------------------------------------------------------------------
# 시나리오 4: 업무 실행 전 실패 후 같은 nonce 재전송
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("variant", ["A", "B"])
def test_scenario4_same_nonce_blocked_new_nonce_succeeds_after_pre_execution_failure(variant):
    lock = ScriptLockSim()
    now = time.time()
    original_nonce = f"syn-nonce-s4-orig-{variant}"
    new_nonce = f"syn-nonce-s4-new-{variant}"

    if variant == "A":
        store = ScriptCacheSim()
        guard = lambda n, t: check_and_record_nonce_variant_a_cache_lock(n, t, t, lock=lock, cache=store)
    else:
        store = ScriptPropertiesSim()
        guard = lambda n, t: check_and_record_nonce_variant_b_properties_lock(n, t, t, lock=lock, props=store)

    first = guard(original_nonce, now)
    assert first.outcome == "ACCEPTED"
    # ... 여기서 업무 실행 로직이 예외를 던졌다고 가정(코드상 표현하지 않음 — 중요한 것은
    # nonce가 이미 "소비됨"으로 기록된 상태로 남는다는 점).

    retry_same_nonce = guard(original_nonce, now + 1)
    assert retry_same_nonce.outcome == "REJECTED_REPLAY", (
        "같은 nonce 재전송은 발급측이 새 nonce를 발급하지 않는 한 차단되어야 한다"
    )

    retry_new_nonce = guard(new_nonce, now + 1)
    assert retry_new_nonce.outcome == "ACCEPTED", (
        "새 nonce로의 재시도는 허용되어야 한다(동일 nonce 재사용 차단과는 별개)"
    )


# ---------------------------------------------------------------------------
# 시나리오 5: CacheService 항목을 시험 목적으로 제거한 뒤 재전송
#   → 허용된다면 FAIL 또는 알려진 보안 한계로 명시
# ---------------------------------------------------------------------------

def test_scenario5_variantA_explicit_cache_removal_known_limitation():
    """*** 이 테스트가 통과(ACCEPTED)하는 것은 버그가 아니라, 대안 A
    (CacheService 단독 저장)의 이미 문서화된 잔존 위험이 실제로 재현됨을
    보여주는 것이다 — "실제 CacheService 조기 유실을 재현"한 것이 아니라
    cache.remove()라는 명시적 호출로 유실을 모사한 것이다. 이 결과는
    대안 비교 설계 문서 §3 대안 A의 '서명 유효기간 내 캐시 유실 시
    replay 성공 가능'이라는 잔존 위험과 정확히 일치하며, KNOWN_LIMITATION
    으로 분류한다(FAIL이 아님 — 이미 예상되고 문서화된 동작이기 때문)."""
    lock = ScriptLockSim()
    cache = ScriptCacheSim()
    nonce = "syn-nonce-s5-cache-removed"
    now = time.time()

    first = check_and_record_nonce_variant_a_cache_lock(nonce, now, now, lock=lock, cache=cache)
    assert first.outcome == "ACCEPTED"

    # 명시적 유실 모사 — 실제 GAS 조기 유실 재현이 아님을 메서드 이름 자체로 표시.
    cache.remove(nonce)

    replay = check_and_record_nonce_variant_a_cache_lock(nonce, now + 1, now + 1, lock=lock, cache=cache)

    if replay.outcome == "ACCEPTED":
        print(
            "[KNOWN_LIMITATION] Variant A: 명시적 cache.remove() 이후 동일 nonce 재전송이 "
            "허용됨 — CacheService 비영속성에서 비롯된 이미 문서화된 잔존 위험(설계 문서 §3 대안 A)."
        )
        assert replay.outcome == "ACCEPTED"  # 알려진 한계로 명시적으로 기록(묵과하지 않음)
    else:
        pytest.fail(
            "예상과 다르게 replay가 차단됨 — 설계 문서의 '대안 A 잔존 위험' 가정이 "
            "이 시뮬레이션 구현과 불일치한다. 가정 또는 구현 중 하나를 재검토해야 한다."
        )


# ---------------------------------------------------------------------------
# 시나리오 6: 지속 저장소에서는 캐시 제거와 무관하게 재전송 차단
# ---------------------------------------------------------------------------

def test_scenario6_variantB_unaffected_by_cache_removal():
    """Variant B는 애초에 CacheService를 쓰지 않는다. 그 사실 자체를
    "캐시를 지워도 영향 없다"로 보여주기 위해, 같은 테스트 안에서 A용
    캐시와 B용 Properties를 독립적으로 운용하고 A쪽 캐시만 제거한 뒤
    B쪽은 전혀 건드리지 않았음에도 재전송이 계속 차단되는지 확인한다."""
    lock_a = ScriptLockSim()
    lock_b = ScriptLockSim()
    cache = ScriptCacheSim()
    props = ScriptPropertiesSim()
    nonce = "syn-nonce-s6"
    now = time.time()

    accept_a = check_and_record_nonce_variant_a_cache_lock(nonce, now, now, lock=lock_a, cache=cache)
    accept_b = check_and_record_nonce_variant_b_properties_lock(nonce, now, now, lock=lock_b, props=props)
    assert accept_a.outcome == "ACCEPTED"
    assert accept_b.outcome == "ACCEPTED"

    cache.remove(nonce)  # A의 저장소만 명시적으로 지움 — B(props)는 손대지 않음

    replay_a = check_and_record_nonce_variant_a_cache_lock(nonce, now + 1, now + 1, lock=lock_a, cache=cache)
    replay_b = check_and_record_nonce_variant_b_properties_lock(nonce, now + 1, now + 1, lock=lock_b, props=props)

    assert replay_a.outcome == "ACCEPTED", "A는 캐시 제거의 영향을 받아 재전송이 통과된다(알려진 한계)"
    assert replay_b.outcome == "REJECTED_REPLAY", "B는 지속 저장소이므로 캐시 제거와 무관하게 계속 차단되어야 한다"


# ---------------------------------------------------------------------------
# 시나리오 7: 서명 유효기간 종료 및 nonce 정리 경계
# ---------------------------------------------------------------------------

def test_scenario7_signature_expiry_and_nonce_cleanup_boundary():
    """ExperimentConfig_new.gs / replay_guard.py 상단에서 유도한
    'TTL >= 2*max_skew_seconds' 불변식을 실제 숫자(120, 240, 300)로
    경계까지 검증한다. 실제 signing_v2.verify_v2()를 그대로 사용한다."""
    assert EXPERIMENT_NONCE_TTL_SECONDS_MIN == 2 * EXPERIMENT_MAX_SKEW_SECONDS == 240
    assert EXPERIMENT_NONCE_TTL_SECONDS_WITH_MARGIN >= EXPERIMENT_NONCE_TTL_SECONDS_MIN

    registry = _build_registry()
    t0 = 1_700_000_000.0  # 고정 기준시각(합성)
    nonce = "syn-nonce-s7"

    # 공격자가 포획했다고 가정하는, "최대한 미래로 채운" timestamp:
    # ts = T0 + max_skew  (경계값, 최초 통과 시각 T0에서 delta = -max_skew, 허용 경계)
    future_padded_ts = t0 + EXPERIMENT_MAX_SKEW_SECONDS
    envelope = _make_signed_envelope(nonce=nonce, timestamp=future_padded_ts)

    # (1) 최초 처리 시각 T0에서 서명 검증 통과 확인(경계값 포함 허용)
    v0 = verify_signature_real(
        registry=registry, method=envelope["method"], operation=envelope["operation"],
        timestamp=envelope["timestamp"], nonce=nonce, idempotency_key=envelope["idempotency_key"],
        key_id=envelope["key_id"], payload=envelope["payload"], signature=envelope["signature"], now=t0,
    )
    assert v0.classification == "ACCEPTED"

    lock = ScriptLockSim()
    cache = ScriptCacheSim()
    # signed_timestamp_epoch_seconds는 envelope가 실제로 주장하는 timestamp(future_padded_ts)다 —
    # nonce를 기록하는 처리 시각(t0)과는 다른 값이다(이것이 바로 "미래 timestamp 허용"을
    # TTL 계산에 반영한다는 요구사항의 핵심).
    first_guard = check_and_record_nonce_variant_a_cache_lock(
        nonce, t0, future_padded_ts, lock=lock, cache=cache
    )
    assert first_guard.outcome == "ACCEPTED"

    # 동적으로 계산된 TTL을 직접 확인: remaining = (future_padded_ts+skew) - t0
    #   = (t0+skew+skew) - t0 = 2*skew = 240, + margin(30) = 270, ceil(270) = 270
    expected_ttl = compute_nonce_ttl_seconds(t0, future_padded_ts, EXPERIMENT_MAX_SKEW_SECONDS, EXPERIMENT_TTL_MARGIN_SECONDS)
    assert expected_ttl == 2 * EXPERIMENT_MAX_SKEW_SECONDS + EXPERIMENT_TTL_MARGIN_SECONDS == 270
    nonce_expires_at = t0 + expected_ttl  # = t0 + 270

    # (2) 유도식상 '이 envelope가 서명 검증을 통과할 수 있는 가장 늦은 시각'
    #     = future_padded_ts + max_skew = T0 + 2*max_skew. 그 경계 바로 안쪽에서
    #     재시도하면 서명은 여전히 통과하지만, 동적으로 계산된 nonce TTL(270s,
    #     margin 30s 포함)이 아직 안 지났으므로 nonce 가드가 막아야 한다(이중 방어 확인).
    latest_signature_acceptable_now = future_padded_ts + EXPERIMENT_MAX_SKEW_SECONDS
    assert latest_signature_acceptable_now == t0 + 2 * EXPERIMENT_MAX_SKEW_SECONDS
    assert nonce_expires_at > latest_signature_acceptable_now, (
        "불변식 확인: nonce 만료시각이 서명 허용 종료시각보다 뒤여야 한다(margin 덕분에 엄격한 부등호)"
    )

    v_at_latest = verify_signature_real(
        registry=registry, method=envelope["method"], operation=envelope["operation"],
        timestamp=envelope["timestamp"], nonce=nonce, idempotency_key=envelope["idempotency_key"],
        key_id=envelope["key_id"], payload=envelope["payload"], signature=envelope["signature"],
        now=latest_signature_acceptable_now,
    )
    assert v_at_latest.classification == "ACCEPTED", "경계값(T0+2*skew)에서는 서명이 여전히 허용되어야 한다"

    guard_at_latest = check_and_record_nonce_variant_a_cache_lock(
        nonce, latest_signature_acceptable_now, future_padded_ts, lock=lock, cache=cache,
    )
    assert guard_at_latest.outcome == "REJECTED_REPLAY", (
        "서명이 아직 유효한 경계 시각(t0+240)에는 동적으로 계산된 nonce TTL(t0+270까지)도 "
        "아직 남아 있어야 하며, 따라서 nonce 가드가 replay를 막아야 한다"
    )

    # (3) 서명 유효기간이 완전히 끝난 시각(경계+1초)에는 서명 자체가 거부되어야
    #     한다 — 이 지점부터는 nonce 저장소 상태와 무관하게 안전하다.
    v_after_expiry = verify_signature_real(
        registry=registry, method=envelope["method"], operation=envelope["operation"],
        timestamp=envelope["timestamp"], nonce=nonce, idempotency_key=envelope["idempotency_key"],
        key_id=envelope["key_id"], payload=envelope["payload"], signature=envelope["signature"],
        now=latest_signature_acceptable_now + 1,
    )
    assert v_after_expiry.classification == "TIMESTAMP_EXPIRED"


# ---------------------------------------------------------------------------
# 참고용 베이스라인(요청 시나리오는 아님): Lock 없이 get+put만 하면
# 실제로 경쟁이 발생함을 실측으로 보여, "Script Lock이 왜 필요한가"라는
# 설계 문서 §3의 주장을 이 로컬 환경에서도 재확인한다. 이 테스트는
# 확률적으로 통과하지 못할 수도 있다는 것 자체가 핵심이므로, 실패 시에도
# 그 사실을 보고에 남긴다(별도 표시 없이 조용히 재시도하지 않는다).
# ---------------------------------------------------------------------------

def test_baseline_no_lock_race_can_produce_more_than_one_acceptance():
    cache = ScriptCacheSim()
    nonce = "syn-nonce-baseline-no-lock"
    n_threads = 20
    barrier = threading.Barrier(n_threads)
    accepted_count = []
    accepted_lock = threading.Lock()

    def worker():
        barrier.wait()
        now = time.time()
        existing = cache.get(nonce, now=now)
        # 의도적으로 get과 put 사이에 지연을 끼워 넣어 경쟁 윈도우를 넓힌다
        # (실제 네트워크 호출 지연을 모사 — 락이 없으면 더 쉽게 깨짐을 보이기 위함).
        time.sleep(0.001)
        if existing is None:
            cache.put(nonce, str(now), 300, now=now)
            with accepted_lock:
                accepted_count.append(1)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    print(f"[BASELINE] Lock 없이 동시 {n_threads}건 중 '통과'로 판정된 건수: {len(accepted_count)}")
    # 이 테스트는 "항상 1보다 커야 한다"고 단정하지 않는다(타이밍에 따라 우연히
    # 1이 나올 수도 있다) — 요점은 Lock으로 감싼 시나리오 2(A/B)가 매번
    # 정확히 1을 내는 것과 달리, 이 베이스라인은 그 보장이 전혀 없다는 것이다.


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
