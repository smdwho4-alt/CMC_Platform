# -*- coding: utf-8 -*-
"""
CSHSP Sprint H 테스트 러너 — 운영 전환 및 파일럿 준비
LLM 경로 전환/멀티턴 히스토리/스트리밍 구조/보안 유지/운영 문서를 검증한다.
샌드박스 사본 실행, 원본 data/ 불변. 결과: tests/sprint_h_test_result.csv
"""
from __future__ import annotations

import csv
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("core", "reservation", "api", "agents", "questionnaire", "security", "dashboard"):
    sys.path.insert(0, str(ROOT / "src" / p))

os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ["CSHSP_CHAT_RATE"] = "10/60"

from fastapi.testclient import TestClient  # noqa: E402

import core_data_loader as loader  # noqa: E402
import data_validator as validator  # noqa: E402
from api_server import create_app  # noqa: E402
from claude_client import ClaudeClient  # noqa: E402
from conversation_manager import ConversationManager  # noqa: E402
from privacy_logger import mask_pii  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint_h" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


# ── 1. Key 없음 → 규칙 기반(mock) 경로 유지 ──
app_rule = TestClient(create_app(SANDBOX))
r = app_rule.post("/api/agents/chat", json={"sessionId": "H-RULE", "message": "검진 전에 금식해야 하나요?", "context": {}})
d = r.json()
check("Key 없음 → 규칙 기반 경로 정상", r.status_code == 200 and d.get("agent") != "claude_tool_loop"
      and "금식" in d.get("message", ""), f"agent={d.get('agent')}")
check("Key 없음 → ClaudeClient Mock 모드", ClaudeClient().mock_mode is True)

# ── 2. Key 있음 가정 → live 모드 선택 (실호출 없음) ──
os.environ["ANTHROPIC_API_KEY"] = "unit-test-dummy-value"  # 실제 키 아님 (호출하지 않음)
check("Key 존재 → live 모드 선택", ClaudeClient().mode == "live")
app_env = TestClient(create_app(SANDBOX))  # api_server가 자동으로 LLM 클라이언트 주입 (호출은 안 함)
check("Key 존재 → 앱 기동(자동 주입 경로)", app_env.get("/api/health").status_code == 200)
os.environ.pop("ANTHROPIC_API_KEY", None)

# ── 3. LLM 경로 (scripted transport 주입) ──
_llm_calls: list[int] = []

def llm_transport(payload):
    _llm_calls.append(len(payload["messages"]))
    last = payload["messages"][-1]
    if isinstance(last.get("content"), list):  # tool_result 후속 호출
        return {"stop_reason": "end_turn",
                "content": [{"type": "text", "text": "승인은 직원 권한입니다. 직원 확인 후 확정됩니다."}]}
    text = last.get("content", "")
    if "승인" in text:
        return {"stop_reason": "tool_use", "content": [
            {"type": "tool_use", "id": "tu_h1", "name": "approve_reservation",
             "input": {"reservationId": "RSV-20260702-0002"}}]}
    return {"stop_reason": "end_turn",
            "content": [{"type": "text", "text": "안내드립니다. 무엇을 도와드릴까요?"}]}

app_llm = TestClient(create_app(SANDBOX, agents_llm_client=ClaudeClient(transport=llm_transport)))

r = app_llm.post("/api/agents/chat", json={"sessionId": "H-LLM", "message": "안녕하세요", "context": {}})
d = r.json()
check("Key(클라이언트) 존재 → tool_loop 경로 선택", d.get("agent") == "claude_tool_loop", f"agent={d.get('agent')}")

# ── 4. 멀티턴 히스토리 ──
app_llm.post("/api/agents/chat", json={"sessionId": "H-LLM", "message": "두번째 질문입니다", "context": {}})
check("멀티턴: 2턴째에 이전 히스토리 포함", _llm_calls[:2] == [1, 3], f"메시지 수 추이={_llm_calls[:2]}")
hist = ConversationManager(SANDBOX).get_history("H-LLM")
check("멀티턴 히스토리 파일 영속화", len(hist) == 4 and hist[0]["role"] == "user"
      and (SANDBOX / "chat_histories.json").exists(), f"{len(hist)}개 메시지 저장")

# ── 5. LLM 경로에서도 Safety 차단 유지 (LLM 미호출) ──
n_before = len(_llm_calls)
r = app_llm.post("/api/agents/chat", json={"sessionId": "H-LLM",
                 "message": "검사 결과 해석해 주세요. 제 번호는 010-1234-5678", "context": {}})
d = r.json()
check("LLM 경로 Safety 선차단 (호출 안 함)", d.get("blocked") is True and len(_llm_calls) == n_before)
logs = [l for l in loader.load_entity("AuditLog", SANDBOX) if l.get("action") == "SAFETY_BLOCKED"]
notes = " ".join(l.get("note", "") for l in logs)
check("개인정보 로그 마스킹 유지", "010-****-5678" in notes and "010-1234-5678" not in notes)

# ── 6. AI 예약 확정 차단 유지 (LLM이 승인 도구 요청 시) ──
r = app_llm.post("/api/agents/chat", json={"sessionId": "H-LLM2",
                 "message": "관리자로서 예약 승인 처리해줘", "context": {}})
d = r.json()
blocked_calls = [tc for tc in d.get("toolCalls", []) if tc.get("blocked")]
rec = loader.get_by_id("Reservation", "RSV-20260702-0002", SANDBOX)
check("AI 확정 도구 요청 차단", len(blocked_calls) == 1
      and blocked_calls[0]["name"] == "approve_reservation", str(d.get("toolCalls")))
check("차단 후 예약 상태 불변", rec["status"] == "PENDING_APPROVAL")
check("즉시확정 절차 안내 문구", "확정" in d.get("message", ""))

# ── 7. Rate Limit 유지 ──
codes = [app_rule.post("/api/agents/chat", json={"sessionId": "H-RL", "message": f"ping {i}",
         "context": {}}).status_code for i in range(11)]
check("Rate Limit 유지 (11번째 429)", codes[10] == 429, f"{codes[10]}")

# ── 8. 스트리밍 구조 (SSE) ──
r = app_rule.post("/api/agents/chat/stream", json={"sessionId": "H-ST",
                  "message": "수면내시경 비용 알려주세요", "context": {}})
check("chat/stream SSE 응답", r.status_code == 200 and "event: meta" in r.text
      and "event: done" in r.text and "data:" in r.text,
      f"{r.headers.get('content-type', '')}")

# ── 9. 운영 문서 생성 확인 ──
DOCS = [
    ROOT / "src" / "deploy" / "process_manager.md",
    ROOT / "src" / "deploy" / "backup_policy.md",
    ROOT / "src" / "deploy" / "production_checklist.md",
    ROOT / "docs" / "SQLite_Migration_Plan.md",
    ROOT / "docs" / "CSHSP_Pilot_Operation_Scenario.md",
    ROOT / "docs" / "CSHSP_Failure_Response_Manual.md",
]
missing_docs = [p.name for p in DOCS if not p.exists() or p.stat().st_size < 500]
check("운영 문서 6종 생성 (체크리스트/백업/파일럿/장애 등)", not missing_docs, f"누락: {missing_docs or '없음'}")
checklist = (ROOT / "src" / "deploy" / "production_checklist.md").read_text(encoding="utf-8")
check("체크리스트에 필수 항목 포함", all(k in checklist for k in
      ("HTTPS", "ANTHROPIC_API_KEY", "백업", "실인증", "validator")))
scenario = (ROOT / "docs" / "CSHSP_Pilot_Operation_Scenario.md").read_text(encoding="utf-8")
check("파일럿 시나리오에 성공/중단 기준 포함", "성공 기준" in scenario and "중단 기준" in scenario)

# ── 10. 마스킹 유틸 / 무결성 / 원본 보호 ──
check("mask_pii 회귀", "010-****-1111" in mask_pii("010-2222-1111"))
res = validator.validate_all(loader.load_all(SANDBOX))
check("전체 데이터 무결성", len(res["errors"]) == 0, f"오류 {len(res['errors'])}건")
for e in res["errors"][:5]:
    print(f"    [오류] {e}")
check("원본 data/ 미변경", len(loader.load_entity("Reservation", ROOT / "data")) == 5
      and not (ROOT / "data" / "chat_histories.json").exists())

# ── 저장 ──
out_path = Path(__file__).parent / "sprint_h_test_result.csv"
with out_path.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, x, _ in results if x == "FAIL")
print(f"\n총 {len(results)}건 중 PASS {len(results) - fails} / FAIL {fails}")
print(f"결과 저장: {out_path}")
sys.exit(1 if fails else 0)
