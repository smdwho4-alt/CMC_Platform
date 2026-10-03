# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — Replay 차단 격리 실측: nonce 만료 경계 계산(로컬 미러)

gas_candidate/NonceTtlBoundary_new.gs와 **동일한 공식**을 그대로 옮긴다.
유도 근거(서명 허용 종료시각 = timestamp + max_skew, 경계 포함)는 그
파일 상단 주석에 있으며 여기서 다시 풀어쓰지 않는다 — 두 곳에 서로 다른
숫자가 생기지 않도록 공식만 재정의한다.
"""
from __future__ import annotations

import math

CACHE_MIN_TTL_SECONDS = 1
CACHE_MAX_TTL_SECONDS = 21600


class NonceTtlConfigError(ValueError):
    """TTL 계산 자체의 설정 오류(margin 과다 등) — 조용히 자르지 않고 예외로 알린다."""


class NonceTtlInvariantViolated(AssertionError):
    """'서명이 아직 허용되는 시점에 nonce가 먼저 만료되지 않는가' 불변식 위반."""


def compute_signature_allowed_end_time(signed_timestamp: float, max_skew_seconds: float) -> float:
    return signed_timestamp + max_skew_seconds


def compute_remaining_signature_retention_seconds(
    now: float, signed_timestamp: float, max_skew_seconds: float
) -> float:
    allowed_end = compute_signature_allowed_end_time(signed_timestamp, max_skew_seconds)
    remaining = allowed_end - now
    if remaining < 0:
        raise NonceTtlConfigError(
            f"remaining={remaining} < 0 — 서명이 이미 만료된 envelope에 대해 "
            "호출됨(verify_v2 ACCEPTED 여부를 먼저 확인했는지 점검)"
        )
    return remaining


def compute_nonce_ttl_seconds(
    now: float, signed_timestamp: float, max_skew_seconds: float, margin_seconds: float
) -> int:
    remaining = compute_remaining_signature_retention_seconds(now, signed_timestamp, max_skew_seconds)
    raw_ttl = remaining + margin_seconds
    ttl = math.ceil(raw_ttl)  # CacheService TTL은 정수초 — 내림/버림 금지(안전 쪽으로 올림)
    if ttl < CACHE_MIN_TTL_SECONDS:
        ttl = CACHE_MIN_TTL_SECONDS
    if ttl > CACHE_MAX_TTL_SECONDS:
        raise NonceTtlConfigError(
            f"계산된 TTL({ttl}초)이 CacheService 상한({CACHE_MAX_TTL_SECONDS}초) 초과 — "
            "max_skew_seconds 또는 margin_seconds 재검토 필요(조용히 자르지 않음)"
        )
    return ttl


def assert_nonce_outlives_signature_window(
    record_time: float, ttl_seconds: int, signature_allowed_end: float
) -> None:
    nonce_expires_at = record_time + ttl_seconds
    if nonce_expires_at < signature_allowed_end:
        raise NonceTtlInvariantViolated(
            f"NONCE_TTL_INVARIANT_VIOLATED: nonce 만료시각({nonce_expires_at}) < "
            f"서명 허용 종료시각({signature_allowed_end})"
        )


# 참고: 이 모듈의 어떤 함수도 CacheService 비영속성 위험을 해소하지 않는다
# (NonceTtlBoundary_new.gs 하단 주석과 동일한 경고 — 중복이지만 로컬
# 미러에도 명시해 둔다. "TTL 계산이 맞다"와 "캐시가 유실되지 않는다"는
# 완전히 다른 명제다).
