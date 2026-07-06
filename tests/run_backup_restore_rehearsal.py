# -*- coding: utf-8 -*-
"""
CSHSP 백업·복구 리허설 — Sprint I
backup_policy.md의 복구 절차를 자동 리허설한다 (원본 data/는 건드리지 않음).

절차: ① 운영 사본 생성 → ② 백업 스냅샷 → ③ 손상 시뮬레이션(파일 절단/파괴)
     → ④ 손상 감지 → ⑤ 손상본 보존(data_broken) → ⑥ 스냅샷 복원 → ⑦ validator 0오류
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "core"))

import core_data_loader as loader  # noqa: E402
import data_validator as validator  # noqa: E402

BASE = Path(__file__).parent / "rehearsal_sandbox"
if BASE.exists():
    shutil.rmtree(BASE)
DATA = BASE / "data"          # 운영 data 역할 (사본)
BACKUP = BASE / "backup"      # 스냅샷 보관

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


# ① 운영 사본 생성 (원본 보호)
shutil.copytree(ROOT / "data", DATA)
check("운영 사본 생성", (DATA / "reservations.json").exists())

# ② 백업 스냅샷 (backup_policy.md 일일 스냅샷 방식)
snap = BACKUP / datetime.now().strftime("%Y%m%d")
shutil.copytree(DATA, snap)
n_files = len(list(snap.glob("*.json")))
check("백업 스냅샷 생성", n_files >= 20, f"{n_files}개 파일")

# ③ 손상 시뮬레이션: 핵심 파일 2개를 서로 다른 방식으로 파괴
(DATA / "reservations.json").write_text('{"entity": "Reservation", "records": [ {"id": "RSV-', encoding="utf-8")  # 절단
(DATA / "slots.json").write_text("\x00\x00CORRUPTED\x00", encoding="utf-8")  # 바이너리 오염
check("손상 시뮬레이션 주입", True, "reservations(절단) + slots(오염)")

# ④ 손상 감지 (Failure Manual B-2)
damaged = []
for f in sorted(DATA.glob("*.json")):
    try:
        json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        damaged.append(f.name)
check("손상 감지", damaged == ["reservations.json", "slots.json"], f"감지: {damaged}")

# ⑤ 손상본 보존 (삭제 금지 원칙)
broken_dir = BASE / f"data_broken_{datetime.now().strftime('%Y%m%d%H%M%S')}"
shutil.move(str(DATA), str(broken_dir))
check("손상본 보존 (data_broken)", broken_dir.exists() and not DATA.exists())

# ⑥ 스냅샷 복원
shutil.copytree(snap, DATA)
restored_ok = True
try:
    json.loads((DATA / "reservations.json").read_text(encoding="utf-8"))
    json.loads((DATA / "slots.json").read_text(encoding="utf-8"))
except (json.JSONDecodeError, UnicodeDecodeError):
    restored_ok = False
check("스냅샷 복원", restored_ok)

# ⑦ 무결성 검증 (validator 0오류) + 건수 대조
res = validator.validate_all(loader.load_all(DATA))
check("복원 후 validator 0오류", len(res["errors"]) == 0, f"오류 {len(res['errors'])}건, 경고 {len(res['warnings'])}건")
orig_counts = loader.summary(ROOT / "data")
restored_counts = loader.summary(DATA)
check("복원 데이터 건수 대조 (원본과 일치)", orig_counts == restored_counts,
      f"Reservation {restored_counts.get('Reservation')}건 등 20개 Entity 일치")
check("원본 data/ 미변경", len(loader.load_entity("Reservation", ROOT / "data")) == 5)

out = Path(__file__).parent / "backup_restore_rehearsal_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["단계", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, x, _ in results if x == "FAIL")
print(f"\n백업·복구 리허설 {len(results)}단계 중 PASS {len(results) - fails} / FAIL {fails}")
print(f"결과 저장: {out}")
sys.exit(1 if fails else 0)
