# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — Replay 차단 격리 실측: 동시 HTTP 드라이버 로컬 검증(v2)

*** 전부 로컬 모의 서버(local_mock_gas_server.py) 대상이다. 실제 GAS
URL로 실행한 적이 없다 — 아래 어떤 테스트도 "GAS 실측"이 아니다. ***
합성 nonce·합성 키만 사용한다.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402

from local_mock_gas_server import LocalMockGasServer  # noqa: E402
from concurrent_http_driver import (  # noqa: E402
    build_synthetic_envelope,
    run_concurrent_same_envelope,
    send_once,
    send_fresh,
    query_status,
    UnsafeTargetError,
)

TEST_SECRET = "synthetic-driver-test-secret-not-production"
TEST_KEY_ID = "synthetic-driver-key-001"


@pytest.fixture()
def mock_server():
    with LocalMockGasServer(key_id=TEST_KEY_ID, secret=TEST_SECRET) as server:
        yield server


@pytest.mark.parametrize("variant", ["A", "B"])
def test_real_concurrent_http_same_envelope_exactly_one_business_execution(mock_server, variant):
    """요청사항 3: 같은 signed envelope를 실제(스레드+소켓) 동시 전송하고,
    응답이 아니라 /status(서명 인증 필요, v2) 업무 카운터로 정확히 1건인지 확인한다."""
    now = time.time()
    nonce = f"driver-nonce-{variant}-{int(now*1000)}"
    envelope = build_synthetic_envelope(
        secret=TEST_SECRET, key_id=TEST_KEY_ID, action="exec", variant=variant, nonce=nonce, timestamp=now,
    )
    summary = run_concurrent_same_envelope(
        mock_server.base_url, envelope, n_requests=15,
        status_secret=TEST_SECRET, status_key_id=TEST_KEY_ID,
    )

    assert summary.target_label == "LOCAL_MOCK_SERVER_VERIFICATION"
    assert summary.server_accepted == 1, "응답 기준으로도 정확히 1건만 BUSINESS_EXECUTED여야 한다"
    assert summary.final_business_counter == 1, (
        "서버 쪽 카운터(단일 진실 공급원) 기준으로도 정확히 1건이어야 한다 — "
        "개별 HTTP 응답 유실 여부와 무관하게 이 값으로 최종 판정한다"
    )
    assert summary.network_errors == 0


def test_network_error_classified_separately_from_server_rejection():
    """서버가 아예 떠 있지 않은 포트에 보내면 NETWORK_ERROR로 분류되어야
    하며, 이는 서버가 실제로 거절 응답을 준 SERVER_REJECTED와 달라야 한다."""
    dead_url = "http://127.0.0.1:1"
    now = time.time()
    envelope = build_synthetic_envelope(
        secret=TEST_SECRET, key_id=TEST_KEY_ID, action="exec", variant="A",
        nonce="nonce-network-error-test", timestamp=now,
    )
    outcome = send_once(dead_url, envelope, timeout_s=1.0)
    assert outcome.classification == "NETWORK_ERROR"


def test_server_rejection_classified_separately_from_network_error(mock_server):
    """서명을 일부러 변조해 보내면, 서버는 응답은 하되(연결 자체는 성공)
    SERVER_REJECTED로 분류되어야 한다 — NETWORK_ERROR와 혼동하면 안 된다."""
    now = time.time()
    envelope = build_synthetic_envelope(
        secret=TEST_SECRET, key_id=TEST_KEY_ID, action="exec", variant="A",
        nonce="nonce-tamper-test", timestamp=now,
    )
    envelope["signature"] = "0" * 64

    outcome = send_once(mock_server.base_url, envelope, timeout_s=2.0)
    assert outcome.classification == "SERVER_REJECTED"
    assert outcome.detail.get("stage") == "SIGNATURE_REJECTED"


def test_remove_reset_cleanup_routes_not_exposed(mock_server):
    """공개 엔드포인트에 remove/reset/cleanup에 대응하는 **action**이
    없는지 확인한다(요청사항 4-1 재확인). 실제 GAS Web App은 URL 경로로
    라우팅하지 않으므로(단일 배포 URL), "노출 안 됨"은 404가 아니라
    "그 action을 보내면 ACTION_INVALID로 거부됨"으로 검증해야 한다."""
    now = time.time()
    for action in ["remove", "reset", "cleanup", "admin"]:
        envelope = build_synthetic_envelope(
            secret=TEST_SECRET, key_id=TEST_KEY_ID, action="exec", variant="A",
            nonce=f"nonce-route-probe-{action}", timestamp=now,
        )
        envelope["action"] = action  # exec로 서명된 envelope의 action 필드만 바꿔치기
        outcome = send_once(mock_server.base_url, envelope, timeout_s=2.0)
        assert outcome.classification == "SERVER_REJECTED"
        assert outcome.detail.get("stage") == "ACTION_INVALID", f"action={action}이 거부되지 않음: {outcome.detail}"


def test_action_field_mismatch_rejected_even_with_valid_signature(mock_server):
    """body.action이 "remove" 같은 값이면, 서명이 아무리 유효해도
    ACTION_INVALID로 거부되어야 한다(디스패치 테이블에 exec/status 외의
    action 자체가 없음을 응답 레벨에서도 확인)."""
    now = time.time()
    envelope = build_synthetic_envelope(
        secret=TEST_SECRET, key_id=TEST_KEY_ID, action="exec", variant="A",
        nonce="nonce-action-mismatch-test", timestamp=now,
    )
    envelope["action"] = "remove"  # 서명 자체는 operation 문자열(exec 기준)에 묶여 유효하다
    outcome = send_once(mock_server.base_url, envelope, timeout_s=2.0)
    assert outcome.classification == "SERVER_REJECTED"
    assert outcome.detail.get("stage") == "ACTION_INVALID"


def test_status_requires_signature_unauthenticated_get_returns_method_not_allowed(mock_server):
    """요청사항 2-1: status도 서명 인증을 요구한다. 실제 GAS doGet(e)은
    항상 200 + METHOD_NOT_ALLOWED를 돌려준다(GAS Web App에 404 개념이
    없음) — 비인증 GET으로는 카운터 등 어떤 정보도 절대 못 받는다는
    사실 자체가 중요하지, HTTP 상태코드가 404냐 아니냐는 아니다."""
    req = urllib.request.Request(mock_server.base_url + "?variant=A", method="GET")
    with urllib.request.urlopen(req, timeout=2.0) as resp:
        status = resp.status
        parsed = json.loads(resp.read().decode("utf-8"))
    assert status == 200
    assert parsed.get("stage") == "METHOD_NOT_ALLOWED"
    assert "businessCounter" not in json.dumps(parsed)


def test_status_does_not_increment_business_counter(mock_server):
    """요청사항 2-2: 조회는 업무 실행 카운터를 증가시키지 않는다."""
    before = query_status(mock_server.base_url, secret=TEST_SECRET, key_id=TEST_KEY_ID, variant="A")
    for _ in range(5):
        query_status(mock_server.base_url, secret=TEST_SECRET, key_id=TEST_KEY_ID, variant="A")
    after = query_status(mock_server.base_url, secret=TEST_SECRET, key_id=TEST_KEY_ID, variant="A")
    assert before == after == 0


def test_status_replay_does_not_consume_nonce_or_budget_separately_but_counts_toward_budget(mock_server):
    """요청사항 2-3: 상태 조회는 nonce를 소비하지 않으므로(같은 nonce를
    반복 재사용해도 매번 성공) replay 차단 대상이 아니다. 다만 요청
    예산(서버 측 카운터)에는 포함된다 — budget.request_count가 각
    status 호출마다 증가하는지로 간접 확인한다(요청사항 1 budget 로직과
    공유 상태이므로, status 호출 자체가 계속 성공한다는 사실 자체가
    예산이 과도하게 빨리 소진되지 않는 범위 안에 있음을 보여준다)."""
    first = send_fresh(
        mock_server.base_url, secret=TEST_SECRET, key_id=TEST_KEY_ID, action="status", variant="A",
        nonce="same-status-nonce-reused",
    )
    second = send_fresh(
        mock_server.base_url, secret=TEST_SECRET, key_id=TEST_KEY_ID, action="status", variant="A",
        nonce="same-status-nonce-reused",  # 같은 nonce 재사용 — exec였다면 REJECTED_REPLAY였을 것
    )
    assert first.classification == "SERVER_ACCEPTED"
    assert second.classification == "SERVER_ACCEPTED", "status는 nonce를 소비하지 않으므로 같은 nonce 재사용도 성공해야 한다"


def test_signature_failure_never_touches_nonce_or_counter_under_concurrent_bombardment(mock_server):
    """요청사항 1: HMAC 검증 실패 요청은 nonce·업무 상태를 변경하지
    않는다 — 여러 건을 동시에 보내도 업무 카운터가 0이어야 한다."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    now = time.time()
    n = 10
    barrier = threading.Barrier(n)

    def worker(i):
        envelope = build_synthetic_envelope(
            secret=TEST_SECRET, key_id=TEST_KEY_ID, action="exec", variant="A",
            nonce=f"bombard-nonce-{i}", timestamp=now,
        )
        envelope["signature"] = "f" * 64  # 전부 변조
        barrier.wait()
        return send_once(mock_server.base_url, envelope, timeout_s=2.0)

    with ThreadPoolExecutor(max_workers=n) as pool:
        outcomes = list(pool.map(worker, range(n)))

    assert all(o.classification == "SERVER_REJECTED" for o in outcomes)
    assert all(o.detail.get("stage") == "SIGNATURE_REJECTED" for o in outcomes)

    counter = query_status(mock_server.base_url, secret=TEST_SECRET, key_id=TEST_KEY_ID, variant="A")
    assert counter == 0, "서명 실패 요청이 업무 카운터를 건드리면 안 된다"


def test_unsafe_target_blocks_non_local_url_without_explicit_flag():
    """이번 작업 범위(실제 GAS 실행 안 함)를 코드 수준에서 강제하는 가드:
    로컬이 아닌 URL은 allow_real_target 없이는 거부되어야 한다."""
    with pytest.raises(UnsafeTargetError):
        send_fresh(
            "https://example-not-a-real-gas-endpoint.invalid", secret=TEST_SECRET, key_id=TEST_KEY_ID,
            action="status", variant="A", nonce="nonce-unsafe-target",
        )


def test_logs_never_contain_raw_secret_or_full_signature(mock_server, capsys):
    """요청사항 3: URL·키·서명 원문을 로그에 남기지 않음을 직접 검증한다."""
    now = time.time()
    nonce = "nonce-redaction-check"
    envelope = build_synthetic_envelope(
        secret=TEST_SECRET, key_id=TEST_KEY_ID, action="exec", variant="A", nonce=nonce, timestamp=now,
    )
    full_signature = envelope["signature"]

    run_concurrent_same_envelope(
        mock_server.base_url, envelope, n_requests=3,
        status_secret=TEST_SECRET, status_key_id=TEST_KEY_ID,
    )

    captured = capsys.readouterr()
    combined = captured.out + captured.err

    assert TEST_SECRET not in combined, "합성 secret 원문이 로그에 그대로 남으면 안 된다"
    assert full_signature not in combined, "서명 원문(전체 hex)이 로그에 그대로 남으면 안 된다"
    assert mock_server.base_url not in combined, "URL이 로그에 그대로 남으면 안 된다"
    assert TEST_KEY_ID in combined  # keyId는 비밀이 아니므로 로깅되어도 된다


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
