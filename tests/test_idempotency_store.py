# -*- coding: utf-8 -*-
"""
CSHSP Sprint8 Commit8-3b — src/idempotency/idempotency_store.py 단위 테스트 v2

격리 개발 STEP의 자동 테스트다. 운영 GAS·Google Sheets에 접근하지 않으며,
모든 데이터는 OS 임시 디렉터리의 SQLite 파일에만 기록한다(테스트 종료 시
정리). 예약 생성·변경 API를 호출하지 않는다. 모든 key/fingerprint/result는
합성(synthetic) 값만 사용하며 실제 payload·개인정보를 포함하지 않는다.

v2 추가: payload 충돌 차단(IDEM-02), 완료 결과 재사용(IDEM-01), FAILED_RETRYABLE
재시도 허용(terminal 아님) 검증을 추가했다. 기존 14개 테스트는 fingerprint
파라미터 추가에 맞춰 호출부만 갱신했고 검증 로직은 보존했다(회귀 확인).
"""
from __future__ import annotations

import io
import shutil
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
from json_store import KST  # noqa: E402

WORKER_COUNT = 8
FP_A = "synthetic-fingerprint-aaaa0001"
FP_B = "synthetic-fingerprint-bbbb0002"


def _now(offset_seconds: float = 0.0) -> datetime:
    """고정된 기준 시각(2026-01-01 00:00:00 KST)에서 offset만큼 이동한 시각을
    반환한다 — 실제 벽시계에 의존하지 않아 TTL 경계 테스트가 결정론적이다."""
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=KST)
    return base + timedelta(seconds=offset_seconds)


def _seed_row(tmpdir, key: str, state: str, fingerprint: str = FP_A, result=None, at: datetime = None):
    at = at or _now()
    ts = at.isoformat(timespec="seconds")
    with store.connect(tmpdir) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO idempotency_store (key, state, fingerprint, result, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (key, state, fingerprint, result, ts, ts),
        )
        conn.execute("COMMIT")


class IdempotencyStoreTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="cshsp_commit8_3b_idempotency_")
        store.init_schema(self._tmpdir)
        self._silence = redirect_stderr(io.StringIO())
        self._silence.__enter__()  # 계측 로그(stderr)로 테스트 출력이 섞이지 않도록 억제

    def tearDown(self):
        self._silence.__exit__(None, None, None)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _row_count(self) -> int:
        with store.connect(self._tmpdir) as conn:
            return conn.execute("SELECT COUNT(*) FROM idempotency_store").fetchone()[0]

    def _raw_row(self, key: str):
        with store.connect(self._tmpdir) as conn:
            row = conn.execute(
                "SELECT state, fingerprint, result FROM idempotency_store WHERE key = ?", (key,)
            ).fetchone()
        return dict(row) if row else None

    # ===================== 회귀 — 기존 14개 테스트(fingerprint 반영) =====================

    # 1. 동일 key 동시 생성 — 동일 fingerprint면 정확히 1건만 CREATED --------------
    def test_concurrent_same_key_exactly_one_created(self):
        key = "dr-b-02-concurrent-same-key"
        barrier = threading.Barrier(WORKER_COUNT)

        def worker():
            barrier.wait()
            with store.connect(self._tmpdir) as conn:
                return store.try_create(conn, key=key, fingerprint=FP_A, now=_now())

        with ThreadPoolExecutor(max_workers=WORKER_COUNT) as ex:
            results = list(ex.map(lambda _: worker(), range(WORKER_COUNT)))

        classifications = [r.classification for r in results]
        self.assertEqual(classifications.count("CREATED"), 1, classifications)
        self.assertEqual(classifications.count("DUPLICATE_LIVE"), WORKER_COUNT - 1)
        self.assertEqual(self._row_count(), 1)
        self.assertEqual(self._raw_row(key)["fingerprint"], FP_A)

    # 2. 서로 다른 key 독립성 ----------------------------------------------------
    def test_distinct_keys_are_independent(self):
        keys = [f"dr-b-02-distinct-{i}" for i in range(WORKER_COUNT)]
        with store.connect(self._tmpdir) as conn:
            results = [store.try_create(conn, key=k, fingerprint=FP_A, now=_now()) for k in keys]
        self.assertTrue(all(r.classification == "CREATED" for r in results))
        self.assertEqual(self._row_count(), WORKER_COUNT)

    # 3. 상태전이 허용 — IN_PROGRESS → SUCCEEDED/FAILED_RETRYABLE/FAILED_FINAL ----
    def test_record_outcome_allowed_from_in_progress(self):
        for outcome in ("SUCCEEDED", "FAILED_RETRYABLE", "FAILED_FINAL"):
            with self.subTest(outcome=outcome):
                key = f"dr-b-02-outcome-{outcome}"
                with store.connect(self._tmpdir) as conn:
                    created = store.try_create(conn, key=key, fingerprint=FP_A, now=_now())
                    self.assertEqual(created.classification, "CREATED")
                    result = store.record_outcome(
                        conn, key=key, outcome_state=outcome, now=_now(1)
                    )
                    self.assertEqual(result.state, outcome)
                    effective = store.get_effective_state(conn, key=key, now=_now(1))
                    self.assertEqual(effective.state, outcome)

    # 4. 상태전이 거절 — IN_PROGRESS가 아닌 레코드에는 record_outcome 금지 --------
    def test_record_outcome_rejected_when_not_in_progress(self):
        key = "dr-b-02-outcome-rejected"
        with store.connect(self._tmpdir) as conn:
            store.try_create(conn, key=key, fingerprint=FP_A, now=_now())
            store.record_outcome(conn, key=key, outcome_state="SUCCEEDED", now=_now(1))
            with self.assertRaises(ValueError):
                store.record_outcome(conn, key=key, outcome_state="FAILED_FINAL", now=_now(2))

    def test_record_outcome_rejects_invalid_outcome_state(self):
        key = "dr-b-02-outcome-invalid"
        with store.connect(self._tmpdir) as conn:
            store.try_create(conn, key=key, fingerprint=FP_A, now=_now())
            with self.assertRaises(ValueError):
                store.record_outcome(conn, key=key, outcome_state="UNKNOWN", now=_now(1))

    # 5. TTL 경계 — 5개 상태 전부(before/boundary/after), 읽기 전용 조회 ------------
    def test_ttl_boundary_all_states(self):
        for state, ttl in store.TTL_SECONDS.items():
            with self.subTest(state=state):
                key = f"dr-b-02-ttl-{state}"
                _seed_row(self._tmpdir, key, state, at=_now())
                with store.connect(self._tmpdir) as conn:
                    before = store.get_effective_state(conn, key=key, now=_now(ttl - 1))
                    boundary = store.get_effective_state(conn, key=key, now=_now(ttl))
                    after = store.get_effective_state(conn, key=key, now=_now(ttl + 1))

                self.assertEqual(before.state, state, "만료 전 raw state 불일치")
                self.assertEqual(boundary.state, state, "경계(TTL초)는 정책값 그대로")
                expected_live = "RECONCILIATION_REQUIRED" if state == "UNKNOWN" else "DUPLICATE_LIVE"
                self.assertEqual(before.classification, expected_live)
                self.assertEqual(boundary.classification, expected_live)
                if state == "IN_PROGRESS":
                    self.assertEqual(after.classification, "RECONCILIATION_REQUIRED")
                else:
                    self.assertEqual(after.classification, "POLICY_UNDETERMINED")
                    self.assertEqual(after.state, state, "정책 미확정 상태는 raw state가 변경되지 않아야 함")

    # 6. 두 호출 순서(직접 try_create vs 선행 조회 후 try_create)가 동일 결과 ------
    def test_two_call_paths_same_result_for_expired_in_progress(self):
        ttl = store.TTL_SECONDS["IN_PROGRESS"]

        key_a = "dr-b-02-path-a"
        with store.connect(self._tmpdir) as conn:
            store.try_create(conn, key=key_a, fingerprint=FP_A, now=_now())
        with store.connect(self._tmpdir) as conn:
            result_a = store.try_create(conn, key=key_a, fingerprint=FP_A, now=_now(ttl + 1))

        key_b = "dr-b-02-path-b"
        with store.connect(self._tmpdir) as conn:
            store.try_create(conn, key=key_b, fingerprint=FP_A, now=_now())
        with store.connect(self._tmpdir) as conn:
            store.get_effective_state(conn, key=key_b, now=_now(ttl + 1))
            result_b = store.try_create(conn, key=key_b, fingerprint=FP_A, now=_now(ttl + 1))

        with store.connect(self._tmpdir) as conn:
            get_result_view = store.get_completed_result(conn, key=key_b, fingerprint=FP_A, now=_now(ttl + 1))

        self.assertEqual(result_a.classification, "RECONCILIATION_REQUIRED")
        self.assertEqual(result_b.classification, "RECONCILIATION_REQUIRED")
        self.assertEqual(result_a.classification, result_b.classification)
        self.assertEqual(result_a.state, result_b.state)
        self.assertEqual(get_result_view.classification, "RECONCILIATION_REQUIRED", "3번째 경로(get_completed_result)도 동일해야 함")

    # 7. UNKNOWN 자동 재실행 차단 + 행 보존 ---------------------------------------
    def test_unknown_blocks_auto_reexecution_and_preserves_row(self):
        key = "dr-b-02-unknown-block"
        ttl = store.TTL_SECONDS["IN_PROGRESS"]
        with store.connect(self._tmpdir) as conn:
            store.try_create(conn, key=key, fingerprint=FP_A, now=_now())
        with store.connect(self._tmpdir) as conn:
            transitioned = store.try_create(conn, key=key, fingerprint=FP_A, now=_now(ttl + 1))
            self.assertEqual(transitioned.classification, "RECONCILIATION_REQUIRED")

        self.assertEqual(self._row_count(), 1, "UNKNOWN 전이 후 행이 삭제됨(ADR 위반)")

        with store.connect(self._tmpdir) as conn:
            retry = store.try_create(conn, key=key, fingerprint=FP_A, now=_now(ttl + 2))
        self.assertEqual(retry.classification, "RECONCILIATION_REQUIRED")
        self.assertNotEqual(retry.classification, "CREATED")
        self.assertEqual(self._row_count(), 1)

    # 8. 정책 미확정 상태 — 만료 후 삭제·재생성 차단, 행 보존 ------------------------
    def test_policy_undetermined_states_block_without_mutation(self):
        for state in ("SUCCEEDED", "FAILED_FINAL", "UNKNOWN"):
            with self.subTest(state=state):
                key = f"dr-b-02-policy-undetermined-{state}"
                ttl = store.TTL_SECONDS[state]
                _seed_row(self._tmpdir, key, state, at=_now())

                with store.connect(self._tmpdir) as conn:
                    result = store.try_create(conn, key=key, fingerprint=FP_A, now=_now(ttl + 1))

                self.assertEqual(result.classification, "POLICY_UNDETERMINED")
                self.assertNotEqual(result.classification, "CREATED")
                raw = self._raw_row(key)
                self.assertIsNotNone(raw, f"{state} 만료 행이 삭제됨(정책 미확정 상태에서는 보존해야 함)")
                self.assertEqual(raw["state"], state, f"{state} 만료 행의 state 컬럼이 임의로 변경됨")

    # 9. 수동 조정 절차(reconcile_unknown) ----------------------------------------
    def test_reconcile_unknown_manual_transition(self):
        key = "dr-b-02-reconcile"
        ttl = store.TTL_SECONDS["IN_PROGRESS"]
        with store.connect(self._tmpdir) as conn:
            store.try_create(conn, key=key, fingerprint=FP_A, now=_now())
            store.try_create(conn, key=key, fingerprint=FP_A, now=_now(ttl + 1))  # IN_PROGRESS -> UNKNOWN

            with self.assertRaises(ValueError):
                store.reconcile_unknown(
                    conn, key=key, resolved_state="SUCCEEDED", performed_by="", now=_now(ttl + 2)
                )

            result = store.reconcile_unknown(
                conn, key=key, resolved_state="SUCCEEDED", performed_by="qa_operator_01", now=_now(ttl + 2)
            )
            self.assertEqual(result.state, "SUCCEEDED")

            with self.assertRaises(ValueError):
                store.reconcile_unknown(
                    conn, key=key, resolved_state="FAILED_FINAL",
                    performed_by="qa_operator_01", now=_now(ttl + 3),
                )

    def test_reconcile_unknown_rejects_retryable_target(self):
        key = "dr-b-02-reconcile-invalid-target"
        with store.connect(self._tmpdir) as conn:
            store.try_create(conn, key=key, fingerprint=FP_A, now=_now())
            store.try_create(conn, key=key, fingerprint=FP_A, now=_now(store.TTL_SECONDS["IN_PROGRESS"] + 1))
            with self.assertRaises(ValueError):
                store.reconcile_unknown(
                    conn, key=key, resolved_state="FAILED_RETRYABLE",
                    performed_by="qa_operator_01", now=_now(1000),
                )

    # 10. key/fingerprint 형식 검증 -------------------------------------------------
    def test_invalid_key_format_rejected(self):
        with store.connect(self._tmpdir) as conn:
            with self.assertRaises(ValueError):
                store.try_create(conn, key="invalid key with space", fingerprint=FP_A, now=_now())
            with self.assertRaises(ValueError):
                store.try_create(conn, key="", fingerprint=FP_A, now=_now())

    def test_invalid_fingerprint_format_rejected(self):
        with store.connect(self._tmpdir) as conn:
            with self.assertRaises(ValueError):
                store.try_create(conn, key="dr-b-02-badfp", fingerprint="has space", now=_now())

    # 11. 트랜잭션 실패 시 rollback + 오류 전달(예상 밖 OperationalError 시뮬레이션) --
    def test_operational_error_rolls_back_and_propagates(self):
        """sqlite3.Connection.execute는 인스턴스 속성으로 교체할 수 없으므로
        (C 확장 타입 제약), 실제 connect()가 반환하는 연결을 감싸는 얇은
        프록시로 COMMIT 시점에만 OperationalError를 주입한다."""
        import sqlite3

        key = "dr-b-02-operational-error"

        class _FlakyProxy:
            def __init__(self, real_conn):
                self._real = real_conn

            def execute(self, sql, *args, **kwargs):
                if sql.strip().upper() == "COMMIT":
                    raise sqlite3.OperationalError("database is locked (simulated)")
                return self._real.execute(sql, *args, **kwargs)

            def __getattr__(self, name):
                return getattr(self._real, name)

        with store.connect(self._tmpdir) as real_conn:
            proxy = _FlakyProxy(real_conn)
            with self.assertRaises(store.IdempotencyError):
                store.try_create(proxy, key=key, fingerprint=FP_A, now=_now())

        self.assertEqual(self._row_count(), 0, "OperationalError 후 rollback이 수행되지 않음")

    # 12. 정리(cleanup) — 임시 리소스 ------------------------------------------------
    def test_cleanup_leaves_no_residue(self):
        tmpdir = tempfile.mkdtemp(prefix="cshsp_commit8_3b_idempotency_cleanup_")
        try:
            store.init_schema(tmpdir)
            with store.connect(tmpdir) as conn:
                store.try_create(conn, key="dr-b-02-cleanup-check", fingerprint=FP_A, now=_now())
            db_path = Path(tmpdir) / "idempotency.db"
            self.assertTrue(db_path.exists())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        self.assertFalse(Path(tmpdir).exists())

    # ===================== 신규 — payload 충돌 차단(IDEM-02) =====================

    # 13. 동일 key·같은 fingerprint 중복 요청(IN_PROGRESS-live, FINAL-live) ---------
    def test_same_key_same_fingerprint_is_duplicate_not_conflict(self):
        key = "dr-b-02-same-fp-in-progress"
        with store.connect(self._tmpdir) as conn:
            store.try_create(conn, key=key, fingerprint=FP_A, now=_now())
            dup = store.try_create(conn, key=key, fingerprint=FP_A, now=_now(1))
        self.assertEqual(dup.classification, "DUPLICATE_LIVE")

        key2 = "dr-b-02-same-fp-final"
        _seed_row(self._tmpdir, key2, "SUCCEEDED", fingerprint=FP_A, at=_now())
        with store.connect(self._tmpdir) as conn:
            dup2 = store.try_create(conn, key=key2, fingerprint=FP_A, now=_now(1))
        self.assertEqual(dup2.classification, "DUPLICATE_LIVE")
        self.assertEqual(self._row_count(), 2, "중복 요청으로 새 행이 추가되면 안 됨")

    # 14. 동일 key·다른 fingerprint 충돌 + 행 불변(IDEM-02) --------------------------
    def test_same_key_different_fingerprint_conflict_preserves_row(self):
        for state in ("IN_PROGRESS", "SUCCEEDED", "FAILED_RETRYABLE", "FAILED_FINAL"):
            with self.subTest(state=state):
                key = f"dr-b-02-conflict-{state}"
                if state == "IN_PROGRESS":
                    with store.connect(self._tmpdir) as conn:
                        store.try_create(conn, key=key, fingerprint=FP_A, now=_now())
                else:
                    _seed_row(self._tmpdir, key, state, fingerprint=FP_A, at=_now())

                before = self._raw_row(key)
                with store.connect(self._tmpdir) as conn:
                    conflict = store.try_create(conn, key=key, fingerprint=FP_B, now=_now(1))
                after = self._raw_row(key)

                self.assertEqual(conflict.classification, "IDEMPOTENCY_CONFLICT")
                self.assertEqual(before, after, "충돌 시 기존 행이 조금이라도 변경되면 안 됨")

    # 15. 동시 충돌 요청에서도 최초 행·fingerprint 보존 ------------------------------
    def test_concurrent_conflicting_fingerprints_preserve_first_winner(self):
        key = "dr-b-02-concurrent-conflict"
        barrier = threading.Barrier(WORKER_COUNT)
        fingerprints = [f"synthetic-fp-worker-{i:04d}" for i in range(WORKER_COUNT)]

        def worker(fp):
            barrier.wait()
            with store.connect(self._tmpdir) as conn:
                return store.try_create(conn, key=key, fingerprint=fp, now=_now())

        with ThreadPoolExecutor(max_workers=WORKER_COUNT) as ex:
            results = list(ex.map(worker, fingerprints))

        classifications = [r.classification for r in results]
        self.assertEqual(classifications.count("CREATED"), 1, classifications)
        self.assertEqual(classifications.count("IDEMPOTENCY_CONFLICT"), WORKER_COUNT - 1)
        self.assertEqual(self._row_count(), 1)

        winner_index = classifications.index("CREATED")
        winning_fp = fingerprints[winner_index]
        self.assertEqual(self._raw_row(key)["fingerprint"], winning_fp, "최초 생성자의 fingerprint가 보존되어야 함")

    # ===================== 신규 — 완료 결과 재사용(IDEM-01) =====================

    # 16. 완료 결과 재조회 ------------------------------------------------------------
    def test_get_completed_result_returns_cached_value_for_final_states(self):
        key = "dr-b-02-cached-result"
        synthetic_result = "synthetic-outcome-token-001"  # 비식별 합성값, PII/payload 아님
        with store.connect(self._tmpdir) as conn:
            store.try_create(conn, key=key, fingerprint=FP_A, now=_now())
            store.record_outcome(conn, key=key, outcome_state="SUCCEEDED", result=synthetic_result, now=_now(1))
            fetched = store.get_completed_result(conn, key=key, fingerprint=FP_A, now=_now(2))
        self.assertEqual(fetched.classification, "CACHED_RESULT")
        self.assertEqual(fetched.result, synthetic_result)

    def test_get_completed_result_conflict_on_different_fingerprint(self):
        key = "dr-b-02-cached-result-conflict"
        with store.connect(self._tmpdir) as conn:
            store.try_create(conn, key=key, fingerprint=FP_A, now=_now())
            store.record_outcome(conn, key=key, outcome_state="SUCCEEDED", result="x", now=_now(1))
            fetched = store.get_completed_result(conn, key=key, fingerprint=FP_B, now=_now(2))
        self.assertEqual(fetched.classification, "IDEMPOTENCY_CONFLICT")
        self.assertIsNone(fetched.result)

    def test_get_completed_result_not_yet_available_for_in_progress(self):
        key = "dr-b-02-cached-result-pending"
        with store.connect(self._tmpdir) as conn:
            store.try_create(conn, key=key, fingerprint=FP_A, now=_now())
            fetched = store.get_completed_result(conn, key=key, fingerprint=FP_A, now=_now(1))
        self.assertEqual(fetched.classification, "DUPLICATE_LIVE")
        self.assertIsNone(fetched.result)

    # 17. 상태·결과 기록 중 실패 시 전체 rollback ------------------------------------
    def test_record_outcome_operational_error_rolls_back_state_and_result_together(self):
        import sqlite3

        key = "dr-b-02-outcome-rollback"

        class _FlakyProxy:
            def __init__(self, real_conn):
                self._real = real_conn

            def execute(self, sql, *args, **kwargs):
                if sql.strip().upper() == "COMMIT":
                    raise sqlite3.OperationalError("database is locked (simulated)")
                return self._real.execute(sql, *args, **kwargs)

            def __getattr__(self, name):
                return getattr(self._real, name)

        with store.connect(self._tmpdir) as real_conn:
            store.try_create(real_conn, key=key, fingerprint=FP_A, now=_now())

        with store.connect(self._tmpdir) as real_conn:
            proxy = _FlakyProxy(real_conn)
            with self.assertRaises(store.IdempotencyError):
                store.record_outcome(
                    proxy, key=key, outcome_state="SUCCEEDED", result="should-not-persist", now=_now(1)
                )

        raw = self._raw_row(key)
        self.assertEqual(raw["state"], "IN_PROGRESS", "상태가 rollback되지 않음(부분 커밋 의심)")
        self.assertIsNone(raw["result"], "result가 rollback되지 않음(상태와 결과가 분리 커밋됨)")

    # ===================== 신규 — FAILED_RETRYABLE은 terminal이 아님 =====================

    # 18. FAILED_RETRYABLE 생존 중 재시도 허용(RETRY_ACCEPTED) -----------------------
    def test_failed_retryable_allows_retry_with_same_fingerprint(self):
        key = "dr-b-02-retryable-allow"
        _seed_row(self._tmpdir, key, "FAILED_RETRYABLE", fingerprint=FP_A, at=_now())
        with store.connect(self._tmpdir) as conn:
            retried = store.try_create(conn, key=key, fingerprint=FP_A, now=_now(1))
        self.assertEqual(retried.classification, "RETRY_ACCEPTED")
        self.assertEqual(retried.state, "IN_PROGRESS")
        raw = self._raw_row(key)
        self.assertEqual(raw["state"], "IN_PROGRESS", "재오픈된 행이 IN_PROGRESS로 전이되어야 함")
        self.assertEqual(self._row_count(), 1, "재오픈은 기존 행을 재사용해야 하며 새 행을 만들지 않음")

    def test_failed_retryable_different_fingerprint_is_conflict_not_retry(self):
        key = "dr-b-02-retryable-conflict"
        _seed_row(self._tmpdir, key, "FAILED_RETRYABLE", fingerprint=FP_A, at=_now())
        with store.connect(self._tmpdir) as conn:
            result = store.try_create(conn, key=key, fingerprint=FP_B, now=_now(1))
        self.assertEqual(result.classification, "IDEMPOTENCY_CONFLICT")
        self.assertEqual(self._raw_row(key)["state"], "FAILED_RETRYABLE", "충돌 시 재오픈되면 안 됨")

    # 18b. 살아있는 FAILED_RETRYABLE에 동일 key·fingerprint 동시 요청 — 실행권 단일성 --
    def test_concurrent_retry_on_live_failed_retryable_grants_single_execution_right(self):
        """재시도 재오픈(FAILED_RETRYABLE→IN_PROGRESS)도 BEGIN IMMEDIATE로
        직렬화되므로, 동시에 들어온 동일 key·동일 fingerprint 요청 중
        **정확히 1건만** RETRY_ACCEPTED(실행권 획득)를 받고 나머지는
        DUPLICATE_LIVE(실행권 없음)여야 한다. 재시도 상한(ADR-017 §16
        "최대 3회")·간격(지수 백오프+Jitter)은 이 모듈의 책임이 아니며
        호출부(클라이언트) 책임으로 남는다 — 이 테스트는 "실행권이 정확히
        1건만 부여되는가"만 검증하고, 재시도 횟수·간격 제한은 검증하지
        않는다(모듈 docstring의 기존 미확정 사항 재확인)."""
        key = "dr-b-02-concurrent-retry-failed-retryable"
        _seed_row(self._tmpdir, key, "FAILED_RETRYABLE", fingerprint=FP_A, at=_now())
        barrier = threading.Barrier(WORKER_COUNT)

        def worker():
            barrier.wait()
            with store.connect(self._tmpdir) as conn:
                return store.try_create(conn, key=key, fingerprint=FP_A, now=_now(1))

        with ThreadPoolExecutor(max_workers=WORKER_COUNT) as ex:
            results = list(ex.map(lambda _: worker(), range(WORKER_COUNT)))

        classifications = [r.classification for r in results]
        self.assertEqual(classifications.count("RETRY_ACCEPTED"), 1, classifications)
        self.assertEqual(classifications.count("DUPLICATE_LIVE"), WORKER_COUNT - 1)
        self.assertEqual(self._row_count(), 1, "재시도 재오픈은 새 행을 만들지 않고 기존 행을 재사용해야 함")
        self.assertEqual(self._raw_row(key)["state"], "IN_PROGRESS")
        self.assertEqual(self._raw_row(key)["fingerprint"], FP_A)

    # 19. 만료된 FAILED_RETRYABLE은 재시도 허용이 아니라 POLICY_UNDETERMINED -------
    def test_failed_retryable_expired_is_policy_undetermined_not_retry_accepted(self):
        key = "dr-b-02-retryable-expired"
        ttl = store.TTL_SECONDS["FAILED_RETRYABLE"]
        _seed_row(self._tmpdir, key, "FAILED_RETRYABLE", fingerprint=FP_A, at=_now())
        with store.connect(self._tmpdir) as conn:
            result = store.try_create(conn, key=key, fingerprint=FP_A, now=_now(ttl + 1))
        self.assertEqual(result.classification, "POLICY_UNDETERMINED")
        self.assertNotEqual(result.classification, "RETRY_ACCEPTED")
        self.assertEqual(self._raw_row(key)["state"], "FAILED_RETRYABLE", "만료 후에도 행이 보존되어야 함")

    # ===================== 신규 — 만료 후 자동 재실행 차단(전 경로 일관성) =====================

    # 20. 유효 상태가 UNKNOWN이면 물리적 상태와 무관하게 모든 조회 경로가 차단 ------
    def test_all_paths_block_auto_reexecution_when_effectively_unknown(self):
        key = "dr-b-02-all-paths-unknown"
        ttl = store.TTL_SECONDS["IN_PROGRESS"]
        with store.connect(self._tmpdir) as conn:
            store.try_create(conn, key=key, fingerprint=FP_A, now=_now())

        # 아직 물리적으로는 IN_PROGRESS(get_effective_state는 부작용 없음)
        with store.connect(self._tmpdir) as conn:
            read_only = store.get_effective_state(conn, key=key, now=_now(ttl + 1))
        self.assertEqual(read_only.classification, "RECONCILIATION_REQUIRED")
        self.assertEqual(self._raw_row(key)["state"], "IN_PROGRESS", "순수 조회는 물리적 전이를 일으키지 않아야 함")

        with store.connect(self._tmpdir) as conn:
            completed_view = store.get_completed_result(conn, key=key, fingerprint=FP_A, now=_now(ttl + 1))
        self.assertEqual(completed_view.classification, "RECONCILIATION_REQUIRED")

        with store.connect(self._tmpdir) as conn:
            creation_attempt = store.try_create(conn, key=key, fingerprint=FP_A, now=_now(ttl + 1))
        self.assertEqual(creation_attempt.classification, "RECONCILIATION_REQUIRED")
        self.assertNotEqual(creation_attempt.classification, "CREATED")
        self.assertEqual(self._raw_row(key)["state"], "UNKNOWN", "try_create 이후에는 물리적으로 전이되어야 함")

    # 21. 명시적 만료 전이 메서드(배치 미연결) ----------------------------------------
    def test_reconcile_expired_in_progress_explicit_method(self):
        key = "dr-b-02-explicit-reconcile"
        ttl = store.TTL_SECONDS["IN_PROGRESS"]
        with store.connect(self._tmpdir) as conn:
            store.try_create(conn, key=key, fingerprint=FP_A, now=_now())

        with store.connect(self._tmpdir) as conn:
            too_early = store.reconcile_expired_in_progress(conn, key=key, now=_now(ttl - 1))
        self.assertEqual(too_early.classification, "NO_ACTION")
        self.assertEqual(self._raw_row(key)["state"], "IN_PROGRESS")

        with store.connect(self._tmpdir) as conn:
            reconciled = store.reconcile_expired_in_progress(conn, key=key, now=_now(ttl + 1))
        self.assertEqual(reconciled.classification, "RECONCILIATION_REQUIRED")
        self.assertEqual(self._raw_row(key)["state"], "UNKNOWN")
        # 이 함수가 실제로 스케줄러·배치에 연결되어 있지 않다는 것은 단위 테스트로
        # 증명할 수 있는 성질이 아니므로(부재증명), 저장소 전체 grep으로 별도
        # 확인한다(완료 보고의 "영향도" 절 참조) — 여기서는 호출 결과만 검증한다.


if __name__ == "__main__":
    unittest.main(verbosity=2)
