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
            request.state.csrf_token = None  # Mock 경로는 CSRF 보호 대상 API에서 별도 차단됨
            request.state.session_id = None
            return user

        raise HTTPException(401, "인증이 필요합니다")

    return require_session_user


def build_require_csrf(require_user):
    """상태변경 API 전용 — require_user와 동일한 함수 객체를 넘겨받아 FastAPI가
    한 요청 내에서 세션 검증을 한 번만 수행하도록 한다(Depends 캐시 재사용).

    CSRF는 브라우저가 자동으로 실어 보내는 Cookie(=ambient authority)를 노리는
    공격이다 — 세션 Cookie로 인증된 요청에만 의미가 있고, X-User-Id Mock(헤더
    기반, 브라우저가 자동으로 붙이지 않음)에는 CSRF 공격 자체가 성립하지 않는다.
    그래서 세션 인증(request.state.session_id 존재)일 때만 검증하고, Mock
    경로는 그대로 통과시킨다(Mock 자체는 이미 별도로 환경 게이트로 제한됨)."""

    def require_csrf(request: Request, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
        session_id = getattr(request.state, "session_id", None)
        if session_id is None:
            return user  # Mock 경로 — CSRF 대상 아님(세션 Cookie 자체가 없음)

        expected = getattr(request.state, "csrf_token", None)
        provided = request.headers.get(CSRF_HEADER_NAME)
        if expected is None or not csrf_token_matches(expected, provided):
            data_dir = getattr(request.app.state, "cshsp_data_dir", None)
            if data_dir:
                store.init_schema(data_dir)
                with store.connect(data_dir) as conn:
                    store.append_auth_audit(
                        conn, audit_id=f"AUD-AUTH-{uuid.uuid4().hex}",
                        event_type="CSRF_VALIDATION_FAILED", actor_user_id=user.get("id"),
                        request_id=request.headers.get("X-Request-Id"),
                        route=str(request.url.path), result="FAILURE",
                        reason_code="CSRF_MISMATCH", source_env=current_env(),
                    )
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
