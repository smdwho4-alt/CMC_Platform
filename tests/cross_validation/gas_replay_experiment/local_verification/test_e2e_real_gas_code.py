# *** 테스트 전용 합성 값 — 운영 재사용 금지 ***
# 이 파일에는 이번 격리 실험을 위해 생성한 합성(synthetic) 테스트
# 키/비밀값이 포함되어 있다. 실제 운영 계정·실제 비밀키와 무관하며,
# 이 저장소에 공개되어 있다는 전제로 다뤄야 한다 — 운영 환경에
# 그대로 재사용하지 않는다.

# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — request.secret 제거(서버 측 KeyRegistry) E2E 검증.

*** 이것은 GAS가 아니다 — Node가 실제 GAS 후보 코드(gas_candidate/,
concatenated_all_v2.js)를 그대로 실행하는 로컬 HTTP 서버이고,
기존(이번 턴에 전혀 수정하지 않은) concurrent_http_driver.py로
실제 와이어 형식 그대로 때린다. ***

테스트가 request.secret을 임의로 주입하지 않는다 — build_synthetic_envelope()
는 원래부터 secret을 wire envelope에 넣지 않으므로(로컬 서명 계산에만
쓰고 전송하지 않음) 그대로 쓴다.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402

from concurrent_http_driver import (  # noqa: E402
    build_synthetic_envelope,
    send_once,
    send_fresh,
    run_concurrent_same_envelope,
    query_status,
)

NODE_SERVER_SCRIPT = (
    Path(__file__).resolve().parent.parent / "node_harness" / "node_gas_http_server.js"
)

# TestKeyRegistry_new.gs에 실제로 등록된 합성 키 쌍과 반드시 일치해야 한다.
REGISTERED_KEY_ID = "real-gas-exp-key-1dd05338"
REGISTERED_SECRET = "95f2e928939b6141904a39a07e44222b3dacd0d9f64eb392f9fdea2e4f12d4f9"


@pytest.fixture()
def node_gas_server():
    proc = subprocess.Popen(
        ["node", str(NODE_SERVER_SCRIPT)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        cwd=str(NODE_SERVER_SCRIPT.parent),
    )
    port = None
    deadline = time.time() + 10
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            continue
        if "NODE_GAS_HTTP_SERVER_LISTENING_ON=" in line:
            port = int(line.strip().split("=")[1])
            break
    assert port is not None, "Node GAS HTTP 서버가 제한시간 내에 뜨지 않음"
    base_url = f"http://127.0.0.1:{port}"
    try:
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_valid_signature_executes_business_exactly_once(node_gas_server):
    """정상 서명 → 업무 실행 1회."""
    now = time.time()
    nonce = f"e2e-valid-{int(now * 1000)}"
    envelope = build_synthetic_envelope(
        secret=REGISTERED_SECRET, key_id=REGISTERED_KEY_ID, action="exec", variant="A",
        nonce=nonce, timestamp=now, scenario_label="e2e-valid",
    )
    assert "secret" not in envelope  # 테스트가 secret을 주입하지 않음을 재확인

    outcome = send_once(node_gas_server, envelope, timeout_s=10.0)
    assert outcome.classification == "SERVER_ACCEPTED"
    assert outcome.detail.get("stage") == "BUSINESS_EXECUTED"

    status = send_fresh(
        node_gas_server, secret=REGISTERED_SECRET, key_id=REGISTERED_KEY_ID, action="status",
        variant="A", nonce=f"e2e-status-{int(now * 1000)}",
    )
    assert status.detail["detail"]["businessCounter"] >= 1


def test_invalid_signature_executes_business_zero_times(node_gas_server):
    """무효 서명 → 실행 0회."""
    now = time.time()
    nonce = f"e2e-invalid-sig-{int(now * 1000)}"
    envelope = build_synthetic_envelope(
        secret=REGISTERED_SECRET, key_id=REGISTERED_KEY_ID, action="exec", variant="A",
        nonce=nonce, timestamp=now, scenario_label="e2e-invalid-sig",
    )
    envelope["signature"] = "0" * 64
    outcome = send_once(node_gas_server, envelope, timeout_s=10.0)
    assert outcome.classification == "SERVER_REJECTED"
    assert outcome.detail.get("stage") == "SIGNATURE_REJECTED"


def test_attacker_chosen_secret_rejected(node_gas_server):
    """공격자가 선택한 secret과 서명 → 거절(등록된 key_id를 사칭해도)."""
    now = time.time()
    nonce = f"e2e-attacker-secret-{int(now * 1000)}"
    attacker_secret = "attacker-chosen-secret-definitely-not-registered"
    envelope = build_synthetic_envelope(
        secret=attacker_secret, key_id=REGISTERED_KEY_ID, action="exec", variant="A",
        nonce=nonce, timestamp=now, scenario_label="e2e-attacker-secret",
    )
    outcome = send_once(node_gas_server, envelope, timeout_s=10.0)
    assert outcome.classification == "SERVER_REJECTED"
    assert outcome.detail.get("stage") == "SIGNATURE_REJECTED"
    assert outcome.detail.get("detail", {}).get("classification") == "SIGNATURE_MISMATCH"


def test_unregistered_key_id_rejected(node_gas_server):
    """미등록 key_id → 거절."""
    now = time.time()
    nonce = f"e2e-unknown-key-{int(now * 1000)}"
    envelope = build_synthetic_envelope(
        secret=REGISTERED_SECRET, key_id="never-registered-key-id-e2e", action="exec", variant="A",
        nonce=nonce, timestamp=now, scenario_label="e2e-unknown-key",
    )
    outcome = send_once(node_gas_server, envelope, timeout_s=10.0)
    assert outcome.classification == "SERVER_REJECTED"
    assert outcome.detail.get("stage") == "SIGNATURE_REJECTED"
    assert outcome.detail.get("detail", {}).get("classification") == "UNKNOWN_KEY_ID"


def test_action_and_variant_tampering_rejected(node_gas_server):
    """exec/status와 variant 변조 → 거절."""
    now = time.time()
    nonce = f"e2e-tamper-{int(now * 1000)}"
    envelope = build_synthetic_envelope(
        secret=REGISTERED_SECRET, key_id=REGISTERED_KEY_ID, action="exec", variant="A",
        nonce=nonce, timestamp=now, scenario_label="e2e-tamper",
    )
    tampered_action = dict(envelope)
    tampered_action["action"] = "status"
    outcome1 = send_once(node_gas_server, tampered_action, timeout_s=10.0)
    assert outcome1.classification == "SERVER_REJECTED"
    assert outcome1.detail.get("stage") != "BUSINESS_EXECUTED"

    tampered_variant = dict(envelope)
    tampered_variant["variant"] = "B"
    outcome2 = send_once(node_gas_server, tampered_variant, timeout_s=10.0)
    assert outcome2.classification == "SERVER_REJECTED"
    assert outcome2.detail.get("stage") != "BUSINESS_EXECUTED"


def test_client_time_and_skew_cannot_change_server_policy(node_gas_server):
    """클라이언트 시각·skew 값으로 서버 정책 변경 불가."""
    stale_ts = time.time() - 100000  # 훨씬 과거
    nonce = f"e2e-stale-{int(time.time() * 1000)}"
    envelope = build_synthetic_envelope(
        secret=REGISTERED_SECRET, key_id=REGISTERED_KEY_ID, action="exec", variant="A",
        nonce=nonce, timestamp=stale_ts, scenario_label="e2e-stale",
        max_skew_seconds=999999999,  # 클라이언트가 거대한 skew를 주장
    )
    outcome = send_once(node_gas_server, envelope, timeout_s=10.0)
    assert outcome.classification == "SERVER_REJECTED"
    assert outcome.detail.get("stage") == "SIGNATURE_REJECTED"
    assert outcome.detail.get("detail", {}).get("classification") == "TIMESTAMP_EXPIRED"


def test_replay_of_same_envelope_does_not_increase_execution(node_gas_server):
    """동일 envelope 재전송 → 실행 증가 없음(동시 버스트 포함)."""
    now = time.time()
    nonce = f"e2e-replay-{int(now * 1000)}"
    envelope = build_synthetic_envelope(
        secret=REGISTERED_SECRET, key_id=REGISTERED_KEY_ID, action="exec", variant="A",
        nonce=nonce, timestamp=now, scenario_label="e2e-replay",
    )
    summary = run_concurrent_same_envelope(
        node_gas_server, envelope, n_requests=10,
        status_secret=REGISTERED_SECRET, status_key_id=REGISTERED_KEY_ID,
    )
    assert summary.server_accepted == 1
    assert summary.network_errors == 0
