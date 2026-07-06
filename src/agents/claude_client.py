# -*- coding: utf-8 -*-
"""
CSHSP Claude Client — Sprint G
Claude API(Messages) 어댑터.

원칙:
- API Key는 절대 하드코딩하지 않는다 — 환경변수 ANTHROPIC_API_KEY로만 관리.
- Key가 없으면 Mock 모드로 동작한다 (플랫폼은 규칙 기반으로 계속 서비스 가능).
- timeout / retry 처리: 실 API는 SDK 내장(max_retries, timeout),
  커스텀 transport(테스트/Mock)는 자체 재시도 루프.

응답은 정규화된 dict로 반환:
  {"stop_reason": "end_turn|tool_use|refusal|...", "content": [{"type": "text"|"tool_use", ...}]}
"""
from __future__ import annotations

import os
import time
from typing import Any, Callable

DEFAULT_MODEL = os.environ.get("CSHSP_CLAUDE_MODEL", "claude-opus-4-8")
DEFAULT_MAX_TOKENS = 2048


class ClaudeClientError(Exception):
    """Claude 호출 실패 (재시도 소진 포함)"""


def _mock_transport(payload: dict[str, Any]) -> dict[str, Any]:
    """Mock 응답: 도구 없이 일반 안내 텍스트만 반환. (API Key 미설정 환경)"""
    return {
        "stop_reason": "end_turn",
        "content": [{
            "type": "text",
            "text": "[Mock 모드] Claude API Key가 설정되지 않아 규칙 기반 안내로 동작합니다. "
                    "검진 예약·프로그램 안내는 채팅 퀵버튼을 이용해 주세요.",
        }],
    }


class ClaudeClient:
    """Messages API 어댑터. transport 주입 시 해당 함수로 호출(테스트/Mock)."""

    def __init__(self, model: str = DEFAULT_MODEL,
                 transport: Callable[[dict], dict] | None = None,
                 timeout: float = 60.0, max_retries: int = 2):
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.attempts = 0  # 관측용: 총 시도 횟수
        self._sdk = None

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if transport is not None:
            self.mode = "custom"
            self._transport = transport
        elif api_key:
            try:
                import anthropic
                self._sdk = anthropic.Anthropic(timeout=timeout, max_retries=max_retries)
                self.mode = "live"
                self._transport = None
            except ImportError:
                self.mode = "mock"
                self._transport = _mock_transport
        else:
            self.mode = "mock"
            self._transport = _mock_transport

    @property
    def mock_mode(self) -> bool:
        return self.mode == "mock"

    def create_message(self, messages: list[dict], system: str | None = None,
                       tools: list[dict] | None = None,
                       max_tokens: int = DEFAULT_MAX_TOKENS) -> dict[str, Any]:
        """Messages 호출 후 정규화 dict 반환. 실패 시 ClaudeClientError."""
        payload: dict[str, Any] = {
            "model": self.model, "max_tokens": max_tokens, "messages": messages,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools

        if self._sdk is not None:
            # SDK가 429/5xx/연결오류를 max_retries만큼 자동 재시도
            try:
                self.attempts += 1
                resp = self._sdk.messages.create(**payload)
            except Exception as e:  # anthropic.APIError 계열 포함
                raise ClaudeClientError(f"Claude API 호출 실패: {e}") from e
            return {
                "stop_reason": resp.stop_reason,
                "content": [b.to_dict() if hasattr(b, "to_dict") else dict(b)
                            for b in resp.content],
            }

        # 커스텀/Mock transport — 자체 재시도 (지수 백오프)
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                self.attempts += 1
                return self._transport(payload)
            except (TimeoutError, ConnectionError, OSError) as e:
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(min(0.1 * (2 ** attempt), 2.0))
        raise ClaudeClientError(f"Claude 호출 실패 (재시도 {self.max_retries}회 소진): {last_err}")
