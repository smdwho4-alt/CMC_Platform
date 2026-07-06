# -*- coding: utf-8 -*-
"""
CSHSP Sprint A 테스트 러너
- 20개 Entity JSON 로드 확인
- Core Data Loader 기능 확인 (get_by_id, 레거시 상태 변환, 방어 로직)
- Validation 전체 실행
- statistics.json 읽기 및 KPI 필드 확인
결과는 tests/sprint_a_test_result.csv 로 저장
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "core"))

import core_data_loader as loader  # noqa: E402
import data_validator as validator  # noqa: E402

results: list[tuple[str, str, str]] = []  # (테스트명, PASS/FAIL, 상세)


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


# 1. 20개 Entity 전체 로드
data = loader.load_all()
check("Entity 20개 정의 확인", len(loader.ENTITY_FILES) == 20, f"{len(loader.ENTITY_FILES)}개")
for entity, records in data.items():
    check(f"{entity} 로드", isinstance(records, list) and len(records) >= 2, f"{len(records)}건")

# 2. Loader 기능
rsv = loader.get_by_id("Reservation", "RSV-20260702-0001")
check("get_by_id 예약 조회", rsv is not None and rsv["status"] == "CONFIRMED",
      f"status={rsv['status'] if rsv else None}")
check("레거시 상태 변환", loader.normalize_legacy_status("예약접수") == "REQUESTED"
      and loader.normalize_legacy_status("CONFIRMED") == "CONFIRMED")
check("없는 파일 방어", loader.load_entity("Patient", data_dir=Path("Z:/없는폴더")) == [])
try:
    loader.load_entity("없는Entity")
    check("미등록 Entity 예외", False)
except loader.CoreDataError:
    check("미등록 Entity 예외", True)

# 3. Validation 전체 실행
result = validator.validate_all(data)
check("Validation 오류 0건", len(result["errors"]) == 0, f"오류 {len(result['errors'])}건, 경고 {len(result['warnings'])}건")
for e in result["errors"]:
    print(f"    [오류] {e}")
for w in result["warnings"]:
    print(f"    [경고] {w}")

# 4. 샘플 예약 데이터 상태값 검증
statuses = {r["status"] for r in data["Reservation"]}
check("예약 상태값 표준 준수", statuses <= set(loader.RESERVATION_STATUSES), f"사용된 상태: {sorted(statuses)}")
slot_statuses = {r["status"] for r in data["Slot"]}
check("Slot 상태값 표준 준수", slot_statuses <= set(loader.SLOT_STATUSES), f"사용된 상태: {sorted(slot_statuses)}")

# 5. statistics.json KPI 필드 확인
stats = data["Statistics"]
kpi_ok = all(
    all(k in s for k in ("totalExaminees", "totalRevenue", "achievementRate", "byType"))
    for s in stats
)
check("Statistics KPI 필드 확인", kpi_ok, f"{len(stats)}건 (기간: {', '.join(s['period'] for s in stats)})")

# 6. 개인정보 메타 확인 (PII 플래그)
pii_entities = [e for e in loader.ENTITY_FILES if loader.load_meta(e).get("containsPII")]
check("PII 플래그 지정 확인", len(pii_entities) > 0, f"PII Entity {len(pii_entities)}개: {', '.join(pii_entities)}")

# 결과 CSV 저장
out = Path(__file__).parent / "sprint_a_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\n총 {len(results)}건 중 PASS {len(results) - fails} / FAIL {fails}")
print(f"결과 저장: {out}")
sys.exit(1 if fails else 0)
