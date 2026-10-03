# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — 실제 실행 전 최종 확인 항목 1(전용 테스트):
"exec 서명을 status에, status 서명을 exec에 사용할 수 없어야 한다."

action 필드 자체는 9필드 서명 대상에 포함되지 않는다(method/operation/
timestamp/nonce/idempotencyKey/keyId/payloadHash뿐). 그래서 이 테스트는
"action 필드가 서명되어 있다"를 확인하는 게 아니라, "operation 필드의
접두사 불일치 때문에 action을 바꿔치기해도 통과하지 못한다"를 실제로
검증한다 — 이 구분 자체가 실행 전 확인 보고에 명시해야 할 사실이다.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402

from local_mock_gas_server import LocalMockGasServer  # noqa: E402
from concurrent_http_driver import build_synthetic_envelope, send_once  # noqa: E402

TEST_SECRET = "synthetic-preflight-secret-not-production"
TEST_KEY_ID = "synthetic-preflight-key-001"


@pytest.fixture()
def mock_server():
    with LocalMockGasServer(key_id=TEST_KEY_ID, secret=TEST_SECRET) as server:
        yield server


def test_exec_signed_envelope_cannot_be_replayed_as_status(mock_server):
    """exec용으로 서명된 envelope의 action 필드만 "status"로 바꿔
    /status에 보내면, 서명 자체는 (operation 등 서명 대상 필드를 안
    건드렸으므로) ACCEPTED로 남지만, operation 접두사가
    "replay_experiment.status.variantA"가 아니므로 거부되어야 한다."""
    now = time.time()
    envelope = build_synthetic_envelope(
        secret=TEST_SECRET, key_id=TEST_KEY_ID, action="exec", variant="A",
        nonce="preflight-exec-to-status", timestamp=now,
    )
    tampered = dict(envelope)
    tampered["action"] = "status"  # 서명 대상 밖의 필드만 변경

    outcome = send_once(mock_server.base_url, tampered, timeout_s=2.0)
    assert outcome.classification == "SERVER_REJECTED"
    # action 필드 자체 불일치(ACTION_INVALID)로도, operation 접두사
    # 불일치(SIGNATURE_REJECTED/OPERATION_ACTION_VARIANT_MISMATCH)로도
    # 막힐 수 있다 — 어느 쪽이든 절대 STATUS_OK가 나오면 안 된다.
    assert outcome.detail.get("stage") != "STATUS_OK"
    assert outcome.detail.get("stage") in ("ACTION_INVALID", "SIGNATURE_REJECTED")


def test_status_signed_envelope_cannot_be_replayed_as_exec(mock_server):
    """반대 방향: status용으로 서명된 envelope를 /exec에 보내면
    BUSINESS_EXECUTED가 나오면 안 된다(업무가 실제로 실행되면 안 됨)."""
    now = time.time()
    envelope = build_synthetic_envelope(
        secret=TEST_SECRET, key_id=TEST_KEY_ID, action="status", variant="A",
        nonce="preflight-status-to-exec", timestamp=now,
    )
    tampered = dict(envelope)
    tampered["action"] = "exec"

    outcome = send_once(mock_server.base_url, tampered, timeout_s=2.0)
    assert outcome.classification == "SERVER_REJECTED"
    assert outcome.detail.get("stage") != "BUSINESS_EXECUTED"
    assert outcome.detail.get("stage") in ("ACTION_INVALID", "SIGNATURE_REJECTED")

    # 업무가 실행되지 않았으므로 카운터도 그대로 0이어야 한다.
    from concurrent_http_driver import query_status
    counter = query_status(mock_server.base_url, secret=TEST_SECRET, key_id=TEST_KEY_ID, variant="A")
    assert counter == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
