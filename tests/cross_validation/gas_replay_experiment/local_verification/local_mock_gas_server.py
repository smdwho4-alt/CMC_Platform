# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — Replay 차단 격리 실측: 로컬 모의 HTTP 서버(v2)

*** 이것은 GAS가 아니다. 실제 GAS Web App을 배포·실행하지 않는다. ***
Main_doPost_stub_new.gs(v2: action 기반 exec/status 통합 디스패치 +
서버측 예산 가드)와 동일한 처리 순서를 `http.server.ThreadingHTTPServer`
(진짜 동시 연결 처리)로 로컬 재현한다.

처리 순서(Main_doPost_stub_new.gs와 동일):
  1) action/variant 유효성 → 2) 서명 검증 → 3) 예산·종료시각 가드
  → 4) action=="status"면 읽기 전용 응답, action=="exec"면 nonce 가드
  → 업무 카운터 증가.

라우트: POST /exec, POST /status만 존재한다. **비인증 GET /status는
더 이상 존재하지 않는다**(요청사항 2-1 반영) — 어떤 GET 요청도 404다.
remove/reset/cleanup에 대응하는 라우트는 여전히 없다.

LockService 모델 수정: 이전 버전은 variant A/B에 서로 다른 Lock 인스턴스를
썼는데, 이는 실제 GAS가 **스크립트당 단 하나의 Script Lock만 가진다**는
사실과 어긋났다(LockService.getScriptLock()은 매번 같은 단일 락을 가리킴).
이번 버전은 예산 가드·Variant A·Variant B가 전부 **같은 하나의 Lock
인스턴스**를 공유한다 — 실제 GAS에서 LockService.getScriptLock()을 여러
함수에서 호출해도 전부 같은 락인 것과 동일하게 맞췄다.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from replay_guard import (  # noqa: E402
    check_and_record_nonce_variant_a_cache_lock,
    check_and_record_nonce_variant_b_properties_lock,
    verify_signature_real,
)
from server_budget_guard import check_and_consume_request_budget  # noqa: E402
from sim_cache_service import ScriptCacheSim  # noqa: E402
from sim_properties_service import ScriptPropertiesSim  # noqa: E402
from sim_script_lock import ScriptLockSim  # noqa: E402
from idempotency.signing_v2 import KeyRecord, KeyRegistry  # noqa: E402


class ServerState:
    """하나의 GAS 스크립트 인스턴스가 요청 간에 공유할 전역 상태.
    lock은 **하나뿐**이다(실제 LockService.getScriptLock()과 동일)."""

    def __init__(self, *, key_id: str, secret: str) -> None:
        self.registry = KeyRegistry()
        self.registry.register(KeyRecord(key_id=key_id, secret=secret, state="ACTIVE"))
        self.lock = ScriptLockSim()  # 예산 가드·Variant A·Variant B 공용(실제 GAS와 동일)
        self.cache = ScriptCacheSim()
        self.props = ScriptPropertiesSim()  # 예산 카운터와 Variant B nonce가 같은 스토어를 공유(실제와 동일)
        self.business_counter_lock = threading.Lock()
        self.business_counter = {"A": 0, "B": 0}

    def increment_business_counter(self, variant: str) -> int:
        with self.business_counter_lock:
            self.business_counter[variant] += 1
            return self.business_counter[variant]

    def get_business_counter(self, variant: str) -> int:
        with self.business_counter_lock:
            return self.business_counter[variant]


def _preprocess_public_request(state: ServerState, request: dict, expected_action: str, expected_action_prefix: str) -> dict:
    """Main_doPost_stub_new.gs의 preprocessPublicRequest_()와 동일(엄격 일치).

    **now는 서버 자신의 시계(time.time())로만 계산한다.** 요청 본문에
    "now" 필드가 있어도 절대 읽지 않는다 — 드라이런에서 실제로 발견된
    설계 결함(클라이언트가 주장하는 now를 그대로 신뢰하면 서명 스큐
    검사·nonce TTL이 전부 무력화됨)을 고친 것이다."""
    server_now = time.time()

    if request.get("action") != expected_action:
        return {"ok": False, "stage": "ACTION_INVALID", "detail": {"action": request.get("action"), "expected": expected_action}}
    if request.get("variant") not in ("A", "B"):
        return {"ok": False, "stage": "VARIANT_INVALID", "detail": {"variant": request.get("variant")}}

    verify_result = verify_signature_real(
        registry=state.registry, method=request["method"], operation=request["operation"],
        timestamp=request["timestamp"], nonce=request["nonce"], idempotency_key=request["idempotency_key"],
        key_id=request["key_id"], payload=request["payload"], signature=request["signature"],
        now=server_now, max_skew_seconds=request["max_skew_seconds"],
    )
    if verify_result.classification != "ACCEPTED":
        return {"ok": False, "stage": "SIGNATURE_REJECTED", "detail": {"classification": verify_result.classification}}

    expected_token = expected_action_prefix + request["variant"]
    if expected_token not in request["operation"]:
        return {"ok": False, "stage": "SIGNATURE_REJECTED", "detail": {"classification": "OPERATION_ACTION_VARIANT_MISMATCH"}}

    budget = check_and_consume_request_budget(server_now, lock=state.lock, props=state.props)
    if budget.outcome != "WITHIN_BUDGET":
        return {"ok": False, "stage": "SERVER_LIMIT_" + budget.outcome, "detail": {
            "request_count": budget.request_count, "elapsed_seconds": budget.elapsed_seconds,
        }}

    return {"ok": True, "now": server_now}


def _do_post_(state: ServerState, request: dict) -> dict:
    pre = _preprocess_public_request(state, request, "exec", "replay_experiment.variant")
    if not pre["ok"]:
        return {"stage": pre["stage"], "detail": pre["detail"]}

    signed_ts = float(request["timestamp"])
    variant = request["variant"]
    if variant == "A":
        nonce_result = check_and_record_nonce_variant_a_cache_lock(
            request["nonce"], pre["now"], signed_ts, lock=state.lock, cache=state.cache,
            max_skew_seconds=request["max_skew_seconds"],
        )
    else:
        nonce_result = check_and_record_nonce_variant_b_properties_lock(
            request["nonce"], pre["now"], signed_ts, lock=state.lock, props=state.props,
            max_skew_seconds=request["max_skew_seconds"],
        )

    if nonce_result.outcome != "ACCEPTED":
        return {"stage": "NONCE_REJECTED_OR_BLOCKED", "detail": {"outcome": nonce_result.outcome}}

    counter_value = state.increment_business_counter(variant)
    return {"stage": "BUSINESS_EXECUTED", "detail": {"nonce": request["nonce"], "businessCounter": counter_value}}


def _do_status_(state: ServerState, request: dict) -> dict:
    """읽기 전용 — nonce 가드 호출 없음, 업무 카운터 증가 없음."""
    pre = _preprocess_public_request(state, request, "status", "replay_experiment.status.variant")
    if not pre["ok"]:
        return {"stage": pre["stage"], "detail": pre["detail"]}

    variant = request["variant"]
    return {"stage": "STATUS_OK", "detail": {"variant": variant, "businessCounter": state.get_business_counter(variant)}}


def make_handler(state: ServerState):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def _respond_json(self, status: int, result: dict) -> None:
            body = json.dumps(result).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            # *** 실제 GAS Web App은 URL 경로로 라우팅하지 않는다 — 배포된
            # 단일 URL(.../exec)에 들어오는 모든 POST가 doPost(e) 하나로만
            # 간다. 경로가 무엇이든(쿼리스트링 등 부가 정보 제외) 전부 같은
            # 처리를 한다 — RealEntryPoint_new.gs의 doPost(e)와 동일하게
            # body.action으로만 라우팅한다(이전 버전은 /exec, /status를
            # 별도 URL 경로로 오인해 실제 GAS와 다르게 동작했었다 — 수정). ***
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                request = json.loads(raw.decode("utf-8"))
            except Exception:  # pragma: no cover
                # RealEntryPoint_new.gs doPost(e)는 파싱 실패를 try/catch로
                # 잡아 정상적인 ContentService 200 응답으로 돌려준다
                # (예외를 던지지 않으므로 GAS의 범용 500 오류 페이지가 아님).
                self._respond_json(200, {"stage": "MALFORMED_REQUEST_BODY", "detail": {}})
                return

            action = request.get("action")
            try:
                if action == "exec":
                    result = _do_post_(state, request)
                elif action == "status":
                    result = _do_status_(state, request)
                else:
                    # ROUTES_ALLOWLIST_에 exec/status 외의 값은 없다 — remove 등도 여기로 와서 거부된다.
                    result = {"stage": "ACTION_INVALID", "detail": {"action": action}}
            except Exception as e:  # pragma: no cover - 방어적(예상 밖 입력에 의한 내부 오류)
                result = {"stage": "SERVER_ERROR", "detail": {"error": str(e)}}
            self._respond_json(200, result)

        def do_GET(self):
            # 실제 GAS doGet(e)과 동일하게, 경로와 무관하게 항상 같은
            # METHOD_NOT_ALLOWED 응답을 200으로 돌려준다(GAS Web App에는
            # 404라는 개념이 없다 — ContentService 응답은 항상 200이다).
            self._respond_json(200, {"stage": "METHOD_NOT_ALLOWED", "detail": {}})

        # remove/reset/cleanup에 대응하는 별도 처리 경로는 애초에 없다
        # (action 디스패치 테이블에 exec/status만 있으므로 자동으로 거부됨).

    return Handler


class LocalMockGasServer:
    def __init__(self, *, key_id: str, secret: str) -> None:
        self.state = ServerState(key_id=key_id, secret=secret)
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.state))
        self._thread: Optional[threading.Thread] = None

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def __enter__(self) -> "LocalMockGasServer":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
