# -*- coding: utf-8 -*-
"""
CSHSP Admin Authentication — 인증 비즈니스 로직 (Sprint8 Commit8-2)

비밀번호 Hash(Argon2id) 검증, 로그인/로그아웃, 세션 생성·검증·만료, 로그인
실패 제한·계정 잠금을 담당한다. SQL 실행 자체는 auth_store.py에 위임하고,
이 모듈은 정책값(유휴시간/절대시간/최대동시세션/실패임계치/잠금시간)과
트랜잭션 경계를 관리한다.

정책값(Sprint8 Commit8-2 PM 승인사항 5·7·16):
- 유휴시간 30분, 절대 유효시간 8시간, 사용자당 최대 동시 세션 2개
- 로그인 5회 연속 실패 시 15분 임시 잠금
"""
from __future__ import annotations

import datetime as _dt
import secrets
import sys
import uuid
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT / "src" / "reservation"))
sys.path.insert(0, str(_ROOT / "src" / "core"))
sys.path.insert(0, str(_HERE))

from json_store import KST, now_iso  # noqa: E402
import core_data_loader as loader  # noqa: E402

import auth_store as store  # noqa: E402

from argon2 import PasswordHasher  # noqa: E402
from argon2.exceptions import VerifyMismatchError, InvalidHash  # noqa: E402

IDLE_TIMEOUT_MINUTES = 30
ABSOLUTE_TIMEOUT_HOURS = 8
MAX_CONCURRENT_SESSIONS = 2
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

_hasher = PasswordHasher()  # Argon2id(argon2-cffi 기본값), Constant-time 검증은 라이브러리 위임


class AuthError(Exception):
    """인증 실패 — 사용자에게는 일반화된 메시지만, 내부적으로만 reason_code 보존."""

    def __init__(self, reason_code: str, message: str = "인증에 실패했습니다"):
        super().__init__(message)
        self.reason_code = reason_code


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(password_hash: str, plain: str) -> bool:
    try:
        _hasher.verify(password_hash, plain)
        return True
    except (VerifyMismatchError, InvalidHash):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHash:
        return True


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _new_security_stamp() -> str:
    return secrets.token_hex(16)


def create_user(
    data_dir: Path | str,
    *,
    user_id: str,
    login_id: str,
    password: str,
    display_name: str | None,
    role_id: str | None,
    created_by: str | None = None,
) -> None:
    """신규 인증 계정 생성. user_id는 반드시 기존 users.json(Core Data Layer)의
    실제 사용자 id와 일치해야 한다(신원은 users.json이 SSOT — 이 저장소는 자격증명만
    관리). 이 함수는 자동으로 호출되지 않으며, 안전한 Bootstrap 경로
    (bootstrap_admin.py CLI 또는 테스트 Fixture)에서만 호출된다."""
    store.init_schema(data_dir)
    with store.connect(data_dir) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            store.insert_user(
                conn,
                user_id=user_id,
                login_id=login_id,
                password_hash=hash_password(password),
                display_name=display_name,
                role_id=role_id,
                security_stamp=_new_security_stamp(),
                created_by=created_by,
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def _is_locked(auth_user: dict[str, Any]) -> bool:
    locked_until = auth_user.get("locked_until")
    if not locked_until:
        return False
    try:
        until = _dt.datetime.fromisoformat(locked_until)
    except ValueError:
        return False
    return _dt.datetime.now(KST) < until


def _identity_record(data_dir: Path | str, user_id: str) -> dict[str, Any] | None:
    """신원 SSOT(users.json)에서 표시정보·역할·활성상태를 조회한다."""
    return next(
        (u for u in loader.load_entity("User", data_dir) if u.get("id") == user_id),
        None,
    )


def authenticate(
    data_dir: Path | str, *, login_id: str, password: str, request_id: str | None, source_env: str
) -> dict[str, Any]:
    """로그인 시도. 성공 시 신원 레코드(dict)를 반환, 실패 시 AuthError를 발생시킨다.
    존재하지 않는 사용자/잘못된 비밀번호/비활성 계정/잠긴 계정을 모두 사용자에게는
    동일한 일반화된 메시지로 취급하되(사용자 열거 방지), 감사로그에는 내부적으로
    구분된 reason_code를 남긴다."""
    store.init_schema(data_dir)
    with store.connect(data_dir) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            auth_user = store.user_by_login_id(conn, login_id)
            if auth_user is None:
                store.append_auth_audit(
                    conn, audit_id=_new_id("AUD-AUTH"), event_type="LOGIN_FAILURE",
                    actor_user_id=None, request_id=request_id, route="/api/auth/login",
                    result="FAILURE", reason_code="USER_NOT_FOUND", source_env=source_env,
                )
                conn.execute("COMMIT")
                raise AuthError("USER_NOT_FOUND")

            user_id = auth_user["id"]

            if auth_user["status"] != "ACTIVE":
                store.append_auth_audit(
                    conn, audit_id=_new_id("AUD-AUTH"), event_type="LOGIN_FAILURE",
                    actor_user_id=user_id, request_id=request_id, route="/api/auth/login",
                    result="FAILURE", reason_code="ACCOUNT_DISABLED", source_env=source_env,
                )
                conn.execute("COMMIT")
                raise AuthError("ACCOUNT_DISABLED")

            if _is_locked(auth_user):
                store.append_auth_audit(
                    conn, audit_id=_new_id("AUD-AUTH"), event_type="LOGIN_FAILURE",
                    actor_user_id=user_id, request_id=request_id, route="/api/auth/login",
                    result="FAILURE", reason_code="ACCOUNT_LOCKED", source_env=source_env,
                )
                conn.execute("COMMIT")
                raise AuthError("ACCOUNT_LOCKED")

            if not verify_password(auth_user["password_hash"], password):
                new_count = store.record_login_failure(
                    conn, user_id, max_attempts=MAX_LOGIN_ATTEMPTS, lock_minutes=LOCKOUT_MINUTES
                )
                event = (
                    "ACCOUNT_TEMP_LOCKED" if new_count >= MAX_LOGIN_ATTEMPTS else "LOGIN_FAILURE"
                )
                store.append_auth_audit(
                    conn, audit_id=_new_id("AUD-AUTH"), event_type=event,
                    actor_user_id=user_id, request_id=request_id, route="/api/auth/login",
                    result="FAILURE", reason_code="BAD_PASSWORD", source_env=source_env,
                )
                conn.execute("COMMIT")
                raise AuthError("BAD_PASSWORD")

            # 신원 SSOT(users.json) 상태도 함께 확인(이중 방어 — §22 계정 비활성화 통제)
            identity = _identity_record(data_dir, user_id)
            if identity is None or identity.get("status") != "ACTIVE":
                store.append_auth_audit(
                    conn, audit_id=_new_id("AUD-AUTH"), event_type="LOGIN_FAILURE",
                    actor_user_id=user_id, request_id=request_id, route="/api/auth/login",
                    result="FAILURE", reason_code="IDENTITY_INACTIVE", source_env=source_env,
                )
                conn.execute("COMMIT")
                raise AuthError("ACCOUNT_DISABLED")

            store.record_login_success(conn, user_id)
            store.append_auth_audit(
                conn, audit_id=_new_id("AUD-AUTH"), event_type="LOGIN_SUCCESS",
                actor_user_id=user_id, request_id=request_id, route="/api/auth/login",
                result="SUCCESS", reason_code=None, source_env=source_env,
            )
            conn.execute("COMMIT")
            return identity
        except AuthError:
            raise
        except Exception:
            conn.execute("ROLLBACK")
            raise


def create_session(
    data_dir: Path | str, *, user_id: str, request_id: str | None, source_env: str
) -> dict[str, Any]:
    """로그인 성공 후 신규 세션을 발급한다(항상 신규 ID — Session Fixation 방지).
    사용자당 최대 동시 세션 수를 초과하면 가장 오래된 세션을 폐기한다."""
    store.init_schema(data_dir)
    with store.connect(data_dir) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            auth_user = store.user_by_id(conn, user_id)
            if auth_user is None:
                conn.execute("ROLLBACK")
                raise AuthError("USER_NOT_FOUND")

            active = store.active_sessions_for_user(conn, user_id)
            if len(active) >= MAX_CONCURRENT_SESSIONS:
                oldest = active[0]
                store.revoke_session(conn, oldest["id"], "CONCURRENT_SESSION_LIMIT")
                store.append_auth_audit(
                    conn, audit_id=_new_id("AUD-AUTH"), event_type="CONCURRENT_SESSION_REVOKED",
                    actor_user_id=user_id, target_user_id=user_id, request_id=request_id,
                    route="/api/auth/login", result="SUCCESS",
                    reason_code="MAX_CONCURRENT_SESSIONS", source_env=source_env,
                )

            session_id = secrets.token_urlsafe(32)
            csrf_token = secrets.token_urlsafe(32)
            absolute_expires_at = (
                _dt.datetime.now(KST) + _dt.timedelta(hours=ABSOLUTE_TIMEOUT_HOURS)
            ).isoformat(timespec="seconds")
            store.insert_session(
                conn,
                session_id=session_id,
                user_id=user_id,
                csrf_token=csrf_token,
                security_stamp_snapshot=auth_user["security_stamp"],
                absolute_expires_at=absolute_expires_at,
            )
            store.append_auth_audit(
                conn, audit_id=_new_id("AUD-AUTH"), event_type="SESSION_CREATED",
                actor_user_id=user_id, request_id=request_id, route="/api/auth/login",
                result="SUCCESS", reason_code=None, source_env=source_env,
            )
            conn.execute("COMMIT")
            return {"session_id": session_id, "csrf_token": csrf_token}
        except AuthError:
            raise
        except Exception:
            conn.execute("ROLLBACK")
            raise


def validate_session(
    data_dir: Path | str, *, session_id: str, request_id: str | None, source_env: str
) -> dict[str, Any] | None:
    """세션 검증. 유효하면 (신원 레코드, csrf_token) 정보를 담은 dict를 반환,
    무효하면 None(호출부가 401 처리). 유휴시간을 갱신한다(부수효과)."""
    if not session_id:
        return None
    store.init_schema(data_dir)
    with store.connect(data_dir) as conn:
        session = store.session_by_id(conn, session_id)
        if session is None:
            return None
        if session["revoked"]:
            return None

        now = _dt.datetime.now(KST)
        try:
            absolute_expires_at = _dt.datetime.fromisoformat(session["absolute_expires_at"])
            last_seen_at = _dt.datetime.fromisoformat(session["last_seen_at"])
        except ValueError:
            return None

        if now >= absolute_expires_at:
            store.revoke_session(conn, session_id, "ABSOLUTE_TIMEOUT")
            store.append_auth_audit(
                conn, audit_id=_new_id("AUD-AUTH"), event_type="SESSION_EXPIRED_ABSOLUTE",
                actor_user_id=session["user_id"], request_id=request_id, result="FAILURE",
                reason_code="ABSOLUTE_TIMEOUT", source_env=source_env,
            )
            return None

        if now - last_seen_at > _dt.timedelta(minutes=IDLE_TIMEOUT_MINUTES):
            store.revoke_session(conn, session_id, "IDLE_TIMEOUT")
            store.append_auth_audit(
                conn, audit_id=_new_id("AUD-AUTH"), event_type="SESSION_EXPIRED_IDLE",
                actor_user_id=session["user_id"], request_id=request_id, result="FAILURE",
                reason_code="IDLE_TIMEOUT", source_env=source_env,
            )
            return None

        auth_user = store.user_by_id(conn, session["user_id"])
        if auth_user is None or auth_user["status"] != "ACTIVE":
            return None
        if auth_user["security_stamp"] != session["security_stamp_snapshot"]:
            # 역할변경/계정변경 이후 재검증 필요 — 세션을 폐기하고 재로그인 요구
            store.revoke_session(conn, session_id, "SECURITY_STAMP_MISMATCH")
            return None

        identity = _identity_record(data_dir, session["user_id"])
        if identity is None or identity.get("status") != "ACTIVE":
            return None

        store.touch_session(conn, session_id)
        return {
            "identity": identity,
            "session_id": session_id,
            "csrf_token": session["csrf_token"],
        }


def logout(
    data_dir: Path | str, *, session_id: str, request_id: str | None, source_env: str
) -> None:
    store.init_schema(data_dir)
    with store.connect(data_dir) as conn:
        session = store.session_by_id(conn, session_id)
        if session is None:
            return
        store.revoke_session(conn, session_id, "LOGOUT")
        store.append_auth_audit(
            conn, audit_id=_new_id("AUD-AUTH"), event_type="LOGOUT",
            actor_user_id=session["user_id"], request_id=request_id, result="SUCCESS",
            reason_code=None, source_env=source_env,
        )


def revoke_all_sessions(
    data_dir: Path | str, *, user_id: str, reason: str, actor_user_id: str | None,
    request_id: str | None, source_env: str
) -> None:
    """관리자 해제 API/역할변경/계정비활성화 시 호출 — 대상 사용자의 모든
    세션을 강제 폐기한다."""
    store.init_schema(data_dir)
    with store.connect(data_dir) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            store.revoke_all_sessions_for_user(conn, user_id, reason)
            store.bump_security_stamp(conn, user_id, _new_security_stamp())
            store.append_auth_audit(
                conn, audit_id=_new_id("AUD-AUTH"), event_type="SESSION_REVOKED",
                actor_user_id=actor_user_id, target_user_id=user_id, request_id=request_id,
                result="SUCCESS", reason_code=reason, source_env=source_env,
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def unlock_account(
    data_dir: Path | str, *, user_id: str, actor_user_id: str | None,
    request_id: str | None, source_env: str
) -> None:
    """관리자에 의한 계정 잠금 수동 해제(§15 관리 CLI/API 대상)."""
    store.init_schema(data_dir)
    with store.connect(data_dir) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "UPDATE auth_users SET failed_login_count = 0, locked_until = NULL, "
                "updated_at = ? WHERE id = ?",
                (now_iso(), user_id),
            )
            store.append_auth_audit(
                conn, audit_id=_new_id("AUD-AUTH"), event_type="ACCOUNT_UNLOCKED",
                actor_user_id=actor_user_id, target_user_id=user_id, request_id=request_id,
                result="SUCCESS", reason_code=None, source_env=source_env,
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
