# -*- coding: utf-8 -*-
"""
CSHSP Conversation Manager — Sprint H
멀티턴 대화 히스토리 영속화 (Claude tool_loop 입력용).

- 저장 파일: data/chat_histories.json  {sessionId: [Claude 메시지 배열]}
- 히스토리는 LLM 연속성에 필요한 '운영 대화 상태'로, 로그가 아니다.
  민감데이터로 취급: 로그로 내보내지 않으며, 세션당 최대 메시지 수를 제한한다.
- 트리밍 시 tool_use/tool_result 짝이 깨지지 않도록 일반 user 턴 경계에서 자른다.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src" / "api"))

from file_lock import DataLock  # noqa: E402

MAX_MESSAGES = 30  # 세션당 보존 메시지 수 (초과 시 앞에서 트리밍)


class ConversationManager:
    def __init__(self, data_dir: Path | str, max_messages: int = MAX_MESSAGES):
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / "chat_histories.json"
        self.max_messages = max_messages
        self._lock = threading.RLock()

    def _load(self) -> dict[str, list]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return {}

    def _write(self, data: dict[str, list]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _trim(history: list[dict], max_messages: int) -> list[dict]:
        """최근 max_messages개로 제한하되, 첫 메시지가 '일반 user 턴'이 되도록 정렬.
        (tool_result로 시작하는 잘린 히스토리는 API가 거부한다)"""
        if len(history) <= max_messages:
            return history
        trimmed = history[-max_messages:]
        for i, msg in enumerate(trimmed):
            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                return trimmed[i:]
        return []  # 안전한 시작점이 없으면 새 대화로 시작

    def get_history(self, session_id: str) -> list[dict]:
        with self._lock, DataLock(self.data_dir):
            return self._load().get(session_id, [])

    def save_history(self, session_id: str, history: list[dict]) -> None:
        with self._lock, DataLock(self.data_dir):
            data = self._load()
            data[session_id] = self._trim(list(history), self.max_messages)
            self._write(data)

    def clear(self, session_id: str) -> None:
        with self._lock, DataLock(self.data_dir):
            data = self._load()
            if session_id in data:
                del data[session_id]
                self._write(data)
