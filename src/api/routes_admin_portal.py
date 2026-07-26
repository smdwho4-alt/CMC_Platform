# -*- coding: utf-8 -*-
"""
CSHSP Admin Portal Routes — Sprint 1 (Commit 2: 관리자 조회 API)

Single Admin Portal의 조회 전용 최소 API. Google Sheets를 예약 마스터 데이터로
Google Workspace Integration Layer(GAS) 경유로 읽기만 한다 — 쓰기 기능 없음
(Enterprise_Architecture_ToBe_v1.0.md §4/§10, PM 승인 제외범위 준수).

인증은 기존 api_server.py의 Mock 인증(X-User-Id 헤더 + ACTIVE 사용자) 패턴을
그대로 미러링한다 — require_user는 api_server.py 내부 closure라 외부에서
import할 수 없으므로, 여기서는 동일 로직을 별도로 구현한다(기존 코드 무수정,
패턴만 재사용).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
for _p in ("core", "services"):
    sys.path.insert(0, str(_ROOT / "src" / _p))

from fastapi import APIRouter, Depends, Header, HTTPException, Query  # noqa: E402

import core_data_loader as loader  # noqa: E402
import pii_mask  # noqa: E402
import sheets_readonly_service as sheets  # noqa: E402


def create_admin_portal_router(data_dir: Path) -> APIRouter:
    """Single Admin Portal 조회 전용 라우터 팩토리 (routes_agents.create_agents_router와 동일 패턴)."""
    router = APIRouter(prefix="/api/admin-portal", tags=["admin-portal"])

    def require_user(x_user_id: str | None = Header(default=None)) -> dict[str, Any]:
        if not x_user_id:
            raise HTTPException(401, "X-User-Id 헤더 필요 (Mock 인증)")
        user = next((u for u in loader.load_entity("User", data_dir) if u.get("id") == x_user_id), None)
        if not user or user.get("status") != "ACTIVE":
            raise HTTPException(401, f"유효하지 않은 사용자: {x_user_id}")
        return user

    @router.get("/health")
    def health():
        """Sheets 연동 상태 확인. 인증 없이 호출 가능 — Portal 셸이 초기 화면에서
        '연동 미설정'과 '일시 오류'를 구분해 표시하기 위한 것으로, 조회 전용이며
        Sheets 데이터를 반환하지 않는다(PII 없음)."""
        try:
            sheets.ping()
            return {"ok": True, "sheetsIntegration": "connected"}
        except sheets.SheetsIntegrationNotConfigured:
            return {"ok": False, "sheetsIntegration": "not_configured",
                    "message": "Sheets 연동이 설정되지 않았습니다. 관리자에게 문의하세요."}
        except sheets.SheetsIntegrationError as e:
            return {"ok": False, "sheetsIntegration": "error", "message": str(e)}

    @router.get("/reservations")
    def list_reservations(
        status: str = Query(default=""),
        dateFrom: str = Query(default=""),
        dateTo: str = Query(default=""),
        user: dict[str, Any] = Depends(require_user),
    ):
        try:
            raw_list = sheets.list_reservations(status=status, date_from=dateFrom, date_to=dateTo)
        except sheets.SheetsIntegrationNotConfigured as e:
            raise HTTPException(503, str(e)) from e
        except sheets.SheetsIntegrationError as e:
            raise HTTPException(502, str(e)) from e
        masked = [pii_mask.build_masked_reservation(r) for r in raw_list]
        return {"ok": True, "count": len(masked), "data": masked}

    @router.get("/reservations/{reservation_no}")
    def get_reservation(reservation_no: str, user: dict[str, Any] = Depends(require_user)):
        try:
            raw = sheets.get_reservation(reservation_no)
        except sheets.SheetsIntegrationNotConfigured as e:
            raise HTTPException(503, str(e)) from e
        except sheets.SheetsIntegrationError as e:
            raise HTTPException(502, str(e)) from e
        if raw is None:
            raise HTTPException(404, f"예약번호 없음: {reservation_no}")
        return {"ok": True, "data": pii_mask.build_masked_reservation(raw)}

    return router
