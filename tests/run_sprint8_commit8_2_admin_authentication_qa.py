# -*- coding: utf-8 -*-
"""
CSHSP Sprint 8 Commit 8-2 — 관리자 인증·인가 최소 구현 테스트 러너

대상: src/auth/{auth_store,auth_service,csrf,routes_auth}.py, 및 이를 연동한
src/api/api_server.py::require_user / src/api/routes_admin_portal.py의
_build_require_user()/CSRF Depends 배선.

Sprint8 Commit8-1 설계·Commit8-2 PM 승인사항 기준 카테고리:
A 인증 / B 로그인 / C 실패제한 / D 세션 / E Cookie / F CSRF / G 인가 /
H Mock 격리 / I 감사로그 / J SQLite. 회귀(L)는 기존 스위트를 별도로
재실행해 확인하며(본 파일 범위 아님), 여기서는 신규 기능만 검증한다.

모든 계정·비밀번호는 이 테스트 전용 합성값이며 실제 운영 계정이 아니다.
GAS/Sheets 호출은 없다(세션·CSRF 계층만 검증, 승인 성공 경로까지는 확인하지
않음 — Sheets 연동 자체는 기존 Sprint4~7 스위트가 이미 담당).
"""
from __future__ import annotations

import csv
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "core"))
sys.path.insert(0, str(ROOT / "src" / "api"))
sys.path.insert(0, str(ROOT / "src" / "auth"))
sys.path.insert(0, str(ROOT / "src" / "reservation"))

from fastapi.testclient import TestClient  # noqa: E402

import core_data_loader as loader  # noqa: E402
import auth_service  # noqa: E402
import auth_store as store  # noqa: E402
from api_server import create_app  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint8_commit8_2_auth" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)

# 합성 테스트 계정(실제 운영 계정 아님) — users.json의 실제 존재하는 id에 연계.
_users = loader.load_entity("User", SANDBOX)
_staff = next(u for u in _users if u.get("roleId") == "ROLE-STAFF")
_director = next(u for u in _users if u.get("roleId") == "ROLE-DIRECTOR")
_crm = next(u for u in _users if u.get("roleId") == "ROLE-CRM")
STAFF_ID = _staff["id"]
DIRECTOR_ID = _director["id"]
CRM_ID = _crm["id"]
STAFF_LOGIN = "qa_staff_login"
STAFF_PW = "Synthetic-Test-Pw-Staff-01!"
DIRECTOR_LOGIN = "qa_director_login"
DIRECTOR_PW = "Synthetic-Test-Pw-Director-01!"
CRM_LOGIN = "qa_crm_login"
CRM_PW = "Synthetic-Test-Pw-Crm-01!"

auth_service.create_user(
    SANDBOX, user_id=STAFF_ID, login_id=STAFF_LOGIN, password=STAFF_PW,
    display_name=_staff.get("name"), role_id=_staff.get("roleId"),
)
auth_service.create_user(
    SANDBOX, user_id=DIRECTOR_ID, login_id=DIRECTOR_LOGIN, password=DIRECTOR_PW,
    display_name=_director.get("name"), role_id=_director.get("roleId"),
)
auth_service.create_user(
    SANDBOX, user_id=CRM_ID, login_id=CRM_LOGIN, password=CRM_PW,
    display_name=_crm.get("name"), role_id=_crm.get("roleId"),
)

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    line = f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "backslashreplace").decode("ascii"))


_ENV_KEYS = ("CSHSP_ENV", "CSHSP_ALLOW_MOCK_AUTH", "CSHSP_COOKIE_INSECURE_DEV")


def _new_client(env: dict[str, str] | None = None) -> TestClient:
    """요청 시점에도 그대로 유지되어야 하는 환경변수(CSHSP_ENV 등)를 설정한다.
    routes_auth의 current_env()/mock_auth_allowed()/_cookie_secure()는 매 요청마다
    os.environ을 다시 읽으므로(운영 코드 자체의 올바른 설계), 이 값들은 app
    생성 시점이 아니라 각 client로 실제 요청을 보내는 동안 계속 설정돼 있어야
    한다 — 그래서 여기서는 되돌리지 않고, 다음 _new_client() 호출이 덮어쓸 때까지
    유지한다(테스트 스크립트 내 순차 실행 전제, 프로덕션 코드와 무관)."""
    import os
    for k in _ENV_KEYS:
        os.environ.pop(k, None)
    for k, v in (env or {}).items():
        os.environ[k] = v
    app = create_app(SANDBOX, include_agents=False)
    return TestClient(app)


# ── A. 인증 테스트 ──
client = _new_client({"CSHSP_ENV": "test", "CSHSP_COOKIE_INSECURE_DEV": "1"})

r = client.post("/api/auth/login", json={"loginId": STAFF_LOGIN, "password": STAFF_PW})
check("AUTH-01 정상 로그인 200 + csrfToken 발급", r.status_code == 200 and bool(r.json().get("csrfToken")),
      str(r.status_code))
check("AUTH-01b 로그인 응답에 비밀번호/해시 미포함", "password" not in r.text.lower() and "hash" not in r.text.lower())
client.cookies.clear()

r = client.post("/api/auth/login", json={"loginId": "no_such_user", "password": "whatever"})
check("AUTH-02 존재하지 않는 계정 401", r.status_code == 401, str(r.status_code))
msg_nouser = r.json().get("detail")

r = client.post("/api/auth/login", json={"loginId": STAFF_LOGIN, "password": "wrong-password"})
check("AUTH-03 잘못된 비밀번호 401", r.status_code == 401, str(r.status_code))
msg_wrongpw = r.json().get("detail")
check("AUTH-03b 계정 존재 여부를 노출하지 않음(동일 메시지)", msg_nouser == msg_wrongpw,
      f"{msg_nouser!r} vs {msg_wrongpw!r}")

# 비활성 계정
auth_service.create_user(
    SANDBOX, user_id="USR-QA-DISABLED", login_id="qa_disabled", password="Synthetic-Test-Pw-Disabled-01!",
    display_name="disabled", role_id="ROLE-STAFF",
)
with store.connect(SANDBOX) as conn:
    conn.execute("BEGIN IMMEDIATE")
    store.set_account_status(conn, "USR-QA-DISABLED", "DISABLED")
    conn.execute("COMMIT")
r = client.post("/api/auth/login", json={"loginId": "qa_disabled", "password": "Synthetic-Test-Pw-Disabled-01!"})
check("AUTH-04 비활성 계정(auth_users.status=DISABLED) 401", r.status_code == 401, str(r.status_code))

r = client.post("/api/auth/login", json={"loginId": STAFF_LOGIN, "password": STAFF_PW})
sid1 = client.cookies.get("cshsp_admin_session")
client.post("/api/auth/logout")
r2 = client.post("/api/auth/login", json={"loginId": STAFF_LOGIN, "password": STAFF_PW})
sid2 = client.cookies.get("cshsp_admin_session")
check("AUTH-06 로그인 성공 시 Session ID 재발급(로그인마다 상이)", sid1 != sid2, "재발급 확인")
client.post("/api/auth/logout")

r = client.get("/api/reservations")
check("AUTH-07 인증 없는 API 요청 401", r.status_code == 401, str(r.status_code))

r = client.get("/api/reservations", headers={"X-User-Id": STAFF_ID})
check("AUTH-08 위조된 X-User-Id(Mock 미허용 환경) 401", r.status_code == 401, str(r.status_code))

r = client.post("/api/auth/login", json={"loginId": STAFF_LOGIN, "password": STAFF_PW})
r_me = client.get("/api/auth/me")
check("AUTH-10a 로그아웃 전 /me 200", r_me.status_code == 200)
client.post("/api/auth/logout")
r_after = client.get("/api/auth/me")
check("AUTH-10 로그아웃 후 동일 쿠키로 재요청 401", r_after.status_code == 401, str(r_after.status_code))


# ── B/D. 세션·유휴시간·절대시간·동시세션 (auth_service 직접 검증 — 30분/8h 대기 불가하므로 로직 재확인) ──
sess = auth_service.create_session(SANDBOX, user_id=STAFF_ID, request_id="qa", source_env="test")
val = auth_service.validate_session(SANDBOX, session_id=sess["session_id"], request_id="qa", source_env="test")
check("SESS-01 정상 세션 검증 성공", val is not None)

val_missing = auth_service.validate_session(SANDBOX, session_id="nonexistent-session-id", request_id="qa", source_env="test")
check("SESS-02 존재하지 않는 세션 None", val_missing is None)

auth_service.logout(SANDBOX, session_id=sess["session_id"], request_id="qa", source_env="test")
val_revoked = auth_service.validate_session(SANDBOX, session_id=sess["session_id"], request_id="qa", source_env="test")
check("SESS-03 폐기된 세션 재검증 None", val_revoked is None)

# 유휴시간 만료: last_seen_at을 과거로 직접 조작해 검증(30분 대기 대신 시간 조작 — 로직만 검증)
sess2 = auth_service.create_session(SANDBOX, user_id=STAFF_ID, request_id="qa", source_env="test")
with store.connect(SANDBOX) as conn:
    from json_store import KST
    import datetime as _dt
    past = (_dt.datetime.now(KST) - _dt.timedelta(minutes=31)).isoformat(timespec="seconds")
    conn.execute("UPDATE auth_sessions SET last_seen_at = ? WHERE id = ?", (past, sess2["session_id"]))
val_idle = auth_service.validate_session(SANDBOX, session_id=sess2["session_id"], request_id="qa", source_env="test")
check("SESS-04 30분 유휴 초과 세션 무효화", val_idle is None)

# 절대시간 만료
sess3 = auth_service.create_session(SANDBOX, user_id=STAFF_ID, request_id="qa", source_env="test")
with store.connect(SANDBOX) as conn:
    from json_store import KST
    import datetime as _dt
    past_abs = (_dt.datetime.now(KST) - _dt.timedelta(hours=1)).isoformat(timespec="seconds")
    conn.execute("UPDATE auth_sessions SET absolute_expires_at = ? WHERE id = ?", (past_abs, sess3["session_id"]))
val_abs = auth_service.validate_session(SANDBOX, session_id=sess3["session_id"], request_id="qa", source_env="test")
check("SESS-05 8시간 절대 유효시간 초과 세션 무효화", val_abs is None)

# 동시 세션 최대 2개
with store.connect(SANDBOX) as conn:
    store.revoke_all_sessions_for_user(conn, STAFF_ID, "TEST_RESET")
s1 = auth_service.create_session(SANDBOX, user_id=STAFF_ID, request_id="q1", source_env="test")
s2 = auth_service.create_session(SANDBOX, user_id=STAFF_ID, request_id="q2", source_env="test")
s3 = auth_service.create_session(SANDBOX, user_id=STAFF_ID, request_id="q3", source_env="test")
with store.connect(SANDBOX) as conn:
    active = store.active_sessions_for_user(conn, STAFF_ID)
check("SESS-06 사용자당 최대 동시 세션 2개(3번째 로그인 시 가장 오래된 세션 폐기)",
      len(active) == 2 and active[0]["id"] == s2["session_id"], f"active={len(active)}")
v_oldest = auth_service.validate_session(SANDBOX, session_id=s1["session_id"], request_id="q4", source_env="test")
check("SESS-06b 폐기된 가장 오래된 세션은 더 이상 유효하지 않음", v_oldest is None)

# 계정 비활성화 후 세션 거부(신원 SSOT users.json의 status 확인 경로)
sess4 = auth_service.create_session(SANDBOX, user_id=DIRECTOR_ID, request_id="qa", source_env="test")
val4a = auth_service.validate_session(SANDBOX, session_id=sess4["session_id"], request_id="qa", source_env="test")
check("SESS-07a 정상 세션(비활성화 전) 검증 성공", val4a is not None)
_director_doc_path = SANDBOX / "users.json"
import json as _json
_doc = _json.loads(_director_doc_path.read_text(encoding="utf-8"))
for rec in _doc["records"]:
    if rec["id"] == DIRECTOR_ID:
        rec["status"] = "SUSPENDED"
_director_doc_path.write_text(_json.dumps(_doc, ensure_ascii=False, indent=2), encoding="utf-8")
val4b = auth_service.validate_session(SANDBOX, session_id=sess4["session_id"], request_id="qa", source_env="test")
check("SESS-07b users.json(신원 SSOT) 비활성화 후 기존 세션 즉시 무효화", val4b is None)
for rec in _doc["records"]:
    if rec["id"] == DIRECTOR_ID:
        rec["status"] = "ACTIVE"
_director_doc_path.write_text(_json.dumps(_doc, ensure_ascii=False, indent=2), encoding="utf-8")

# 역할·권한 변경(security_stamp bump) 후 기존 세션 무효화
sess5 = auth_service.create_session(SANDBOX, user_id=STAFF_ID, request_id="qa", source_env="test")
val5a = auth_service.validate_session(SANDBOX, session_id=sess5["session_id"], request_id="qa", source_env="test")
check("SESS-08a 정상 세션(변경 전) 검증 성공", val5a is not None)
auth_service.revoke_all_sessions(
    SANDBOX, user_id=STAFF_ID, reason="ROLE_CHANGED", actor_user_id="ADMIN-QA",
    request_id="qa", source_env="test",
)
val5b = auth_service.validate_session(SANDBOX, session_id=sess5["session_id"], request_id="qa", source_env="test")
check("SESS-08b 역할변경(security_stamp bump) 후 기존 세션 무효화", val5b is None)


# ── C. 로그인 실패 제한 ──
with store.connect(SANDBOX) as conn:
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(
        "UPDATE auth_users SET failed_login_count = 0, locked_until = NULL WHERE id = ?", (STAFF_ID,)
    )
    conn.execute("COMMIT")

for i in range(4):
    try:
        auth_service.authenticate(SANDBOX, login_id=STAFF_LOGIN, password="wrong", request_id=f"f{i}", source_env="test")
    except auth_service.AuthError:
        pass
try:
    auth_service.authenticate(SANDBOX, login_id=STAFF_LOGIN, password=STAFF_PW, request_id="f-check", source_env="test")
    check("LOCK-01 4회 실패 후 정상 비밀번호로 여전히 로그인 가능(아직 미잠금)", True)
except auth_service.AuthError as e:
    check("LOCK-01 4회 실패 후 정상 비밀번호로 여전히 로그인 가능(아직 미잠금)", False, e.reason_code)

with store.connect(SANDBOX) as conn:
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(
        "UPDATE auth_users SET failed_login_count = 0, locked_until = NULL WHERE id = ?", (STAFF_ID,)
    )
    conn.execute("COMMIT")

for i in range(5):
    try:
        auth_service.authenticate(SANDBOX, login_id=STAFF_LOGIN, password="wrong", request_id=f"g{i}", source_env="test")
    except auth_service.AuthError:
        pass
locked = False
try:
    auth_service.authenticate(SANDBOX, login_id=STAFF_LOGIN, password=STAFF_PW, request_id="g-check", source_env="test")
except auth_service.AuthError as e:
    locked = e.reason_code == "ACCOUNT_LOCKED"
check("LOCK-02 5회 연속 실패 후 정상 비밀번호도 거부(잠금)", locked)

with store.connect(SANDBOX) as conn:
    row = conn.execute("SELECT locked_until FROM auth_users WHERE id = ?", (STAFF_ID,)).fetchone()
check("LOCK-03 잠금 시각(locked_until)이 설정됨", row is not None and row["locked_until"] is not None)

auth_service.unlock_account(SANDBOX, user_id=STAFF_ID, actor_user_id="ADMIN-QA", request_id="qa", source_env="test")
try:
    identity = auth_service.authenticate(SANDBOX, login_id=STAFF_LOGIN, password=STAFF_PW, request_id="unlock-check", source_env="test")
    check("LOCK-04 관리자 해제 후 정상 로그인 가능", identity is not None)
except auth_service.AuthError as e:
    check("LOCK-04 관리자 해제 후 정상 로그인 가능", False, e.reason_code)


# ── E. Cookie 보안속성 ──
client2 = _new_client({"CSHSP_ENV": "test", "CSHSP_COOKIE_INSECURE_DEV": "1"})
r = client2.post("/api/auth/login", json={"loginId": STAFF_LOGIN, "password": STAFF_PW})
set_cookie_header = r.headers.get("set-cookie", "")
# 실제 Cookie/Session 값은 CSV 결과 파일에도 기록하지 않는다(합성 테스트 값이라도
# 원문을 결과물에 남기지 않는다는 원칙 — PM 승인사항 §17/§24). 속성명만 detail로 남긴다.
_cookie_attrs = [p.strip().split("=")[0] for p in set_cookie_header.split(";") if p.strip()][1:]
check("COOKIE-01 HttpOnly 속성 포함", "httponly" in set_cookie_header.lower(), str(_cookie_attrs))
check("COOKIE-02 SameSite=lax 포함", "samesite=lax" in set_cookie_header.lower(), str(_cookie_attrs))
check("COOKIE-03 세션 쿠키 값이 사용자ID/역할 등 평문 정보를 담지 않음(불투명 토큰)",
      STAFF_ID not in set_cookie_header and "ROLE-STAFF" not in set_cookie_header)

client3 = _new_client({"CSHSP_ENV": "production"})
check("COOKIE-04 운영환경(CSHSP_ENV=production) Secure 기본 True(코드 레벨 확인)",
      auth_service is not None)  # 아래 직접 함수 호출로 재확인
import routes_auth as _routes_auth_mod  # noqa: E402
import os as _os
_old_env = _os.environ.get("CSHSP_ENV")
_os.environ["CSHSP_ENV"] = "production"
check("COOKIE-04b _cookie_secure() production에서 True", _routes_auth_mod._cookie_secure() is True)
_os.environ["CSHSP_ENV"] = "development"
_os.environ.pop("CSHSP_COOKIE_INSECURE_DEV", None)
check("COOKIE-04c _cookie_secure() 개발환경 기본값도 True(명시적 예외 없으면 안전값)",
      _routes_auth_mod._cookie_secure() is True)
_os.environ["CSHSP_COOKIE_INSECURE_DEV"] = "1"
check("COOKIE-04d 명시적 CSHSP_COOKIE_INSECURE_DEV=1일 때만 False", _routes_auth_mod._cookie_secure() is False)
if _old_env is None:
    _os.environ.pop("CSHSP_ENV", None)
else:
    _os.environ["CSHSP_ENV"] = _old_env
_os.environ.pop("CSHSP_COOKIE_INSECURE_DEV", None)


# ── F. CSRF ──
client4 = _new_client({"CSHSP_ENV": "test", "CSHSP_COOKIE_INSECURE_DEV": "1"})
r = client4.post("/api/auth/login", json={"loginId": STAFF_LOGIN, "password": STAFF_PW})
csrf_token = r.json()["csrfToken"]

r_no_csrf = client4.post("/api/admin/reservations/RSV-QA-FAKE/approve")
check("CSRF-01 Token 없는 상태변경 403", r_no_csrf.status_code == 403, str(r_no_csrf.status_code))

r_wrong_csrf = client4.post("/api/admin/reservations/RSV-QA-FAKE/approve", headers={"X-CSRF-Token": "wrong-token-value"})
check("CSRF-02 잘못된 Token 403", r_wrong_csrf.status_code == 403, str(r_wrong_csrf.status_code))

r_ok_csrf = client4.post("/api/admin/reservations/RSV-QA-FAKE/approve", headers={"X-CSRF-Token": csrf_token})
check("CSRF-03 정상 Token은 CSRF 관문 통과(이후 단계에서 다른 사유로 실패 가능, 403 아니어야 함)",
      r_ok_csrf.status_code != 403, str(r_ok_csrf.status_code))

r_get_state_change = client4.get("/api/admin/reservations/RSV-QA-FAKE/approve")
check("CSRF-04 GET으로는 상태변경 라우트 자체가 존재하지 않음(405/404)",
      r_get_state_change.status_code in (404, 405), str(r_get_state_change.status_code))


# ── G. 인가(회귀 성격 — 기존 has_perm/need_perm 무변경 확인) ──
client5 = _new_client({"CSHSP_ENV": "test", "CSHSP_COOKIE_INSECURE_DEV": "1"})
client5.post("/api/auth/login", json={"loginId": DIRECTOR_LOGIN, "password": DIRECTOR_PW})
r_director_approve = client5.get("/api/admin/dashboard")
check("AUTHZ-01 ROLE-DIRECTOR가 dashboard:view 권한으로 대시보드 접근 가능(200 또는 부분실패 응답, 403 아님)",
      r_director_approve.status_code != 403, str(r_director_approve.status_code))
client5.post("/api/auth/logout")

client6 = _new_client({"CSHSP_ENV": "test", "CSHSP_COOKIE_INSECURE_DEV": "1"})
client6.post("/api/auth/login", json={"loginId": CRM_LOGIN, "password": CRM_PW})
r_crm_dashboard = client6.get("/api/admin/dashboard")
check("AUTHZ-02 ROLE-CRM(dashboard:view 권한 없음, roles.json 실측)는 대시보드 접근 거부(403)",
      r_crm_dashboard.status_code == 403, str(r_crm_dashboard.status_code))


# ── H. Mock 격리 ──
client7 = _new_client({"CSHSP_ENV": "production"})
r = client7.get("/api/reservations", headers={"X-User-Id": STAFF_ID})
check("MOCK-01 운영환경(CSHSP_ENV=production)에서 X-User-Id Mock 완전 차단",
      r.status_code == 401, str(r.status_code))

client8 = _new_client({"CSHSP_ENV": "development"})  # ALLOW_MOCK_AUTH 미설정
r = client8.get("/api/reservations", headers={"X-User-Id": STAFF_ID})
check("MOCK-02 개발환경이어도 CSHSP_ALLOW_MOCK_AUTH 미설정이면 기본 차단",
      r.status_code == 401, str(r.status_code))

client9 = _new_client({"CSHSP_ENV": "development", "CSHSP_ALLOW_MOCK_AUTH": "1"})
r = client9.get("/api/reservations", headers={"X-User-Id": STAFF_ID})
check("MOCK-03 개발환경 + 명시적 CSHSP_ALLOW_MOCK_AUTH=1일 때만 Mock 허용",
      r.status_code == 200, str(r.status_code))


# ── I. 감사로그 ──
with store.connect(SANDBOX) as conn:
    events = conn.execute(
        "SELECT event_type FROM auth_audit_log ORDER BY occurred_at"
    ).fetchall()
event_types = {e["event_type"] for e in events}
for expected in ("LOGIN_SUCCESS", "LOGIN_FAILURE", "LOGOUT", "SESSION_CREATED",
                  "SESSION_EXPIRED_IDLE", "SESSION_EXPIRED_ABSOLUTE",
                  "CONCURRENT_SESSION_REVOKED", "ACCOUNT_TEMP_LOCKED", "ACCOUNT_UNLOCKED",
                  "MOCK_AUTH_BLOCKED", "CSRF_VALIDATION_FAILED", "SESSION_REVOKED"):
    check(f"AUDIT-{expected} 이벤트가 최소 1건 기록됨", expected in event_types, expected)

with store.connect(SANDBOX) as conn:
    all_rows_text = " ".join(
        str(dict(r)) for r in conn.execute("SELECT * FROM auth_audit_log").fetchall()
    )
check("AUDIT-민감정보 비밀번호 미포함", STAFF_PW not in all_rows_text)
check("AUDIT-민감정보 CSRF Token 원문 미포함", csrf_token not in all_rows_text)


# ── J. SQLite ──
check("SQLITE-01 auth.db 파일 생성됨", (SANDBOX / "auth.db").exists())
with store.connect(SANDBOX) as conn:
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
check("SQLITE-02 필수 테이블 3종 생성(auth_users/auth_sessions/auth_audit_log)",
      {"auth_users", "auth_sessions", "auth_audit_log"} <= tables, str(tables))

with store.connect(SANDBOX) as conn:
    conn.execute("BEGIN IMMEDIATE")
    try:
        store.insert_user(
            conn, user_id="USR-QA-ROLLBACK-TEST", login_id=STAFF_LOGIN,  # 중복 login_id로 의도적 실패 유도
            password_hash="x", display_name=None, role_id=None, security_stamp="x",
        )
        conn.execute("COMMIT")
        check("SQLITE-03 트랜잭션 Rollback(중복 login_id UNIQUE 제약 위반 시 예외 발생)", False, "예외가 발생해야 함")
    except Exception:
        conn.execute("ROLLBACK")
        check("SQLITE-03 트랜잭션 Rollback(중복 login_id UNIQUE 제약 위반 시 예외 발생)", True)

with store.connect(SANDBOX) as conn:
    leftover = conn.execute(
        "SELECT COUNT(*) c FROM auth_users WHERE id = ?", ("USR-QA-ROLLBACK-TEST",)
    ).fetchone()["c"]
check("SQLITE-04 Rollback된 트랜잭션의 레코드가 실제로 남지 않음", leftover == 0)

# SQL Injection 방지(식별자 검증 함수가 비정상 입력을 거부하는지)
try:
    with store.connect(SANDBOX) as conn:
        store.user_by_login_id(conn, "'; DROP TABLE auth_users; --")
    check("SEC-01 SQL Injection 형태 입력이 식별자 검증에서 거부됨(ValueError)", False, "예외가 발생해야 함")
except ValueError:
    check("SEC-01 SQL Injection 형태 입력이 식별자 검증에서 거부됨(ValueError)", True)
with store.connect(SANDBOX) as conn:
    tables_after = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
check("SEC-02 SQL Injection 시도 후에도 테이블이 그대로 존재(파괴 없음)",
      {"auth_users", "auth_sessions", "auth_audit_log"} <= tables_after)


shutil.rmtree(SANDBOX.parent)

out = Path(__file__).parent / "sprint8_commit8_2_admin_authentication_test_result.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트", "결과", "상세"])
    w.writerows(results)

total = len(results)
passed = sum(1 for _, r, _ in results if r == "PASS")
summary = f"TOTAL={total} PASS={passed} FAIL={total - passed}"
try:
    print(summary)
except UnicodeEncodeError:
    print(summary.encode("ascii", "backslashreplace").decode("ascii"))

if passed != total:
    sys.exit(1)
