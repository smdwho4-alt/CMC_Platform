# -*- coding: utf-8 -*-
"""
Sprint8 Commit8-2c STEP2 공용 Helper — Mock 기반 상태변경 테스트를 실제 Session
인증(로그인 → 서버 발급 Cookie → 서버 발급 CSRF Token)으로 전환하기 위한 최소
유틸리티. 이 파일은 신규 파일이며 기존 테스트 파일의 구조를 리팩터링하지 않는다
(각 파일은 이 함수 하나만 import해서 쓴다).

클라이언트가 임의로 만든 Session ID/Cookie/CSRF Token은 사용하지 않는다 — 전부
실제 로그인 API(`/api/auth/login`)가 서버에서 발급한 값 그대로 사용한다.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT / "src" / "auth"))

import auth_service  # noqa: E402
import auth_store as store  # noqa: E402

_SYNTHETIC_PASSWORD = "Synthetic-Test-Pw-Step2-01!"


def ensure_session(
    client: Any, data_dir, *, user_id: str, role_id: str, display_name: str | None, login_id: str
) -> dict[str, str]:
    """user_id(실제 users.json 사용자 id)에 연계된 합성 인증 계정을 만들고
    (이미 있으면 재사용), 주어진 TestClient로 실제 로그인 API를 호출해 서버가
    발급한 세션 Cookie를 client.cookies에 저장한다.

    반환값은 이후 상태변경 요청에 그대로 넣을 {"X-CSRF-Token": ...} 헤더 dict —
    호출부가 필요하면 다른 헤더와 딕셔너리 병합(**csrf_headers)해서 쓰면 된다.
    """
    store.init_schema(data_dir)
    with store.connect(data_dir) as conn:
        existing = store.user_by_id(conn, user_id)
    if existing is None:
        auth_service.create_user(
            data_dir, user_id=user_id, login_id=login_id,
            password=_SYNTHETIC_PASSWORD, display_name=display_name, role_id=role_id,
        )
    r = client.post("/api/auth/login", json={"loginId": login_id, "password": _SYNTHETIC_PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"세션 로그인 실패({login_id}): {r.status_code} {r.text}")
    return {"X-CSRF-Token": r.json()["csrfToken"]}
