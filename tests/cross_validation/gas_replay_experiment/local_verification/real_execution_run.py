# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — v3 패키지 실제 실행 오케스트레이션 스크립트

이 스크립트는 base_url에 따라 로컬 모의 서버든 실제 GAS든 **동일한
시나리오 순서(v3 §3-1 표, 60건)**를 수행한다. 먼저 로컬 모의 서버로
드라이런해 전체 흐름 자체가 올바른지 확인한 뒤에만 실제 GAS URL로
재실행한다(이번 요청 "확인 전까지는 로컬 검증만" 원칙).

규칙(요청사항 그대로):
  - 동일 envelope 재전송 시험(재사용 재전송, 동시 버스트, 경계 재전송)은
    timestamp·nonce·서명을 바꾸지 않는다 — build_synthetic_envelope()로
    한 번만 만들고 그 객체를 그대로 재전송한다.
  - 별개의 신규 요청(최초 요청, status 조회, 새 nonce 재시도)만
    send_fresh()를 쓴다(실행 직전 timestamp 생성).
  - 오류·상한 초과·예상 밖 업무 실행이 나오면 그 즉시 중단한다(자동 재시도 없음).
  - secret은 로그에 남기지 않는다(환경변수로만 받는다).
  - 네트워크 오류는 PASS로 집계하지 않는다(별도 분류로 보고서에 남긴다).
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from concurrent_http_driver import (  # noqa: E402
    build_synthetic_envelope,
    run_concurrent_same_envelope,
    send_once,
    send_fresh,
    query_status,
    UnsafeTargetError,
)


class ExperimentHaltedError(Exception):
    """예상 밖 결과가 나오면 즉시 던진다 — 자동 재시도하지 않고 전체 실행을 멈춘다."""


@dataclass
class VectorResult:
    label: str
    classification: str
    stage: str
    extra: dict


def _record(results: list[VectorResult], label: str, outcome, extra: dict | None = None) -> VectorResult:
    r = VectorResult(
        label=label, classification=outcome.classification,
        stage=outcome.detail.get("stage", "") if hasattr(outcome, "detail") else "",
        extra=extra or {},
    )
    results.append(r)
    print(f"[VECTOR] {label}: classification={r.classification} stage={r.stage}")
    return r


def _assert_or_halt(condition: bool, message: str) -> None:
    if not condition:
        raise ExperimentHaltedError(message)


def run_full_sequence(
    base_url: str, *, secret: str, key_id: str, allow_real_target: bool, max_skew_seconds: int = 120,
) -> dict[str, Any]:
    results: list[VectorResult] = []
    run_id = int(time.time())
    counter_after_s1: dict[str, int] = {}

    # ------------------------------------------------------------------
    # 시나리오1: 최초 허용·재사용 거절(A/B) — exec 4건 + status 2건 = 6건
    # ------------------------------------------------------------------
    for variant in ("A", "B"):
        nonce = f"s1-{run_id}-{variant}"
        now = time.time()
        envelope = build_synthetic_envelope(
            secret=secret, key_id=key_id, action="exec", variant=variant, nonce=nonce,
            timestamp=now, scenario_label="s1", max_skew_seconds=max_skew_seconds,
        )
        first = send_once(base_url, envelope, timeout_s=10.0)
        _record(results, f"s1-{variant}-first", first)
        _assert_or_halt(first.classification == "SERVER_ACCEPTED", f"s1-{variant}-first이 SERVER_ACCEPTED가 아님: {first}")

        replay = send_once(base_url, envelope, timeout_s=10.0)  # 동일 envelope 그대로 재전송
        _record(results, f"s1-{variant}-replay", replay)
        _assert_or_halt(
            replay.classification == "SERVER_REJECTED" and replay.detail.get("stage") == "NONCE_REJECTED_OR_BLOCKED",
            f"s1-{variant}-replay가 NONCE_REJECTED_OR_BLOCKED가 아님: {replay}",
        )

        status_outcome = send_fresh(
            base_url, secret=secret, key_id=key_id, action="status", variant=variant,
            nonce=f"s1-status-{run_id}-{variant}", allow_real_target=allow_real_target, timeout_s=10.0,
        )
        _record(results, f"s1-{variant}-status", status_outcome)
        _assert_or_halt(status_outcome.classification == "SERVER_ACCEPTED", f"s1-{variant}-status 실패: {status_outcome}")
        counter = status_outcome.detail["detail"]["businessCounter"]
        _assert_or_halt(counter == 1, f"s1-{variant} 이후 카운터가 1이 아님: {counter}")
        counter_after_s1[variant] = counter

    # ------------------------------------------------------------------
    # 시나리오2: 동시 동일 nonce(A/B, 각 20건 동시, 1회만) — exec 40건 + status 2건 = 42건
    # ------------------------------------------------------------------
    s2_summaries = {}
    for variant in ("A", "B"):
        # 업무 카운터는 시퀀스 전체에 걸친 누적값이다(시나리오1에서 이미
        # variant당 1씩 올라가 있음) — 그래서 "절대값 1"이 아니라 "이
        # 버스트 직전 대비 정확히 1 증가"로 판정해야 한다. 별도의 "직전
        # 조회" 요청을 새로 추가하지 않고, 시나리오1에서 이미 확인한
        # counter_after_s1[variant]을 그대로 기준값으로 재사용한다
        # (요청 예산 60건을 그대로 지키기 위함 — 새 status 호출을
        # 추가하면 계획보다 많아진다).
        counter_before = counter_after_s1[variant]

        nonce = f"s2-{run_id}-{variant}"
        now = time.time()
        envelope = build_synthetic_envelope(
            secret=secret, key_id=key_id, action="exec", variant=variant, nonce=nonce,
            timestamp=now, scenario_label="s2", max_skew_seconds=max_skew_seconds,
        )
        summary = run_concurrent_same_envelope(
            base_url, envelope, n_requests=20, status_secret=secret, status_key_id=key_id,
            allow_real_target=allow_real_target, request_timeout_s=10.0,
        )
        s2_summaries[variant] = asdict(summary)
        results.append(VectorResult(
            label=f"s2-{variant}-burst", classification="SUMMARY",
            stage="", extra=asdict(summary),
        ))
        print(f"[VECTOR] s2-{variant}-burst: {summary} (counter_before={counter_before})")
        _assert_or_halt(summary.server_accepted == 1, f"s2-{variant} server_accepted != 1: {summary}")
        _assert_or_halt(
            summary.final_business_counter - counter_before == 1,
            f"s2-{variant} 버스트로 카운터가 정확히 1 증가하지 않음: before={counter_before}, after={summary.final_business_counter}",
        )
        # 네트워크 오류는 PASS로 집계하지 않는다 — 0이 아니면 그 사실을 결과에 남기되
        # 즉시 중단하지는 않는다(네트워크 오류 자체는 "서버 결함"이 아닐 수 있음).
        if summary.network_errors > 0:
            print(f"[WARNING] s2-{variant}: network_errors={summary.network_errors} (PASS로 집계하지 않음)")

    # ------------------------------------------------------------------
    # 시나리오4: 업무실행 전 실패 후 재전송(A/B) — exec 6건 + status 2건 = 8건
    # ------------------------------------------------------------------
    for variant in ("A", "B"):
        original_nonce = f"s4-orig-{run_id}-{variant}"
        now = time.time()
        original_envelope = build_synthetic_envelope(
            secret=secret, key_id=key_id, action="exec", variant=variant, nonce=original_nonce,
            timestamp=now, scenario_label="s4", max_skew_seconds=max_skew_seconds,
        )
        first = send_once(base_url, original_envelope, timeout_s=10.0)
        _record(results, f"s4-{variant}-original", first)
        _assert_or_halt(first.classification == "SERVER_ACCEPTED", f"s4-{variant}-original 실패: {first}")

        retry_same = send_once(base_url, original_envelope, timeout_s=10.0)  # 동일 envelope
        _record(results, f"s4-{variant}-retry-same-nonce", retry_same)
        _assert_or_halt(
            retry_same.classification == "SERVER_REJECTED",
            f"s4-{variant}-retry-same-nonce가 거부되지 않음: {retry_same}",
        )

        retry_new = send_fresh(
            base_url, secret=secret, key_id=key_id, action="exec", variant=variant,
            nonce=f"s4-new-{run_id}-{variant}", scenario_label="s4-retry",
            allow_real_target=allow_real_target, timeout_s=10.0,
        )
        _record(results, f"s4-{variant}-retry-new-nonce", retry_new)
        _assert_or_halt(retry_new.classification == "SERVER_ACCEPTED", f"s4-{variant}-retry-new-nonce 실패: {retry_new}")

        status_outcome = send_fresh(
            base_url, secret=secret, key_id=key_id, action="status", variant=variant,
            nonce=f"s4-status-{run_id}-{variant}", allow_real_target=allow_real_target, timeout_s=10.0,
        )
        _record(results, f"s4-{variant}-status", status_outcome)

    # ------------------------------------------------------------------
    # 시나리오7: 서명 유효기간-nonce 정리 경계(A만 대표) — exec 3건 + status 1건 = 4건
    # 실제 wall-clock 대기 필요(~2분).
    # ------------------------------------------------------------------
    t0 = time.time()
    future_padded_ts = t0 + max_skew_seconds
    s7_nonce = f"s7-{run_id}-A"
    s7_envelope = build_synthetic_envelope(
        secret=secret, key_id=key_id, action="exec", variant="A", nonce=s7_nonce,
        timestamp=future_padded_ts, scenario_label="s7", max_skew_seconds=max_skew_seconds,
    )
    # now는 envelope 생성과 별개로 전송 시점에 실제 서버가 보는 현재시각이다.
    first7 = send_once(base_url, s7_envelope, timeout_s=10.0)
    _record(results, "s7-A-t0-accept", first7)
    _assert_or_halt(first7.classification == "SERVER_ACCEPTED", f"s7-A-t0-accept 실패: {first7}")

    wait1 = max(0.0, (future_padded_ts + max_skew_seconds - 1) - time.time())
    print(f"[WAIT] s7: 서명 경계 이전 재전송까지 {wait1:.1f}초 대기")
    time.sleep(wait1)
    near_boundary = send_once(base_url, s7_envelope, timeout_s=10.0)
    _record(results, "s7-A-near-boundary-replay", near_boundary)
    _assert_or_halt(
        near_boundary.classification == "SERVER_REJECTED" and near_boundary.detail.get("stage") == "NONCE_REJECTED_OR_BLOCKED",
        f"s7-A-near-boundary-replay가 NONCE_REJECTED_OR_BLOCKED가 아님: {near_boundary}",
    )

    wait2 = max(0.0, (future_padded_ts + max_skew_seconds + 2) - time.time())
    print(f"[WAIT] s7: 서명 경계 이후 재전송까지 {wait2:.1f}초 대기")
    time.sleep(wait2)
    after_expiry = send_once(base_url, s7_envelope, timeout_s=10.0)
    _record(results, "s7-A-after-signature-expiry", after_expiry)
    _assert_or_halt(
        after_expiry.classification == "SERVER_REJECTED" and after_expiry.detail.get("stage") == "SIGNATURE_REJECTED",
        f"s7-A-after-signature-expiry가 SIGNATURE_REJECTED가 아님: {after_expiry}",
    )

    status7 = send_fresh(
        base_url, secret=secret, key_id=key_id, action="status", variant="A",
        nonce=f"s7-status-{run_id}", allow_real_target=allow_real_target, timeout_s=10.0,
    )
    _record(results, "s7-A-status", status7)

    total_requests = sum(
        1 if r.classification != "SUMMARY" else r.extra.get("n_requests", 0) + 1  # 버스트 n건 + status 1건
        for r in results
    )

    return {
        "results": [asdict(r) for r in results],
        "s2_summaries": s2_summaries,
        "computed_total_requests": total_requests,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--allow-real-target", action="store_true")
    parser.add_argument("--out", default="real_execution_result_new.json")
    args = parser.parse_args()

    secret = os.environ.get("REPLAY_EXPERIMENT_SECRET")
    key_id = os.environ.get("REPLAY_EXPERIMENT_KEY_ID")
    if not secret or not key_id:
        print("REPLAY_EXPERIMENT_SECRET / REPLAY_EXPERIMENT_KEY_ID 환경변수가 필요합니다.", file=sys.stderr)
        sys.exit(2)

    try:
        outcome = run_full_sequence(
            args.base_url, secret=secret, key_id=key_id, allow_real_target=args.allow_real_target,
        )
    except (ExperimentHaltedError, UnsafeTargetError) as e:
        print(f"[HALTED] {e}", file=sys.stderr)
        sys.exit(1)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(outcome, f, ensure_ascii=False, indent=2)
    print(f"[DONE] 결과를 {args.out}에 저장했습니다. 총 요청 수(계산): {outcome['computed_total_requests']}")
