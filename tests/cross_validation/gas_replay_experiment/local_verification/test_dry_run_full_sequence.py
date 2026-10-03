# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — real_execution_run.py 전체 시퀀스 드라이런(로컬 모의 서버 대상).

실제 GAS로 넘어가기 전에, v3 §3-1 표의 60건 시퀀스 전체(시나리오1·2·4·7)를
로컬에서 끝까지 한 번 통과시켜 오케스트레이션 자체의 정확성을 검증한다.
max_skew_seconds를 짧게(3초) 줘서 시나리오7의 실제 대기 시간을 몇 초로
줄인다(실제 실행에서는 120초를 쓴다 — 이 축소는 로컬 드라이런 전용).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from local_mock_gas_server import LocalMockGasServer  # noqa: E402
from real_execution_run import run_full_sequence  # noqa: E402

TEST_SECRET = "synthetic-dryrun-secret-not-production"
TEST_KEY_ID = "synthetic-dryrun-key-001"


def test_full_sequence_dry_run_against_local_mock_server():
    with LocalMockGasServer(key_id=TEST_KEY_ID, secret=TEST_SECRET) as server:
        outcome = run_full_sequence(
            server.base_url, secret=TEST_SECRET, key_id=TEST_KEY_ID,
            allow_real_target=False, max_skew_seconds=3,
        )
    assert outcome["computed_total_requests"] >= 59  # 버스트 2건(20+1씩) + 나머지 순차 요청
    print(outcome["computed_total_requests"])


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v", "-s"]))
