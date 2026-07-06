# -*- coding: utf-8 -*-
"""
CSHSP Session Store — Sprint G
채팅 세션(본인확인 상태) 영속화 계층.

- SessionStore: 공통 인터페이스 — Redis 교체 시 이 인터페이스만 구현하면 된다
  (RedisSessionStore(get/set/delete)를 동일 시그니처로 작성 후 라우터 주입 교체).
- FileSessionStore: JSON 파일 기반 (서버 재시작에도 본인확인 상태 유지)
- MemorySessionStore: 테스트/개발용

저장 최소화 원칙: verifyState / patientId / pendingCode만 저장한다 (대화 내용 저장 안 함).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

DEFAULT_SESSION = {"verifyState": "UNVERIFIED", "patientId": None, "pendingCode": None}


class SessionStore:
    """세션 저장소 인터페이스"""

    def get(self, sid: str) -> dict[str, Any]:
        raise NotImplementedError

    def set(self, sid: str, data: dict[str, Any]) -> None:
        raise NotImplementedError

    def delete(self, sid: str) -> None:
        raise NotImplementedError


class MemorySessionStore(SessionStore):
    def __init__(self):
        self._data: dict[str, dict] = {}

    def get(self, sid: str) -> dict[str, Any]:
        return self._data.setdefault(sid, dict(DEFAULT_SESSION))

    def set(self, sid: str, data: dict[str, Any]) -> None:
        self._data[sid] = data

    def delete(self, sid: str) -> None:
        self._data.pop(sid, None)


class FileSessionStore(SessionStore):
    """JSON 파일 영속화. 프로세스 내 스레드 잠금 + 즉시 저장."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, sid: str) -> dict[str, Any]:
        with self._lock:
            if sid not in self._data:
                self._data[sid] = dict(DEFAULT_SESSION)
                self._save()
            return self._data[sid]

    def set(self, sid: str, data: dict[str, Any]) -> None:
        with self._lock:
            self._data[sid] = data
            self._save()

    def delete(self, sid: str) -> None:
        with self._lock:
            self._data.pop(sid, None)
            self._save()
