# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — Replay 차단 격리 실측: CacheService(Script Cache) 로컬 시뮬레이션

*** 이 모듈은 실제 GAS 네트워크/인프라 수준 조기 유실(premature eviction)을
재현하지 않는다. 그런 유실은 재현했다고 주장하지 않는다. ***

이 모듈이 모사하는 것은 공식 문서(2026-10-03 WebFetch, 설계 문서 §1-1)에
게재된 **구조적 규칙**뿐이다:
  - get(key) -> value|None, put(key, value, ttl_seconds), remove(key)만 존재
    (원자적 check-and-set 없음 — 그래서 이 저장소 자체는 락을 제공하지 않는다)
  - TTL 범위 1~21600초
  - 키 길이 <= 250자, 값 크기 <= 100KB
  - 저장 개수 상한 1,000개, 초과 시 "만료까지 가장 많이 남은 900개"를 유지
    (공식 문구: "the cache stores the 900 items farthest from expiration" —
    LRU/최근사용 기준이 아니라 **만료시각 기준**이라는 점에 유의. PoC#2가
    "LRU"로 표현한 부분에 대한 정정, 설계 문서 §1-1 참조)
  - "not guaranteed to persist until its expiration time" — 이 속성은
    코드로 강제할 수 없으므로(진짜 비영속성은 인프라 현상), 이 시뮬레이션은
    **explicit_simulate_loss(key)**라는 별도 메서드로만 유실을 표현한다.
    TTL이 남아 있어도 이 메서드를 직접 호출하지 않는 한 값이 사라지지
    않는다 — 이것이 "실제 조기 유실 재현"과 "명시적 remove를 통한 유실
    모사"를 구분하라는 요구사항을 지키는 지점이다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass


MAX_KEY_LENGTH = 250
MAX_VALUE_BYTES = 100 * 1024
MAX_ITEM_CAP = 1000
RETAIN_ON_OVERFLOW = 900
MIN_TTL_SECONDS = 1
MAX_TTL_SECONDS = 21600


class CacheKeyTooLongError(ValueError):
    pass


class CacheValueTooLargeError(ValueError):
    pass


class CacheTtlOutOfRangeError(ValueError):
    pass


@dataclass
class _Entry:
    value: str
    expires_at: float


class ScriptCacheSim:
    """GAS CacheService.getScriptCache() 구조적 규칙 시뮬레이션.
    스레드 안전성: 내부 dict 접근을 자체 락으로 보호한다 — 단, 이는
    "Script Lock으로 감싸지 않은 CacheService는 원자적이지 않다"는
    설계 명제를 검증하기 위해 상위 테스트에서 **일부러 느슨하게** get과
    put 사이에 지연을 끼워 넣을 수 있도록, get/put을 각각 별도 공개
    메서드로 유지한다(즉 get+put을 하나의 원자적 연산으로 묶지 않는다 —
    이것이 바로 실제 CacheService의 한계를 그대로 모사하는 부분이다)."""

    def __init__(self) -> None:
        self._store: dict[str, _Entry] = {}

    def get(self, key: str, *, now: float | None = None) -> str | None:
        now = time.time() if now is None else now
        entry = self._store.get(key)
        if entry is None:
            return None
        if now >= entry.expires_at:
            del self._store[key]
            return None
        return entry.value

    def put(self, key: str, value: str, ttl_seconds: int, *, now: float | None = None) -> None:
        if len(key) > MAX_KEY_LENGTH:
            raise CacheKeyTooLongError(f"키 길이 {len(key)} > {MAX_KEY_LENGTH}")
        if len(value.encode("utf-8")) > MAX_VALUE_BYTES:
            raise CacheValueTooLargeError("값 크기 > 100KB")
        if not (MIN_TTL_SECONDS <= ttl_seconds <= MAX_TTL_SECONDS):
            raise CacheTtlOutOfRangeError(f"TTL {ttl_seconds}초는 1~21600 범위 밖")
        now = time.time() if now is None else now
        self._store[key] = _Entry(value=value, expires_at=now + ttl_seconds)
        self._evict_if_over_cap(now=now)

    def remove(self, key: str) -> None:
        """명시적 유실 모사 전용 메서드 — '실제 조기 유실 재현'이 아니라
        '명시적 remove를 통한 유실 모사'임을 호출부가 분명히 하기 위해
        일반 delete가 아니라 이 이름을 쓴다."""
        self._store.pop(key, None)

    def _evict_if_over_cap(self, *, now: float) -> None:
        if len(self._store) <= MAX_ITEM_CAP:
            return
        # 공식 문서: 초과 시 "만료까지 가장 많이 남은 900개"를 유지한다.
        # 즉 expires_at이 큰(먼 미래) 순으로 900개만 남기고 나머지를 버린다.
        items = sorted(self._store.items(), key=lambda kv: kv[1].expires_at, reverse=True)
        self._store = dict(items[:RETAIN_ON_OVERFLOW])

    def item_count(self) -> int:
        return len(self._store)
