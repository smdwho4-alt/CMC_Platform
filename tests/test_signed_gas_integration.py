# -*- coding: utf-8 -*-
"""
CSHSP Sprint8 Commit8-3b — src/idempotency/signed_gas_integration.py 통합테스트

**실제 네트워크를 호출하지 않는다.** 합성 데이터·합성 키·로컬
SQLite·Fake Secondary·Fake GAS(FakeReceiver + FakeBusinessAdapter)만
사용한다. 운영 라우트·실제 GAS/Sheets/CacheService에 연결하지 않는다.
인증·권한검사는 이 테스트의 범위 밖이다(전제조건으로만 가정).
"""
from __future__ import annotations

import io
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest
import unittest.mock
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from datetime import datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src" / "idempotency"))
sys.path.insert(0, str(_ROOT / "src" / "reservation"))

import idempotency_store as store  # noqa: E402
import gas_orchestration as orch  # noqa: E402
import nonce_store  # noqa: E402
import signing_v2  # noqa: E402
import signed_gas_integration as sgi  # noqa: E402
from json_store import KST  # noqa: E402

SYNTHETIC_SECRET = "synthetic-test-secret-integration-0001"
SYNTHETIC_SECRET_OTHER = "synthetic-test-secret-integration-0002"
WORKER_COUNT = 8

VALID_RAW_JSON = '{"startDate":"2026-10-01","endDate":"2026-10-31","capacity":6}'
VALID_RAW_JSON_B = '{"startDate":"2026-11-01","endDate":"2026-11-30","capacity":8}'
OPERATION = "slot_generate"


def _now(offset_seconds: float = 0.0) -> datetime:
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=KST)
    return base + timedelta(seconds=offset_seconds)


def _flip_last_hex_char(hexstr: str) -> str:
    last = hexstr[-1]
    new_last = "1" if last == "0" else "0"
    return hexstr[:-1] + new_last


class FakeBusinessAdapter:
    """실제 GAS 업무 로직(예: Sheets 쓰기)을 대신하는 테스트 전용 더블.
    호출 횟수만 센다 — 실제 네트워크·Sheets 접근 없음."""

    def __init__(self):
        self.call_count = 0
        self.calls: list[dict] = []
        self._lock = threading.Lock()

    def __call__(self, payload: dict) -> str:
        with self._lock:
            self.call_count += 1
            self.calls.append(payload)
        return "FAKE_BUSINESS_OK"


class _FailNCommitsProxy:
    """지정 횟수만큼 UPDATE 포함 트랜잭션의 COMMIT만 실패시키는 프록시
    (tests/test_gas_orchestration.py와 동일 패턴 재사용)."""

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


class SignedGasIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="cshsp_commit8_3b_signed_integration_")
        store.init_schema(self._tmpdir)
        self._issuer_dir = Path(self._tmpdir) / "issuer_nonce"
        self._receiver_dir = Path(self._tmpdir) / "receiver_nonce"

        self._registry = signing_v2.KeyRegistry()
        self._registry.register(
            signing_v2.KeyRecord(key_id="key-active", secret=SYNTHETIC_SECRET, state="ACTIVE")
        )
        self._registry.register(
            signing_v2.KeyRecord(key_id="key-secondary", secret=SYNTHETIC_SECRET_OTHER, state="ACTIVE")
        )

        self._business = FakeBusinessAdapter()
        self._receiver = sgi.FakeReceiver(
            self._receiver_dir, key_registry=self._registry, business_adapter=self._business,
            max_skew_seconds=signing_v2.TEST_DEFAULT_MAX_SKEW_SECONDS,
        )
        self._issuer_secondary = nonce_store.FakeSecondaryNonceStore()
        self._issuer_cfg = sgi.IssuerConfig(
            secret=SYNTHETIC_SECRET, key_id="key-active",
            issuer_nonce_data_dir=self._issuer_dir, issuer_secondary_store=self._issuer_secondary,
        )

        self._silence = redirect_stderr(io.StringIO())
        self._silence.__enter__()

    def tearDown(self):
        self._silence.__exit__(None, None, None)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _handle(self, *, raw_json_text=VALID_RAW_JSON, idempotency_key="idem-0001", now=None, **kwargs):
        if now is None:
            now = _now()
        with store.connect(self._tmpdir) as conn:
            return sgi.handle_request(
                conn, raw_json_text=raw_json_text, operation=OPERATION,
                idempotency_key=idempotency_key, method="POST",
                issuer_config=self._issuer_cfg, receiver=self._receiver, now=now, **kwargs
            )

    # 1. 정상 요청 ------------------------------------------------------------------
    def test_normal_request_business_executed_exactly_once(self):
        result = self._handle()
        self.assertEqual(result.outcome, "SENT_SUCCESS")
        self.assertTrue(result.gas_called)
        self.assertEqual(self._business.call_count, 1)

    def test_normal_request_issuer_nonce_does_not_cause_receiver_false_rejection(self):
        """발급 때 저장한 nonce를 수신부가 곧바로 재사용으로 거절하지
        않는지 확인 — 네임스페이스 분리 핵심 검증."""
        result = self._handle()
        self.assertEqual(result.outcome, "SENT_SUCCESS")
        self.assertEqual(self._business.call_count, 1)

    # 2. 동일 요청 재시도 — 캐시 반환 -------------------------------------------------
    def test_identical_retry_returns_cached_no_extra_execution(self):
        first = self._handle(idempotency_key="idem-cache-0001")
        self.assertEqual(first.outcome, "SENT_SUCCESS")
        second = self._handle(idempotency_key="idem-cache-0001")
        self.assertEqual(second.outcome, "NOT_SENT_CACHED")
        self.assertFalse(second.gas_called)
        self.assertEqual(self._business.call_count, 1)

    # 3. 동일 key·다른 payload — 충돌 ------------------------------------------------
    def test_same_key_different_payload_conflict_zero_execution(self):
        first = self._handle(idempotency_key="idem-conflict-0001", raw_json_text=VALID_RAW_JSON)
        self.assertEqual(first.outcome, "SENT_SUCCESS")
        second = self._handle(idempotency_key="idem-conflict-0001", raw_json_text=VALID_RAW_JSON_B)
        self.assertEqual(second.outcome, "NOT_SENT_BLOCKED")
        self.assertFalse(second.gas_called)
        self.assertEqual(self._business.call_count, 1)  # 최초 1회만, 충돌 시도는 0회

    # 4. 동시 동일 요청 — 정확히 1회 --------------------------------------------------
    def test_concurrent_identical_requests_business_executed_exactly_once(self):
        barrier = threading.Barrier(WORKER_COUNT)
        results = []
        results_lock = threading.Lock()

        def worker():
            barrier.wait()
            r = self._handle(idempotency_key="idem-concurrent-0001")
            with results_lock:
                results.append(r.outcome)

        with ThreadPoolExecutor(max_workers=WORKER_COUNT) as pool:
            futures = [pool.submit(worker) for _ in range(WORKER_COUNT)]
            for f in futures:
                f.result()

        self.assertEqual(self._business.call_count, 1)
        sent = [r for r in results if r == "SENT_SUCCESS"]
        self.assertEqual(len(sent), 1)

    # 5. 서명·keyId·payload·timestamp 변조 — 전부 실행 0회 -----------------------------
    def test_signature_tamper_zero_execution(self):
        def tamper(envelope: sgi.SignedEnvelope) -> sgi.SignedEnvelope:
            return sgi.SignedEnvelope(
                method=envelope.method, operation=envelope.operation, timestamp=envelope.timestamp,
                nonce=envelope.nonce, idempotency_key=envelope.idempotency_key, key_id=envelope.key_id,
                payload=envelope.payload, signature=_flip_last_hex_char(envelope.signature),
            )
        result = self._handle(idempotency_key="idem-tamper-sig-0001", envelope_tamperer=tamper)
        self.assertIn(result.outcome, ("SENT_FAILED_FINAL", "SENT_FAILED_RETRYABLE"))
        self.assertEqual(self._business.call_count, 0)

    def test_keyid_tamper_zero_execution(self):
        def tamper(envelope: sgi.SignedEnvelope) -> sgi.SignedEnvelope:
            return sgi.SignedEnvelope(
                method=envelope.method, operation=envelope.operation, timestamp=envelope.timestamp,
                nonce=envelope.nonce, idempotency_key=envelope.idempotency_key, key_id="key-secondary",
                payload=envelope.payload, signature=envelope.signature,
            )
        result = self._handle(idempotency_key="idem-tamper-keyid-0001", envelope_tamperer=tamper)
        self.assertIn(result.outcome, ("SENT_FAILED_FINAL", "SENT_FAILED_RETRYABLE"))
        self.assertEqual(self._business.call_count, 0)

    def test_payload_tamper_zero_execution(self):
        def tamper(envelope: sgi.SignedEnvelope) -> sgi.SignedEnvelope:
            tampered_payload = dict(envelope.payload)
            tampered_payload["capacity"] = 999
            return sgi.SignedEnvelope(
                method=envelope.method, operation=envelope.operation, timestamp=envelope.timestamp,
                nonce=envelope.nonce, idempotency_key=envelope.idempotency_key, key_id=envelope.key_id,
                payload=tampered_payload, signature=envelope.signature,
            )
        result = self._handle(idempotency_key="idem-tamper-payload-0001", envelope_tamperer=tamper)
        self.assertIn(result.outcome, ("SENT_FAILED_FINAL", "SENT_FAILED_RETRYABLE"))
        self.assertEqual(self._business.call_count, 0)

    def test_timestamp_tamper_zero_execution(self):
        def tamper(envelope: sgi.SignedEnvelope) -> sgi.SignedEnvelope:
            far_past = str(float(envelope.timestamp) - 100000)
            return sgi.SignedEnvelope(
                method=envelope.method, operation=envelope.operation, timestamp=far_past,
                nonce=envelope.nonce, idempotency_key=envelope.idempotency_key, key_id=envelope.key_id,
                payload=envelope.payload, signature=envelope.signature,
            )
        result = self._handle(idempotency_key="idem-tamper-ts-0001", envelope_tamperer=tamper)
        self.assertIn(result.outcome, ("SENT_FAILED_FINAL", "SENT_FAILED_RETRYABLE"))
        self.assertEqual(self._business.call_count, 0)

    # 6. 같은 signed envelope 재전송 — replay 차단 -------------------------------------
    def test_replay_of_same_envelope_blocked_at_receiver(self):
        """발급 측 idempotency 계층을 완전히 우회해, 탈취한 envelope를
        수신부에 직접 재전송하는 공격을 시뮬레이션한다."""
        captured: dict = {}

        def capture(envelope: sgi.SignedEnvelope) -> sgi.SignedEnvelope:
            captured["envelope"] = envelope
            return envelope

        first = self._handle(idempotency_key="idem-replay-0001", envelope_tamperer=capture)
        self.assertEqual(first.outcome, "SENT_SUCCESS")
        self.assertEqual(self._business.call_count, 1)

        # 발급측/오케스트레이션을 완전히 건너뛰고 수신부에 직접 재전송
        replay_response = self._receiver.receive(
            captured["envelope"], now=_now().timestamp(), now_iso=_now().isoformat(timespec="seconds")
        )
        self.assertFalse(replay_response.success)
        self.assertIn("NONCE_REPLAYED", replay_response.result)
        self.assertEqual(self._business.call_count, 1)  # 증가 없음

    # 7. Secondary ERROR(수신측) — 실행 0회, Primary nonce 보존 -----------------------
    def test_receiver_secondary_error_zero_execution_primary_preserved(self):
        """수신측 Secondary의 일시 장애(ERROR). nonce_store.py 단위
        레벨의 동일 메커니즘은 이미
        tests/test_nonce_store.py::test_secondary_error_blocks_but_preserves_primary_and_blocks_reuse
        에서 검증됐다 — 이 테스트는 FakeReceiver를 통해서도 동일하게
        작동하는지 확인한다(재작성 아님, passthrough 재확인)."""
        self._receiver.force_secondary_error(times=1)
        captured: dict = {}

        def capture(envelope: sgi.SignedEnvelope) -> sgi.SignedEnvelope:
            captured["envelope"] = envelope
            return envelope

        result = self._handle(idempotency_key="idem-secondary-error-0001", envelope_tamperer=capture)
        self.assertEqual(result.outcome, "SENT_FAILED_RETRYABLE")
        self.assertEqual(self._business.call_count, 0)

        nonce = captured["envelope"].nonce
        self.assertTrue(self._receiver.raw_nonce_row_exists(nonce), "Secondary 오류 후에도 Primary 보존돼야 함")

        # 같은 envelope 재전송(동일 nonce 재사용) -> Primary 단계에서 즉시 거절, 실행 증가 없음
        replay = self._receiver.receive(
            captured["envelope"], now=_now().timestamp(), now_iso=_now().isoformat(timespec="seconds")
        )
        self.assertFalse(replay.success)
        self.assertIn("NONCE_REPLAYED", replay.result)
        self.assertEqual(self._business.call_count, 0)

    # 7-1. Secondary DENY(수신측, ERROR와 구분) — 실행 0회, Primary nonce 보존 ----------
    def test_receiver_secondary_deny_zero_execution_primary_preserved(self):
        """ERROR(일시 장애)가 아니라 DENY(Secondary가 "이미 본 nonce"로
        응답) 시나리오. Primary는 아직 이 nonce를 모르는 상태에서
        Secondary만 먼저 거절하는 드문 경우를 재현한다(예: 수신측
        프로세스 재시작으로 SQLite는 리셋됐지만 CacheService는 살아
        있는 상황). 핵심 메커니즘은 이미
        tests/test_nonce_store.py::test_secondary_existing_blocks_but_preserves_primary_and_blocks_reuse
        에서 검증됐다 — 이 테스트는 FakeReceiver를 통해 수동으로 구성한
        envelope로 동일 동작을 재확인한다(nonce가 발급 시점에 랜덤
        생성되므로, 발급 플로우를 거치지 않고 직접 envelope를 만들어야
        Secondary를 미리 오염시킬 수 있다)."""
        manual_nonce = nonce_store.generate_nonce()
        now_epoch = _now().timestamp()
        now_iso = _now().isoformat(timespec="seconds")
        self._receiver.mark_secondary_seen_for_test(manual_nonce, now_epoch)

        payload = {"startDate": "2026-10-01", "endDate": "2026-10-31", "capacity": 6}
        signature = signing_v2.sign_v2(
            secret=SYNTHETIC_SECRET, method="POST", operation=OPERATION, timestamp=str(now_epoch),
            nonce=manual_nonce, idempotency_key="idem-deny-manual-0001", key_id="key-active", payload=payload,
        )
        envelope = sgi.SignedEnvelope(
            method="POST", operation=OPERATION, timestamp=str(now_epoch), nonce=manual_nonce,
            idempotency_key="idem-deny-manual-0001", key_id="key-active", payload=payload, signature=signature,
        )

        response = self._receiver.receive(envelope, now=now_epoch, now_iso=now_iso)
        self.assertFalse(response.success)
        self.assertIn("NONCE_REPLAYED", response.result)
        self.assertEqual(self._business.call_count, 0)
        self.assertTrue(self._receiver.raw_nonce_row_exists(manual_nonce), "DENY여도 Primary에는 보존돼야 함")

        # 같은 envelope 재전송해도 실행 증가 없음
        replay = self._receiver.receive(envelope, now=now_epoch, now_iso=now_iso)
        self.assertFalse(replay.success)
        self.assertEqual(self._business.call_count, 0)

    # 8. 서명 준비 실패(발급측 ERROR) — 업무 실행 0회 -----------------------------------
    def test_prepare_dispatch_failure_zero_execution(self):
        """발급측 자체 저장소의 ERROR 시나리오. 이 시나리오에서는
        envelope 자체가 아직 만들어지지 않으므로 "재전송" 검증은
        적용 대상이 아니다(DENY 시나리오는 별도 테스트 참조 —
        envelope가 만들어지기 전이라 재전송 개념 자체가 없는 것은
        ERROR/DENY 둘 다 마찬가지)."""
        self._issuer_secondary.force_error(times=1)
        result = self._handle(idempotency_key="idem-prep-fail-0001")
        self.assertEqual(result.outcome, "NOT_SENT_PREP_FAILED")
        self.assertFalse(result.gas_called)
        self.assertEqual(self._business.call_count, 0)

    # 8-1. 발급측 Secondary DENY(ERROR와 구분) — 업무 실행 0회, Primary 보존 ------------
    def test_issuer_secondary_deny_zero_execution_primary_preserved(self):
        """정정: 이전 보고에서 "발급측은 매번 새 nonce를 생성하므로
        DENY가 구조적으로 불가능하다"고 설명했으나 부정확했다 —
        `prepare_dispatch`가 쓰는 `nonce_store.generate_nonce()`와
        `evaluate_and_register_nonce()`는 발급측·수신측에 동일하게
        재사용되는 함수이므로, 발급측도 DENY 경로를 그대로 갖고
        있다. 정상 경로에서 "우연히" 발생할 확률이 낮을 뿐이다.

        이 테스트는 `nonce_store.generate_nonce()`를 고정값으로
        패치해(표준 `unittest.mock.patch.object`, 가드·서명·nonce
        검증 로직 자체는 건드리지 않음) 그 고정 nonce를 발급측
        Secondary에 **미리** "이미 본 것"으로 등록한 뒤
        `handle_request()`를 호출한다 — `prepare_dispatch`가 그
        고정 nonce를 다시 발급받아 자체 기록을 시도하면 Secondary가
        DENY로 응답해야 한다."""
        fixed_nonce = nonce_store.generate_nonce()
        now0 = _now()
        self._issuer_secondary.check_and_mark(fixed_nonce, now0.timestamp())

        with unittest.mock.patch.object(nonce_store, "generate_nonce", return_value=fixed_nonce):
            result = self._handle(idempotency_key="idem-issuer-deny-0001", now=now0)

        self.assertEqual(result.outcome, "NOT_SENT_PREP_FAILED")
        self.assertFalse(result.gas_called)
        self.assertEqual(self._business.call_count, 0)

        # 발급측 Primary에도 이 nonce가 등록·보존됐는지 직접 확인
        # (Primary는 NEW로 먼저 커밋되고, Secondary가 DENY라도 삭제되지
        # 않는다 — nonce_store.py의 기존 "보존" 원칙 재확인, 재작성 아님).
        with nonce_store.connect(self._issuer_dir) as conn:
            row = conn.execute(
                "SELECT nonce FROM nonce_store WHERE nonce = ?", (fixed_nonce,)
            ).fetchone()
        self.assertIsNotNone(row, "발급측 Secondary DENY 후에도 Primary는 보존돼야 함")

    # 8-2. 동일 nonce 재사용 vs 신규 nonce를 쓰는 같은 작업 재시도 — 구분 확인 -----------
    def test_retry_after_nonce_store_failed_uses_new_nonce_and_succeeds(self):
        """NONCE_STORE_FAILED(retryable=True)는 "같은 nonce 재사용이
        허용된다"는 뜻이 **아니다** — 이 테스트는 (a) 실패했던 바로 그
        nonce는 여전히 거절되고, (b) 같은 idempotency key로의 재시도가
        **새 nonce**를 발급해 성공하는 것을 구분해서 확인한다. 자동
        재시도는 없다 — 재시도는 테스트가 `handle_request()`를 다시
        수동으로 호출해 수행한다(새 HTTP 요청 시뮬레이션)."""
        key = "idem-retry-new-nonce-0001"
        self._receiver.force_secondary_error(times=1)
        captured: list = []

        def capture(envelope: sgi.SignedEnvelope) -> sgi.SignedEnvelope:
            captured.append(envelope)
            return envelope

        first = self._handle(idempotency_key=key, envelope_tamperer=capture)
        self.assertEqual(first.outcome, "SENT_FAILED_RETRYABLE")
        self.assertEqual(self._business.call_count, 0)
        first_nonce = captured[0].nonce

        # (a) 실패했던 바로 그 nonce는 (이 테스트가 Primary를 정리하지
        # 않는 한) 여전히 거절된다 — Primary에 이미 등록돼 보존됐기
        # 때문(§7 재확인). 이것이 운영에서도 "영구" 차단된다는 보장은
        # 아니다 — 실제 보존 기간은 배치 정리 정책에 달려 있다
        # (signed_gas_integration.py 모듈 docstring 재확인).
        same_nonce_retry = self._receiver.receive(
            captured[0], now=_now().timestamp(), now_iso=_now().isoformat(timespec="seconds")
        )
        self.assertFalse(same_nonce_retry.success)
        self.assertIn("NONCE_REPLAYED", same_nonce_retry.result)
        self.assertEqual(self._business.call_count, 0)

        # (b) 같은 key로 재시도(새 HTTP 요청 시뮬레이션) -> RETRY_ACCEPTED
        # -> prepare_dispatch가 다시 실행되어 "새 nonce"를 발급 -> 성공.
        second = self._handle(idempotency_key=key, envelope_tamperer=capture)
        self.assertEqual(second.outcome, "SENT_SUCCESS")
        self.assertEqual(self._business.call_count, 1)
        second_nonce = captured[1].nonce
        self.assertNotEqual(first_nonce, second_nonce, "재시도는 새 nonce를 써야 한다(동일 nonce 재사용 아님)")

    # 9. 업무 반영 후 timeout — UNKNOWN, 새 nonce라도 재요청 우회 불가 -----------------
    def test_timeout_after_business_execution_marks_unknown_and_blocks_retry(self):
        """timeout(SENT_UNCERTAIN) 이후에는 — NONCE_STORE_FAILED와
        달리 — **idempotency 계층 자체가 재시도를 차단**한다. 재요청이
        `NOT_SENT_BLOCKED`로 끝난다는 것은 `prepare_dispatch()`가 전혀
        호출되지 않았다는 뜻이고(gas_orchestration.execute_with_idempotency의
        코드 구조상, NOT_SENT_BLOCKED는 prepare_dispatch 호출 이전의
        분기에서만 반환됨 — Open Question 문서 재확인), 따라서 **새
        nonce조차 발급되지 않는다** — "새 nonce를 쓰면 우회할 수
        있지 않을까"라는 시도 자체가 코드 구조상 불가능함을 보여준다."""
        result = self._handle(idempotency_key="idem-timeout-0001", network_fault=TimeoutError("simulated"))
        self.assertEqual(result.outcome, "SENT_UNCERTAIN")
        self.assertEqual(self._business.call_count, 1)  # 수신측은 실제로 실행함

        retry = self._handle(idempotency_key="idem-timeout-0001")
        self.assertEqual(retry.outcome, "NOT_SENT_BLOCKED")
        self.assertFalse(retry.gas_called)  # prepare_dispatch/gas_adapter 둘 다 호출 안 됨(새 nonce도 발급 안 됨)
        self.assertEqual(self._business.call_count, 1)  # 증가 없음

    # 10. 결과·UNKNOWN 기록 이중 실패 — TTL 경과 후에도 재실행 차단 --------------------
    def test_double_record_failure_then_ttl_elapses_blocks_re_execution(self):
        """수신측은 정상 성공을 반환하지만(발급측 기준 "확정 성공"
        경로), 그 결과를 로컬에 기록하는 record_outcome()도, 안전망인
        mark_unknown()도 둘 다 실패하는 "이중 실패"를 재현한다
        (tests/test_gas_orchestration.py의 동일 시나리오를 이 새
        통합 흐름 위에서 재검증 — _FailNCommitsProxy가 record_outcome의
        COMMIT과 그 직후 fallback mark_unknown의 COMMIT을 순서대로
        2회 실패시킨다). network_fault는 쓰지 않는다 — gas_adapter가
        예외 없이 성공을 반환해야 record_outcome 경로를 타기 때문이다."""
        key = "idem-double-fail-0001"
        now0 = _now()

        with store.connect(self._tmpdir) as real_conn:
            proxy = _FailNCommitsProxy(real_conn, fail_count=2)  # record_outcome + mark_unknown 둘 다 실패
            result = sgi.handle_request(
                proxy, raw_json_text=VALID_RAW_JSON, operation=OPERATION, idempotency_key=key,
                method="POST", issuer_config=self._issuer_cfg, receiver=self._receiver, now=now0,
            )
        self.assertEqual(result.outcome, "SENT_UNCERTAIN")
        self.assertFalse(result.record_write_ok)
        self.assertEqual(self._business.call_count, 1)  # 수신측 실행은 이미 일어남

        # TTL 이내 재요청 -> 여전히 차단(증가 없음)
        retry_within_ttl = self._handle(idempotency_key=key, now=_now(5))
        self.assertEqual(retry_within_ttl.outcome, "NOT_SENT_BLOCKED")
        self.assertEqual(self._business.call_count, 1)

        # 가상시계로 IN_PROGRESS TTL(60초) 경과 후 재요청 -> 여전히 차단(증가 없음)
        retry_after_ttl = self._handle(idempotency_key=key, now=_now(600))
        self.assertEqual(retry_after_ttl.outcome, "NOT_SENT_BLOCKED")
        self.assertEqual(self._business.call_count, 1)

    # 11. 기존 회귀검증 ---------------------------------------------------------------
    def test_existing_modules_unchanged_regression_smoke(self):
        """signing_v2/nonce_store/idempotency_store/gas_orchestration/
        payload_schema_guard/request_payload_schemas/signing_v2_guarded가
        이 통합 모듈 도입으로 깨지지 않았는지 가볍게 재확인한다(전체
        회귀는 별도 unittest 명령으로 실행, 완료 보고 참조)."""
        import payload_schema_guard
        import request_payload_schemas
        import signing_v2_guarded

        self.assertEqual(signing_v2.compute_payload_hash({"a": 1}), signing_v2.compute_payload_hash({"a": 1}))
        payload_schema_guard.validate_payload_schema_interim({"a": 1})
        request_payload_schemas.validate_request_schema("slot_generate", {"startDate": "x", "endDate": "y"})
        guarded_hash = signing_v2_guarded.compute_payload_hash_guarded(
            '{"startDate":"x","endDate":"y"}', operation="slot_generate"
        )
        self.assertEqual(len(guarded_hash), 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
