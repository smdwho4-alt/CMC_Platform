# -*- coding: utf-8 -*-
"""
CSHSP Admin Authentication — SQLite 저장소 (Sprint8 Commit8-2)

관리자 인증 자격증명(로그인ID/비밀번호 Hash/잠금상태)과 서버 관리형 세션을
SQLite로 관리한다. 신원(표시이름/역할/계정활성상태)의 SSOT는 여전히 기존
`data/users.json`(Core Data Layer)이며, 이 저장소는 그 신원 레코드의 `id`를
외래키로 참조하는 "인증 전용" 보조 저장소다 — roles.json이 역할·권한 정의만
담당하고 사용자 계정 저장소가 아닌 것과 동일한 관계를, users.json과 이
auth 저장소 사이에도 유지한다(PM Commit8-2 승인사항 1).

DB 파일은 기존 데이터 디렉터리 규칙과 동일하게 매개변수화된 data_dir 하위
(`<data_dir>/auth.db`)에 둔다 — 기존 `data/`가 이미 .gitignore로 전체 제외되어
있어 별도 gitignore 작업이 필요 없고, 테스트는 항상 격리된 샌드박스 data_dir을
쓰므로(기존 관례) 운영 DB와 자동으로 분리된다.
"""
from __future__ import annotations

import datetime as _dt
import re
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT / "src" / "reservation"))

from json_store import KST, now_iso  # noqa: E402

SCHEMA_VERSION = 1

_DB_FILENAME = "auth.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS auth_users (
    id TEXT PRIMARY KEY,
    login_id TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    role_id TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    last_login_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT,
    security_stamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES auth_users(id),
    csrf_token TEXT NOT NULL,
    security_stamp_snapshot TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    absolute_expires_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0,
    revoked_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_active
    ON auth_sessions(user_id, revoked);

CREATE TABLE IF NOT EXISTS auth_audit_log (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    actor_user_id TEXT,
    target_user_id TEXT,
    request_id TEXT,
    route TEXT,
    result TEXT,
    reason_code TEXT,
    source_env TEXT
);
CREATE INDEX IF NOT EXISTS idx_auth_audit_event ON auth_audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_auth_audit_time ON auth_audit_log(occurred_at);
"""

_ID_SAFE_RE = re.compile(r"^[A-Za-z0-9_.\-:]{1,64}$")


def _db_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / _DB_FILENAME


def _validate_identifier(value: str, field_name: str) -> str:
    """SQLite는 Parameter Binding으로 값 자체는 안전하지만, 식별자성 값(ID류)의
    형식을 별도로 검증해 애플리케이션 레벨의 이상값(공백/제어문자 등) 유입을
    방지한다. SQL 문자열 자체에는 어떤 사용자 입력도 직접 문자열 결합하지 않는다
    (모든 쿼리는 '?' Placeholder만 사용, SQL Injection 방지)."""
    if not isinstance(value, str) or not _ID_SAFE_RE.match(value):
        raise ValueError(f"허용되지 않는 {field_name} 형식")
    return value


@contextmanager
def connect(data_dir: Path | str) -> Iterator[sqlite3.Connection]:
    """단일 커넥션 컨텍스트. WAL 모드 + FK 활성화. 트랜잭션은 호출부가 명시적으로
    commit/rollback한다(사용 후 자동 close, 예외 시 자동 rollback)."""
    path = _db_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        conn.close()


def init_schema(data_dir: Path | str) -> None:
    """스키마가 없으면 생성한다(idempotent — 여러 번 호출해도 안전).
    기존 DB 파일이 있으면 손상시키지 않고 CREATE TABLE IF NOT EXISTS만 수행한다."""
    with connect(data_dir) as conn:
        conn.executescript(_SCHEMA_SQL)
        cur = conn.execute("PRAGMA user_version")
        current = cur.fetchone()[0]
        if current == 0:
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")


def user_by_login_id(conn: sqlite3.Connection, login_id: str) -> dict[str, Any] | None:
    _validate_identifier(login_id, "login_id")
    row = conn.execute(
        "SELECT * FROM auth_users WHERE login_id = ?", (login_id,)
    ).fetchone()
    return dict(row) if row else None


def user_by_id(conn: sqlite3.Connection, user_id: str) -> dict[str, Any] | None:
    _validate_identifier(user_id, "user_id")
    row = conn.execute(
        "SELECT * FROM auth_users WHERE id = ?", (user_id,)
    ).fetchone()
    return dict(row) if row else None


def insert_user(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    login_id: str,
    password_hash: str,
    display_name: str | None,
    role_id: str | None,
    security_stamp: str,
    created_by: str | None = None,
) -> None:
    _validate_identifier(user_id, "user_id")
    _validate_identifier(login_id, "login_id")
    now = now_iso()
    conn.execute(
        """INSERT INTO auth_users
           (id, login_id, password_hash, display_name, role_id, status,
            failed_login_count, locked_until, must_change_password,
            last_login_at, created_at, updated_at, created_by, security_stamp)
           VALUES (?, ?, ?, ?, ?, 'ACTIVE', 0, NULL, 0, NULL, ?, ?, ?, ?)""",
        (user_id, login_id, password_hash, display_name, role_id,
         now, now, created_by, security_stamp),
    )


def record_login_success(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute(
        """UPDATE auth_users
           SET failed_login_count = 0, locked_until = NULL,
               last_login_at = ?, updated_at = ?
           WHERE id = ?""",
        (now_iso(), now_iso(), user_id),
    )


def record_login_failure(
    conn: sqlite3.Connection, user_id: str, *, max_attempts: int, lock_minutes: int
) -> int:
    """실패 횟수를 원자적으로 1 증가시키고, 임계치 도달 시 잠금시각을 설정한다.
    반환값은 갱신 후 실패 횟수. 이 함수는 호출부가 하나의 트랜잭션(BEGIN
    IMMEDIATE) 내에서 호출해 동시 요청에 의한 우회를 방지해야 한다."""
    row = conn.execute(
        "SELECT failed_login_count FROM auth_users WHERE id = ?", (user_id,)
    ).fetchone()
    if row is None:
        return 0
    new_count = row["failed_login_count"] + 1
    locked_until = None
    if new_count >= max_attempts:
        locked_until = (
            _dt.datetime.now(KST) + _dt.timedelta(minutes=lock_minutes)
        ).isoformat(timespec="seconds")
    conn.execute(
        """UPDATE auth_users
           SET failed_login_count = ?, locked_until = ?, updated_at = ?
           WHERE id = ?""",
        (new_count, locked_until, now_iso(), user_id),
    )
    return new_count


def bump_security_stamp(conn: sqlite3.Connection, user_id: str, new_stamp: str) -> None:
    """역할변경/계정변경/보안설정변경 시 호출 — 이 사용자의 모든 기존 세션이
    다음 검증 시점에 자동으로 무효화된다(security_stamp_snapshot 불일치)."""
    conn.execute(
        "UPDATE auth_users SET security_stamp = ?, updated_at = ? WHERE id = ?",
        (new_stamp, now_iso(), user_id),
    )


def set_account_status(conn: sqlite3.Connection, user_id: str, status: str) -> None:
    if status not in ("ACTIVE", "DISABLED"):
        raise ValueError("허용되지 않는 status 값")
    conn.execute(
        "UPDATE auth_users SET status = ?, updated_at = ? WHERE id = ?",
        (status, now_iso(), user_id),
    )


def insert_session(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    user_id: str,
    csrf_token: str,
    security_stamp_snapshot: str,
    absolute_expires_at: str,
) -> None:
    now = now_iso()
    conn.execute(
        """INSERT INTO auth_sessions
           (id, user_id, csrf_token, security_stamp_snapshot,
            created_at, last_seen_at, absolute_expires_at, revoked, revoked_reason)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL)""",
        (session_id, user_id, csrf_token, security_stamp_snapshot,
         now, now, absolute_expires_at),
    )


def session_by_id(conn: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
    _validate_identifier(session_id, "session_id")
    row = conn.execute(
        "SELECT * FROM auth_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    return dict(row) if row else None


def touch_session(conn: sqlite3.Connection, session_id: str) -> None:
    conn.execute(
        "UPDATE auth_sessions SET last_seen_at = ? WHERE id = ?",
        (now_iso(), session_id),
    )


def revoke_session(conn: sqlite3.Connection, session_id: str, reason: str) -> None:
    conn.execute(
        "UPDATE auth_sessions SET revoked = 1, revoked_reason = ? WHERE id = ?",
        (reason, session_id),
    )


def active_sessions_for_user(conn: sqlite3.Connection, user_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT * FROM auth_sessions
           WHERE user_id = ? AND revoked = 0
           ORDER BY created_at ASC""",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def revoke_all_sessions_for_user(conn: sqlite3.Connection, user_id: str, reason: str) -> None:
    conn.execute(
        "UPDATE auth_sessions SET revoked = 1, revoked_reason = ? WHERE user_id = ? AND revoked = 0",
        (reason, user_id),
    )


def append_auth_audit(
    conn: sqlite3.Connection,
    *,
    audit_id: str,
    event_type: str,
    actor_user_id: str | None,
    target_user_id: str | None = None,
    request_id: str | None = None,
    route: str | None = None,
    result: str = "SUCCESS",
    reason_code: str | None = None,
    source_env: str | None = None,
) -> None:
    conn.execute(
        """INSERT INTO auth_audit_log
           (id, event_type, occurred_at, actor_user_id, target_user_id,
            request_id, route, result, reason_code, source_env)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (audit_id, event_type, now_iso(), actor_user_id, target_user_id,
         request_id, route, result, reason_code, source_env),
    )
