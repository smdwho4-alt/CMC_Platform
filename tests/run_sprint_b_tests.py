# -*- coding: utf-8 -*-
"""
CSHSP Sprint B 테스트 러너 — Reservation Engine
원본 data/를 보호하기 위해 tests/sandbox_sprint_b/data 사본에서 실행한다.
결과는 tests/sprint_b_test_result.csv 로 저장.
"""
from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "core"))
sys.path.insert(0, str(ROOT / "src" / "reservation"))

import core_data_loader as loader  # noqa: E402
import data_validator as validator  # noqa: E402
import reservation_engine as engine  # noqa: E402
import state_machine as sm  # noqa: E402
from alternative_slot_recommender import recommend_alternative_slots  # noqa: E402
from slot_generator import generate_slots  # noqa: E402

# ── 샌드박스 준비 (원본 data/ 불변) ──
SANDBOX = Path(__file__).parent / "sandbox_sprint_b" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)
D = SANDBOX

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


def slot(slot_id: str) -> dict:
    return next(s for s in loader.load_entity("Slot", D) if s["id"] == slot_id)


audit_before = len(loader.load_entity("AuditLog", D))

# ── 0. Slot Generator ──
created = generate_slots("2026-07-21", "2026-07-24", data_dir=D)  # 화~금 4일
check("Slot 생성기 (영업일 4일 x 10타임)", len(created) == 40, f"{len(created)}개 생성")
created_hol = generate_slots("2026-08-17", "2026-08-17", data_dir=D)  # 휴진일
check("Slot 생성기 휴진일 차단", len(created_hol) == 0, "2026-08-17 HOLIDAY → 0개")
created_cap1 = generate_slots("2026-07-27", "2026-07-27", data_dir=D, capacity=1)  # 월, 정원 1
check("Slot 생성기 정원 옵션", len(created_cap1) == 10 and created_cap1[0]["capacity"] == 1, "정원 1짜리 10개")
dup_gen = generate_slots("2026-07-21", "2026-07-21", data_dir=D)
check("Slot 생성기 기존 Slot 보존", len(dup_gen) == 0, "중복 생성 0개")

# ── 1. 정상 예약 신청 ──
r1 = engine.create_reservation_request(
    "PT-2026-0003", "PRG-BASIC", "2026-07-08", "08:30",
    "SLOT-20260708-0830-A", "AI_ASSISTANT", "USR-9000", data_dir=D)
check("정상 예약 신청 → PENDING_APPROVAL", r1["success"] and r1["reservation"]["status"] == "PENDING_APPROVAL",
      f"{r1['reservation']['id'] if r1['reservation'] else r1['reasons']}")
check("예약번호 형식 YYYYMMDD-0001", bool(r1["reservation"]) and
      len(r1["reservation"]["reservationNo"].split("-")) == 2, r1["reservation"]["reservationNo"])
check("신청 후 Slot HOLD", slot("SLOT-20260708-0830-A")["status"] == "HOLD")
RID1 = r1["reservation"]["id"]

# ── 2. 직원 승인 (AI는 승인 불가) ──
try:
    engine.approve_reservation(RID1, "USR-9000", data_dir=D)
    check("AI 계정 승인 차단", False, "예외 미발생")
except engine.EnginePermissionError as e:
    check("AI 계정 승인 차단", True, str(e)[:40])

rec = engine.approve_reservation(RID1, "USR-0002", data_dir=D)
s1 = slot("SLOT-20260708-0830-A")
check("직원 승인 → CONFIRMED", rec["status"] == "CONFIRMED", f"approvedBy={rec['approvedBy']}")
check("승인 후 Slot 점유 반영", s1["reservedCount"] == 4 and s1["status"] == "AVAILABLE",
      f"reservedCount={s1['reservedCount']}, status={s1['status']} (정원 6 미달 → AVAILABLE 복귀)")
ntf = loader.load_entity("Notification", D)
check("승인 시 Notification 생성 준비", any(n.get("reservationId") == RID1 and n["status"] == "PENDING" for n in ntf))

# ── 3. 예약 취소 ──
rec = engine.cancel_reservation(RID1, "USR-0002", "QA 테스트 취소", data_dir=D)
s1 = slot("SLOT-20260708-0830-A")
check("예약 취소 → CANCELLED", rec["status"] == "CANCELLED")
check("취소 후 Slot AVAILABLE 복구", s1["status"] == "AVAILABLE" and s1["reservedCount"] == 3,
      f"reservedCount={s1['reservedCount']}")

# ── 4. 중복예약 차단 (PT-2026-0001은 7/8 CONFIRMED 보유) ──
r4 = engine.create_reservation_request(
    "PT-2026-0001", "PRG-BASIC", "2026-07-08", "08:30",
    "SLOT-20260708-0830-A", "WEB", "PATIENT", data_dir=D)
check("동일 환자 동일일자 중복 차단", not r4["success"] and r4["verdict"] == "DUPLICATED", "; ".join(r4["reasons"])[:60])

# ── 5. FULL Slot 차단 + 대기예약 전환 ──
r5 = engine.create_reservation_request(
    "PT-2026-0004", "PRG-SMART", "2026-07-08", "09:00",
    "SLOT-20260708-0900-A", "WEB", "PATIENT", data_dir=D)
check("FULL Slot 예약 차단", not r5["success"] and r5["verdict"] == "FULL")
check("차단 시 대체 Slot 제공 (≤5)", 0 < len(r5["alternatives"]) <= 5, f"{len(r5['alternatives'])}개")
r5w = engine.create_reservation_request(
    "PT-2026-0004", "PRG-SMART", "2026-07-08", "09:00",
    "SLOT-20260708-0900-A", "WEB", "PATIENT", data_dir=D, allow_waiting=True)
check("FULL Slot 대기예약(WAITING) 전환", r5w["success"] and r5w["reservation"]["status"] == "WAITING",
      f"waitingCount={slot('SLOT-20260708-0900-A')['waitingCount']}")

# ── 6. BLOCKED / HOLD Slot 차단 ──
r6 = engine.create_reservation_request(
    "PT-2026-0002", "PRG-BASIC", "2026-07-20", "09:00",
    "SLOT-20260720-0900-A", "WEB", "PATIENT", data_dir=D)
check("BLOCKED Slot 예약 차단", not r6["success"] and r6["verdict"] == "BLOCKED")
r6h = engine.validate_slot("SLOT-20260715-1000-A", "PT-2026-0002", "2026-07-15", data_dir=D)
check("HOLD Slot 판정", r6h["verdict"] == "HOLD")

# ── 7. 잘못된 상태 전이 차단 ──
check("전이표: COMPLETED→CONFIRMED 불가", not sm.can_transition("COMPLETED", "CONFIRMED"))
check("전이표: REQUESTED→COMPLETED 불가", not sm.can_transition("REQUESTED", "COMPLETED"))
check("전이표: CONFIRMED→NO_SHOW 가능", sm.can_transition("CONFIRMED", "NO_SHOW"))
check("전이표: CHANGED→PENDING_APPROVAL 가능", sm.can_transition("CHANGED", "PENDING_APPROVAL"))
try:
    engine.approve_reservation(RID1, "USR-0002", data_dir=D)  # CANCELLED 예약 재승인 시도
    check("취소건 재승인 차단 + 감사기록", False, "예외 미발생")
except sm.InvalidTransitionError:
    logs = loader.load_entity("AuditLog", D)
    check("취소건 재승인 차단 + 감사기록",
          any(l["action"] == "INVALID_TRANSITION" and l["entityId"] == RID1 for l in logs))

# ── 8. NO_SHOW (CONFIRMED에서만) ──
r8 = engine.create_reservation_request(
    "PT-2026-0003", "PRG-BASIC", "2026-07-10", "08:30",
    "SLOT-20260710-0830-A", "PHONE", "USR-0002", data_dir=D)
RID8 = r8["reservation"]["id"]
try:
    engine.mark_no_show(RID8, "USR-0002", data_dir=D)  # PENDING 상태에서 노쇼 시도
    check("PENDING 상태 노쇼 차단", False, "예외 미발생")
except sm.InvalidTransitionError:
    check("PENDING 상태 노쇼 차단", True)
engine.approve_reservation(RID8, "USR-0002", data_dir=D)
rec8 = engine.mark_no_show(RID8, "USR-0002", data_dir=D)
check("CONFIRMED → NO_SHOW 전환", rec8["status"] == "NO_SHOW")

# ── 9. 예약 거절 ──
r9 = engine.create_reservation_request(
    "PT-2026-0002", "PRG-BASIC", "2026-07-21", "09:00",
    "SLOT-20260721-0900-A", "AI_ASSISTANT", "USR-9000", data_dir=D)
rec9 = engine.reject_reservation(r9["reservation"]["id"], "USR-0002", "QA 테스트 거절", data_dir=D)
check("직원 거절 → REJECTED + Slot 복구", rec9["status"] == "REJECTED"
      and slot("SLOT-20260721-0900-A")["status"] == "AVAILABLE")

# ── 10. 예약 변경 (CONFIRMED → CHANGED → PENDING_APPROVAL) ──
r10 = engine.create_reservation_request(
    "PT-2026-0002", "PRG-SMART", "2026-07-22", "09:00",
    "SLOT-20260722-0900-A", "PHONE", "USR-0002", data_dir=D)
RID10 = r10["reservation"]["id"]
engine.approve_reservation(RID10, "USR-0002", data_dir=D)
r10c = engine.change_reservation(RID10, "SLOT-20260723-1000-A", "2026-07-23", "10:00",
                                 "USR-0002", "수검자 요청", data_dir=D)
check("예약 변경 → 재승인 대기", r10c["success"] and r10c["reservation"]["status"] == "PENDING_APPROVAL"
      and len(r10c["reservation"]["changeHistory"]) == 1)
check("변경 후 기존/신규 Slot 상태", slot("SLOT-20260722-0900-A")["status"] == "AVAILABLE"
      and slot("SLOT-20260723-1000-A")["status"] == "HOLD")

# ── 11. 정원 도달 시 SLOT_FULL (정원 1 슬롯) ──
r11 = engine.create_reservation_request(
    "PT-2026-0001", "PRG-VIP", "2026-07-27", "09:00",
    "SLOT-20260727-0900-A", "WEB", "PATIENT", data_dir=D)
engine.approve_reservation(r11["reservation"]["id"], "USR-0002", data_dir=D)
check("정원 도달 시 Slot FULL", slot("SLOT-20260727-0900-A")["status"] == "FULL")
r11b = engine.create_reservation_request(
    "PT-2026-0004", "PRG-VIP", "2026-07-27", "09:00",
    "SLOT-20260727-0900-A", "WEB", "PATIENT", data_dir=D)
check("FULL 전환 후 신규 신청 차단", not r11b["success"] and r11b["verdict"] == "FULL")

# ── 12. 대체시간 추천 ──
alts = recommend_alternative_slots("2026-07-08", "09:00", "PRG-BASIC", data_dir=D)
check("대체 Slot 최대 5개 추천", 0 < len(alts) <= 5, f"{len(alts)}개: {[a['id'] for a in alts[:3]]}...")
check("추천 Slot 전부 AVAILABLE", all(a["status"] == "AVAILABLE" for a in alts))
dists = [abs((__import__('datetime').datetime.strptime(a['date'], '%Y-%m-%d').date()
              - __import__('datetime').date(2026, 7, 8)).days) for a in alts]
check("추천 정렬: 요청일 가까운 순", dists == sorted(dists), f"날짜거리={dists}")

# ── 13. 감사로그 생성 확인 ──
logs = loader.load_entity("AuditLog", D)
actions = {l["action"] for l in logs}
required_events = {"RESERVATION_REQUESTED", "RESERVATION_APPROVED", "RESERVATION_CANCELLED",
                   "RESERVATION_REJECTED", "RESERVATION_CHANGED", "SLOT_HELD", "SLOT_RELEASED",
                   "SLOT_FULL", "INVALID_TRANSITION", "DUPLICATED_REJECTED"}
check("감사로그 누적 기록", len(logs) > audit_before, f"{audit_before} → {len(logs)}건")
check("표준 이벤트 10종 전부 발생", required_events <= actions,
      f"누락: {sorted(required_events - actions) or '없음'}")

# ── 14. Sprint A Validator 재사용 — 최종 무결성 ──
result = validator.validate_all(loader.load_all(D))
check("전체 데이터 무결성 (Validator 재사용)", len(result["errors"]) == 0,
      f"오류 {len(result['errors'])}건, 경고 {len(result['warnings'])}건")
for e in result["errors"][:5]:
    print(f"    [오류] {e}")

# ── 원본 data/ 불변 확인 ──
orig = loader.load_entity("Reservation", ROOT / "data")
check("원본 data/ 미변경 확인", len(orig) == 5, f"원본 예약 {len(orig)}건 유지")

# ── 결과 저장 ──
out = Path(__file__).parent / "sprint_b_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\n총 {len(results)}건 중 PASS {len(results) - fails} / FAIL {fails}")
print(f"결과 저장: {out}")
sys.exit(1 if fails else 0)
