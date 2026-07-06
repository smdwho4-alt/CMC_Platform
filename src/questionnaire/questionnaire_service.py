# -*- coding: utf-8 -*-
"""
CSHSP Questionnaire Service — Sprint F
사전문진 응답 수집·제출·직원 검토. 의료 판단 없음 — 상태 관리와 기록만 담당한다.

상태 전이:
  DRAFT → SUBMITTED → REVIEWED | REJECTED
  REJECTED → SUBMITTED (보완 후 재제출)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src" / "reservation"))

from json_store import now_iso, read_doc, write_doc  # noqa: E402

STATUS_TRANSITIONS = {
    "DRAFT": {"SUBMITTED"},
    "SUBMITTED": {"REVIEWED", "REJECTED"},
    "REJECTED": {"SUBMITTED"},
    "REVIEWED": set(),
}


class QuestionnaireError(Exception):
    """문진 처리 오류 (없음/전이 불가/소유자 불일치)"""


def _load(data_dir: Path):
    path = Path(data_dir) / "questionnaires.json"
    doc = read_doc(path)
    return path, doc


def _find(doc: dict, qid: str) -> dict[str, Any]:
    rec = next((r for r in doc["records"] if r.get("id") == qid), None)
    if rec is None:
        raise QuestionnaireError(f"문진 없음: {qid}")
    return rec


def _assert_transition(rec: dict, target: str) -> None:
    cur = rec.get("status")
    if target not in STATUS_TRANSITIONS.get(cur, set()):
        raise QuestionnaireError(f"허용되지 않는 문진 상태 전이: {cur} → {target}")


def submit_answers(qid: str, answers: list[dict[str, Any]], data_dir: Path,
                   patient_id: str | None = None) -> dict[str, Any]:
    """응답 제출: DRAFT/REJECTED → SUBMITTED. patient_id 지정 시 소유자 일치 확인."""
    path, doc = _load(data_dir)
    rec = _find(doc, qid)
    if patient_id and rec.get("patientId") != patient_id:
        raise QuestionnaireError(f"문진 소유자 불일치: {qid}")
    _assert_transition(rec, "SUBMITTED")

    by_code = {a.get("code"): a for a in answers}
    for item in rec.get("items", []):
        a = by_code.get(item.get("code"))
        if a:
            item["answer"] = a.get("answer")
            if a.get("detail") is not None:
                item["detail"] = a.get("detail")
    unanswered = [i["code"] for i in rec.get("items", []) if i.get("answer") in (None, "")]
    if unanswered:
        raise QuestionnaireError(f"미응답 항목: {', '.join(unanswered)}")

    rec.update({"status": "SUBMITTED", "submittedAt": now_iso(), "updatedAt": now_iso()})
    write_doc(path, doc)
    return rec


def review(qid: str, reviewer_user_id: str, decision: str, note: str = "",
           data_dir: Path | None = None) -> dict[str, Any]:
    """직원 검토: SUBMITTED → REVIEWED(확인) | REJECTED(보완 요청)."""
    if decision not in ("REVIEWED", "REJECTED"):
        raise QuestionnaireError(f"결정값은 REVIEWED/REJECTED만 가능: {decision}")
    path, doc = _load(data_dir)
    rec = _find(doc, qid)
    _assert_transition(rec, decision)
    rec.update({"status": decision, "reviewedBy": reviewer_user_id,
                "reviewedAt": now_iso(), "reviewNote": note or None, "updatedAt": now_iso()})
    write_doc(path, doc)
    return rec


def list_by_status(status: str, data_dir: Path) -> list[dict[str, Any]]:
    _, doc = _load(data_dir)
    return [r for r in doc["records"] if not status or r.get("status") == status]
