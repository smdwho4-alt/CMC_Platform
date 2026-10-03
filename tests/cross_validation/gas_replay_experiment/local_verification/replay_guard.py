# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — Replay 차단 격리 실측: 로컬 가드 로직

이 모듈은 gas_candidate/VariantA_CacheLock_new.gs,
gas_candidate/VariantB_PropertiesLock_new.gs와 **동일한 제어 흐름**을
Python으로 옮긴 것이다 — 로컬 검증이 실제로 후보 .gs 코드와 같은
알고리즘을 검증하도록 하기 위함이다(다른 로직을 만들어 놓고 검증했다고
말하지 않기 위해).

서명 검증은 스텁이 아니라 **실제** `src/idempotency/signing_v2.py`의
`verify_v2`/`KeyRegistry`/`KeyRecord`를 그대로 가져와 쓴다 — 이미 검증된
운영급 로직을 재사용하고, 이번 실험이 다루는 nonce 가드(Cache/Lock vs
Properties/Lock) 비교에만 집중한다.

EXPERIMENT_NONCE_TTL_SECONDS 유도 근거는
gas_candidate/ExperimentConfig_new.gs 상단 주석과 동일하다(여기서 다시
풀어 쓰지 않고 그 파일을 근거 문서로 가리킨다 — 두 곳에 서로 다른
숫자가 생기는 것을 막기 위해 상수만 재정의하고 유도 설명은 원본에 둔다).
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# 저장소 루트 기준 상대 경로로 계산한다(특정 로컬 머신의 절대 경로를
# 하드코딩하지 않음) — 이 파일 위치: tests/cross_validation/
# gas_replay_experiment/local_verification/ 이므로 4단계 위가 저장소 루트.
_REPO_SRC = Path(__file__).resolve().parents[4] / "src"
if str(_REPO_SRC) not in sys.path:
    sys.path.insert(0, str(_REPO_SRC))

from idempotency.signing_v2 import (  # noqa: E402
    KeyRecord,
    KeyRegistry,
    VerificationResult,
    verify_v2,
)

from sim_script_lock import ScriptLockSim  # noqa: E402
from sim_cache_service import ScriptCacheSim  # noqa: E402
from sim_properties_service import PropertiesQuotaExceededError, ScriptPropertiesSim  # noqa: E402
from nonce_ttl_boundary import (  # noqa: E402
    compute_nonce_ttl_seconds,
    compute_signature_allowed_end_time,
    assert_nonce_outlives_signature_window,
    NonceTtlConfigError,
    NonceTtlInvariantViolated,
)


# ExperimentConfig_new.gs와 동일한 값(유도 근거는 그 파일 참조)
EXPERIMENT_MAX_SKEW_SECONDS = 120
EXPERIMENT_NONCE_TTL_SECONDS_MIN = 2 * EXPERIMENT_MAX_SKEW_SECONDS  # 240 (이론적 최소값, 참고용)
EXPERIMENT_NONCE_TTL_SECONDS_WITH_MARGIN = 300  # 참고/비교용 — 동적 계산의 대조군(고정값이었다면)
EXPERIMENT_TTL_MARGIN_SECONDS = 30  # 동적 TTL 계산에 더하는 처리 지연 여유분(실험 설정값)
DEFAULT_LOCK_WAIT_TIMEOUT_MS = 5000


@dataclass(frozen=True)
class NonceGuardOutcome:
    outcome: str  # "ACCEPTED" | "REJECTED_REPLAY" | "BLOCKED_LOCK_TIMEOUT" | "BLOCKED_STORE_ERROR"
    error: Optional[str] = None


def verify_signature_real(
    *,
    registry: KeyRegistry,
    method: str,
    operation: str,
    timestamp: str,
    nonce: str,
    idempotency_key: str,
    key_id: str,
    payload: dict,
    signature: str,
    now: float,
    max_skew_seconds: int = EXPERIMENT_MAX_SKEW_SECONDS,
) -> VerificationResult:
    """signing_v2.verify_v2()를 그대로 호출한다(재구현 아님)."""
    return verify_v2(
        registry=registry,
        protocol_version="2",
        method=method,
        operation=operation,
        timestamp=timestamp,
        nonce=nonce,
        idempotency_key=idempotency_key,
        key_id=key_id,
        payload=payload,
        signature=signature,
        now=now,
        max_skew_seconds=max_skew_seconds,
    )


def check_and_record_nonce_variant_a_cache_lock(
    nonce: str,
    now_epoch_seconds: float,
    signed_timestamp_epoch_seconds: float,
    *,
    lock: ScriptLockSim,
    cache: ScriptCacheSim,
    max_skew_seconds: float = EXPERIMENT_MAX_SKEW_SECONDS,
    margin_seconds: float = EXPERIMENT_TTL_MARGIN_SECONDS,
    lock_timeout_ms: int = DEFAULT_LOCK_WAIT_TIMEOUT_MS,
) -> NonceGuardOutcome:
    """VariantA_CacheLock_new.gs의 checkAndRecordNonce_VariantA_CacheLock_()와
    동일한 제어 흐름. TTL은 고정값이 아니라 이 요청의 실제
    signed_timestamp_epoch_seconds로부터 매번 동적으로 계산한다."""
    acquired = lock.try_lock(lock_timeout_ms)
    if not acquired:
        return NonceGuardOutcome(outcome="BLOCKED_LOCK_TIMEOUT")
    try:
        try:
            existing = cache.get(nonce, now=now_epoch_seconds)
        except Exception as e:  # pragma: no cover - 저장소 오류 fail-closed 경로
            return NonceGuardOutcome(outcome="BLOCKED_STORE_ERROR", error=str(e))

        if existing is not None:
            return NonceGuardOutcome(outcome="REJECTED_REPLAY")

        try:
            signature_allowed_end = compute_signature_allowed_end_time(
                signed_timestamp_epoch_seconds, max_skew_seconds
            )
            ttl_seconds = compute_nonce_ttl_seconds(
                now_epoch_seconds, signed_timestamp_epoch_seconds, max_skew_seconds, margin_seconds
            )
            assert_nonce_outlives_signature_window(now_epoch_seconds, ttl_seconds, signature_allowed_end)
            cache.put(nonce, str(now_epoch_seconds), ttl_seconds, now=now_epoch_seconds)
        except (NonceTtlConfigError, NonceTtlInvariantViolated) as e:
            return NonceGuardOutcome(outcome="BLOCKED_STORE_ERROR", error=str(e))
        except Exception as e:
            return NonceGuardOutcome(outcome="BLOCKED_STORE_ERROR", error=str(e))

        return NonceGuardOutcome(outcome="ACCEPTED")
    finally:
        lock.release_lock()


def check_and_record_nonce_variant_b_properties_lock(
    nonce: str,
    now_epoch_seconds: float,
    signed_timestamp_epoch_seconds: float,
    *,
    lock: ScriptLockSim,
    props: ScriptPropertiesSim,
    max_skew_seconds: float = EXPERIMENT_MAX_SKEW_SECONDS,
    margin_seconds: float = EXPERIMENT_TTL_MARGIN_SECONDS,
    lock_timeout_ms: int = DEFAULT_LOCK_WAIT_TIMEOUT_MS,
) -> NonceGuardOutcome:
    """VariantB_PropertiesLock_new.gs의
    checkAndRecordNonce_VariantB_PropertiesLock_()와 동일한 제어 흐름.
    Cache 변형과 동일한 expiresAt(=recordTime+ttlSeconds) 경계 규약을 쓴다."""
    acquired = lock.try_lock(lock_timeout_ms)
    if not acquired:
        return NonceGuardOutcome(outcome="BLOCKED_LOCK_TIMEOUT")
    try:
        key = f"nonce_{nonce}"
        try:
            existing_raw = props.get_property(key)
        except Exception as e:  # pragma: no cover
            return NonceGuardOutcome(outcome="BLOCKED_STORE_ERROR", error=str(e))

        if existing_raw is not None:
            record_time_str, ttl_str = existing_raw.split(":")
            existing_expires_at = float(record_time_str) + float(ttl_str)
            if now_epoch_seconds < existing_expires_at:
                return NonceGuardOutcome(outcome="REJECTED_REPLAY")
            # now >= existing_expires_at: Cache의 자동 삭제와 동일한 경계에서
            # 여기서는 "덮어쓰기 허용"으로 같은 효과를 낸다(VariantB .gs 동일 주석 참조).

        try:
            signature_allowed_end = compute_signature_allowed_end_time(
                signed_timestamp_epoch_seconds, max_skew_seconds
            )
            ttl_seconds = compute_nonce_ttl_seconds(
                now_epoch_seconds, signed_timestamp_epoch_seconds, max_skew_seconds, margin_seconds
            )
            assert_nonce_outlives_signature_window(now_epoch_seconds, ttl_seconds, signature_allowed_end)
            props.set_property(key, f"{now_epoch_seconds}:{ttl_seconds}")
        except PropertiesQuotaExceededError as e:
            return NonceGuardOutcome(outcome="BLOCKED_STORE_ERROR", error=str(e))
        except (NonceTtlConfigError, NonceTtlInvariantViolated) as e:
            return NonceGuardOutcome(outcome="BLOCKED_STORE_ERROR", error=str(e))
        except Exception as e:  # pragma: no cover
            return NonceGuardOutcome(outcome="BLOCKED_STORE_ERROR", error=str(e))

        return NonceGuardOutcome(outcome="ACCEPTED")
    finally:
        lock.release_lock()
