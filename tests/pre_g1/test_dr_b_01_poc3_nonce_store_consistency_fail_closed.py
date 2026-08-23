# -*- coding: utf-8 -*-
"""
Sprint8 Pre-G1-B-F — DR-B-01 PoC#3: Nonce 이중저장소 정합성 불일치 Fail-Closed 처리 검증

목적: ADR-017 §29 PoC#3("양쪽 저장소 간 정합성이 어긋나는 경우의 처리 로직 검증")을
격리된 최소 harness로 독립 검증한다. 실행계획서:
docs/Sprint8_DR_B_01_PoC3_Nonce_Store_Consistency_Fail_Closed_Test_Plan.md

이 파일은 Commit8-3b Production 코드가 아니다(ADR-017 §29, Pre-Implementation
Harness). Production 코드(src/auth/service_hmac.py 등)를 import하지 않으며,
운영 GAS·운영 Google Sheets·외부 네트워크에 접근하지 않는다. Python 표준
라이브러리만 사용한다.

이 harness는 실제 GAS CacheService 구현이나 Production 통합을 검증하는 것이
아니라, 저장소 판단 조합(NEW/EXISTING/ERROR/UNKNOWN)에 따른 Fail-Closed
결정 로직만 검증한다.
  - 1차 저장소: 임시 SQLite(실제 sqlite3, INSERT 성공=NEW, IntegrityError=EXISTING,
    force_error 주입으로 ERROR 재현)
  - 2차 저장소: deterministic in-memory adapter(실제 GAS CacheService 미호출,
    organic 상태 추적 + 시나리오별 override로 EXISTING/ERROR/UNKNOWN 재현)

범위 밖(계획서 §7 재확인, 이 harness가 다루지 않음): Canonical String/HMAC
형식 정합성(별도 Gap), service_hmac.py 수정, GAS HMAC 구현, timestamp 허용
초값, Nonce/Idempotency TTL·CAS 정책 확정, 실제 GAS CacheService eviction·
동시성 검증(PoC#2 범위), DR-B-02 Phase 1/Phase 2.

사전 성공 기준(계획서 8.1절 원문, 실행 전 고정):
  PASS - 모든 Primary/Secondary NEW/NEW 판단이 ALLOW 후보로 처리되고, 그 외
    모든 조합(EXISTING/ERROR/UNKNOWN이 하나라도 섞인 경우)은 예외 없이 DENY
    이며, 반복된 동일 nonce 요청은 DENY이고, 서로 다른 nonce는 서로
    독립적으로 처리되며(교차오염 없음), 예외 발생 시 default deny가
    유지되고, cleanup이 완료된 경우.
  PASS WITH CONDITIONS - 위 PASS 기준(ALLOW/DENY 오분류 0건)은 전부 충족했으나
    정리 단계에서 경미한 잔존이 있었거나 일부 시나리오가 harness 제약으로
    완전히 재현되지 못한 경우.
  FAIL - mismatch/EXISTING/ERROR/UNKNOWN이 하나라도 섞인 조합에서 ALLOW가
    한 건이라도 나온 경우, 반복 nonce의 재호출이 DENY가 아닌 경우, 서로
    다른 nonce 간 상태가 교차오염된 경우, ERROR/UNKNOWN이 NEW로 변환된
    경우, 예외 발생 후 default allow가 관측된 경우, 또는 cleanup 실패.

용어 제한: 이 파일에서 ALLOW는 harness의 결정값(정상 처리 후보로 판단됨)을
가리키는 용어일 뿐, Production 업무처리의 최종 승인을 의미하지 않는다. 이
PoC 결과를 Production 구현·배포 적합성으로 확대 해석하지 않는다.

record 유지/rollback 정책: Fail-Closed는 요청 허용 여부에 대한 원칙이며,
실패 후 1차 저장소 record를 유지할지 rollback할지에 대한 정책은 이 PoC가
임의로 확정하지 않는다(관측값으로만 기록).
"""
from __future__ import annotations

import os
import re
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path

PRIMARY_NEW = "NEW"
PRIMARY_EXISTING = "EXISTING"
PRIMARY_ERROR = "ERROR"

SECONDARY_NEW = "NEW"
SECONDARY_EXISTING = "EXISTING"
SECONDARY_ERROR = "ERROR"

DECISION_ALLOW = "ALLOW"
DECISION_DENY = "DENY"
DECISION_NOT_APPLICABLE = "DECISION_NOT_APPLICABLE"

VALID_PRIMARY = set([PRIMARY_NEW, PRIMARY_EXISTING, PRIMARY_ERROR])
VALID_SECONDARY = set([SECONDARY_NEW, SECONDARY_EXISTING, SECONDARY_ERROR])

SCHEMA_SQL = "CREATE TABLE nonce_store (id INTEGER PRIMARY KEY AUTOINCREMENT, nonce TEXT NOT NULL, UNIQUE(nonce));"


def synthetic_nonce():
    return "poc3-" + str(uuid.uuid4())


def sanitize_error(exc):
    msg = str(exc)
    msg = re.sub(r"poc3-[0-9a-fA-F-]{20,}", "[NONCE-REDACTED]", msg)
    msg = re.sub(r"[A-Za-z0-9_-]{25,}", "[TOKEN-REDACTED]", msg)
    return msg


def fail_closed_decision(primary_result, secondary_result):
    if primary_result not in VALID_PRIMARY:
        return DECISION_DENY
    if secondary_result not in VALID_SECONDARY:
        return DECISION_DENY
    if primary_result == PRIMARY_NEW and secondary_result == SECONDARY_NEW:
        return DECISION_ALLOW
    return DECISION_DENY


class PrimaryNonceStore(object):
    def __init__(self, db_path):
        self.db_path = db_path
        conn = self._connect()
        try:
            conn.executescript(SCHEMA_SQL)
        finally:
            conn.close()

    def _connect(self):
        return sqlite3.connect(str(self.db_path), timeout=5.0, isolation_level=None)

    def check_and_record(self, nonce, force_error=False):
        if force_error:
            return (PRIMARY_ERROR, "forced_error_injection_harness")
        conn = self._connect()
        try:
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("INSERT INTO nonce_store (nonce) VALUES (?)", (nonce,))
                conn.execute("COMMIT")
                return (PRIMARY_NEW, None)
            except sqlite3.IntegrityError as e:
                conn.execute("ROLLBACK")
                return (PRIMARY_EXISTING, sanitize_error(e))
            except sqlite3.OperationalError as e:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                return (PRIMARY_ERROR, sanitize_error(e))
        finally:
            conn.close()


class SecondaryCacheAdapter(object):
    def __init__(self):
        self._seen = set()
        self._overrides = {}

    def override(self, nonce, forced_result):
        self._overrides[nonce] = forced_result

    def check_and_record(self, nonce, raise_exception=False):
        if raise_exception:
            raise RuntimeError("forced_secondary_exception_harness")
        if nonce in self._overrides:
            return self._overrides.pop(nonce)
        if nonce in self._seen:
            return SECONDARY_EXISTING
        self._seen.add(nonce)
        return SECONDARY_NEW

    def snapshot(self):
        return {"seen_count": len(self._seen), "pending_overrides": len(self._overrides)}

    def clear(self):
        self._seen.clear()
        self._overrides.clear()


def evaluate_nonce_request(primary, secondary, nonce, force_primary_error=False, secondary_raise_exception=False):
    result = {
        "scenario": None,
        "primaryResult": None,
        "secondaryResult": None,
        "decision": None,
        "expectedDecision": None,
        "pass": None,
        "recordRetainedNote": "observation only, not a fixed policy",
        "errorType": None,
        "errorMessageSafe": None,
        "notes": [],
    }
    try:
        primary_result, _detail = primary.check_and_record(nonce, force_error=force_primary_error)
        result["primaryResult"] = primary_result
    except Exception as e:
        result["decision"] = DECISION_DENY
        result["errorType"] = "PRIMARY_EVALUATION_EXCEPTION"
        result["errorMessageSafe"] = sanitize_error(e)
        result["notes"].append("primary evaluation exception - default deny applied")
        return result

    try:
        secondary_result = secondary.check_and_record(nonce, raise_exception=secondary_raise_exception)
        result["secondaryResult"] = secondary_result
    except Exception as e:
        result["decision"] = DECISION_DENY
        result["errorType"] = "SECONDARY_EVALUATION_EXCEPTION"
        result["errorMessageSafe"] = sanitize_error(e)
        result["notes"].append("secondary evaluation exception - default deny applied, no fail-open")
        return result

    result["decision"] = fail_closed_decision(result["primaryResult"], result["secondaryResult"])
    return result


class DrB01Poc3NonceStoreConsistencyFailClosed(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="cshsp_pre_g1_b_f_")
        self.db_path = Path(self._tmpdir) / "poc3_nonce.db"
        self.primary = PrimaryNonceStore(self.db_path)
        self.secondary = SecondaryCacheAdapter()

    def tearDown(self):
        self.secondary.clear()
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(self.db_path) + suffix)
            if p.exists():
                p.unlink()
        os.rmdir(self._tmpdir)

    def _assert_decision(self, scenario, result, expected):
        result["scenario"] = scenario
        result["expectedDecision"] = expected
        result["pass"] = result["decision"] == expected
        print("[" + scenario + "] " + str(result))
        self.assertEqual(result["decision"], expected)

    def test_p3_01_primary_new_secondary_new_allow_candidate(self):
        nonce = synthetic_nonce()
        result = evaluate_nonce_request(self.primary, self.secondary, nonce)
        self.assertEqual(result["primaryResult"], PRIMARY_NEW)
        self.assertEqual(result["secondaryResult"], SECONDARY_NEW)
        self._assert_decision("P3-01", result, DECISION_ALLOW)

    def test_p3_02_primary_new_secondary_existing_core_extreme_case_deny(self):
        nonce = synthetic_nonce()
        self.secondary.override(nonce, SECONDARY_EXISTING)
        result = evaluate_nonce_request(self.primary, self.secondary, nonce)
        self.assertEqual(result["primaryResult"], PRIMARY_NEW)
        self.assertEqual(result["secondaryResult"], SECONDARY_EXISTING)
        self._assert_decision("P3-02", result, DECISION_DENY)

    def test_p3_03_primary_existing_secondary_new_reverse_mismatch_deny(self):
        nonce = synthetic_nonce()
        priming = self.primary.check_and_record(nonce)
        self.assertEqual(priming[0], PRIMARY_NEW)
        result = evaluate_nonce_request(self.primary, self.secondary, nonce)
        self.assertEqual(result["primaryResult"], PRIMARY_EXISTING)
        self.assertEqual(result["secondaryResult"], SECONDARY_NEW)
        self._assert_decision("P3-03", result, DECISION_DENY)

    def test_p3_04_both_existing_replay_deny(self):
        nonce = synthetic_nonce()
        priming = evaluate_nonce_request(self.primary, self.secondary, nonce)
        self.assertEqual(priming["decision"], DECISION_ALLOW)
        result = evaluate_nonce_request(self.primary, self.secondary, nonce)
        self.assertEqual(result["primaryResult"], PRIMARY_EXISTING)
        self.assertEqual(result["secondaryResult"], SECONDARY_EXISTING)
        self._assert_decision("P3-04", result, DECISION_DENY)

    def test_p3_05_primary_error_secondary_new_deny(self):
        nonce = synthetic_nonce()
        result = evaluate_nonce_request(self.primary, self.secondary, nonce, force_primary_error=True)
        self.assertEqual(result["primaryResult"], PRIMARY_ERROR)
        self.assertEqual(result["secondaryResult"], SECONDARY_NEW)
        self._assert_decision("P3-05", result, DECISION_DENY)

    def test_p3_06_primary_new_secondary_error_deny(self):
        nonce = synthetic_nonce()
        self.secondary.override(nonce, SECONDARY_ERROR)
        result = evaluate_nonce_request(self.primary, self.secondary, nonce)
        self.assertEqual(result["primaryResult"], PRIMARY_NEW)
        self.assertEqual(result["secondaryResult"], SECONDARY_ERROR)
        self._assert_decision("P3-06", result, DECISION_DENY)

    def test_p3_07_both_error_deny(self):
        nonce = synthetic_nonce()
        self.secondary.override(nonce, SECONDARY_ERROR)
        result = evaluate_nonce_request(self.primary, self.secondary, nonce, force_primary_error=True)
        self.assertEqual(result["primaryResult"], PRIMARY_ERROR)
        self.assertEqual(result["secondaryResult"], SECONDARY_ERROR)
        self._assert_decision("P3-07", result, DECISION_DENY)

    def test_p3_08_secondary_unknown_value_not_treated_as_new_deny(self):
        nonce = synthetic_nonce()
        self.secondary.override(nonce, "GARBAGE_UNSCHEMA_VALUE")
        result = evaluate_nonce_request(self.primary, self.secondary, nonce)
        self.assertEqual(result["primaryResult"], PRIMARY_NEW)
        self.assertEqual(result["secondaryResult"], "GARBAGE_UNSCHEMA_VALUE")
        self._assert_decision("P3-08", result, DECISION_DENY)

    def test_p3_09_same_nonce_repeat_call_second_denied(self):
        nonce = synthetic_nonce()
        first = evaluate_nonce_request(self.primary, self.secondary, nonce)
        first["scenario"] = "P3-09-first"
        print("[P3-09-first] " + str(first))
        self.assertEqual(first["decision"], DECISION_ALLOW)

        second = evaluate_nonce_request(self.primary, self.secondary, nonce)
        self.assertEqual(second["primaryResult"], PRIMARY_EXISTING)
        self.assertEqual(second["secondaryResult"], SECONDARY_EXISTING)
        self._assert_decision("P3-09-repeat", second, DECISION_DENY)

    def test_p3_10_distinct_nonces_independent_no_cross_contamination(self):
        nonce_a = synthetic_nonce()
        nonce_b = synthetic_nonce()

        result_a1 = evaluate_nonce_request(self.primary, self.secondary, nonce_a)
        self._assert_decision("P3-10-a-first", result_a1, DECISION_ALLOW)

        result_b1 = evaluate_nonce_request(self.primary, self.secondary, nonce_b)
        self._assert_decision("P3-10-b-first", result_b1, DECISION_ALLOW)

        result_a2 = evaluate_nonce_request(self.primary, self.secondary, nonce_a)
        self._assert_decision("P3-10-a-repeat", result_a2, DECISION_DENY)

        result_b2 = evaluate_nonce_request(self.primary, self.secondary, nonce_b)
        self._assert_decision("P3-10-b-repeat", result_b2, DECISION_DENY)

    def test_p3_11_exception_during_judgment_default_deny_no_secret_leak(self):
        nonce = synthetic_nonce()
        result = evaluate_nonce_request(self.primary, self.secondary, nonce, secondary_raise_exception=True)
        result["scenario"] = "P3-11"
        print("[P3-11] " + str(result))
        self.assertEqual(result["decision"], DECISION_DENY)
        self.assertEqual(result["errorType"], "SECONDARY_EVALUATION_EXCEPTION")
        self.assertIsNotNone(result["errorMessageSafe"])
        self.assertNotIn(nonce, result["errorMessageSafe"])
        self.assertNotIn("Secret", result["errorMessageSafe"])

    def test_p3_12_cleanup_verification(self):
        for _ in range(3):
            evaluate_nonce_request(self.primary, self.secondary, synthetic_nonce())

        before_snapshot = self.secondary.snapshot()
        db_exists_before = self.db_path.exists()

        self.secondary.clear()
        after_snapshot = self.secondary.snapshot()

        result = {
            "scenario": "P3-12",
            "decision": DECISION_NOT_APPLICABLE,
            "before": before_snapshot,
            "after": after_snapshot,
            "db_existed_before_cleanup": db_exists_before,
        }
        print("[P3-12] " + str(result))
        self.assertEqual(after_snapshot["seen_count"], 0)
        self.assertEqual(after_snapshot["pending_overrides"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
