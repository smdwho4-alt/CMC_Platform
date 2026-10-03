# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — Replay 차단 격리 실측: Script Properties 로컬 시뮬레이션

*** 운영 채택안이 아니다. 소량 합성 데이터 비교 실험 전용. ***

공식 문서(2026-10-03 WebFetch, 설계 문서 §1-1) 확인 사실:
  - 전체 저장 한도 500KB/스토어, 값 최대 9KB/건
  - get/set/delete만 존재, 원자적 set-if-absent 없음(이번 조사 범위에서 확인)
  - 자동 TTL 만료가 없다 — CacheService의 put(key, value, ttl)과 달리
    expirationInSeconds 인자가 없다. 그래서 이 시뮬레이션에도 TTL 자동
    삭제 메서드를 두지 않는다(실제 PropertiesService에 없는 기능을
    시뮬레이션에만 추가하면 후보 .gs 코드와 불일치하게 된다).
  - 명시적 영속성 보장 문구는 이번 조사에서 확인하지 못했다(공백) — 이
    시뮬레이션은 "CacheService 시뮬레이션과 분리된 별도 dict"로만
    영속성 차이를 표현한다. 즉 ScriptCacheSim.remove()를 호출해도 이
    PropertiesServiceSim 내용은 전혀 영향받지 않는다 — 이것이 "지속
    저장소는 캐시 제거와 무관하다"는 시나리오의 근거다.
"""
from __future__ import annotations


PROPERTIES_TOTAL_LIMIT_BYTES = 500 * 1024
PROPERTIES_MAX_VALUE_BYTES = 9 * 1024


class PropertiesQuotaExceededError(Exception):
    pass


class ScriptPropertiesSim:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def _total_bytes(self, *, exclude_key: str | None = None) -> int:
        total = 0
        for k, v in self._store.items():
            if k == exclude_key:
                continue
            total += len(k.encode("utf-8")) + len(v.encode("utf-8"))
        return total

    def get_property(self, key: str) -> str | None:
        return self._store.get(key)

    def set_property(self, key: str, value: str) -> None:
        value_bytes = len(value.encode("utf-8"))
        if value_bytes > PROPERTIES_MAX_VALUE_BYTES:
            raise PropertiesQuotaExceededError(
                f"값 크기 {value_bytes}B > 9KB 한도"
            )
        prospective_total = self._total_bytes(exclude_key=key) + len(key.encode("utf-8")) + value_bytes
        if prospective_total > PROPERTIES_TOTAL_LIMIT_BYTES:
            raise PropertiesQuotaExceededError(
                f"전체 저장 한도 초과 예상({prospective_total}B > 500KB)"
            )
        self._store[key] = value

    def delete_property(self, key: str) -> None:
        self._store.pop(key, None)

    def item_count(self) -> int:
        return len(self._store)

    def total_bytes(self) -> int:
        return self._total_bytes()
