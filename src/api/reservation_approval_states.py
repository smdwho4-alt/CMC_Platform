# -*- coding: utf-8 -*-
"""
Sheets 예약 승인 State Machine — Sprint 4 Commit 2(Reservation Approval Foundation)

로컬 JSON의 9-상태 머신(reservation/state_machine.py)과는 별개로, Google Sheets
예약상태(한글) 도메인에서 이번 Commit이 다루는 전이만 최소로 정의한다.

PM 결정 1(Sprint4_Commit2_Implementation_Plan_v1.0.md §12-1): 별도 "승인대기"
상태를 신설하지 않고 기존 '예약접수'를 승인 대기 상태로 재사용한다. 이번 Commit이
허용하는 전이는 다음 두 가지뿐이다.

    예약접수 → 예약확정
    예약접수 → 거절

그 외 상태(검진중/검진완료/일정변경/예약취소 등)와 그 전이는 기존
admin_reservations_v2_new.html이 계속 담당하므로 이 모듈은 관여하지 않는다.
Slot/정원 검사는 Commit 3 범위이며 이 모듈에 포함하지 않는다.
"""
from __future__ import annotations

SHEETS_APPROVAL_TRANSITIONS: dict[str, set[str]] = {
    "예약접수": {"예약확정", "거절"},
}


class InvalidApprovalTransitionError(Exception):
    """허용되지 않는 승인/거절 전이 — 이미 처리됐거나 승인 대상 상태가 아님."""

    def __init__(self, current: str, target: str):
        self.current, self.target = current, target
        super().__init__(f"허용되지 않는 승인 전이: {current} → {target}")


def can_transition(current_status: str, target_status: str) -> bool:
    return target_status in SHEETS_APPROVAL_TRANSITIONS.get(current_status, set())


def assert_can_transition(current_status: str, target_status: str) -> None:
    if not can_transition(current_status, target_status):
        raise InvalidApprovalTransitionError(current_status, target_status)
