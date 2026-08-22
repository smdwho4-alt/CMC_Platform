# -*- coding: utf-8 -*-
"""
Sprint8 Pre-G1-A — DR-B-01 PoC#1: SQLite UNIQUE 제약의 동시요청 원자성 검증

목적: ADR-017 §13이 채택한 Nonce 이중저장 구조 중 "FastAPI 측 SQLite UNIQUE
제약으로 원자성 확보(별도 Lock 불필요)"라는 설계 전제를, 격리된 최소 harness로
독립 검증한다.

이 파일은 Commit8-3b Production 코드가 아니다(ADR-017 §29, Pre-Implementation
Harness). Production DB, 운영 GAS, 운영 Google Sheets를 사용하지 않으며, 매
테스트 실행마다 OS 임시 디렉터리에 새 SQLite 파일을 생성하고 종료 시 정리한다.
Python 표준 라이브러리(sqlite3/threading/concurrent.futures/tempfile/uuid)만
사용하며 저장소의 다른 코드를 import하지 않는다.

사전 성공 기준(실행 전 고정, §5 참조):
  PASS             - 동일 nonce 경쟁에서 최종 성공 1건, UNIQUE 거부가 예상대로
                      발생, 최종 행 수 1건, 데이터 손상 없음, 예상 밖 예외 없음,
                      임시 DB 정리 완료.
  PASS WITH CONDITIONS - 원자성 자체는 확인되었으나 환경 의존적인 lock 오류
                      (OperationalError: database is locked)가 관찰되어 Production
                      설계에 추가 retry/timeout 기준이 필요한 경우.
  FAIL             - 동일 nonce가 2건 이상 저장되거나, rollback 후 DB가 손상/
                      사용불가 상태가 되거나, 예상 밖 오류로 검증 자체가 불가능
                      하거나, 결과가 반복 실행마다 불안정한 경우.

이 PoC의 결과는 SQLite 계층의 기술 검증일 뿐이며 GAS CacheService 검증,
Nonce 이중저장 정합성 검증, Commit8-3b 구현, DR-B-02, Production 배포 가능
여부를 의미하지 않는다(ADR-017 §29, Pre-G1 ≠ G6).
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# --- harness 설정값(고정, Production 값이 아니라 이 PoC 실행 시의 관찰 조건) ---
JOURNAL_MODE = "WAL"          # 기존 src/auth/auth_store.py::connect()와 동일 관행을
BUSY_TIMEOUT_MS = 5000        # 참고해 재현했다(코드 import 없이 값만 독립 재구현).
WORKER_COUNT = 8              # 로컬 환경에서 무리 없는 보수적 값
REPEAT_COUNT = 20             # P1-07 반복 안정성 검증 횟수

_SCHEMA_SQL = """
CREATE TABLE nonce_store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nonce TEXT NOT NULL,
    inserted_at TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    UNIQUE(nonce)
);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    """워커별 독립 connection. isolation_level=None으로 트랜잭션을 명시 제어한다."""
    conn = sqlite3.connect(str(db_path), timeout=BUSY_TIMEOUT_MS / 1000.0, isolation_level=None)
    conn.execute(f"PRAGMA journal_mode={JOURNAL_MODE}")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return conn


def _insert_nonce(db_path: Path, nonce: str, worker_id: str, barrier: threading.Barrier | None = None):
    """단일 워커의 단일 삽입 시도. 결과를 ('OK'|'UNIQUE'|'LOCKED'|'OTHER', 예외문자열)로 분류한다.
    무한 retry 없음 — 정확히 1회만 시도한다."""
    conn = _connect(db_path)
    try:
        if barrier is not None:
            barrier.wait()  # 모든 워커의 시작 시점을 최대한 동기화
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO nonce_store (nonce, inserted_at, worker_id) VALUES (?, ?, ?)",
                (nonce, time.time().__repr__(), worker_id),
            )
            conn.execute("COMMIT")
            return ("OK", None)
        except sqlite3.IntegrityError as e:
            conn.execute("ROLLBACK")
            return ("UNIQUE", str(e))
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                return ("LOCKED", str(e))
            raise
    except Exception as e:  # noqa: BLE001 - 예상 밖 오류를 별도 분류하기 위해 최상위에서도 포착
        return ("OTHER", f"{type(e).__name__}: {e}")
    finally:
        conn.close()


class DrB01Poc1SqliteNonceAtomicity(unittest.TestCase):
    """P1-01~P1-08. 각 테스트는 자체 임시 DB를 생성·정리한다(테스트 간 공유 없음)."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="cshsp_pre_g1_a_")
        self.db_path = Path(self._tmpdir) / "poc1_nonce.db"
        conn = _connect(self.db_path)
        try:
            conn.executescript(_SCHEMA_SQL)
        finally:
            conn.close()

    def tearDown(self):
        # 임시 DB 및 WAL 보조파일 정리
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(self.db_path) + suffix)
            if p.exists():
                p.unlink()
        os.rmdir(self._tmpdir)

    def _row_count(self, nonce_filter: str | None = None) -> int:
        conn = _connect(self.db_path)
        try:
            if nonce_filter is None:
                return conn.execute("SELECT COUNT(*) FROM nonce_store").fetchone()[0]
            return conn.execute(
                "SELECT COUNT(*) FROM nonce_store WHERE nonce = ?", (nonce_filter,)
            ).fetchone()[0]
        finally:
            conn.close()

    # P1-01 --------------------------------------------------------------
    def test_p1_01_single_insert_success(self):
        nonce = f"n-{uuid.uuid4()}"
        status, err = _insert_nonce(self.db_path, nonce, "w0")
        self.assertEqual(status, "OK", f"최초 삽입이 실패함: {err}")
        self.assertEqual(self._row_count(nonce), 1)
        print(f"[P1-01] nonce={nonce} status={status} row_count=1")

    # P1-02 --------------------------------------------------------------
    def test_p1_02_sequential_duplicate_rejected(self):
        nonce = f"n-{uuid.uuid4()}"
        first = _insert_nonce(self.db_path, nonce, "w0")
        second = _insert_nonce(self.db_path, nonce, "w1")
        self.assertEqual(first[0], "OK")
        self.assertEqual(second[0], "UNIQUE", f"순차 중복 삽입이 거부되지 않음: {second}")
        self.assertEqual(self._row_count(nonce), 1)
        print(f"[P1-02] first={first[0]} second={second[0]} row_count=1")

    # P1-03 --------------------------------------------------------------
    def test_p1_03_concurrent_same_nonce_exactly_one_success(self):
        nonce = f"n-{uuid.uuid4()}"
        barrier = threading.Barrier(WORKER_COUNT)
        with ThreadPoolExecutor(max_workers=WORKER_COUNT) as ex:
            futs = [
                ex.submit(_insert_nonce, self.db_path, nonce, f"w{i}", barrier)
                for i in range(WORKER_COUNT)
            ]
            results = [f.result() for f in futs]
        statuses = [r[0] for r in results]
        ok_count = statuses.count("OK")
        unique_count = statuses.count("UNIQUE")
        locked_count = statuses.count("LOCKED")
        other_count = statuses.count("OTHER")
        row_count = self._row_count(nonce)
        print(
            f"[P1-03] workers={WORKER_COUNT} OK={ok_count} UNIQUE={unique_count} "
            f"LOCKED={locked_count} OTHER={other_count} final_row_count={row_count}"
        )
        self.assertEqual(other_count, 0, f"예상 밖 오류 발생: {results}")
        self.assertEqual(ok_count, 1, f"동일 nonce 동시삽입에서 성공이 정확히 1건이 아님: {results}")
        self.assertEqual(row_count, 1, "최종 행 수가 1이 아님(데이터 중복 의심)")
        self.assertEqual(unique_count + locked_count, WORKER_COUNT - 1)

    # P1-04 --------------------------------------------------------------
    def test_p1_04_concurrent_distinct_nonces_all_succeed(self):
        nonces = [f"n-{uuid.uuid4()}" for _ in range(WORKER_COUNT)]
        barrier = threading.Barrier(WORKER_COUNT)
        with ThreadPoolExecutor(max_workers=WORKER_COUNT) as ex:
            futs = [
                ex.submit(_insert_nonce, self.db_path, nonces[i], f"w{i}", barrier)
                for i in range(WORKER_COUNT)
            ]
            results = [f.result() for f in futs]
        statuses = [r[0] for r in results]
        ok_count = statuses.count("OK")
        total_rows = self._row_count()
        print(f"[P1-04] distinct_nonces={WORKER_COUNT} OK={ok_count} total_rows={total_rows}")
        self.assertEqual(ok_count, WORKER_COUNT, f"서로 다른 nonce 동시삽입 중 일부 실패: {results}")
        self.assertEqual(total_rows, WORKER_COUNT)

    # P1-05 --------------------------------------------------------------
    def test_p1_05_rollback_then_db_still_usable(self):
        nonce = f"n-{uuid.uuid4()}"
        first = _insert_nonce(self.db_path, nonce, "w0")
        self.assertEqual(first[0], "OK")
        failed = _insert_nonce(self.db_path, nonce, "w1")  # 의도적 실패 → ROLLBACK 유도
        self.assertEqual(failed[0], "UNIQUE")
        # ROLLBACK 이후에도 DB가 정상 사용 가능한지 - 새 nonce 삽입으로 확인
        other_nonce = f"n-{uuid.uuid4()}"
        after = _insert_nonce(self.db_path, other_nonce, "w2")
        self.assertEqual(after[0], "OK", "ROLLBACK 이후 DB를 정상적으로 사용할 수 없음")
        self.assertEqual(self._row_count(), 2, "ROLLBACK된 트랜잭션이 행 수에 영향을 준 것으로 의심됨")
        print(f"[P1-05] first={first[0]} rollback_trigger={failed[0]} after_insert={after[0]} total_rows=2")

    # P1-06 --------------------------------------------------------------
    def test_p1_06_unique_enforced_across_independent_connections(self):
        nonce = f"n-{uuid.uuid4()}"
        conn_a = _connect(self.db_path)
        conn_b = _connect(self.db_path)
        try:
            conn_a.execute("BEGIN IMMEDIATE")
            conn_a.execute(
                "INSERT INTO nonce_store (nonce, inserted_at, worker_id) VALUES (?, ?, ?)",
                (nonce, time.time().__repr__(), "conn_a"),
            )
            conn_a.execute("COMMIT")
            with self.assertRaises(sqlite3.IntegrityError):
                conn_b.execute("BEGIN IMMEDIATE")
                conn_b.execute(
                    "INSERT INTO nonce_store (nonce, inserted_at, worker_id) VALUES (?, ?, ?)",
                    (nonce, time.time().__repr__(), "conn_b"),
                )
                conn_b.execute("COMMIT")
            conn_b.execute("ROLLBACK")
        finally:
            conn_a.close()
            conn_b.close()
        self.assertEqual(self._row_count(nonce), 1)
        print("[P1-06] 독립 connection(conn_a, conn_b) 간 UNIQUE 제약 유지 확인, row_count=1")

    # P1-07 --------------------------------------------------------------
    def test_p1_07_repeated_execution_stability(self):
        outcomes = []
        for i in range(REPEAT_COUNT):
            nonce = f"n-rep{i}-{uuid.uuid4()}"
            barrier = threading.Barrier(WORKER_COUNT)
            with ThreadPoolExecutor(max_workers=WORKER_COUNT) as ex:
                futs = [
                    ex.submit(_insert_nonce, self.db_path, nonce, f"w{j}", barrier)
                    for j in range(WORKER_COUNT)
                ]
                results = [f.result() for f in futs]
            statuses = [r[0] for r in results]
            ok = statuses.count("OK")
            row_count = self._row_count(nonce)
            outcomes.append((ok, row_count, statuses.count("OTHER")))
        ok_values = {o[0] for o in outcomes}
        row_values = {o[1] for o in outcomes}
        other_total = sum(o[2] for o in outcomes)
        print(
            f"[P1-07] repeats={REPEAT_COUNT} distinct_ok_values={ok_values} "
            f"distinct_row_values={row_values} other_errors_total={other_total}"
        )
        self.assertEqual(ok_values, {1}, f"반복 실행 중 성공 건수가 매번 1로 안정적이지 않음: {outcomes}")
        self.assertEqual(row_values, {1}, f"반복 실행 중 최종 행 수가 매번 1로 안정적이지 않음: {outcomes}")
        self.assertEqual(other_total, 0)

    # P1-08 --------------------------------------------------------------
    def test_p1_08_lock_vs_unique_conflict_classified_separately(self):
        # P1-03과 동일한 경쟁 조건을 재사용하되, 이번 테스트의 목적은 결과를
        # LOCKED와 UNIQUE로 "구분해서 집계할 수 있는가" 자체를 확인하는 것이다.
        # busy_timeout이 5000ms로 설정되어 있어 이 harness의 짧은 트랜잭션
        # 규모에서는 LOCKED가 관찰되지 않을 수 있음을 실행 전에 기록해 둔다.
        nonce = f"n-{uuid.uuid4()}"
        barrier = threading.Barrier(WORKER_COUNT)
        with ThreadPoolExecutor(max_workers=WORKER_COUNT) as ex:
            futs = [
                ex.submit(_insert_nonce, self.db_path, nonce, f"w{i}", barrier)
                for i in range(WORKER_COUNT)
            ]
            results = [f.result() for f in futs]
        statuses = [r[0] for r in results]
        classification = {
            "OK": statuses.count("OK"),
            "UNIQUE": statuses.count("UNIQUE"),
            "LOCKED": statuses.count("LOCKED"),
            "OTHER": statuses.count("OTHER"),
        }
        print(
            f"[P1-08] busy_timeout_ms={BUSY_TIMEOUT_MS} classification={classification}"
        )
        self.assertEqual(classification["OTHER"], 0)
        self.assertEqual(classification["OK"], 1)
        # LOCKED는 0건일 수 있다(정상) — 이 테스트는 "분류 체계가 실제로 동작하는가"를
        # 검증하는 것이지 LOCKED 발생 자체를 요구하지 않는다.
        self.assertEqual(classification["UNIQUE"] + classification["LOCKED"], WORKER_COUNT - 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
