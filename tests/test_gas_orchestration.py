# -*- coding: utf-8 -*-
"""
CSHSP Sprint8 Commit8-3b — src/idempotency/gas_orchestration.py 격리 통합테스트

**실제 네트워크를 호출하지 않는다.** `FakeGasAdapter`는 이 파일에만 존재하는
테스트 전용 더블이며, 큐에 미리 준비한 응답/예외를 순서대로 소비한다. 운영
`src/api/routes_admin_portal.py`는 이 테스트에서 import·수정하지 않는다.
모든 key/fingerprint/result는 합성(synthetic) 값만 사용한다.
"""
from __future__ import annotations

import io
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from datetime import datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src" / "idempotency"))

import idempotency_store as store  # noqa: E402
import gas_orchestration as orch  # noqa: E402
from json_store import KST  # noqa: E402

FP_A = "synthetic-fingerprint-aaaa0001"
FP_B = "synthetic-fingerprint-bbbb0002"
WORKER_COUNT = 8


def _now(offset_seconds: float = 0.0) -> datetime:
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=KST)
    return base + timedelta(seconds=offset_seconds)


class FakeGasAdapter:
    """테스트 전용 더블. 실제 네트워크를 호출하지 않는다. `script`에 담긴
    항목(`GasResponse` 인스턴스 또는 예외 인스턴스/클래스)을 순서대로
    하나씩 소비한다. `call_count`/`calls`로 호출 횟수·인자를 검증에
    쓴다(인자는 synthetic key/fingerprint뿐, PII 아님)."""

    def __init__(self, *script):
        self._script = list(script)
        self.call_count = 0
        self.calls: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def __call__(self, *, key: str, fingerprint: str) -> orch.GasResponse:
        with self._lock:
            self.call_count += 1
            self.calls.append((key, fingerprint))
            if not self._script:
                raise AssertionError(
                    f"FakeGasAdapter: 스크립트 소진(예상보다 많이 호출됨, call_count={self.call_count})"
                )
            instruction = self._script.pop(0)
        if isinstance(instruction, BaseException):
            raise instruction
        if isinstance(instruction, type) and issubclass(instruction, BaseException):
            raise instruction("simulated network failure (fake, not a real exception type guess)")
        return instruction


class _FailNCommitsProxy:
    """지정한 횟수(`fail_count`)만큼, **UPDATE문을 포함한 트랜잭션의**
    COMMIT만 OperationalError로 실패시키는 프록시(그 이후는 정상 통과).
    `try_create()`의 최초 생성(INSERT, UPDATE 없음)은 항상 통과시키고,
    `record_outcome()`/`mark_unknown()`처럼 UPDATE로 상태를 바꾸는 커밋만
    표적으로 삼는다 — 그래야 "GAS 호출까지는 정상 진행된 뒤, 결과 기록
    단계에서만 실패"하는 시나리오를 정확히 재현할 수 있다."""

    def __init__(self, real_conn, fail_count: int):
        self._real = real_conn
        self._remaining = fail_count
        self._saw_update_since_begin = False

    def execute(self, sql, *args, **kwargs):
        upper = sql.strip().upper()
        if upper.startswith("BEGIN"):
            self._saw_update_since_begin = False
        elif upper.startswith("UPDATE"):
            self._saw_update_since_begin = True
        elif upper == "COMMIT":
            if self._saw_update_since_begin and self._remaining > 0:
                self._remaining -= 1
                raise sqlite3.OperationalError("database is locked (simulated)")
        return self._real.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._real, name)


class GasOrchestrationTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="cshsp_commit8_3b_orchestration_")
        store.init_schema(self._tmpdir)
        self._silence = redirect_stderr(io.StringIO())
        self._silence.__enter__()

    def tearDown(self):
        self._silence.__exit__(None, None, None)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _raw_row(self, key: str):
        with store.connect(self._tmpdir) as conn:
            row = conn.execute(
                "SELECT state, fingerprint, result FROM idempotency_store WHERE key = ?", (key,)
            ).fetchone()
        return dict(row) if row else None

    # 1. 최초 성공 및 동일 요청 결과 재사용(GAS 호출 수: 1회 → 0회) ------------------
    def test_first_success_and_duplicate_reuses_cached_result_zero_extra_calls(self):
        key = "orch-first-success-dup"
        adapter = FakeGasAdapter(orch.GasResponse(success=True, result="synthetic-ok-001"))

        with store.connect(self._tmpdir) as conn:
            first = orch.execute_with_idempotency(
                conn, key=key, fingerprint=FP_A, gas_adapter=adapter, now=_now()
            )
        self.assertEqual(first.outcome, "SENT_SUCCESS")
        self.assertTrue(first.gas_called)
        self.assertEqual(adapter.call_count, 1)

        with store.connect(self._tmpdir) as conn:
            second = orch.execute_with_idempotency(
                conn, key=key, fingerprint=FP_A, gas_adapter=adapter, now=_now(1)
            )
        self.assertEqual(second.outcome, "NOT_SENT_CACHED")
        self.assertFalse(second.gas_called)
        self.assertEqual(second.store_result.result, "synthetic-ok-001")
        self.assertEqual(adapter.call_count, 1, "동일 요청 재사용 시 GAS가 추가 호출되면 안 됨")

    # 2. 동일 key·다른 fingerprint 충돌(GAS 호출 0회) ------------------------------
    def test_different_fingerprint_conflict_zero_gas_calls(self):
        key = "orch-conflict"
        adapter = FakeGasAdapter(orch.GasResponse(success=True, result="should-not-be-used"))

        with store.connect(self._tmpdir) as conn:
            orch.execute_with_idempotency(conn, key=key, fingerprint=FP_A, gas_adapter=adapter, now=_now())

        conflicting_adapter = FakeGasAdapter()  # 호출되면 즉시 AssertionError
        with store.connect(self._tmpdir) as conn:
            result = orch.execute_with_idempotency(
                conn, key=key, fingerprint=FP_B, gas_adapter=conflicting_adapter, now=_now(1)
            )
        self.assertEqual(result.outcome, "NOT_SENT_BLOCKED")
        self.assertFalse(result.gas_called)
        self.assertEqual(result.store_result.classification, "IDEMPOTENCY_CONFLICT")
        self.assertEqual(conflicting_adapter.call_count, 0)
        self.assertEqual(adapter.call_count, 1, "최초 성공 호출만 1회여야 함")

    # 3. 동일 key 동시 요청 — Fake GAS 호출 정확히 1회 ------------------------------
    def test_concurrent_requests_gas_called_exactly_once(self):
        key = "orch-concurrent"
        adapter = FakeGasAdapter(orch.GasResponse(success=True, result="synthetic-ok-concurrent"))
        barrier = threading.Barrier(WORKER_COUNT)

        def worker():
            barrier.wait()
            with store.connect(self._tmpdir) as conn:
                return orch.execute_with_idempotency(
                    conn, key=key, fingerprint=FP_A, gas_adapter=adapter, now=_now()
                )

        with ThreadPoolExecutor(max_workers=WORKER_COUNT) as ex:
            results = list(ex.map(lambda _: worker(), range(WORKER_COUNT)))

        self.assertEqual(adapter.call_count, 1, "동시 요청에서도 Fake GAS는 정확히 1회만 호출되어야 함")
        outcomes = [r.outcome for r in results]
        self.assertEqual(outcomes.count("SENT_SUCCESS"), 1, outcomes)
        # 나머지 7건은 실행권을 얻지 못해 GAS를 호출하지 않는다 — 단, 승자 스레드가
        # record_outcome까지 먼저 끝내버리는 실제 스레드 스케줄링 타이밍에 따라
        # "아직 처리중(NOT_SENT_BLOCKED)"으로 보일 수도, "이미 완료된 결과 재사용
        # (NOT_SENT_CACHED)"으로 보일 수도 있다 — 둘 다 gas_called=False이므로
        # 정상이며, 어느 쪽이 몇 건인지는 고정하지 않는다(결정론적이지 않음).
        non_winners = [r for r in results if r.outcome != "SENT_SUCCESS"]
        self.assertEqual(len(non_winners), WORKER_COUNT - 1, outcomes)
        self.assertTrue(all(not r.gas_called for r in non_winners), outcomes)
        self.assertTrue(
            all(r.outcome in ("NOT_SENT_BLOCKED", "NOT_SENT_CACHED") for r in non_winners), outcomes
        )

    # 4. 전송 전 확정 실패(실행권 자체를 얻지 못함 — RECONCILIATION_REQUIRED/POLICY_UNDETERMINED) --
    def test_execution_right_denied_before_send_zero_gas_calls(self):
        for seed_state, ttl_offset in (
            ("UNKNOWN", store.TTL_SECONDS["UNKNOWN"] + 1),  # 48h 지남 -> POLICY_UNDETERMINED
            ("SUCCEEDED", store.TTL_SECONDS["SUCCEEDED"] + 1),  # 900s 지남 -> POLICY_UNDETERMINED
        ):
            with self.subTest(seed_state=seed_state):
                key = f"orch-denied-{seed_state}"
                with store.connect(self._tmpdir) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    ts = _now().isoformat(timespec="seconds")
                    conn.execute(
                        "INSERT INTO idempotency_store (key, state, fingerprint, result, created_at, updated_at) "
                        "VALUES (?, ?, ?, NULL, ?, ?)",
                        (key, seed_state, FP_A, ts, ts),
                    )
                    conn.execute("COMMIT")

                adapter = FakeGasAdapter()  # 호출되면 즉시 AssertionError
                with store.connect(self._tmpdir) as conn:
                    result = orch.execute_with_idempotency(
                        conn, key=key, fingerprint=FP_A, gas_adapter=adapter, now=_now(ttl_offset)
                    )
                self.assertEqual(result.outcome, "NOT_SENT_BLOCKED")
                self.assertFalse(result.gas_called)
                self.assertEqual(adapter.call_count, 0)

        # 살아있는 IN_PROGRESS(다른 동시 요청이 이미 처리 중, 아직 결과 미확정)
        # 케이스 — orchestration이 아니라 store.try_create()로 직접 "생성만" 해
        # record_outcome 이전 상태(진짜 '처리 중')를 재현한다. orchestration으로
        # 끝까지 실행하면 단일 스레드 안에서 즉시 완료되어버려 이 상태를 재현할
        # 수 없다.
        key_ip = "orch-denied-in-progress-live"
        with store.connect(self._tmpdir) as conn:
            created = store.try_create(conn, key=key_ip, fingerprint=FP_A, now=_now())
        self.assertEqual(created.classification, "CREATED")

        adapter2 = FakeGasAdapter()  # 호출되면 즉시 AssertionError
        with store.connect(self._tmpdir) as conn:
            result2 = orch.execute_with_idempotency(
                conn, key=key_ip, fingerprint=FP_A, gas_adapter=adapter2, now=_now(1)
            )
        self.assertEqual(result2.outcome, "NOT_SENT_BLOCKED")
        self.assertEqual(result2.store_result.classification, "DUPLICATE_LIVE")
        self.assertEqual(result2.store_result.state, "IN_PROGRESS")
        self.assertEqual(adapter2.call_count, 0)

    # 5. 원격 반영 후 timeout — UNKNOWN 즉시 기록, 재요청 시 호출 증가 없음 ----------
    def test_timeout_after_dispatch_marks_unknown_immediately_and_blocks_retry(self):
        key = "orch-timeout-unknown"
        adapter = FakeGasAdapter(TimeoutError)  # 첫 호출에서 예외

        with store.connect(self._tmpdir) as conn:
            first = orch.execute_with_idempotency(
                conn, key=key, fingerprint=FP_A, gas_adapter=adapter, now=_now()
            )
        self.assertEqual(first.outcome, "SENT_UNCERTAIN")
        self.assertTrue(first.gas_called)
        self.assertTrue(first.record_write_ok, "mark_unknown 폴백이 성공해야 함")
        self.assertEqual(adapter.call_count, 1)

        raw = self._raw_row(key)
        self.assertEqual(raw["state"], "UNKNOWN", "timeout 감지 즉시(60초 대기 없이) UNKNOWN으로 전이되어야 함")

        # 재요청(클라이언트의 재시도) — 같은 key·fingerprint, GAS는 추가 호출되면 안 됨
        with store.connect(self._tmpdir) as conn:
            retry = orch.execute_with_idempotency(
                conn, key=key, fingerprint=FP_A, gas_adapter=adapter, now=_now(1)
            )
        self.assertEqual(retry.outcome, "NOT_SENT_BLOCKED")
        self.assertFalse(retry.gas_called)
        self.assertEqual(adapter.call_count, 1, "재요청 시 Fake GAS 호출 횟수가 증가하면 안 됨")

    # 6. 성공 후 로컬 결과 저장 실패 — 재호출 없음, mark_unknown 폴백 성공 ------------
    def test_success_then_local_record_failure_no_recall_marks_unknown(self):
        key = "orch-success-record-fail"
        adapter = FakeGasAdapter(orch.GasResponse(success=True, result="synthetic-ok-should-be-lost"))

        with store.connect(self._tmpdir) as real_conn:
            # record_outcome()의 COMMIT 1회만 실패시키고, 뒤이은 mark_unknown()의
            # COMMIT은 통과시킨다(폴백 성공 시나리오).
            proxy = _FailNCommitsProxy(real_conn, fail_count=1)
            result = orch.execute_with_idempotency(
                proxy, key=key, fingerprint=FP_A, gas_adapter=adapter, now=_now()
            )

        self.assertEqual(result.outcome, "SENT_UNCERTAIN")
        self.assertTrue(result.gas_called)
        self.assertEqual(adapter.call_count, 1, "로컬 기록 실패가 GAS 재호출로 이어지면 안 됨")
        self.assertTrue(result.record_write_ok, "mark_unknown 폴백은 성공해야 함(fail_count=1)")

        raw = self._raw_row(key)
        self.assertEqual(raw["state"], "UNKNOWN")
        self.assertIsNone(raw["result"], "SUCCEEDED 기록이 실패했으므로 result가 남아있으면 안 됨")

    # 7. UNKNOWN 기록까지 실패한 경우 — 실행권 재부여 차단(안전망 확인) --------------
    def test_both_record_and_mark_unknown_fail_execution_right_not_regranted(self):
        key = "orch-double-failure"
        adapter = FakeGasAdapter(orch.GasResponse(success=True, result="synthetic-ok-double-fail"))

        with store.connect(self._tmpdir) as real_conn:
            # record_outcome COMMIT 실패 + 뒤이은 mark_unknown COMMIT도 실패(fail_count=2)
            proxy = _FailNCommitsProxy(real_conn, fail_count=2)
            result = orch.execute_with_idempotency(
                proxy, key=key, fingerprint=FP_A, gas_adapter=adapter, now=_now()
            )

        self.assertEqual(result.outcome, "SENT_UNCERTAIN")
        self.assertFalse(result.record_write_ok, "두 기록 시도 모두 실패해야 하는 시나리오")
        self.assertEqual(adapter.call_count, 1, "기록이 이중으로 실패해도 GAS를 재호출하면 안 됨")

        raw = self._raw_row(key)
        self.assertEqual(raw["state"], "IN_PROGRESS", "두 UPDATE 모두 rollback되어 원래 상태로 남아야 함")

        # 안전망 확인: 정상 연결로 같은 key·fingerprint 재시도 시도 — 60초 TTL
        # 이내이므로 실행권이 재부여되면 안 된다(DUPLICATE_LIVE여야 함, CREATED 아님).
        fresh_adapter = FakeGasAdapter()  # 호출되면 즉시 AssertionError
        with store.connect(self._tmpdir) as conn:
            safety_net = orch.execute_with_idempotency(
                conn, key=key, fingerprint=FP_A, gas_adapter=fresh_adapter, now=_now(1)
            )
        self.assertEqual(safety_net.outcome, "NOT_SENT_BLOCKED")
        self.assertEqual(safety_net.store_result.classification, "DUPLICATE_LIVE")
        self.assertNotEqual(safety_net.store_result.classification, "CREATED")
        self.assertEqual(fresh_adapter.call_count, 0, "실행권이 재부여되지 않았으므로 GAS 호출도 없어야 함")

    # 7b. 이중 기록 실패 "이후 IN_PROGRESS TTL까지 경과" — 기존 lazy 전이로 UNKNOWN 수렴 --
    def test_double_record_failure_then_ttl_elapses_converges_to_unknown_without_gas_recall(self):
        """직전 테스트(#7)는 "이중 실패 직후, TTL 이내"의 안전망만 확인했다.
        이 테스트는 그 상태에서 **가상시계만** IN_PROGRESS TTL 경과 후로
        이동시켜(실제 대기 없음), 기존 lazy 전이 메커니즘(`try_create()`가
        만료된 IN_PROGRESS를 발견하면 수행하는 UNKNOWN 전이)이 **명시적
        mark_unknown() 기록이 두 번 다 실패했음에도 불구하고** 결국 올바르게
        동작함을 확인한다 — Fake GAS 누적 호출은 여전히 1회여야 한다."""
        key = "orch-double-failure-ttl-elapsed"
        adapter = FakeGasAdapter(orch.GasResponse(success=True, result="synthetic-ok-ttl-elapsed"))

        with store.connect(self._tmpdir) as real_conn:
            proxy = _FailNCommitsProxy(real_conn, fail_count=2)  # record_outcome + mark_unknown 모두 실패
            first = orch.execute_with_idempotency(
                proxy, key=key, fingerprint=FP_A, gas_adapter=adapter, now=_now()
            )
        self.assertEqual(first.outcome, "SENT_UNCERTAIN")
        self.assertFalse(first.record_write_ok)
        self.assertEqual(adapter.call_count, 1)
        self.assertEqual(
            self._raw_row(key)["state"], "IN_PROGRESS", "이중 실패 직후에는 원래 상태로 남아야 함"
        )

        ttl = store.TTL_SECONDS["IN_PROGRESS"]
        # 실제 대기 없이 가상시계만 TTL 경과 후로 이동시켜 같은 key·fingerprint로 재요청
        with store.connect(self._tmpdir) as conn:
            retry = orch.execute_with_idempotency(
                conn, key=key, fingerprint=FP_A, gas_adapter=adapter, now=_now(ttl + 1)
            )

        self.assertEqual(retry.outcome, "NOT_SENT_BLOCKED")
        self.assertFalse(retry.gas_called)
        self.assertEqual(adapter.call_count, 1, "TTL 경과 후 재요청에서도 Fake GAS 누적 호출은 1회여야 함")
        self.assertEqual(retry.store_result.classification, "RECONCILIATION_REQUIRED")

        raw = self._raw_row(key)
        self.assertEqual(
            raw["state"], "UNKNOWN", "TTL 경과 후에는 기존 lazy 전이로 UNKNOWN이 되어야 함"
        )
        with store.connect(self._tmpdir) as conn:
            row_count = conn.execute(
                "SELECT COUNT(*) FROM idempotency_store WHERE key = ?", (key,)
            ).fetchone()[0]
        self.assertEqual(row_count, 1, "행이 삭제되지 않고 보존되어야 함")

    # 7c. 실행권 획득 후, 전송 '준비' 단계 실패 — GAS 호출 0회, 기존 행 보존 ---------
    def test_prep_failure_after_execution_right_zero_gas_calls_row_preserved(self):
        """실행권(CREATED)을 얻은 **직후**, 실제 GAS 전송 **전**의 준비 단계
        (`prepare_dispatch`, 예: HMAC 서명 생성)에서 실패하는 경우를
        재현한다. 이는 실행권 자체를 얻지 못해 차단되는 기존 테스트
        (`test_execution_right_denied_before_send_zero_gas_calls`,
        outcome=`NOT_SENT_BLOCKED`)와 질적으로 다르다 — 여기서는 실행권을
        **얻었다.** 이전 STEP까지 이 계층에는 이런 준비 단계 자체가 없어서
        주입할 지점이 없었다 — 이번 STEP에서 `prepare_dispatch` 파라미터를
        신설해 그 지점을 명시적으로 추가했다(모듈 docstring 참조)."""
        key = "orch-prep-failure"

        def failing_prepare():
            raise ValueError("synthetic HMAC signing failure (fake, not a real crypto error)")

        adapter = FakeGasAdapter()  # 호출되면 즉시 AssertionError — 0회 호출 기대

        with store.connect(self._tmpdir) as conn:
            result = orch.execute_with_idempotency(
                conn, key=key, fingerprint=FP_A, gas_adapter=adapter,
                prepare_dispatch=failing_prepare, now=_now(),
            )

        self.assertEqual(result.outcome, "NOT_SENT_PREP_FAILED")
        self.assertNotEqual(
            result.outcome, "NOT_SENT_BLOCKED", "실행권 자체를 얻지 못한 차단과는 구분되어야 함"
        )
        self.assertFalse(result.gas_called)
        self.assertEqual(adapter.call_count, 0, "준비 단계 실패 시 GAS는 호출되면 안 됨")

        raw = self._raw_row(key)
        self.assertIsNotNone(raw, "실행권 획득으로 생성된 행이 보존되어야 함")
        self.assertEqual(
            raw["state"], "IN_PROGRESS",
            "준비 단계 실패는 '확정 미전송'이므로 UNKNOWN 등으로 임의 변경하지 않는다",
        )

        # 정책 미확정 상태에서 자동 재실행을 허용하지 않는다는 불변조건의 실제 사례:
        # 같은 key·fingerprint로 즉시 재시도해도(아직 60초 TTL 이내) 실행권이
        # 다시 부여되지 않아야 한다 — 준비 실패로 "확정 미전송"임을 알더라도
        # 기존 TTL 차단 규칙을 그대로 따르며 임의로 즉시 재발급하지 않는다.
        adapter2 = FakeGasAdapter()  # 호출되면 즉시 AssertionError
        with store.connect(self._tmpdir) as conn:
            immediate_retry = orch.execute_with_idempotency(
                conn, key=key, fingerprint=FP_A, gas_adapter=adapter2, now=_now(1)
            )
        self.assertEqual(immediate_retry.outcome, "NOT_SENT_BLOCKED")
        self.assertEqual(immediate_retry.store_result.classification, "DUPLICATE_LIVE")
        self.assertEqual(adapter2.call_count, 0)

    # 8. 명시적 수동 조정 후 결과 조회 ------------------------------------------------
    def test_manual_reconciliation_then_result_lookup(self):
        key = "orch-manual-reconcile"
        adapter = FakeGasAdapter(TimeoutError)

        with store.connect(self._tmpdir) as conn:
            uncertain = orch.execute_with_idempotency(
                conn, key=key, fingerprint=FP_A, gas_adapter=adapter, now=_now()
            )
        self.assertEqual(uncertain.outcome, "SENT_UNCERTAIN")
        self.assertEqual(self._raw_row(key)["state"], "UNKNOWN")

        # 운영자가 Sheets를 직접 확인한 뒤 수동 조정(ADR-017 §23 경로)
        with store.connect(self._tmpdir) as conn:
            store.reconcile_unknown(
                conn, key=key, resolved_state="SUCCEEDED", performed_by="qa_operator_01",
                result="synthetic-manually-confirmed-ok", now=_now(2),
            )

        with store.connect(self._tmpdir) as conn:
            fetched = store.get_completed_result(conn, key=key, fingerprint=FP_A, now=_now(3))
        self.assertEqual(fetched.classification, "CACHED_RESULT")
        self.assertEqual(fetched.result, "synthetic-manually-confirmed-ok")
        self.assertEqual(adapter.call_count, 1, "수동 조정 과정에서 GAS가 호출되면 안 됨")


if __name__ == "__main__":
    unittest.main(verbosity=2)
