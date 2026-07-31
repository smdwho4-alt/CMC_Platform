# -*- coding: utf-8 -*-
"""
CSHSP Admin Authentication — 로그인/로그아웃/세션 인증 Router (Sprint8 Commit8-2)

목표 흐름(Sprint8 Commit8-1 설계 §15~19 그대로 구현):
관리자 브라우저 → POST /api/auth/login → SQLite 세션 생성 → HttpOnly Cookie 발급
→ 이후 요청은 Cookie로 세션 검증 → roles.json 기반 인가(has_perm 재사용).

이 모듈은 다음을 제공한다.
- create_auth_router(data_dir): /api/auth/login, /api/auth/logout, /api/auth/me
- build_require_session_user(data_dir): 세션 우선, Mock은 명시적 환경설정 시에만
  허용하는 인증 Depends — 기존 require_user를 대체하는 데 사용한다.
- build_require_csrf(require_user): 상태변경 API에 추가하는 CSRF 검증 Depends.

X-User-Id Mock 격리 정책(Sprint8 Commit8-1 §34, Commit8-2 §14 그대로 구현):
운영환경(CSHSP_ENV=production)에서는 Mock을 완전히 차단한다. 그 외 환경에서도
CSHSP_ALLOW_MOCK_AUTH=1이 명시적으로 설정된 경우에만 Mock을 허용한다(둘 다
만족해야 함 — 기본값은 비활성화). 인증 시스템 장애 시에도 이 게이트를 우회해
Mock으로 자동 전환하지 않는다(PM 승인사항 13).
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT / "src" / "core"))
sys.path.insert(0, str(_HERE))

from fastapi import APIRouter, Depends, HTTPException, Request, Response  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import core_data_loader as loader  # noqa: E402

import auth_service  # noqa: E402
import auth_store as store  # noqa: E402
from csrf import CSRF_HEADER_NAME, csrf_token_matches  # noqa: E402

SESSION_COOKIE_NAME = "cshsp_admin_session"


def current_env() -> str:
    return os.environ.get("CSHSP_ENV", "development").strip().lower()


def mock_auth_allowed() -> bool:
    """Mock 인증 허용 여부 — 운영환경이 아니고, 명시적 허용 플래그가 설정된
    경우에만 True. 두 조건 중 하나라도 확인 불가/미설정이면 False(Fail-Closed,
    Sprint8 Commit8-1 §34 '확인 안 되면 안전한 쪽' 원칙)."""
    if current_env() == "production":
        return False
    allow = os.environ.get("CSHSP_ALLOW_MOCK_AUTH", "").strip().lower()
    return allow in ("1", "true", "yes")


def _cookie_secure() -> bool:
    """운영/Staging은 항상 Secure. 로컬 개발 HTTP 환경만 명시적 예외를 둔다
    (기본값은 안전한 값 — PM 승인사항 §11)."""
    if current_env() in ("production", "staging"):
        return True
    return os.environ.get("CSHSP_COOKIE_INSECURE_DEV", "").strip().lower() not in (
        "1", "true", "yes"
    )


def _log_mock_blocked(data_dir: Path | str, *, x_user_id: str | None, request_id: str | None, route: str) -> None:
    store.init_schema(data_dir)
    with store.connect(data_dir) as conn:
        store.append_auth_audit(
            conn, audit_id=f"AUD-AUTH-{uuid.uuid4().hex}", event_type="MOCK_AUTH_BLOCKED",
            actor_user_id=x_user_id, request_id=request_id, route=route,
            result="FAILURE", reason_code="MOCK_AUTH_NOT_ALLOWED", source_env=current_env(),
        )


def build_require_session_user(data_dir: Path | str):
    """require_user 대체용 Depends. 세션 Cookie를 우선 검증하고, 실패 시에만
    (그리고 mock_auth_allowed()일 때만) 기존 X-User-Id Mock으로 대체 동작한다."""

    def require_session_user(request: Request) -> dict[str, Any]:
        request_id = request.headers.get("X-Request-Id")
        session_id = request.cookies.get(SESSION_COOKIE_NAME)

        if session_id:
            result = auth_service.validate_session(
                data_dir, session_id=session_id, request_id=request_id, source_env=current_env()
            )
            if result is not None:
                request.state.csrf_token = result["csrf_token"]
                request.state.session_id = result["session_id"]
                request.state.auth_method = "session"
                return result["identity"]

        x_user_id = request.headers.get("X-User-Id")
        if x_user_id:
            if not mock_auth_allowed():
                _log_mock_blocked(
                    data_dir, x_user_id=x_user_id, request_id=request_id, route=str(request.url.path)
                )
                raise HTTPException(401, "인증이 필요합니다")
            user = next(
                (u for u in loader.load_entity("User", data_dir) if u.get("id") == x_user_id), None
            )
            if not user or user.get("status") != "ACTIVE":
                raise HTTPException(401, f"유효하지 않은 사용자: {x_user_id}")
            request.state.csrf_token = None
            request.state.session_id = None
            # Mock 경로임을 서버가 스스로 판정해 기록한다(클라이언트가 보낸 어떤 값도
            # 신뢰하지 않음 — X-User-Id/roleId 등은 신원 조회에만 쓰이고, "이 요청이
            # Mock 경로로 인증됐다"는 사실 자체는 이 분기에 실제로 도달했다는 것으로만
            # 판정한다). require_write_block(Commit8-2c)가 이 값으로 상태변경을 차단한다.
            request.state.auth_method = "mock"
            return user

        raise HTTPException(401, "인증이 필요합니다")

    return require_session_user


def _audit_write_blocked(request: Request, user: dict[str, Any], event_type: str, reason_code: str) -> None:
    data_dir = getattr(request.app.state, "cshsp_data_dir", None)
    if not data_dir:
        return
    store.init_schema(data_dir)
    with store.connect(data_dir) as conn:
        store.append_auth_audit(
            conn, audit_id=f"AUD-AUTH-{uuid.uuid4().hex}",
            event_type=event_type, actor_user_id=user.get("id"),
            request_id=request.headers.get("X-Request-Id"),
            route=str(request.url.path), result="FAILURE",
            reason_code=reason_code, source_env=current_env(),
        )


def build_require_csrf(require_user):
    """상태변경 API 전용 — require_user와 동일한 함수 객체를 넘겨받아 FastAPI가
    한 요청 내에서 세션 검증을 한 번만 수행하도록 한다(Depends 캐시 재사용).

    두 가지를 함께 강제한다(Sprint8 Commit8-2c, PM 승인사항):
    1) Mock(X-User-Id) 인증 사용자는 CSRF Token 유무와 무관하게 상태변경
       API에서 완전히 차단된다 — Mock은 세션이 없어 원래 CSRF 공격 자체가
       성립하지 않지만, 개발·테스트 환경에서 실수로 Mock이 활성화된 채 실제
       Write 경로(Sheets/GAS)에 도달하는 것을 구조적으로 막기 위한 별도 통제다.
       이 판단은 request.state.auth_method(서버가 build_require_session_user에서
       직접 설정, 클라이언트가 보낸 어떤 헤더·값도 신뢰하지 않음)만 근거로 한다.
    2) 세션(Cookie) 인증 사용자는 기존과 동일하게 CSRF Token을 검증한다.
    """

    def require_csrf(request: Request, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
        auth_method = getattr(request.state, "auth_method", None)

        if auth_method == "mock":
            _audit_write_blocked(request, user, "MOCK_WRITE_BLOCKED", "MOCK_STATE_CHANGE_FORBIDDEN")
            raise HTTPException(403, "Mock 인증으로는 상태변경 작업을 수행할 수 없습니다")

        session_id = getattr(request.state, "session_id", None)
        if session_id is None:
            # auth_method가 "session"도 "mock"도 아닌 미확인 상태 — 신뢰할 수 없으므로
            # 안전한 쪽(차단)을 기본값으로 한다(Fail-Closed).
            _audit_write_blocked(request, user, "MOCK_WRITE_BLOCKED", "UNVERIFIED_AUTH_METHOD")
            raise HTTPException(403, "상태변경 작업을 수행할 수 없습니다")

        expected = getattr(request.state, "csrf_token", None)
        provided = request.headers.get(CSRF_HEADER_NAME)
        if expected is None or not csrf_token_matches(expected, provided):
            _audit_write_blocked(request, user, "CSRF_VALIDATION_FAILED", "CSRF_MISMATCH")
            raise HTTPException(403, "CSRF 토큰이 유효하지 않습니다")
        return user

    return require_csrf


class LoginBody(BaseModel):
    loginId: str
    password: str


def create_auth_router(data_dir: Path | str) -> APIRouter:
    router = APIRouter()
    require_user = build_require_session_user(data_dir)

    @router.post("/api/auth/login")
    def login(body: LoginBody, request: Request, response: Response):
        request_id = request.headers.get("X-Request-Id")
        try:
            identity = auth_service.authenticate(
                data_dir, login_id=body.loginId, password=body.password,
                request_id=request_id, source_env=current_env(),
            )
        except auth_service.AuthError:
            # 사용자 열거 방지 — 원인과 무관하게 동일한 일반화된 메시지(§10)
            raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다")

        session = auth_service.create_session(
            data_dir, user_id=identity["id"], request_id=request_id, source_env=current_env()
        )
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session["session_id"],
            httponly=True,
            secure=_cookie_secure(),
            samesite="lax",
            path="/",
        )
        return {
            "user": {
                "id": identity["id"],
                "displayName": identity.get("name"),
                "roleId": identity.get("roleId"),
            },
            "csrfToken": session["csrf_token"],
        }

    @router.post("/api/auth/logout")
    def logout(request: Request, response: Response, user: dict = Depends(require_user)):
        session_id = getattr(request.state, "session_id", None)
        if session_id:
            auth_service.logout(
                data_dir, session_id=session_id, request_id=request.headers.get("X-Request-Id"),
                source_env=current_env(),
            )
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        return {"success": True}

    @router.get("/api/auth/me")
    def me(request: Request, user: dict = Depends(require_user)):
        return {
            "user": {
                "id": user["id"],
                "displayName": user.get("name"),
                "roleId": user.get("roleId"),
            },
            "csrfToken": getattr(request.state, "csrf_token", None),
        }

    return router
