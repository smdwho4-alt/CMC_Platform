# -*- coding: utf-8 -*-
"""
CSHSP Rate Limit — Sprint G
슬라이딩 윈도우 방식 기본 요청 제한 (키 단위: 세션ID/IP 등).

기본값은 환경변수 CSHSP_CHAT_RATE ("요청수/초", 예: "30/60")로 조정한다.
프로세스 메모리 기반 — 다중 인스턴스 배포 시 Redis 카운터로 교체.
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque


def rate_from_env(default: str = "30/60") -> tuple[int, int]:
    raw = os.environ.get("CSHSP_CHAT_RATE", default)
    try:
        n, w = raw.split("/")
        return max(1, int(n)), max(1, int(w))
    except ValueError:
        return 30, 60


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """key의 요청 허용 여부. 허용 시 기록까지 수행."""
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.max_requests:
                return False
            q.append(now)
            return True

    def remaining(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            q = self._hits.get(key, deque())
            while q and now - q[0] > self.window:
                q.popleft()
            return max(0, self.max_requests - len(q))
