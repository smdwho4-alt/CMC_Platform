# -*- coding: utf-8 -*-
"""
CSHSP Reservation State Machine — Sprint B

예약 상태 전이표 (Sprint B 확정):

  REQUESTED ──────────→ PENDING_APPROVAL ──→ CONFIRMED ──→ COMPLETED
      │                        │                 │
      ├→ CANCELLED             ├→ CANCELLED      ├→ CANCELLED
      └→ REJECTED              └→ REJECTED       ├→ NO_SHOW   (CONFIRMED에서만)
                                                 └→ CHANGED ──→ PENDING_APPROVAL

  WAITING(대기예약) → PENDING_APPROVAL / CANCELLED / REJECTED  (Sprint B 확장)

잘못된 전이는 InvalidTransitionError로 차단한다.
"""
from __future__ import annotations

RESERVATION_TRANSITIONS: dict[str, set[str]] = {
    "REQUESTED":        {"PENDING_APPROVAL", "CANCELLED", "REJECTED"},
    "PENDING_APPROVAL": {"CONFIRMED", "CANCELLED", "REJECTED"},
    "CONFIRMED":        {"COMPLETED", "CANCELLED", "CHANGED", "NO_SHOW"},
    "CHANGED":          {"PENDING_APPROVAL"},
    "WAITING":          {"PENDING_APPROVAL", "CANCELLED", "REJECTED"},
    "COMPLETED":        set(),
    "CANCELLED":        set(),
    "NO_SHOW":          set(),
    "REJECTED":         set(),
}

TERMINAL_STATES = {s for s, nxt in RESERVATION_TRANSITIONS.items() if not nxt}

# 취소 가능 상태 (스펙: REQUESTED / PENDING_APPROVAL / CONFIRMED + WAITING 확장)
CANCELLABLE_STATES = {s for s, nxt in RESERVATION_TRANSITIONS.items() if "CANCELLED" in nxt}
# 거절 가능 상태 (스펙: REQUESTED / PENDING_APPROVAL + WAITING 확장)
REJECTABLE_STATES = {s for s, nxt in RESERVATION_TRANSITIONS.items() if "REJECTED" in nxt}


class InvalidTransitionError(Exception):
    """허용되지 않는 상태 전이"""

    def __init__(self, current: str, target: str):
        self.current, self.target = current, target
        super().__init__(f"허용되지 않는 상태 전이: {current} → {target} "
                         f"(허용: {sorted(RESERVATION_TRANSITIONS.get(current, set())) or '없음(종결 상태)'})")


def can_transition(current: str, target: str) -> bool:
    """current → target 전이 허용 여부"""
    return target in RESERVATION_TRANSITIONS.get(current, set())


def assert_transition(current: str, target: str) -> None:
    """전이 불가 시 InvalidTransitionError 발생"""
    if current not in RESERVATION_TRANSITIONS:
        raise InvalidTransitionError(current, target)
    if not can_transition(current, target):
        raise InvalidTransitionError(current, target)


def allowed_next(current: str) -> list[str]:
    """현재 상태에서 전이 가능한 상태 목록"""
    return sorted(RESERVATION_TRANSITIONS.get(current, set()))
