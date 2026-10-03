# *** 테스트 전용 합성 값 — 운영 재사용 금지 ***
# 이 파일에는 이번 격리 실험을 위해 생성한 합성(synthetic) 테스트
# 키/비밀값이 포함되어 있다. 실제 운영 계정·실제 비밀키와 무관하며,
# 이 저장소에 공개되어 있다는 전제로 다뤄야 한다 — 운영 환경에
# 그대로 재사용하지 않는다.

# -*- coding: utf-8 -*-
"""최종 드라이런: 실제 v3 GAS 후보 코드(Node HTTP 서버로 감쌈)를 대상으로
real_execution_run.py(계획된 60건 시퀀스 그대로)를 1회 돌려본다 —
실제 GAS에 보내기 직전의 마지막 로컬 리허설. max_skew_seconds만 짧게
줄여(3초) 실제 대기시간을 줄인다(실제 실행에서는 120초 사용)."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

NODE_SERVER_SCRIPT = (
    Path(__file__).resolve().parent.parent / "node_harness" / "node_gas_http_server.js"
)

from real_execution_run import run_full_sequence  # noqa: E402

TEST_SECRET = "95f2e928939b6141904a39a07e44222b3dacd0d9f64eb392f9fdea2e4f12d4f9"
TEST_KEY_ID = "real-gas-exp-key-1dd05338"


def test_final_dry_run_against_real_v3_code():
    proc = subprocess.Popen(
        ["node", str(NODE_SERVER_SCRIPT)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        cwd=str(NODE_SERVER_SCRIPT.parent),
    )
    port = None
    deadline = time.time() + 10
    try:
        while time.time() < deadline:
            line = proc.stdout.readline()
            if "NODE_GAS_HTTP_SERVER_LISTENING_ON=" in line:
                port = int(line.strip().split("=")[1])
                break
        assert port is not None
        base_url = f"http://127.0.0.1:{port}"

        # 중요: 서버는 이제 클라이언트가 보낸 max_skew_seconds를 절대
        # 읽지 않는다(오늘 수정된 보안 고정) — 서명·nonce TTL 전부
        # 서버 상수 EXPERIMENT_MAX_SKEW_SECONDS(120)만 쓴다. 그래서
        # 여기서 짧은 값(3초)을 줘도 실제 대기 시간은 줄어들지 않는다
        # (이전 드라이런에서 실제로 이 사실을 재확인했다 — 그때는 3을
        # 줬다가 s7 단계가 실패해서 발견함). 실제 계획과 동일하게 120을
        # 써서 끝까지 충실하게 재현한다(약 2분 소요).
        outcome = run_full_sequence(
            base_url, secret=TEST_SECRET, key_id=TEST_KEY_ID, allow_real_target=False, max_skew_seconds=120,
        )
        print("computed_total_requests:", outcome["computed_total_requests"])
        assert outcome["computed_total_requests"] == 60
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v", "-s"]))
