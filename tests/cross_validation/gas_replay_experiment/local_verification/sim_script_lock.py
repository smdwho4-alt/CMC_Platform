# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — Replay 차단 격리 실측: Script Lock 로컬 시뮬레이션

이 모듈은 실제 GAS LockService를 실행하지 않는다. 공식 문서(2026-10-03
WebFetch, 설계 문서 §1-1)에서 확인한 Lock 클래스의 **동작 계약**만을
그대로 모사한다:

  - tryLock(timeout_ms) -> bool (타임아웃 시 False, 예외 아님)
  - waitLock(timeout_ms) -> None, 타임아웃 시 예외(LockTimeoutError)
  - releaseLock() -> None (여러 번 호출해도 안전)
  - hasLock() -> bool

내부적으로는 진짜 OS 스레딩 기본 요소(threading.Lock)를 사용한다 — 즉
이 시뮬레이션에서의 "동시 요청" 테스트는 실제 OS 스레드 간 경쟁이며,
한 실행 안에서 순차적으로 반복 호출하는 것이 아니다(요청사항: "같은
실행 안의 반복 호출을 동시성 실측이라고 표현하지 않는다"를 지키기 위해
threading 기반으로 구현했다).

Script Lock의 "사용자 신원과 무관한 전역 상호배제"라는 스코프 의미는,
이 시뮬레이션에서 **프로세스 전체에 단 하나의 공유 Lock 인스턴스**를
쓰는 것으로 표현한다 — 여러 "사용자"를 흉내 내는 스레드가 전부 같은
인스턴스를 공유해야 Script Lock과 같은 의미가 된다(User Lock이었다면
사용자별로 별도 Lock 인스턴스가 필요했을 것이나, 이번 실험은 User Lock을
다루지 않는다).
"""
from __future__ import annotations

import threading
import time


class LockTimeoutError(Exception):
    """waitLock() 타임아웃 시 발생 — 공식 문서: "throws an exception when
    the lock could not be acquired instead of returning false"."""


class ScriptLockSim:
    """GAS LockService.getScriptLock()의 계약만 모사한다. 실제 GAS
    보유시간·quota 제약은 공식 문서에 게재되어 있지 않았다(조사 공백) —
    이 시뮬레이션은 그런 제약을 재현하지 않는다(재현했다고 주장하지 않음)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._held_by_thread: threading.Thread | None = None

    def try_lock(self, timeout_ms: int) -> bool:
        acquired = self._lock.acquire(timeout=timeout_ms / 1000.0)
        if acquired:
            self._held_by_thread = threading.current_thread()
        return acquired

    def wait_lock(self, timeout_ms: int) -> None:
        acquired = self._lock.acquire(timeout=timeout_ms / 1000.0)
        if not acquired:
            raise LockTimeoutError(
                f"waitLock 타임아웃({timeout_ms}ms) — 공식 문서상 waitLock은 "
                "false를 반환하지 않고 예외를 던진다."
            )
        self._held_by_thread = threading.current_thread()

    def has_lock(self) -> bool:
        return self._held_by_thread is threading.current_thread()

    def release_lock(self) -> None:
        if self._held_by_thread is threading.current_thread():
            self._held_by_thread = None
            try:
                self._lock.release()
            except RuntimeError:
                pass
