# -*- coding: utf-8 -*-
"""
CSHSP AI Metrics — Sprint G
AI 상담 이벤트 집계 (Dashboard용).

이벤트 소스: data/ai_events.json (라우터가 기록 — 메시지 원문은 저장하지 않는다)
+ audit_logs.json의 SAFETY_BLOCKED 교차 집계.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src" / "core"))
sys.path.insert(0, str(_ROOT / "src" / "reservation"))
sys.path.insert(0, str(_ROOT / "src" / "api"))

import core_data_loader as loader  # noqa: E402
from file_lock import DataLock  # noqa: E402
from json_store import now_iso, read_doc, write_doc  # noqa: E402

# 기록 가능한 이벤트 유형 (개인정보·메시지 원문 없음)
EVENT_TYPES = [
    "CHAT",                     # 채팅 턴 1회
    "SAFETY_BLOCKED",           # Safety Guard 차단
    "RESERVATION_CREATED",      # 예약 신청 전환
    "VERIFIED_BASIC",           # 본인확인 1단계
    "VERIFIED_PHONE",           # 본인확인 2단계
    "QUESTIONNAIRE_SUBMITTED",  # 문진 제출
    "CRM_ESCALATION",           # 상담원 연결/에스컬레이션
    "RATE_LIMITED",             # 요청 제한 발동
]


def record_event(data_dir: Path | str, event_type: str, session_id: str,
                 detail: str | None = None) -> None:
    """AI 이벤트 1건 기록 (append-only, 메시지 원문 저장 금지)."""
    if event_type not in EVENT_TYPES:
        return
    data_dir = Path(data_dir)
    ts = now_iso()
    with DataLock(data_dir):
        path = data_dir / "ai_events.json"
        doc = read_doc(path)
        doc.setdefault("entity", "AiEvent")
        doc["records"].append({
            "type": event_type, "sessionId": session_id,
            "timestamp": ts, "hour": ts[11:13],
            **({"detail": detail} if detail else {}),
        })
        write_doc(path, doc)


def compute_ai_metrics(data_dir: Path | str) -> dict[str, Any]:
    """AI 상담 KPI 집계."""
    data_dir = Path(data_dir)
    events = read_doc(data_dir / "ai_events.json")["records"]
    by_type = Counter(e.get("type") for e in events)

    # Safety 차단 상세 — 감사로그에서 카테고리별 집계
    safety_by_category: Counter = Counter()
    for log in loader.load_entity("AuditLog", data_dir):
        if log.get("action") == "SAFETY_BLOCKED":
            safety_by_category[(log.get("after") or {}).get("category") or "UNKNOWN"] += 1

    hourly = Counter(e.get("hour") for e in events if e.get("type") == "CHAT")
    verified_sessions = {e["sessionId"] for e in events if e.get("type") == "VERIFIED_BASIC"}

    total_chats = by_type.get("CHAT", 0)
    conversions = by_type.get("RESERVATION_CREATED", 0)
    return {
        "totalChats": total_chats,
        "uniqueSessions": len({e.get("sessionId") for e in events}),
        "reservationConversions": conversions,
        "conversionRate": round(conversions / total_chats * 100, 1) if total_chats else 0,
        "safetyBlocks": by_type.get("SAFETY_BLOCKED", 0),
        "safetyByCategory": dict(safety_by_category),
        "verifiedSessions": len(verified_sessions),
        "phoneVerified": by_type.get("VERIFIED_PHONE", 0),
        "questionnaireSubmits": by_type.get("QUESTIONNAIRE_SUBMITTED", 0),
        "crmEscalations": by_type.get("CRM_ESCALATION", 0),
        "rateLimited": by_type.get("RATE_LIMITED", 0),
        "hourlyChats": {f"{h:02d}": hourly.get(f"{h:02d}", 0) for h in range(24)},
    }
