# -*- coding: utf-8 -*-
"""
CSHSP Sprint F 테스트 러너 — AI Chat Widget & Operational Flow
채팅 API·본인확인·문진 제출/검토·알림 워커·운영 리허설 시나리오를 검증한다.
샌드박스 사본 실행, 원본 data/ 불변. 결과: tests/sprint_f_test_result.csv
"""
from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("core", "reservation", "api", "agents", "questionnaire", "workers"):
    sys.path.insert(0, str(ROOT / "src" / p))

from fastapi.testclient import TestClient  # noqa: E402

import core_data_loader as loader  # noqa: E402
import data_validator as validator  # noqa: E402
import notification_worker as worker  # noqa: E402
from api_server import create_app  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint_f" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)

client = TestClient(create_app(SANDBOX))
STAFF = {"X-User-Id": "USR-0002"}
SID = "CHAT-TEST-0001"

# Sprint8 Commit8-2c STEP2: 승인(상태변경)은 Mock이 차단된다. 이 파일은 STAFF
# 단일 역할만 쓰므로(다른 역할과 섞이지 않음), 메인 client를 그대로 세션
# 로그인해도 안전하다.
from _step2_session_helper import ensure_session  # noqa: E402
STAFF_CSRF = ensure_session(
    client, SANDBOX, user_id="USR-0002", role_id="ROLE-STAFF",
    display_name="QA STAFF", login_id="qa_step2_f_staff",
)

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


def chat(message: str, context: dict | None = None, sid: str = SID):
    r = client.post("/api/agents/chat", json={"sessionId": sid, "message": message,
                                              "context": context or {}})
    return r.status_code, r.json()


# ── 1. 채팅 API 기본 ──
code, d = chat("검진 전에 금식해야 하나요?")
check("채팅 API 정상 응답", code == 200 and "금식" in d["message"], d.get("agent", ""))
check("응답에 verifyState 포함", d.get("verifyState") == "UNVERIFIED")

code, d = chat("어떤 검진 프로그램이 좋을까요?")
check("예약 상담 메시지 처리", code == 200 and d.get("blocked") is False)

# ── 2. 본인확인 전 게이트 ──
code, d = chat("내 예약 확인해줘")
check("본인확인 전 예약조회 차단", d.get("needVerification") is True and "본인확인" in d["message"])
code, d = chat("예약 신청할게요", {"programId": "PRG-BASIC", "date": "2026-07-10",
                                  "time": "08:30", "patientId": "PT-2026-0001"})
check("클라이언트 patientId 불신 (미인증 신청 차단)", d.get("needVerification") is True)

# ── 3. 본인확인 흐름 (UNVERIFIED → BASIC → PHONE) ──
r = client.post("/api/agents/verify", json={"sessionId": SID, "name": "테스트박", "phone": "010-0000-0003"})
check("1단계 이름+전화 확인 → VERIFIED_BASIC", r.json().get("verifyState") == "VERIFIED_BASIC")
r_bad = client.post("/api/agents/verify", json={"sessionId": SID, "name": "다른사람", "phone": "010-9999-9999"})
check("불일치 정보 → 인증 실패", r_bad.json().get("success") is False)

code, d = chat("내 예약 확인해줘")
check("VERIFIED_BASIC 개인정보 마스킹", "1999****" in d["message"] and "010-****-0003" in d["message"],
      d["patient"]["birthDate"] + " / " + d["patient"]["phone"])

r = client.post("/api/agents/verify", json={"sessionId": SID, "code": "000000"})
check("잘못된 인증번호 거부", r.json().get("success") is False)
r = client.post("/api/agents/verify", json={"sessionId": SID, "code": "123456"})
check("2단계 인증번호 → VERIFIED_PHONE", r.json().get("verifyState") == "VERIFIED_PHONE")
code, d = chat("내 예약 확인해줘")
check("VERIFIED_PHONE 기본정보 표시", "1999-07-21" in d["message"] and "010-0000-0003" in d["message"])

# ── 4. 채팅 예약 신청 → PENDING_APPROVAL ──
code, d = chat("예약 신청할게요", {"programId": "PRG-BASIC", "date": "2026-07-10", "time": "08:30"})
rsv = d.get("reservation") or {}
RID = rsv.get("id", "")
check("채팅 예약 신청 → PENDING_APPROVAL", d.get("success") is True
      and rsv.get("status") == "PENDING_APPROVAL", RID)
check("세션 환자로 신청됨 (PT-2026-0003)", rsv.get("patientId") == "PT-2026-0003")
check("확정 아님 안내 문구", "직원 확인" in d["message"])

# ── 5. Safety 차단 + audit log ──
code, d = chat("검사 결과 수치 좀 해석해 주세요")
check("의료 진단/해석 질문 차단", d.get("blocked") is True and "의료진 상담" in d["message"])
logs = loader.load_entity("AuditLog", SANDBOX)
sb = [l for l in logs if l.get("action") == "SAFETY_BLOCKED" and l.get("entityId") == SID]
check("Safety 차단 audit log 기록", len(sb) >= 1,
      f"{len(sb)}건, category={sb[0]['after']['category'] if sb else '-'}")

# ── 6. 직원 승인 → 알림 PENDING → Worker 처리 ──
r = client.post(f"/api/reservations/{RID}/approve", headers=STAFF_CSRF)
check("직원 승인 → CONFIRMED", r.status_code == 200 and r.json()["reservation"]["status"] == "CONFIRMED")
ntf_pending = [n for n in loader.load_entity("Notification", SANDBOX)
               if n["status"] == "PENDING" and n.get("reservationId") == RID]
check("승인 알림 PENDING 생성", len(ntf_pending) == 1, ntf_pending[0]["id"] if ntf_pending else "")

NTF_ID = ntf_pending[0]["id"] if ntf_pending else ""
res1 = worker.process_pending(SANDBOX, sender=lambda rec, pts:
                              (False, "MOCK 실패 주입") if rec["id"] == NTF_ID
                              else worker.default_mock_sender(rec, pts))
check("Worker FAILED 처리 Mock", any(x["id"] == NTF_ID and x["result"] == "FAILED" for x in res1["details"]),
      f"sent {res1['sent']} / failed {res1['failed']}")
worker.retry_failed(SANDBOX)
res2 = worker.process_pending(SANDBOX)
ntf_after = next(n for n in loader.load_entity("Notification", SANDBOX) if n["id"] == NTF_ID)
check("Worker PENDING → SENT 처리", ntf_after["status"] == "SENT" and ntf_after.get("sentAt"),
      f"재처리 후 sent {res2['sent']}건")

# ── 7. 문진 제출 → 직원 검토 ──
code, d = chat("사전 문진 할게요", {"reservationId": RID})
qst = d.get("questionnaire") or {}
QID = qst.get("id", "")
check("문진 시작 (DRAFT)", d.get("success") is True and qst.get("status") == "DRAFT", QID)

answers = [{"code": c, "answer": a} for c, a in
           [("Q01", "아니오"), ("Q02", "아니오"), ("Q03", "예"), ("Q04", "해당없음"), ("Q05", "아니오")]]
r = client.post(f"/api/agents/questionnaires/{QID}/submit",
                json={"sessionId": SID, "answers": answers})
check("문진 제출 성공 (SUBMITTED)", r.status_code == 200
      and r.json()["questionnaire"]["status"] == "SUBMITTED")
r_other = client.post(f"/api/agents/questionnaires/{QID}/submit",
                      json={"sessionId": "CHAT-OTHER", "answers": answers})
check("미인증 세션 문진 제출 차단", r_other.status_code == 403)

r = client.get("/api/questionnaires?status=SUBMITTED", headers=STAFF)
check("직원 문진 목록 조회 (마스킹 포함)", r.status_code == 200
      and any(q["id"] == QID and "****" in q["patientBirthMasked"] for q in r.json()["records"]))
# client는 위에서 STAFF 세션으로 로그인해 Cookie를 갖고 있어(세션이 있으면 Mock
# 헤더보다 항상 우선) 다른 신원(AI)을 Mock으로 흉내낼 수 없다 — 별도 Mock 전용
# client로 검증한다.
client_mock_ai = TestClient(create_app(SANDBOX))
check("AI 계정 문진 목록 차단", client_mock_ai.get("/api/questionnaires",
      headers={"X-User-Id": "USR-9000"}).status_code == 403)
r = client.post(f"/api/questionnaires/{QID}/review", headers=STAFF,
                json={"decision": "REVIEWED", "note": "이상 없음"})
check("문진 REVIEWED 처리", r.status_code == 200 and r.json()["questionnaire"]["status"] == "REVIEWED")
r_again = client.post(f"/api/questionnaires/{QID}/review", headers=STAFF,
                      json={"decision": "REJECTED"})
check("검토 완료 후 재검토 차단", r_again.status_code == 400)

# ── 8. 운영 리허설: 신청→승인→알림→문진→검토 전체 상태 확인 ──
final_rsv = loader.get_by_id("Reservation", RID, SANDBOX)
final_qst = next(q for q in loader.load_entity("Questionnaire", SANDBOX) if q["id"] == QID)
final_ntf = next(n for n in loader.load_entity("Notification", SANDBOX) if n["id"] == NTF_ID)
scenario_ok = (final_rsv["status"] == "CONFIRMED" and final_ntf["status"] == "SENT"
               and final_qst["status"] == "REVIEWED" and final_qst["reviewedBy"] == "USR-0002")
check("전체 시나리오 신청→승인→알림→문진→검토", scenario_ok,
      f"RSV={final_rsv['status']} / NTF={final_ntf['status']} / QST={final_qst['status']}")
acts = {l["action"] for l in loader.load_entity("AuditLog", SANDBOX)}
check("시나리오 감사로그 (신청/승인/차단)",
      {"RESERVATION_REQUESTED", "RESERVATION_APPROVED", "SAFETY_BLOCKED"} <= acts)

# ── 9. 무결성 / 원본 보호 ──
res = validator.validate_all(loader.load_all(SANDBOX))
check("전체 데이터 무결성", len(res["errors"]) == 0, f"오류 {len(res['errors'])}건, 경고 {len(res['warnings'])}건")
for e in res["errors"][:5]:
    print(f"    [오류] {e}")
check("원본 data/ 미변경", len(loader.load_entity("Reservation", ROOT / "data")) == 5)

# ── 저장 ──
out = Path(__file__).parent / "sprint_f_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, x, _ in results if x == "FAIL")
print(f"\n총 {len(results)}건 중 PASS {len(results) - fails} / FAIL {fails}")
print(f"결과 저장: {out}")
sys.exit(1 if fails else 0)
