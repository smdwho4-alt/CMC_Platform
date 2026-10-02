# -*- coding: utf-8 -*-
"""
CSHSP Sprint8 Commit8-3b — src/idempotency/nonce_store.py 단위 테스트

Primary는 실제 SQLite(임시 디렉터리), Secondary는 FakeSecondaryNonceStore다.
실제 GAS CacheService 접근 없음. 모든 nonce는 테스트 합성값이다.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src" / "idempotency"))

import nonce_store as ns  # noqa: E402


class _FailingConnProxy:
    """내부 커넥션을 감싸, 지정한 SQL 접두사가 실행될 때 강제로
    sqlite3.OperationalError를 발생시키는 테스트 전용 프록시(기존
    test_idempotency_store.py의 _FailNCommitsProxy/_FlakyProxy 패턴 재사용)."""

    def __init__(self, real_conn: sqlite3.Connection, fail_on_prefix: str):
        self._real = real_conn
        self._fail_on_prefix = fail_on_prefix

    def execute(self, sql, *args, **kwargs):
        if sql.strip().upper().startswith(self._fail_on_prefix):
            raise sqlite3.OperationalError("synthetic induced failure for test")
        return self._real.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._real, name)


class NonceStoreBasicTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmpdir.name)
        ns.init_schema(self.data_dir)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_generate_nonce_format(self):
        nonce = ns.generate_nonce()
        self.assertEqual(len(nonce), 32)  # 16바이트 = hex 32자
        int(nonce, 16)  # hex 디코딩 가능해야 함(ValueError 없이)

    def test_accepted_on_first_use(self):
        secondary = ns.FakeSecondaryNonceStore()
        with ns.connect(self.data_dir) as conn:
            result = ns.evaluate_and_register_nonce(
                conn, secondary, nonce="n-first-use", now=1000.0, now_iso="2026-01-01T00:00:00+09:00"
            )
        self.assertEqual(result.classification, "ACCEPTED")
        self.assertEqual(result.primary_status, "NEW")
        self.assertEqual(result.secondary_status, "NEW")

    # 1. nonce 동시 재사용 차단 -------------------------------------------------------
    def test_concurrent_same_nonce_only_one_accepted(self):
        """동일 nonce로 여러 스레드가 동시에 요청해도 정확히 1건만
        ACCEPTED여야 한다(ThreadPoolExecutor + Barrier로 동시성 유발)."""
        n_threads = 8
        barrier = threading.Barrier(n_threads)
        secondary = ns.FakeSecondaryNonceStore()
        results = []
        results_lock = threading.Lock()

        def worker():
            barrier.wait()
            with ns.connect(self.data_dir) as conn:
                r = ns.evaluate_and_register_nonce(
                    conn, secondary, nonce="n-concurrent", now=2000.0,
                    now_iso="2026-01-01T00:00:00+09:00",
                )
            with results_lock:
                results.append(r.classification)

        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            futures = [pool.submit(worker) for _ in range(n_threads)]
            for f in futures:
                f.result()

        accepted = [c for c in results if c == "ACCEPTED"]
        replayed = [c for c in results if c == "NONCE_REPLAYED"]
        self.assertEqual(len(accepted), 1, f"정확히 1건만 ACCEPTED여야 함: {results}")
        self.assertEqual(len(replayed), n_threads - 1)

    # 2. Primary 실패 시 차단(기존 저장 거부 - replay) ---------------------------------
    def test_primary_existing_blocks_without_consulting_secondary(self):
        """Primary가 이미 EXISTING이면 Secondary는 조회조차 하지 않고
        즉시 차단한다(force_error를 걸어도 호출되지 않아야 함)."""
        secondary = ns.FakeSecondaryNonceStore()
        with ns.connect(self.data_dir) as conn:
            first = ns.evaluate_and_register_nonce(
                conn, secondary, nonce="n-dup", now=3000.0, now_iso="2026-01-01T00:00:00+09:00"
            )
        self.assertEqual(first.classification, "ACCEPTED")

        secondary.force_error(times=1)  # Secondary가 호출되면 ERROR를 반환하도록 설정
        with ns.connect(self.data_dir) as conn:
            second = ns.evaluate_and_register_nonce(
                conn, secondary, nonce="n-dup", now=3001.0, now_iso="2026-01-01T00:00:01+09:00"
            )
        self.assertEqual(second.classification, "NONCE_REPLAYED")
        self.assertEqual(second.primary_status, "EXISTING")
        self.assertIsNone(second.secondary_status, "Primary에서 이미 막혔으면 Secondary는 조회하지 않음")

    # 3. Primary 트랜잭션 자체의 실패 시 차단(OperationalError 전파) --------------------
    def test_primary_operational_error_blocks_request(self):
        """Primary의 COMMIT 단계에서 OperationalError가 발생하면
        NonceStoreError가 호출부로 전파되어 요청이 차단되어야 한다
        (조용히 통과시키지 않음)."""
        secondary = ns.FakeSecondaryNonceStore()
        with ns.connect(self.data_dir) as real_conn:
            proxy = _FailingConnProxy(real_conn, fail_on_prefix="COMMIT")
            with self.assertRaises(ns.NonceStoreError):
                ns.evaluate_and_register_nonce(
                    proxy, secondary, nonce="n-primary-fail", now=4000.0,
                    now_iso="2026-01-01T00:00:00+09:00",
                )

        # Primary 트랜잭션이 COMMIT 실패로 ROLLBACK되었으므로, 동일 nonce는
        # 이후 정상 경로에서 여전히 NEW로 취급되어야 한다(레코드가 남지 않음).
        with ns.connect(self.data_dir) as conn:
            retry = ns.evaluate_and_register_nonce(
                conn, secondary, nonce="n-primary-fail", now=4001.0,
                now_iso="2026-01-01T00:00:01+09:00",
            )
        self.assertEqual(retry.classification, "ACCEPTED")

    # 4. Secondary DENY/오류 후 Primary 보존 및 재사용 차단 ----------------------------
    def test_secondary_existing_blocks_but_preserves_primary_and_blocks_reuse(self):
        secondary = ns.FakeSecondaryNonceStore()
        # Secondary에 동일 nonce를 미리 등록해 두어, Primary NEW 이후
        # Secondary가 EXISTING을 반환하도록 유도한다.
        secondary.check_and_mark("n-secondary-deny", now=5000.0)

        with ns.connect(self.data_dir) as conn:
            first = ns.evaluate_and_register_nonce(
                conn, secondary, nonce="n-secondary-deny", now=5000.5,
                now_iso="2026-01-01T00:00:00+09:00",
            )
        self.assertEqual(first.classification, "NONCE_REPLAYED")
        self.assertEqual(first.primary_status, "NEW")
        self.assertEqual(first.secondary_status, "EXISTING")

        # Primary 레코드가 삭제되지 않고 보존되었는지 직접 확인
        with ns.connect(self.data_dir) as conn:
            row = conn.execute(
                "SELECT nonce FROM nonce_store WHERE nonce = ?", ("n-secondary-deny",)
            ).fetchone()
        self.assertIsNotNone(row, "Secondary DENY 이후에도 Primary 레코드는 보존되어야 함")

        # 동일(보존된) nonce로 재사용을 시도하면 Primary 단계에서 즉시
        # 재차단되어야 한다(Secondary는 다시 조회하지 않음).
        with ns.connect(self.data_dir) as conn:
            second = ns.evaluate_and_register_nonce(
                conn, secondary, nonce="n-secondary-deny", now=5001.0,
                now_iso="2026-01-01T00:00:01+09:00",
            )
        self.assertEqual(second.classification, "NONCE_REPLAYED")
        self.assertEqual(second.primary_status, "EXISTING")
        self.assertIsNone(second.secondary_status)

    def test_secondary_error_blocks_but_preserves_primary_and_blocks_reuse(self):
        secondary = ns.FakeSecondaryNonceStore()
        secondary.force_error(times=1)

        with ns.connect(self.data_dir) as conn:
            first = ns.evaluate_and_register_nonce(
                conn, secondary, nonce="n-secondary-error", now=6000.0,
                now_iso="2026-01-01T00:00:00+09:00",
            )
        self.assertEqual(first.classification, "NONCE_STORE_FAILED")
        self.assertEqual(first.primary_status, "NEW")
        self.assertEqual(first.secondary_status, "ERROR")

        with ns.connect(self.data_dir) as conn:
            row = conn.execute(
                "SELECT nonce FROM nonce_store WHERE nonce = ?", ("n-secondary-error",)
            ).fetchone()
        self.assertIsNotNone(row, "Secondary ERROR 이후에도 Primary 레코드는 보존되어야 함")

        with ns.connect(self.data_dir) as conn:
            second = ns.evaluate_and_register_nonce(
                conn, secondary, nonce="n-secondary-error", now=6001.0,
                now_iso="2026-01-01T00:00:01+09:00",
            )
        self.assertEqual(second.classification, "NONCE_REPLAYED")
        self.assertEqual(second.primary_status, "EXISTING")
        self.assertIsNone(second.secondary_status)

    def test_invalid_nonce_format_rejected(self):
        secondary = ns.FakeSecondaryNonceStore()
        with ns.connect(self.data_dir) as conn:
            with self.assertRaises(ValueError):
                ns.evaluate_and_register_nonce(
                    conn, secondary, nonce="invalid nonce with spaces\n", now=7000.0,
                    now_iso="2026-01-01T00:00:00+09:00",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
