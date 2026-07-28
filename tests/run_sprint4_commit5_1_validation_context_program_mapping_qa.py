# -*- coding: utf-8 -*-
"""
CSHSP Sprint 4 Commit 5-1 — Validation Context + Program Mapping Helper 테스트 러너

대상: src/reservation/reservation_engine.py
- validate_slot()에 추가된 validation_context 파라미터(기본값 "slot_generation")
  및 _CONTEXT_DISABLED_CHECKS 조회 테이블
- 신규 헬퍼 resolve_program() (Program.code 완전일치 → Program.name 완전일치 → None)

PM 지시(Sprint 4 Commit 5-1, PM Final Alignment Fix 반영) 근거:
- validate_slot() 기존 동작은 100% 동일해야 한다(기본값 slot_generation, 기존 호출자
  create_reservation_request()/change_reservation() 영향 없음)
- PATIENT_DUPLICATE(환자 동일일자 중복) 검사를 제외하는 컨텍스트는 reservation_approval
  하나뿐이다. simulation은 slot_generation과 동일하게 전체 검사(PATIENT_DUPLICATE 포함)를
  수행한다 — PM 최종 정책(초기 구현은 simulation도 제외했으나 PM 검토로 수정됨)
- 알 수 없는 컨텍스트 문자열은 Safe Default(전체 검사, 검증 완화 없음)로 처리한다
  — "Fail Closed"가 아니라 "이미 검증된 가장 안전한 기본 동작"이라는 의미
- resolve_program()은 Fuzzy/부분일치 없이 code→name 순서의 완전일치만 수행
- Health Check에서 발견된 '온김에검진'(Program.name과만 일치, Program.code는 ONKIME)
  케이스가 실제로 매핑되어야 한다

원본 data/ 보호를 위해 사본 샌드박스에서 실행. GAS/Sheets 호출 없음(순수 엔진 함수 테스트).
결과: tests/sprint4_commit5_1_validation_context_program_mapping_test_result.csv
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
import reservation_engine as engine  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint4_commit5_1" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)
D = SANDBOX

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    line = f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "backslashreplace").decode("ascii"))


# ── 0. 고정 파라미터 (샌드박스 원본 data/ 실제 레코드 기준) ──
# RSV-20260702-0002: patientId=PT-2026-0002, reservationDate=2026-07-10, status=PENDING_APPROVAL(ACTIVE_STATUSES)
# SLOT-20260710-0830-A: date=2026-07-10, status=AVAILABLE, capacity=6/reservedCount=2 → 정원 여유 있음
DUP_PATIENT = "PT-2026-0002"
DUP_DATE = "2026-07-10"
DUP_SLOT = "SLOT-20260710-0830-A"

# ── 1. Program Mapping Helper: resolve_program() ──
CODE_MATCHES = ["BASIC", "SMART", "VIP", "PREMIUM", "YOUNG", "ONKIME"]
for code in CODE_MATCHES:
    p = engine.resolve_program(code, data_dir=D)
    check(f"resolve_program('{code}') → Program.code 완전일치로 매핑 성공", p is not None and p.get("code") == code)

p_name = engine.resolve_program("온김에검진", data_dir=D)
check("resolve_program('온김에검진') → Program.name 완전일치로 매핑 성공(Health Check 반영)",
      p_name is not None and p_name.get("name") == "온김에검진" and p_name.get("code") == "ONKIME")

p_none = engine.resolve_program("존재하지않는프로그램", data_dir=D)
check("resolve_program(미존재값) → None 반환", p_none is None)

p_empty = engine.resolve_program("", data_dir=D)
check("resolve_program('') → None 반환(빈 입력)", p_empty is None)

p_null = engine.resolve_program(None, data_dir=D)
check("resolve_program(None) → None 반환", p_null is None)

# code 우선순위 확인: code가 다른 Program의 name과 우연히 같은 경우는 없지만,
# 정상 code 매칭이 name 루프까지 가지 않고 먼저 종료되는지 구조적으로 재확인(정적 검사)
_SRC = (ROOT / "src" / "reservation" / "reservation_engine.py").read_text(encoding="utf-8")
check("resolve_program() 구현에 code 매칭 루프가 name 매칭 루프보다 먼저 존재(코드 순서 확인)",
      _SRC.index('p.get("code") == program_input') < _SRC.index('p.get("name") == program_input'))
check("resolve_program()이 fuzzy/부분/포함 매칭을 쓰지 않음(in/startswith/re 미사용 정적 확인)",
      "in program_input" not in _SRC and "program_input in" not in _SRC.replace("if not program_input", ""))

# ── 2. Validation Context: 기본값(slot_generation)은 기존 동작과 100% 동일 ──
v_default = engine.validate_slot(DUP_SLOT, DUP_PATIENT, DUP_DATE, data_dir=D)
check("validation_context 생략(기본값 slot_generation) → 환자 동일일자 중복 검사로 DUPLICATED",
      v_default["verdict"] == "DUPLICATED")

v_explicit_default = engine.validate_slot(DUP_SLOT, DUP_PATIENT, DUP_DATE, data_dir=D,
                                           validation_context="slot_generation")
check("validation_context='slot_generation' 명시 → 생략했을 때와 동일 결과(DUPLICATED)",
      v_explicit_default["verdict"] == "DUPLICATED" and v_explicit_default == v_default)

# ── 3. Validation Context: reservation_approval — 환자 중복 검사만 제외 ──
v_approval = engine.validate_slot(DUP_SLOT, DUP_PATIENT, DUP_DATE, data_dir=D,
                                   validation_context="reservation_approval")
check("validation_context='reservation_approval' → 동일 조건에서 DUPLICATED가 아님(환자 중복 검사 제외됨)",
      v_approval["verdict"] != "DUPLICATED")
check("validation_context='reservation_approval' → 정원 여유 있는 AVAILABLE Slot이므로 AVAILABLE 판정",
      v_approval["verdict"] == "AVAILABLE")

# ── 4. Validation Context: simulation — PM 최종 정책(Commit 5-1 보완): 전체 검사 수행 ──
# PATIENT_DUPLICATE 검사를 제외하는 컨텍스트는 reservation_approval 하나뿐이다.
# simulation은 slot_generation과 동일하게 환자 동일일자 중복 검사를 그대로 수행한다.
v_sim = engine.validate_slot(DUP_SLOT, DUP_PATIENT, DUP_DATE, data_dir=D,
                              validation_context="simulation")
check("validation_context='simulation' → PATIENT_DUPLICATE 검사 수행됨(DUPLICATED, PM 최종 정책)",
      v_sim["verdict"] == "DUPLICATED")
check("validation_context='simulation' 결과가 'slot_generation'(기본값) 결과와 동일(둘 다 전체 검사)",
      v_sim == v_default)
check("validation_context='simulation' 결과가 'reservation_approval' 결과와 다름(simulation은 제외하지 않음)",
      v_sim != v_approval)

# ── 5. reservation_approval/simulation도 다른 검사는 그대로 수행(전체 무력화 아님) ──
# 존재하지 않는 Slot → INVALID는 컨텍스트와 무관하게 항상 발생해야 한다
v_invalid_slot = engine.validate_slot("SLOT-NOT-EXIST", DUP_PATIENT, DUP_DATE, data_dir=D,
                                       validation_context="reservation_approval")
check("reservation_approval 컨텍스트에서도 존재하지 않는 Slot → INVALID(다른 검사는 그대로 작동)",
      v_invalid_slot["verdict"] == "INVALID")

# BLOCKED(휴진일) Slot: SLOT-20260626-0830-A는 FULL, 대신 날짜 형식/휴진일 등은 별도 확인
# 정원마감(FULL) Slot에서 reservation_approval 컨텍스트라도 FULL은 그대로 차단되어야 한다
v_full = engine.validate_slot("SLOT-20260626-0830-A", DUP_PATIENT, "2026-06-26", data_dir=D,
                               validation_context="reservation_approval")
check("reservation_approval 컨텍스트에서도 FULL Slot은 그대로 FULL 차단(환자중복 외 검사는 무력화되지 않음)",
      v_full["verdict"] == "FULL")

# ── 6. 알 수 없는 validation_context 문자열 → Safe Default(전체 검사, 검증 완화 없음) ──
v_unknown = engine.validate_slot(DUP_SLOT, DUP_PATIENT, DUP_DATE, data_dir=D,
                                  validation_context="no_such_context")
check("알 수 없는 validation_context → PATIENT_DUPLICATE 포함 전체 검사 수행(DUPLICATED, Safe Default)",
      v_unknown["verdict"] == "DUPLICATED")
check("알 수 없는 validation_context 결과가 'slot_generation'(기본값) 결과와 동일(Safe Default = 이미 검증된 가장 안전한 동작)",
      v_unknown == v_default)

# ── 7. 기존 호출자 회귀 확인: create_reservation_request()/change_reservation() 시그니처·호출 불변 ──
check("create_reservation_request() 내부의 validate_slot() 호출에 validation_context 인자 없음(기존 동작 불변)",
      "v = validate_slot(slot_id, patient_id, requested_date, data_dir, program_id)" in _SRC)
check("change_reservation() 내부의 validate_slot() 호출에 validation_context 인자 없음(기존 동작 불변)",
      "v = validate_slot(new_slot_id, rec[\"patientId\"], new_date, data_dir," in _SRC)

# ── 8. Commit5-1 당시 절대 금지 사항 — Commit 5-2에서 PM 승인 하에 연동됨(이력 보존) ──
# 이 파일 최초 작성 시점(Commit 5-1)에는 이 4개 항목이 routes_admin_portal.py에
# "존재하지 않아야" 했다(Approval Pipeline 연동은 별도 Commit으로 분리). 이후
# Sprint4 Commit5-2(Approval Pipeline Policy Integration, PM 승인)에서 정확히 이
# 4가지를 연동하는 것이 그 Commit의 승인된 목표였으므로, 아래 4개 체크는 "없어야
# 한다"에서 "Commit5-2 이후 존재해야 한다"로 뒤집혔다 — 이 파일이 계속 재사용되는
# 회귀 스위트이므로 최신 승인 상태를 반영한다(과거 시점의 의미는 이 주석으로 보존).
_ROUTES_SRC = (ROOT / "src" / "api" / "routes_admin_portal.py").read_text(encoding="utf-8")
check("routes_admin_portal.py(Approval Pipeline)에 validation_context 연동됨(Commit5-2, PM 승인)",
      "validation_context" in _ROUTES_SRC)
check("routes_admin_portal.py에 resolve_program 연동됨(Commit5-2, PM 승인)",
      "resolve_program" in _ROUTES_SRC)
check("routes_admin_portal.py에 RESERVATION_PROGRAM_UNMAPPED 코드 존재(Commit5-2, PM 승인)",
      "RESERVATION_PROGRAM_UNMAPPED" in _ROUTES_SRC)
check("routes_admin_portal.py에 SLOT_POLICY_VALIDATION_FAILED 코드 존재(Commit5-2, PM 승인)",
      "SLOT_POLICY_VALIDATION_FAILED" in _ROUTES_SRC)

# ── 결과 저장 ──
out = Path(__file__).parent / "sprint4_commit5_1_validation_context_program_mapping_test_result.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트", "결과", "상세"])
    w.writerows(results)

total = len(results)
passed = sum(1 for _, r, _ in results if r == "PASS")
summary = f"TOTAL={total} PASS={passed} FAIL={total - passed}"
try:
    print(summary)
except UnicodeEncodeError:
    print(summary.encode("ascii", "backslashreplace").decode("ascii"))

if passed != total:
    sys.exit(1)
