# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — Replay 차단 격리 실측: 실제 동시 HTTP 드라이버(v2)

*** 이번 턴에서는 이 드라이버를 로컬 모의 서버(local_mock_gas_server.py)
에만 사용한다. 실제 GAS URL로 실행하지 않는다. ***

v2 변경점(이번 요청 반영):
  - /status도 서명 인증을 요구하므로, query_status()가 더 이상 비인증
    GET이 아니라 서명된 POST다(build_synthetic_envelope(action="status")).
  - 각 요청의 timestamp는 "실행 직전"에 생성한다 — send_fresh()가 호출
    시점에 time.time()을 찍고 그 자리에서 서명한다. 동시 버스트
    (run_concurrent_same_envelope)는 예외다: 거기서는 "같은 envelope를
    여러 번 복제 전송"하는 것 자체가 테스트 대상이므로, 하나의 envelope를
    버스트 시작 직전에 한 번만 만든다(이것도 "직전 생성" 원칙 안에 있다
    — 버스트 전체가 하나의 논리적 "요청 시도"이기 때문).
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

# 저장소 루트 기준 상대 경로로 계산한다(특정 로컬 머신의 절대 경로를
# 하드코딩하지 않음) — 이 파일 위치: tests/cross_validation/
# gas_replay_experiment/local_verification/ 이므로 4단계 위가 저장소 루트.
_REPO_SRC = Path(__file__).resolve().parents[4] / "src"
if str(_REPO_SRC) not in sys.path:
    sys.path.insert(0, str(_REPO_SRC))

from idempotency.signing_v2 import sign_v2  # noqa: E402


class UnsafeTargetError(Exception):
    """base_url이 로컬이 아닌데 allow_real_target 없이 호출된 경우 — 이번
    턴의 '실제 GAS 실행 안 함' 제약을 코드 수준에서 강제하기 위한 가드."""


def _assert_safe_target(base_url: str, *, allow_real_target: bool) -> str:
    is_local = "127.0.0.1" in base_url or "localhost" in base_url
    if is_local:
        return "LOCAL_MOCK_SERVER_VERIFICATION"
    if not allow_real_target:
        raise UnsafeTargetError(
            "base_url이 로컬이 아닌데 allow_real_target=True가 없습니다 — "
            "이번 작업 범위는 로컬 모의 서버 검증까지이며 실제 GAS 실행은 하지 않습니다."
        )
    return "REAL_GAS_EXECUTION"


def _redact_signature(sig: str) -> str:
    return sig[:8] + "...masked(" + str(len(sig)) + "hex)"


@dataclass
class RequestOutcome:
    classification: str  # "NETWORK_ERROR" | "SERVER_REJECTED" | "SERVER_ACCEPTED"
    detail: dict = field(default_factory=dict)


def send_once(base_url: str, envelope: dict, *, timeout_s: float = 5.0) -> RequestOutcome:
    """base_url에 그대로 1회 POST한다. **실제 GAS Web App은 URL 경로로
    라우팅하지 않는다** — 배포된 단일 URL(.../exec)에 들어오는 모든
    요청이 doPost(e) 하나로만 가고, exec/status 구분은 JSON 본문의
    "action" 필드로만 한다(RealEntryPoint_new.gs doPost(e)와 동일).
    이전 버전은 "/exec"·"/status"를 별도 URL 경로로 오인해 실제 GAS
    배포와 맞지 않았다 — 실행 전 재검토로 발견해 수정했다. 네트워크
    예외와 서버의 구조화된 거절을 구분한다."""
    data = json.dumps(envelope).encode("utf-8")
    req = urllib.request.Request(
        base_url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
            status_code = resp.status
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        return RequestOutcome(classification="NETWORK_ERROR", detail={"error_type": type(e).__name__})

    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception as e:
        return RequestOutcome(classification="NETWORK_ERROR", detail={"error_type": "InvalidResponseBody", "msg": str(e)})

    expected_success_stage = "BUSINESS_EXECUTED" if envelope["action"] == "exec" else "STATUS_OK"
    if status_code == 200 and parsed.get("stage") == expected_success_stage:
        return RequestOutcome(classification="SERVER_ACCEPTED", detail=parsed)
    return RequestOutcome(classification="SERVER_REJECTED", detail=parsed)


def build_synthetic_envelope(
    *, secret: str, key_id: str, action: str, variant: str, nonce: str, timestamp: float,
    scenario_label: str = "concurrency", max_skew_seconds: int = 120,
) -> dict:
    """합성 envelope 생성. action("exec"|"status")과 variant를 operation
    필드 값에 인코딩해 서명에 묶는다(Main_doPost_stub_new.gs와 동일 규약):
      exec   → "replay_experiment.variant{variant}.{scenario_label}"
      status → "replay_experiment.status.variant{variant}"
    secret은 이 함수 바깥(로그)으로 노출되지 않는다 — 호출부가 secret을
    별도로 들고 있다가 로깅하지 않도록 주의해야 한다."""
    if action == "exec":
        operation = f"replay_experiment.variant{variant}.{scenario_label}"
    elif action == "status":
        operation = f"replay_experiment.status.variant{variant}"
    else:
        raise ValueError(f"알 수 없는 action: {action}")

    payload = {"synthetic": True, "note": "no-real-data"}
    ts_str = str(timestamp)
    sig = sign_v2(
        secret=secret, method="POST", operation=operation, timestamp=ts_str, nonce=nonce,
        idempotency_key=f"idem-{nonce}", key_id=key_id, payload=payload,
    )
    return {
        "action": action, "variant": variant, "method": "POST", "operation": operation, "timestamp": ts_str,
        "nonce": nonce, "idempotency_key": f"idem-{nonce}", "key_id": key_id, "payload": payload,
        "signature": sig,
        # "now" 필드는 제거했다(이전엔 참고용 메타데이터로 남겨 서버가
        # 무시한다고만 문서화했으나, 그 필드 값이 부동소수점으로
        # 직렬화되어 GAS 쪽 엄격한 raw JSON 파서가 통째로 "본문 형식
        # 오류"로 거부하는 실제 장애를 일으켰다 — 서버가 "무시"하더라도
        # 파싱 단계 자체를 통과 못 하면 소용없으므로 필드 자체를 없앴다).
        #
        # max_skew_seconds는 보내지만, 서버는 이 값을 신뢰하지 않는다 —
        # 검증에는 서버 쪾 상수(EXPERIMENT_MAX_SKEW_SECONDS)만 쓰도록
        # 고쳤다(Main_doPost_stub_new.gs). 클라이언트가 이 필드로 검증
        # 범위를 넓히거나 좁힐 수 없다.
        "max_skew_seconds": max_skew_seconds,
    }


def send_fresh(
    base_url: str, *, secret: str, key_id: str, action: str, variant: str, nonce: str,
    scenario_label: str = "sequential", allow_real_target: bool = False, timeout_s: float = 5.0,
) -> RequestOutcome:
    """순차 단건 요청 전용 — timestamp를 **호출 시점에 바로** 생성하고
    서명해서 보낸다(요청사항 3: "각 요청의 timestamp는 실행 직전에
    생성한다"). 동시 버스트에는 쓰지 않는다(run_concurrent_same_envelope 참조)."""
    _assert_safe_target(base_url, allow_real_target=allow_real_target)
    now = time.time()  # 실행 직전 생성 — 여기서 미리 만들어 두지 않는다
    envelope = build_synthetic_envelope(
        secret=secret, key_id=key_id, action=action, variant=variant, nonce=nonce,
        timestamp=now, scenario_label=scenario_label,
    )
    return send_once(base_url, envelope, timeout_s=timeout_s)


def query_status(
    base_url: str, *, secret: str, key_id: str, variant: str, allow_real_target: bool = False, timeout_s: float = 5.0,
) -> int:
    """서명 인증이 필요한 /status 호출(v2) — 더 이상 비인증 GET이 아니다.
    nonce는 저장소에 기록되지 않으므로 고정 sentinel 값을 재사용해도
    안전하다(Main_doPost_stub_new.gs §(3) 참조)."""
    outcome = send_fresh(
        base_url, secret=secret, key_id=key_id, action="status", variant=variant,
        nonce="status-query-nonce-not-stored", allow_real_target=allow_real_target, timeout_s=timeout_s,
    )
    if outcome.classification != "SERVER_ACCEPTED":
        raise RuntimeError(f"status 조회 실패: {outcome.classification} {outcome.detail}")
    return int(outcome.detail["detail"]["businessCounter"])


@dataclass
class ConcurrencyRunSummary:
    target_label: str
    variant: str
    n_requests: int
    network_errors: int
    server_rejected: int
    server_accepted: int
    final_business_counter: int


def run_concurrent_same_envelope(
    base_url: str,
    envelope: dict,
    *,
    n_requests: int,
    status_secret: str,
    status_key_id: str,
    allow_real_target: bool = False,
    request_timeout_s: float = 5.0,
) -> ConcurrencyRunSummary:
    """같은 signed exec envelope를 n_requests개 동시에 전송한다(실제
    스레드 + 실제 소켓 — 같은 실행 내 반복호출이 아니다). 완료 후
    /status(서명 인증 필요, v2)로 서버 쪽 업무 카운터를 읽어 '정확히
    1건'을 확인한다(개별 응답 유실과 무관).

    status_secret/status_key_id를 **반드시 별도 인자로** 받는다 —
    envelope(JSON 직렬화되어 실제로 네트워크에 나가는 객체) 안에는
    secret을 절대 넣지 않으므로, envelope에서 꺼내 쓰는 방법 자체가
    없다(보안상 의도된 설계 — secret이 요청 바디에 실리면 와이어에
    노출된다)."""
    if envelope["action"] != "exec":
        raise ValueError("run_concurrent_same_envelope는 action='exec' envelope에만 쓴다")

    target_label = _assert_safe_target(base_url, allow_real_target=allow_real_target)
    variant = envelope["variant"]

    print(
        f"[{target_label}] variant={variant} nonce=...{envelope['nonce'][-6:]} "
        f"keyId={envelope['key_id']} signature={_redact_signature(envelope['signature'])} "
        f"n_requests={n_requests}"
    )  # URL은 의도적으로 출력하지 않음

    barrier = threading.Barrier(n_requests)
    outcomes: list[RequestOutcome] = []
    outcomes_lock = threading.Lock()

    def worker():
        barrier.wait()
        outcome = send_once(base_url, envelope, timeout_s=request_timeout_s)
        with outcomes_lock:
            outcomes.append(outcome)

    with ThreadPoolExecutor(max_workers=n_requests) as pool:
        futures = [pool.submit(worker) for _ in range(n_requests)]
        for f in futures:
            f.result(timeout=request_timeout_s + 5)

    network_errors = sum(1 for o in outcomes if o.classification == "NETWORK_ERROR")
    server_rejected = sum(1 for o in outcomes if o.classification == "SERVER_REJECTED")
    server_accepted = sum(1 for o in outcomes if o.classification == "SERVER_ACCEPTED")

    time.sleep(0.05)  # 마지막 쓰기가 반영될 아주 짧은 여유(로컬 기준 — 실제 GAS는 별도 실측 필요)
    final_counter = query_status(
        base_url, secret=status_secret, key_id=status_key_id, variant=variant,
        allow_real_target=allow_real_target, timeout_s=request_timeout_s,
    )

    print(
        f"[{target_label}] 결과: network_errors={network_errors} "
        f"server_rejected={server_rejected} server_accepted={server_accepted} "
        f"final_business_counter={final_counter}"
    )

    return ConcurrencyRunSummary(
        target_label=target_label, variant=variant, n_requests=n_requests,
        network_errors=network_errors, server_rejected=server_rejected, server_accepted=server_accepted,
        final_business_counter=final_counter,
    )
