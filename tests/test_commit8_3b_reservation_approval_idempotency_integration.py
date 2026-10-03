# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-3b — 예약 승인/거절 ↔ Idempotency 실행권 판정 최소 통합 검증.

대상(이번에 수정/추가한 파일만, 둘 다 기존 gas_orchestration.py/idempotency_store.py
를 그대로 재사용 — 새 idempotency 로직을 다시 만들지 않음):
- src/api/routes_admin_portal.py :: _process_reservation_approval() 4단계
  (POST /api/admin/reservations/{no}/approve|reject)
- src/services/sheets_write_service.py :: update_status_idempotent() (신규 추가)

합성 데이터(sandbox data_dir 복사본)·Fake GAS(update_status 직접 monkeypatch)·
로컬 SQLite(idempotency_store)만 쓴다 — 실제 GAS/Sheets 접근 없음.

**발견한 선행 결함(이번 작업과 무관, 코드는 수정하지 않음 — 원인만 규명,
이번 커밋 전 재검토에서 세분화)**:
`tests/run_sprint4_commit2_approval_qa.py`를 환경변수만 다르게 주고 비교:
- 환경변수 없음(이번 변경 전/후 동일): 41/61 PASS — 변경 전/후 동일하게
  재현되어 이번 통합 작업이 원인이 아님을 먼저 확인했다.
- `CSHSP_COOKIE_INSECURE_DEV=1`만 추가(routes_auth.py::_cookie_secure()의
  Secure 쿠키 기본값 때문에 그 스크립트가 세션 쿠키를 보존 못 하는 문제):
  54/61.
- 추가로 `CSHSP_GAS_WEBAPP_URL`까지 설정(이번에 새로 추가된
  `check_configured()`가 `update_status()`와 별도로 이 값을 직접 확인하는데,
  그 스크립트는 `update_status()`만 monkeypatch하고 이 값은 설정하지
  않았음): **58/61**까지 개선. 이 두 환경변수는 코드가 아니라 그 스크립트의
  "실행 조건"이며, 이번 변경이 `check_configured()`를 `prepare_dispatch`로
  분리해 추가한 것이 두 번째 환경변수가 새로 필요해진 이유다(비즈니스
  로직은 고치지 않음).
- 남은 3건 중 1건("(9) GAS 오류 시 502 반환")은 **이번 통합이 의도적으로
  바꾼 계약**이다 — GAS 예외를 더 이상 "확정 실패"(502)로 단정하지 않고
  `gas_orchestration` 설계 원칙대로 "결과 불확실"(409
  `APPROVAL_RESULT_UNKNOWN`)로 분류한다. 되돌리지 않았다 — 되돌리면 이번
  통합의 핵심 안전장치(전송후 불확실 결과를 확정 실패로 오판하지 않는 것)
  자체를 없애는 것이기 때문이다. 그 스크립트의 기대값이 낡은 것이다.
- 남은 3건 중 2건("(10) 승인/거절 성공 시 Audit 1건 생성"×2)은 **이번 변경과
  완전히 무관**함을 `git apply -R`로 이번 통합 diff(3개 파일)만 정확히
  되돌린 뒤 동일 환경변수로 재실행해 재확인했다(되돌린 코드에서도 똑같이
  2건 FAIL, 59/61) — 원인은 그 스크립트가 `/api/audit-logs` 조회에 쓰는
  `DIRECTOR = {"X-User-Id": ...}`(Mock-Auth 헤더 방식)가 Sprint8 Commit8-2c
  이후 그 엔드포인트에서도 거부(401 "로그인이 필요합니다")되기 때문 —
  승인/거절 자체(이번 통합 대상)는 200으로 정상 동작했고 Audit도 실제로는
  기록됐다(진단 스크립트로 직접 확인). 이 결함은 그 스크립트가 쓰는 인증
  메커니즘 자체가 낡은 것이라 "실행 조건"(환경변수) 수준으로 고칠 수 없고,
  스크립트의 그 부분을 재작성해야 하므로 이번 범위(실행 조건 맞추기) 밖이라
  건드리지 않았다.
이번 테스트는 기존에 이미 지원되는 그 환경변수(로컬 개발 전용 예외, 코드
변경 없음)를 설정해 실제 세션 로그인으로 검증한다 — 또한 Mock 인증
(X-User-Id)은 Sprint8 Commit8-2c에서 상태변경 API에 의도적으로 차단되어
있음을 먼저 확인했다(이 테스트도 그 차단을 그대로 존중해 실제 세션을 쓴다).

**호출 순서 검토(이번 커밋 전 재검토)**: 기대한 "idempotency 실행권 획득 →
슬롯 변경 → GAS 쓰기" 순서와 달리, 실제 코드는 승인(예약확정)일 때
"슬롯 변경(3번) → idempotency 실행권 획득+GAS 쓰기(4번)" 순서다(거절은 슬롯
단계 자체가 없어 순서 문제가 없음). `gas_orchestration.execute_with_
idempotency()`가 `gas_adapter`를 호출당 정확히 1회만 호출한다는 것(재시도
루프 없음, 모듈 docstring 명시)과 `_reserve_slot_for_approval()`이
`DataLock`+"동일 예약번호가 이미 점유 목록에 있으면 거부" 체크로 동시
중복요청을 **idempotency 계층 이전에** 이미 직렬화·차단한다는 것(코드로
추적 확인)을 근거로, 슬롯 변경을 adapter 안으로 옮기는 재구조화는 **하지
않기로 결정**했다 — 그 모듈은 adapter가 던지는 모든 예외를 예외 타입 구분
없이 `SENT_UNCERTAIN`으로 취급하므로(네트워크 불확실성과 구분하지 않는
의도된 설계), 슬롯 검증 실패(예: SLOT_FULL)가 adapter 안에 있으면 "GAS를
부르지도 않은 로컬 검증 실패"가 "GAS 결과 불확실"로 오분류되고 idempotency
key가 불필요하게 소모된다 — 현재의 좁은 창(슬롯 선점 후 희귀한 PREP_FAILED/
BLOCKED/CACHED 분기에서만 되돌림)보다 더 나쁜 결함이다. 현재 방식의 창은
Sprint4부터 있던 기존 comment("경쟁조건을 완전히 없애지는 못한다")가 가리키는
것과 동일한, 이미 알려진 좁은 창일 뿐이며 이번 통합이 새로 만든 것이 아니다.

**idempotency key 한계(1줄)**: key(`admin_approval:{reservation_no}:
{action_tag}`)는 URL 경로의 `reservation_no`(라우트가 신뢰)와 호출된
엔드포인트가 고정하는 `action_tag`(approve|reject 둘뿐, 클라이언트가 임의
주입 불가)로만 구성되어 같은 작업의 재시도는 항상 같은 key를 만든다 —
단, approve↔reject처럼 **다른 key로 전환**하는 것 자체의 안전성은
idempotency가 아니라 `approval_states.assert_can_transition()`(2단계)이
담당한다는 경계가 있다(idempotency 레이어의 책임 밖, 한계로만 기록).

흐름 단위 시나리오(8개, 유닛테스트 재탕 아님 — "실제 라우트에 연결됐을 때도
동일하게 동작하는가"만 검증):
1. 성공            2. 중복 요청(동일 key 재전송)
3. payload 충돌    4. 전송 후 timeout → 결과불확실(UNKNOWN), Slot 보존
5. 결과 기록 실패 → 결과불확실(UNKNOWN)
6. UNKNOWN 상태의 즉시 재요청 차단(GAS 재호출 안 됨)
7. 동시 동일요청의 GAS 쓰기·슬롯 변경 단일성
8. 순차 중복 승인 요청의 co-occupant 슬롯 점유 비영향(신규, 이번 커밋 전
   마지막 재검토에서 추가 — scenario8 docstring 참조)

**슬롯 선처리 경로 재검토 결과(이번 턴)**: `_safe_rollback_slot()`과 그
호출부(`_reserve_slot_for_approval`/`_rollback_slot_reservation`/
`reservation_engine._release_slot`)를 코드로 추적한 결과, 롤백은 **그
호출이 새로 추가한 `reservation_no` 1건만** `sheetsReservationNos`에서
제거하고 `reservedCount`를 정확히 1만 감소시킨다 — 다른 예약(co-occupant)의
점유 기록이나 그 예약 자체의 Sheets 상태(이 라우트 코드는 Sheets의 status
필드를 로컬에서 전혀 쓰지 않음, GAS updateStatus 호출 자체가 유일한 변경
경로이고 그 호출은 idempotency 허가 후에만 발생)를 건드릴 수 있는 코드
경로가 구조적으로 없음을 확인했다(진단: scenario8 docstring).

**부가 발견(버그 아님, 투명성 기록)**: 진단 결과 approve 경로에서
`_safe_rollback_slot()`이 `NOT_SENT_BLOCKED`/`NOT_SENT_CACHED` 분기(lines
~800-812)에서 실제로 호출되는 경우는 **현재 가드 순서상 발생하지 않는다**
— 어떤 재요청이든 `_reserve_slot_for_approval()`의 기존(Sprint4) "이미 점유
기록 있으면 재점유 금지" 가드가 idempotency 계층보다 먼저 걸려
`SLOT_RESERVATION_CONFLICT`로 막기 때문이다(scenario8이 이를 실제로
재현·확인). 결과는 여전히 안전하다(중복 차단, GAS 미호출, co-occupant
비영향 모두 scenario8로 확인) — 재구조화는 이미 결정대로 하지 않는다.

**추가하지 않은 것(이미 충분/해당 없음)**: 거절 경로는 이미 2/3/6번
시나리오가 전부 거절로 수행되므로(1번 성공 경로도 2번의 첫 호출이 거절
성공을 포함) 별도 추가 없음. 알림 중복 방지는 `routes_admin_portal.py`가
`notification_worker.py`/CRM 알림 경로를 전혀 import·호출하지 않음을 grep으로
확인했으므로(이 승인/거절 흐름과 알림이 아예 미연결) **해당 없음** — 테스트를
억지로 만들지 않았다.
"""
from __future__ import annotations

import json
import shutil
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in ("core", "api", "services", "reservation", "auth", "idempotency"):
    sys.path.insert(0, str(ROOT / "src" / _p))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import idempotency_store as idem_store  # noqa: E402
import sheets_readonly_service as sheets  # noqa: E402
import sheets_write_service as sheets_write  # noqa: E402
from routes_admin_portal import create_admin_namespace_router  # noqa: E402
from routes_auth import create_auth_router  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _step2_session_helper import ensure_session  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_commit8_3b_approval_idempotency" / "data"

_FAKE_DB: dict[str, dict] = {}


@pytest.fixture()
def sandbox_app(monkeypatch):
    if SANDBOX.parent.exists():
        shutil.rmtree(SANDBOX.parent)
    shutil.copytree(ROOT / "data", SANDBOX)

    # run_sprint4_commit2_approval_qa.py와 동일한 패턴: 큰 capacity의 더미 Slot
    # 주입(approve 경로 검증용, 거절 경로는 Slot을 전혀 쓰지 않음).
    slots_doc = json.loads((SANDBOX / "slots.json").read_text(encoding="utf-8"))
    slots_doc["records"].append({
        "id": "SLOT-C83B-0900-A", "date": "2026-07-28", "time": "09:00",
        "capacity": 50, "reservedCount": 0, "waitingCount": 0, "status": "AVAILABLE",
        "roomId": "ROOM-0001", "programRestriction": None, "note": "Commit8-3b 통합검증 더미",
        "createdAt": "2026-07-28T00:00:00+09:00", "updatedAt": "2026-07-28T00:00:00+09:00",
    })
    (SANDBOX / "slots.json").write_text(
        json.dumps(slots_doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 로컬 개발 전용 기존 예외 환경변수(코드 변경 없음) — 위 모듈 docstring의
    # "발견한 선행 결함" 설명 참조. 운영/Staging에는 영향 없음(_cookie_secure()
    # 가 그 환경에서는 이 값을 무시하고 항상 True를 반환).
    monkeypatch.setenv("CSHSP_COOKIE_INSECURE_DEV", "1")
    # sheets_write_service.check_configured()(prepare_dispatch)는 update_status()
    # 자체의 monkeypatch 여부와 무관하게 이 환경변수만 독립적으로 확인한다 —
    # 값은 실제로 쓰이지 않는다(각 테스트가 update_status를 직접 monkeypatch해
    # 실제 네트워크 요청이 전혀 발생하지 않음), 형식 통과만 필요하다.
    monkeypatch.setenv("CSHSP_GAS_WEBAPP_URL", "https://example-fake-gas-not-called.invalid/exec")
    monkeypatch.delenv("CSHSP_ALLOW_MOCK_AUTH", raising=False)
    monkeypatch.delenv("CSHSP_ENV", raising=False)

    _FAKE_DB.clear()
    app = FastAPI()
    app.include_router(create_auth_router(SANDBOX))
    app.include_router(create_admin_namespace_router(SANDBOX))
    client = TestClient(app)
    csrf = ensure_session(
        client, SANDBOX, user_id="USR-0002", role_id="ROLE-STAFF",
        display_name="QA STAFF C83B", login_id="qa_c83b_staff",
    )
    client.headers.update(csrf)  # 이후 모든 요청에 X-CSRF-Token 자동 포함
    return client


def _reset_fixture(no: str, *, status: str = "예약접수",
                    wish_date: str = "2026-07-28", wish_time: str = "09:00",
                    program: str = "BASIC") -> None:
    _FAKE_DB[no] = {"reservationNo": no, "status": status, "name": "QA더미", "program": program,
                     "wishDate": wish_date, "wishTime": wish_time}


def _fake_get_reservation(no, **kw):
    # 의도적으로 "읽을 때마다 항상 최초(접수) 상태를 본다"로 고정한다 — GAS
    # updateStatus가 compare-and-swap을 지원하지 않는다는 기존 코드 comment가
    # 가리키는 경쟁조건(재조회로도 완전히 없어지지 않는 틈)을 재현한다. 이
    # idempotency 계층이 없다면 시나리오 2/3에서 중복/충돌 재전송이 막히지
    # 않는다는 것이 이번 통합의 핵심 검증 대상이다.
    return dict(_FAKE_DB[no]) if no in _FAKE_DB else None


@pytest.fixture(autouse=True)
def _patch_sheets_read(monkeypatch):
    monkeypatch.setattr(sheets, "get_reservation", _fake_get_reservation)


# ── 1. 성공 ──
def test_scenario1_success(sandbox_app, monkeypatch):
    _reset_fixture("C83B-S1")
    calls: list[tuple[str, str]] = []

    def fake_update_status(no, status, **kw):
        calls.append((no, status))
        return {"ok": True}

    monkeypatch.setattr(sheets_write, "update_status", fake_update_status)

    r = sandbox_app.post("/api/admin/reservations/C83B-S1/approve")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "예약확정"
    assert calls == [("C83B-S1", "예약확정")]


# ── 2. 중복 요청(동일 key 재전송) ──
def test_scenario2_duplicate_request_same_key_not_resent(sandbox_app, monkeypatch):
    _reset_fixture("C83B-S2")
    calls: list[tuple[str, str]] = []

    def fake_update_status(no, status, **kw):
        calls.append((no, status))
        return {"ok": True}

    monkeypatch.setattr(sheets_write, "update_status", fake_update_status)

    body = {"reason": "동일 사유 재전송 테스트"}
    r1 = sandbox_app.post("/api/admin/reservations/C83B-S2/reject", json=body)
    assert r1.status_code == 200, r1.text

    r2 = sandbox_app.post("/api/admin/reservations/C83B-S2/reject", json=body)
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"]["code"] == "APPROVAL_NOT_SENT_CACHED"
    assert calls == [("C83B-S2", "거절")]  # GAS는 1번만 호출됨(두 번째는 idempotency가 차단)


# ── 3. payload 충돌(동일 key, 다른 사유) ──
def test_scenario3_payload_conflict_same_key_different_body(sandbox_app, monkeypatch):
    _reset_fixture("C83B-S3")
    calls: list[tuple[str, str]] = []

    def fake_update_status(no, status, **kw):
        calls.append((no, status))
        return {"ok": True}

    monkeypatch.setattr(sheets_write, "update_status", fake_update_status)

    r1 = sandbox_app.post("/api/admin/reservations/C83B-S3/reject", json={"reason": "사유 A"})
    assert r1.status_code == 200, r1.text

    r2 = sandbox_app.post("/api/admin/reservations/C83B-S3/reject", json={"reason": "사유 B(다른 내용)"})
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"]["code"] == "APPROVAL_NOT_SENT_BLOCKED"
    assert calls == [("C83B-S3", "거절")]  # 충돌 요청은 GAS에 도달조차 하지 않음


# ── 4. 전송 후 timeout → 결과불확실(UNKNOWN), Slot 보존 ──
def test_scenario4_timeout_result_unknown_slot_preserved(sandbox_app, monkeypatch):
    _reset_fixture("C83B-S4")
    calls: list[tuple[str, str]] = []

    def fake_update_status_timeout(no, status, **kw):
        calls.append((no, status))
        raise sheets_write.SheetsIntegrationError("GAS 호출 실패(updateStatus): 가상 timeout")

    monkeypatch.setattr(sheets_write, "update_status", fake_update_status_timeout)

    r = sandbox_app.post("/api/admin/reservations/C83B-S4/approve")
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "APPROVAL_RESULT_UNKNOWN"
    assert calls == [("C83B-S4", "예약확정")]

    slots_doc = json.loads((SANDBOX / "slots.json").read_text(encoding="utf-8"))
    slot = next(s for s in slots_doc["records"] if s["id"] == "SLOT-C83B-0900-A")
    # Rollback이 호출됐다면 이 예약번호가 사라졌을 것 — 보존 확인(이중예약 위험 회피).
    assert "C83B-S4" in (slot.get("sheetsReservationNos") or [])


# ── 5. 결과 기록 실패(GAS는 성공했으나 로컬 저장 실패) → 결과불확실(UNKNOWN) ──
def test_scenario5_record_outcome_failure_result_unknown(sandbox_app, monkeypatch):
    _reset_fixture("C83B-S5")
    calls: list[tuple[str, str]] = []

    def fake_update_status_ok(no, status, **kw):
        calls.append((no, status))
        return {"ok": True}

    monkeypatch.setattr(sheets_write, "update_status", fake_update_status_ok)

    def raise_record_outcome(*a, **kw):
        raise idem_store.IdempotencyError("합성 로컬 저장 실패(테스트 전용)")

    monkeypatch.setattr(idem_store, "record_outcome", raise_record_outcome)

    r = sandbox_app.post("/api/admin/reservations/C83B-S5/reject", json={"reason": "기록실패 테스트"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "APPROVAL_RESULT_UNKNOWN"
    assert calls == [("C83B-S5", "거절")]  # GAS 호출은 실제로 성공함 — 로컬 기록만 실패


# ── 6. UNKNOWN 상태의 즉시 재요청 차단(GAS 재호출 안 됨) ──
def test_scenario6_unknown_state_blocks_immediate_retry(sandbox_app, monkeypatch):
    _reset_fixture("C83B-S6")
    calls: list[tuple[str, str, str]] = []

    def fake_update_status_timeout(no, status, **kw):
        calls.append(("timeout-attempt", no, status))
        raise sheets_write.SheetsIntegrationError("가상 timeout")

    monkeypatch.setattr(sheets_write, "update_status", fake_update_status_timeout)

    r1 = sandbox_app.post("/api/admin/reservations/C83B-S6/reject", json={"reason": "최초 시도"})
    assert r1.status_code == 409, r1.text
    assert r1.json()["detail"]["code"] == "APPROVAL_RESULT_UNKNOWN"

    # 이번엔 GAS가 성공한다고 가정해도(재시도 자체가 막히는지가 핵심) 동일
    # key+동일 payload로 즉시 재요청.
    def fake_update_status_would_succeed(no, status, **kw):
        calls.append(("retry-attempt", no, status))
        return {"ok": True}

    monkeypatch.setattr(sheets_write, "update_status", fake_update_status_would_succeed)

    r2 = sandbox_app.post("/api/admin/reservations/C83B-S6/reject", json={"reason": "최초 시도"})
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"]["code"] == "APPROVAL_NOT_SENT_BLOCKED"
    assert calls == [("timeout-attempt", "C83B-S6", "거절")]  # retry-attempt는 기록되지 않음(GAS 재호출 안 됨)


# ── 7. 동시 동일요청의 GAS 쓰기·슬롯 변경 단일성(승인 경로, 신규) ──
def test_scenario7_concurrent_duplicate_approve_single_gas_call_and_slot_change(
    sandbox_app, monkeypatch,
):
    """동일 reservation_no+승인을 거의 동시에 2번 호출해도 GAS 쓰기 1회·
    슬롯 reservedCount 증가 1회만 일어나는지 확인한다. 가짜 GAS 응답에 짧은
    sleep을 둬 두 스레드의 idempotency 실행권 경쟁 창을 넓힌다 — 순차
    monkeypatch 호출(시나리오 2/3/6)과 달리 실제로 거의 동시에 FastAPI
    threadpool에서 겹쳐 실행되는지를 검증하는 것이 이 시나리오의 핵심이다."""
    _reset_fixture("C83B-S7")
    lock = threading.Lock()
    calls: list[tuple[str, str]] = []

    def fake_update_status_slow(no, status, **kw):
        time.sleep(0.15)
        with lock:
            calls.append((no, status))
        return {"ok": True}

    monkeypatch.setattr(sheets_write, "update_status", fake_update_status_slow)

    results: list[int] = []

    def _call():
        r = sandbox_app.post("/api/admin/reservations/C83B-S7/approve")
        with lock:
            results.append(r.status_code)

    t1 = threading.Thread(target=_call)
    t2 = threading.Thread(target=_call)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert sorted(results) == [200, 409], results  # 하나만 성공, 다른 하나는 차단(코드는 경쟁 시점에 따라 다를 수 있음)
    assert calls == [("C83B-S7", "예약확정")]  # GAS 쓰기는 정확히 1회

    slots_doc = json.loads((SANDBOX / "slots.json").read_text(encoding="utf-8"))
    slot = next(s for s in slots_doc["records"] if s["id"] == "SLOT-C83B-0900-A")
    assert slot["reservedCount"] == 1  # 슬롯 점유도 정확히 1회(이중 점유 없음)
    assert slot["sheetsReservationNos"].count("C83B-S7") == 1


# ── 8. 순차 중복 승인 요청 — co-occupant 슬롯 점유 비영향(신규, 커밋 전 재검토) ──
def test_scenario8_duplicate_approve_does_not_touch_other_occupant_slot_share(
    sandbox_app, monkeypatch,
):
    """진단 결과(이번 재검토): 동일 예약번호로 승인→성공 후 **순차** 재요청하면
    실제로는 idempotency 계층(`APPROVAL_NOT_SENT_CACHED`, lines ~800-812의
    `_safe_rollback_slot` 분기)이 아니라, 그보다 먼저 실행되는 기존(Sprint4)
    슬롯 중복점유 가드(`_reserve_slot_for_approval()`의 "이미 점유 기록으로
    남아 있으면 새로 점유하지 않는다" 체크, `SLOT_RESERVATION_CONFLICT`)가
    차단한다 — idempotency의 신규 rollback 분기는 approve 경로에서는 (현재
    가드 순서상) 도달하지 않는다. 재구조화는 이번 범위가 아니다(이미 결정:
    위 §주석 "호출 순서 검토" 참조). 이 테스트가 실제로 검증하는 것은 그
    경로가 실제로 안전한가: 중복 요청이 (a) GAS를 다시 호출하지 않고 (b)
    같은 슬롯을 공유하는 **다른 예약(co-occupant)**의 점유·카운트를 전혀
    건드리지 않는가다 — 기존 7개 시나리오는 capacity=50에 co-occupant가
    전혀 없는 슬롯만 써서 이 교차-예약 비영향을 한 번도 확인하지 않았다."""
    other_no = "C83B-OTHER-OCCUPANT"
    slots_doc = json.loads((SANDBOX / "slots.json").read_text(encoding="utf-8"))
    slot = next(s for s in slots_doc["records"] if s["id"] == "SLOT-C83B-0900-A")
    slot["reservedCount"] = 1
    slot["sheetsReservationNos"] = [other_no]
    (SANDBOX / "slots.json").write_text(
        json.dumps(slots_doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _reset_fixture("C83B-S8")
    calls: list[tuple[str, str]] = []

    def fake_update_status(no, status, **kw):
        calls.append((no, status))
        return {"ok": True}

    monkeypatch.setattr(sheets_write, "update_status", fake_update_status)

    r1 = sandbox_app.post("/api/admin/reservations/C83B-S8/approve")
    assert r1.status_code == 200, r1.text

    r2 = sandbox_app.post("/api/admin/reservations/C83B-S8/approve")
    assert r2.status_code == 409, r2.text
    # 실제로 어떤 차단 코드가 뜨는지 그대로 검증(위 docstring 진단 결과) —
    # idempotency CACHED가 아니라 기존 슬롯 가드가 먼저 막는다.
    assert r2.json()["detail"]["code"] == "SLOT_RESERVATION_CONFLICT", r2.text
    assert calls == [("C83B-S8", "예약확정")]  # GAS는 1번만 호출됨

    slots_doc2 = json.loads((SANDBOX / "slots.json").read_text(encoding="utf-8"))
    slot2 = next(s for s in slots_doc2["records"] if s["id"] == "SLOT-C83B-0900-A")
    # co-occupant는 그대로, C83B-S8은 정확히 1회만 점유(중복 차단 요청이
    # 추가로 점유를 만들거나 co-occupant를 건드리지 않았음).
    assert slot2["reservedCount"] == 2
    assert sorted(slot2["sheetsReservationNos"]) == sorted([other_no, "C83B-S8"])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
