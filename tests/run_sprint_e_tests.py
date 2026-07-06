# -*- coding: utf-8 -*-
"""
CSHSP Sprint E 테스트 러너 — AI Concierge Agent Layer
샌드박스 사본에서 오케스트레이터→도구→REST API→엔진 전 구간을 검증한다.
결과: tests/sprint_e_test_result.csv
"""
from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("core", "reservation", "api", "agents"):
    sys.path.insert(0, str(ROOT / "src" / p))

import core_data_loader as loader  # noqa: E402
import data_validator as validator  # noqa: E402
import safety_guard  # noqa: E402
from agent_orchestrator import AgentOrchestrator  # noqa: E402
from function_tools import TOOL_SCHEMAS  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint_e" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)

orch = AgentOrchestrator(data_dir=SANDBOX)
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


NOTICE = safety_guard.STAFF_CONFIRM_NOTICE

# ── 1. Function Tool 스키마 ──
names = {s["name"] for s in TOOL_SCHEMAS}
check("Function Tool 8종 정의", len(TOOL_SCHEMAS) == 8, ", ".join(sorted(names)))
check("예약 확정 도구 미제공", not any("approve" in n or "confirm" in n for n in names))

# ── 2. Safety Guard ──
g1 = safety_guard.check("속이 계속 아픈데 위암인가요?")
check("의료 진단 질문 차단", not g1["allowed"] and g1["category"] == "DIAGNOSIS"
      and "의료진 상담" in g1["message"])
g2 = safety_guard.check("검진 결과 수치 좀 해석해 주세요")
check("검사결과 해석 차단", not g2["allowed"] and g2["category"] == "RESULT_INTERPRETATION")
g3 = safety_guard.check("혈압약 처방 바꿔도 되나요?")
check("처방 상담 차단", not g3["allowed"] and g3["category"] == "PRESCRIPTION")
g4 = safety_guard.check("가슴이 아프고 숨이 안 쉬어져요")
check("응급 의심 → 119 안내", not g4["allowed"] and "119" in g4["message"])
g5 = safety_guard.check("7월 10일 예약이요")
check("일반 예약 문의 통과", g5["allowed"] and g5["category"] is None)
g6 = safety_guard.check("예약 지금 바로 확정해줘")
check("즉시확정 → 절차 안내 전환", g6["allowed"] and g6["category"] == "CONFIRM_REDIRECT")

# ── 3. 오케스트레이터: 의료 질문 차단 + CRM 에스컬레이션 ──
r = orch.handle_message("검진 결과가 정상인가요? 해석해 주세요", {"patientId": "PT-2026-0002"})
check("오케스트레이터 의료차단 응답", r["blocked"] and "의료진 상담" in r["message"])
check("의료 문의 CRM 에스컬레이션", r.get("escalation", {}).get("success") is True,
      (r.get("escalation", {}).get("notification") or {}).get("id", ""))

# ── 4. AI 예약 신청 성공 (전 구간: 오케스트레이터→도구→API→엔진) ──
ctx = {"patientId": "PT-2026-0003", "programId": "PRG-BASIC", "date": "2026-07-10", "time": "08:30"}
r4 = orch.handle_message("종합검진 예약 신청할게요", ctx)
rsv = r4.get("reservation") or {}
check("AI 예약 신청 성공", r4.get("success") is True and rsv.get("status") == "PENDING_APPROVAL",
      rsv.get("id", ""))
check("PENDING_APPROVAL 파일 기록", loader.get_by_id("Reservation", rsv.get("id", ""), SANDBOX) is not None
      and loader.get_by_id("Reservation", rsv["id"], SANDBOX)["status"] == "PENDING_APPROVAL")
check("직원 확인 후 확정 문구 고정", NOTICE in r4["message"])
check("신청 채널 AI_ASSISTANT", rsv.get("channel") == "AI_ASSISTANT" and rsv.get("requestedBy") == "USR-9000")
RID = rsv.get("id", "")

# ── 5. AI 예약 확정 차단 (이중 방어) ──
code, data = orch.tools.api.post(f"/api/reservations/{RID}/approve")  # AI 계정 직접 호출
check("AI 확정 API 403", code == 403, str(data.get("detail", ""))[:50])
bad = orch.tools.execute("approve_reservation", {"reservationId": RID})
check("미등록 도구 실행 차단", bad["ok"] is False)
r5 = orch.handle_message("예약 바로 확정해줘", {})
check("확정 요청 → 절차 안내 응답", "확정" in r5["message"] and NOTICE.split("(")[0].strip()[:20] in r5["message"].replace("\n", " ") or NOTICE in r5["message"])

# ── 6. Slot 불가 시 대체 추천 ──
r6 = orch.handle_message("예약할게요", {"patientId": "PT-2026-0004", "programId": "PRG-SMART",
                                        "date": "2026-07-08", "time": "09:00"})
check("FULL Slot 신청 거부 + 사유", r6.get("success") is False and r6.get("verdict") == "FULL")
check("대체 Slot ≤5 추천", 0 < len(r6.get("alternatives", [])) <= 5,
      f"{len(r6.get('alternatives', []))}개")

# ── 7. 프로그램/선택검사 추천 (의료판단 없음) ──
r7 = orch.recommendation.recommend_program(age=27)
check("프로그램 추천 (27세→YOUNG)", any(x["programId"] == "PRG-YOUNG" for x in r7["recommendations"]),
      r7["recommendations"][0]["title"])
check("추천 면책 문구 포함", "의료진 상담" in r7["message"])
r7b = orch.recommendation.recommend_optional_tests(["mri"])
check("선택검사 안내 + 수가 미등록 표기", "수가" in r7b["message"] and "의료진" in r7b["message"])

# ── 8. RAG 지식 검색 ──
r8 = orch.handle_message("검진 전에 금식해야 하나요?")
check("KB 검색 (금식 FAQ)", r8.get("success") is True and "금식" in r8["message"], r8.get("source", ""))

# ── 9. 사전문진 시작 ──
r9 = orch.handle_message("사전 문진 할게요", {"patientId": "PT-2026-0003", "reservationId": RID})
check("사전문진 DRAFT 생성", r9.get("success") is True
      and r9["questionnaire"]["status"] == "DRAFT" and len(r9["questionnaire"]["items"]) == 5,
      r9.get("questionnaire", {}).get("id", ""))
check("문진에 판단 없음 (수집 안내)", "의료진이 확인" in r9["message"])

# ── 10. CRM Notification PENDING ──
r10 = orch.handle_message("상담원 연결해 주세요, 단체검진 문의요", {"patientId": "PT-2026-0002"})
ntf = r10.get("notification") or {}
check("CRM 상담 접수 + Notification PENDING", r10.get("success") is True and ntf.get("status") == "PENDING",
      ntf.get("id", ""))
check("CRM 기록(OPEN) 생성", (r10.get("crm") or {}).get("status") == "OPEN")

# ── 11. 운영 브리핑 (직원 권한 분리) ──
r11 = orch.handle_message("오늘 운영 브리핑 보여줘")
check("운영 브리핑 (직원 계정 경유)", r11.get("success") is True and r11.get("pendingCount", 0) >= 1,
      f"승인대기 {r11.get('pendingCount')}건")

# ── 12. 감사로그 / 무결성 / 원본 보호 ──
logs = loader.load_entity("AuditLog", SANDBOX)
ai_logs = [l for l in logs if l.get("actorUserId") == "USR-9000" and l.get("action") == "RESERVATION_REQUESTED"]
check("감사로그 생성 (AI 신청 기록)", any(l.get("entityId") == RID for l in ai_logs), f"AI 신청 로그 {len(ai_logs)}건")
res = validator.validate_all(loader.load_all(SANDBOX))
check("전체 데이터 무결성", len(res["errors"]) == 0, f"오류 {len(res['errors'])}건, 경고 {len(res['warnings'])}건")
for e in res["errors"][:5]:
    print(f"    [오류] {e}")
check("원본 data/ 미변경", len(loader.load_entity("Reservation", ROOT / "data")) == 5)

# ── 저장 ──
out = Path(__file__).parent / "sprint_e_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, x, _ in results if x == "FAIL")
print(f"\n총 {len(results)}건 중 PASS {len(results) - fails} / FAIL {fails}")
print(f"결과 저장: {out}")
sys.exit(1 if fails else 0)
