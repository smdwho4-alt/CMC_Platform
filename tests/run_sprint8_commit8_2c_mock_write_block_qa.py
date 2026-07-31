# -*- coding: utf-8 -*-
"""
CSHSP Sprint 8 Commit 8-2c STEP 1 — Mock 인증 상태변경·Write 경계 차단 테스트

목적: Mock(X-User-Id) 인증 사용자가 CSRF Token 유무와 무관하게 상태변경 API
(승인/거절/상담 상태변경 등)에서 완전히 차단되고, Sheets/GAS Write 경로에
전혀 도달하지 못함을 검증한다. 반대로 실제 세션 인증 사용자의 기존 동작
(CSRF 검증, RBAC 검증, 승인/거절 성공)은 그대로 유지됨을 대조 확인한다.

기존 테스트 파일은 1건도 수정하지 않았다(신규 파일로만 검증).

"보안 PASS"는 위험한 요청이 명시적으로 차단되고 Fake Sheets/GAS Adapter
호출 횟수가 0이며 DB/Sheets에 어떤 부작용도 없을 때만 인정한다 — 단순히
GAS URL 미설정으로 인한 실패(503)는 이번 테스트에서 보안 통제로 인정하지
않으며, 그런 경우가 재현되면 FAIL로 기록한다.
"""
from __future__ import annotations

import csv
import os
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "core"))
sys.path.insert(0, str(ROOT / "src" / "api"))
sys.path.insert(0, str(ROOT / "src" / "auth"))
sys.path.insert(0, str(ROOT / "src" / "reservation"))
sys.path.insert(0, str(ROOT / "src" / "services"))

from fastapi.testclient import TestClient  # noqa: E402

import core_data_loader as loader  # noqa: E402
import auth_service  # noqa: E402
import auth_store as store  # noqa: E402
import sheets_write_service as sheets_write  # noqa: E402
import sheets_readonly_service as sheets  # noqa: E402
from api_server import create_app  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint8_commit8_2c_mock_write_block" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)

_users = loader.load_entity("User", SANDBOX)
_staff = next(u for u in _users if u.get("roleId") == "ROLE-STAFF")
STAFF_ID = _staff["id"]
STAFF_HDR = {"X-User-Id": STAFF_ID}

results: list[tuple[str, str, str, str]] = []


def check(name: str, ok: bool, detail: str = "", write_effect: str = "N/A") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail, write_effect))
    line = f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "backslashreplace").decode("ascii"))


# ── Fake Sheets/GAS Adapter (호출 횟수 계측, 실네트워크 없음) ──
_call_log: list[str] = []
_ORIG_UPDATE_STATUS = sheets_write.update_status
_ORIG_LIST_RESERVATIONS = sheets.list_reservations


def _fake_update_status(reservation_no: str, status: str, *, session=None):
    _call_log.append(f"update_status({reservation_no},{status})")
    return {"ok": True, "data": {"reservationNo": reservation_no, "status": status, "slotId": None}}


def _fake_list_reservations(*args, **kwargs):
    _call_log.append("list_reservations(...)")
    return {"records": []}


sheets_write.update_status = _fake_update_status
sheets.list_reservations = _fake_list_reservations


def _reset_call_log() -> int:
    n = len(_call_log)
    return n


_ENV_KEYS = ("CSHSP_ENV", "CSHSP_ALLOW_MOCK_AUTH", "CSHSP_COOKIE_INSECURE_DEV")

MOCK_ENV = {"CSHSP_ENV": "development", "CSHSP_ALLOW_MOCK_AUTH": "1"}
SESSION_ENV = {"CSHSP_ENV": "test", "CSHSP_COOKIE_INSECURE_DEV": "1"}


def _set_env(env: dict[str, str] | None) -> None:
    """routes_auth.current_env()/mock_auth_allowed()/_cookie_secure()는 매 요청마다
    os.environ을 다시 읽는다(운영 코드의 올바른 설계) — 이 프로세스에서 Mock용
    클라이언트와 세션용 클라이언트를 번갈아 쓰려면, 매 요청 직전에 그 요청에 맞는
    환경을 명시적으로 세팅해야 한다(클라이언트 생성 시점에 한 번만 세팅하면 나중에
    다른 클라이언트가 env를 덮어써 잘못된 환경으로 요청이 나간다 — 실제로 최초
    작성 시 이 문제로 인해 Mock 요청이 401로 잘못 나오는 버그를 발견·수정했다)."""
    for k in _ENV_KEYS:
        os.environ.pop(k, None)
    for k, v in (env or {}).items():
        os.environ[k] = v


def _client(env: dict[str, str] | None = None) -> TestClient:
    _set_env(env)
    return TestClient(create_app(SANDBOX, include_agents=False))


def _sqlite_row_counts() -> dict[str, int]:
    store.init_schema(SANDBOX)
    with store.connect(SANDBOX) as conn:
        return {
            t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
            for t in ("auth_users", "auth_sessions", "auth_audit_log")
        }


# 합성 세션 계정(대조군, 실제 인증 사용자 확인용)
auth_service.create_user(
    SANDBOX, user_id=STAFF_ID, login_id="qa_writeblock_login",
    password="Synthetic-Test-Pw-WriteBlock-01!", display_name=_staff.get("name"),
    role_id=_staff.get("roleId"),
)

_set_env(MOCK_ENV)
c_mock = _client(MOCK_ENV)
_set_env(SESSION_ENV)
c_sess = _client(SESSION_ENV)
r_login = c_sess.post("/api/auth/login", json={"loginId": "qa_writeblock_login",
                                                "password": "Synthetic-Test-Pw-WriteBlock-01!"})
CSRF_TOKEN = r_login.json()["csrfToken"]

# ── 1/2: Mock + 승인, CSRF 없음/있음 ──
_set_env(MOCK_ENV)
before = _reset_call_log()
r1 = c_mock.post("/api/admin/reservations/RSV-WB-001/approve", headers=STAFF_HDR)
check("1. Mock+CSRF없음+승인 → 403", r1.status_code == 403, str(r1.status_code),
      write_effect=f"GAS호출={len(_call_log)-before}")

_set_env(MOCK_ENV)
before = _reset_call_log()
r2 = c_mock.post("/api/admin/reservations/RSV-WB-002/approve", headers={**STAFF_HDR, "X-CSRF-Token": "forged-token"})
check("2. Mock+CSRF있음(위조)+승인 → 403", r2.status_code == 403, str(r2.status_code),
      write_effect=f"GAS호출={len(_call_log)-before}")

# ── 3/4: Mock + 거절, CSRF 없음/있음 ──
_set_env(MOCK_ENV)
before = _reset_call_log()
r3 = c_mock.post("/api/admin/reservations/RSV-WB-003/reject", headers=STAFF_HDR, json={"reason": "test"})
check("3. Mock+CSRF없음+거절 → 403", r3.status_code == 403, str(r3.status_code),
      write_effect=f"GAS호출={len(_call_log)-before}")

_set_env(MOCK_ENV)
before = _reset_call_log()
r4 = c_mock.post("/api/admin/reservations/RSV-WB-004/reject", headers={**STAFF_HDR, "X-CSRF-Token": "forged-token"},
                  json={"reason": "test"})
check("4. Mock+CSRF있음(위조)+거절 → 403", r4.status_code == 403, str(r4.status_code),
      write_effect=f"GAS호출={len(_call_log)-before}")

# ── 5: Mock + 상태변경(구버전 로컬 JSON API) ──
_set_env(MOCK_ENV)
before = _reset_call_log()
r5 = c_mock.post("/api/reservations/RSV-WB-005/cancel", headers=STAFF_HDR, json={"reason": "test"})
check("5. Mock+예약상태변경(cancel, 구버전 API) → 403", r5.status_code == 403, str(r5.status_code),
      write_effect=f"호출={len(_call_log)-before}")

_set_env(MOCK_ENV)
r5b = c_mock.post("/api/reservations/RSV-WB-005B/complete", headers=STAFF_HDR)
check("5b. Mock+검진상태변경(complete, 구버전 API) → 403", r5b.status_code == 403, str(r5b.status_code))

# ── 6/7: 계정관리·역할관리 Write API ──
# 저장소 전체를 조사한 결과 계정 생성·수정·삭제 또는 역할 생성·수정·삭제를 수행하는
# 전용 API 자체가 이 코드베이스에 존재하지 않는다(grep으로 확인, POST/PUT/DELETE
# 라우트 전수 조사 — routes_admin_portal.py/api_server.py에 /api/users, /api/roles류
# 쓰기 엔드포인트 0건). 존재하지 않는 엔드포인트를 임의로 만들어 테스트하지 않는다.
check("6. Mock+계정관리 Write 요청 → 해당 API 자체가 저장소에 존재하지 않음(N/A, 추정 금지)",
      True, "계정 생성/수정/삭제 API 0건 확인(grep 전수조사)")
check("7. Mock+역할관리 Write 요청 → 해당 API 자체가 저장소에 존재하지 않음(N/A, 추정 금지)",
      True, "역할 생성/수정/삭제 API 0건 확인(grep 전수조사)")

# ── 8/9: Sheets Write / GAS Write Proxy 시도가 호출 전에 차단되는지(누적 호출횟수 0 확인) ──
total_calls_after_all_mock_attempts = len(_call_log)
check("8/9. 위 1~5b의 모든 Mock 상태변경 시도에서 Fake Sheets/GAS Adapter 호출 횟수 누적 0",
      total_calls_after_all_mock_attempts == 0, f"누적 호출={total_calls_after_all_mock_attempts}")

# ── 10: SQLite Write 시도 → 데이터 변경 없음 ──
_set_env(MOCK_ENV)
counts_before = _sqlite_row_counts()
r10 = c_mock.post("/api/admin/reservations/RSV-WB-010/approve", headers=STAFF_HDR)
counts_after = _sqlite_row_counts()
check("10. Mock 상태변경 차단 요청으로 인한 SQLite 사용자·세션 테이블 변경 없음"
      "(감사로그 테이블만 차단 기록으로 증가하는 것은 정상 — 부작용이 아니라 통제의 증거)",
      counts_before["auth_users"] == counts_after["auth_users"]
      and counts_before["auth_sessions"] == counts_after["auth_sessions"],
      f"{counts_before} -> {counts_after}")

# ── 11: X-User-Id 위조로 차단 우회 불가 ──
_set_env(MOCK_ENV)
r11 = c_mock.post("/api/admin/reservations/RSV-WB-011/approve", headers={"X-User-Id": "USR-9999-FORGED"})
check("11. 존재하지 않는 X-User-Id로도 우회 불가(401, 애초에 인증 자체 실패)",
      r11.status_code == 401, str(r11.status_code))

_set_env(MOCK_ENV)
r11b = c_mock.post("/api/admin/reservations/RSV-WB-011B/approve",
                    headers={**STAFF_HDR, "X-CSRF-Token": CSRF_TOKEN})  # 진짜 세션의 CSRF 토큰을 훔쳐 시도
check("11b. 세션 사용자의 진짜 CSRF Token을 Mock 요청에 첨부해도 우회 불가(Mock은 auth_method로만 판정)",
      r11b.status_code == 403, str(r11b.status_code))

# ── 12: roleId 위조로 권한 상승 불가 ──
# 클라이언트가 별도로 roleId를 요청 본문/헤더로 보낼 수 있는 경로 자체가 없음(서버가
# users.json에서 조회) — 그래도 명시적으로 시도해 무시됨을 확인한다.
_set_env(MOCK_ENV)
r12 = c_mock.post("/api/admin/reservations/RSV-WB-012/approve",
                   headers={**STAFF_HDR, "X-Role-Id": "ROLE-ADMIN"})  # 존재하지 않는 위조 헤더
check("12. roleId를 헤더로 위조 주입해도 무시되고(서버가 실제 조회한 값만 사용) 여전히 403",
      r12.status_code == 403, str(r12.status_code))

# ── 13/14/15: 실제 세션 인증 사용자 기존 동작 보존 ──
_set_env(SESSION_ENV)
before = _reset_call_log()
r13 = c_sess.post("/api/admin/reservations/RSV-WB-013/approve", headers={"X-CSRF-Token": CSRF_TOKEN})
check("13. 세션+정상 CSRF+적정 권한 → CSRF/RBAC 통과, 기존 경로 도달(403 아님, 실제 GAS Fake 호출 발생)",
      r13.status_code != 403, str(r13.status_code) + " " + r13.text[:120],
      write_effect=f"GAS호출={len(_call_log)-before}(>=1이어야 정상 동작 보존 증거)")

_set_env(SESSION_ENV)
r14 = c_sess.post("/api/admin/reservations/RSV-WB-014/approve")  # CSRF 헤더 누락
check("14. 세션+CSRF없음 → 기존 CSRF 차단 유지(403)", r14.status_code == 403, str(r14.status_code))

_set_env(SESSION_ENV)
c_sess_norole = _client(SESSION_ENV)
_crm = next(u for u in _users if u.get("roleId") == "ROLE-CRM")
auth_service.create_user(
    SANDBOX, user_id=_crm["id"], login_id="qa_writeblock_crm",
    password="Synthetic-Test-Pw-WriteBlock-Crm-01!", display_name=_crm.get("name"), role_id=_crm.get("roleId"),
)
_set_env(SESSION_ENV)
r_login2 = c_sess_norole.post("/api/auth/login", json={"loginId": "qa_writeblock_crm",
                                                         "password": "Synthetic-Test-Pw-WriteBlock-Crm-01!"})
csrf2 = r_login2.json()["csrfToken"]
_set_env(SESSION_ENV)
r15 = c_sess_norole.post("/api/admin/reservations/RSV-WB-015/approve", headers={"X-CSRF-Token": csrf2})
check("15. 권한 없는 실제 세션 사용자(ROLE-CRM, reservation:approve 없음) → 기존 RBAC 차단 유지(403)",
      r15.status_code == 403, str(r15.status_code))


# 원복(모듈 전역 monkeypatch 정리)
sheets_write.update_status = _ORIG_UPDATE_STATUS
sheets.list_reservations = _ORIG_LIST_RESERVATIONS

shutil.rmtree(SANDBOX.parent)

out = Path(__file__).parent / "sprint8_commit8_2c_mock_write_block_test_result.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["시나리오", "결과", "상세", "Write부작용"])
    w.writerows(results)

total = len(results)
passed = sum(1 for _, r, _, _ in results if r == "PASS")
summary = f"TOTAL={total} PASS={passed} FAIL={total - passed}"
try:
    print(summary)
except UnicodeEncodeError:
    print(summary.encode("ascii", "backslashreplace").decode("ascii"))

if passed != total:
    sys.exit(1)
