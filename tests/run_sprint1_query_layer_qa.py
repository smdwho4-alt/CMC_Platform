# -*- coding: utf-8 -*-
"""
CSHSP Sprint 1 — Commit 1(조회 계층) 테스트 러너

대상:
- src/services/pii_mask.py (마스킹 유틸리티, PM 승인 기준 §12)
- src/services/sheets_readonly_service.py (GAS 조회 전용 연동, 실네트워크 호출 없이
  Fake Session으로 GAS 응답을 흉내내어 검증한다 — 운영 Sheets/GAS는 전혀 호출하지 않음)

결과는 tests/sprint1_query_layer_test_result.csv 로 저장한다.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "services"))

import pii_mask  # noqa: E402
import sheets_readonly_service as svc  # noqa: E402

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


# ── 1. pii_mask 단위 테스트 ─────────────────────────────
check("mask_name 3글자", pii_mask.mask_name("홍길동") == "홍○○", pii_mask.mask_name("홍길동"))
check("mask_name 2글자", pii_mask.mask_name("김철") == "김○", pii_mask.mask_name("김철"))
check("mask_name 1글자(마스킹 불가, 원본유지)", pii_mask.mask_name("김") == "김")
check("mask_name 빈값", pii_mask.mask_name("") == "")

check("mask_birth 정상포맷", pii_mask.mask_birth("1980-05-05") == "1980-**-**", pii_mask.mask_birth("1980-05-05"))
check("mask_birth 비정상포맷 전체마스킹", pii_mask.mask_birth("abc") == "****-**-**")
check("mask_birth 빈값", pii_mask.mask_birth("") == "****-**-**")

check("mask_phone 하이픈포맷", pii_mask.mask_phone("010-1234-5678") == "010-****-5678", pii_mask.mask_phone("010-1234-5678"))
check("mask_phone 숫자만", pii_mask.mask_phone("01012345678") == "010-****-5678")
check("mask_phone 짧은값", pii_mask.mask_phone("123") == "***-****-****")

check("mask_email 정상포맷", pii_mask.mask_email("user1234@example.com") == "use***@example.com", pii_mask.mask_email("user1234@example.com"))
check("mask_email @없음 원본유지", pii_mask.mask_email("invalid") == "invalid")

_raw = {
    "reservationNo": "20260726-0001", "name": "홍길동", "birth": "1980-05-05",
    "phone": "010-1234-5678", "program": "SMART", "wishDate": "2026-08-01",
    "wishTime": "09:00", "status": "PENDING_APPROVAL", "note": "특이사항없음",
    "manager": "김담당", "estimatedCost": "500000",  # 화이트리스트 밖 필드 — 결과에 없어야 함
}
_masked = pii_mask.build_masked_reservation(_raw)
check("build_masked_reservation: 이름 마스킹", _masked.get("name") == "홍○○")
check("build_masked_reservation: 생년월일 마스킹", _masked.get("birth") == "1980-**-**")
check("build_masked_reservation: 휴대전화 마스킹", _masked.get("phone") == "010-****-5678")
check("build_masked_reservation: 비PII 필드 포함", _masked.get("program") == "SMART" and _masked.get("status") == "PENDING_APPROVAL")
check("build_masked_reservation: 화이트리스트 밖 필드(manager) 제외됨", "manager" not in _masked)
check("build_masked_reservation: 화이트리스트 밖 필드(estimatedCost) 제외됨", "estimatedCost" not in _masked)
check("build_masked_reservation: 원본 raw phone 값이 결과에 그대로 노출되지 않음",
      "010-1234-5678" not in str(_masked.values()))


# ── 2. sheets_readonly_service 단위 테스트 (Fake Session, 실네트워크 없음) ──
class _FakeResponse:
    def __init__(self, payload: dict, status_ok: bool = True):
        self._payload = payload
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise svc.requests.exceptions.HTTPError("fake http error")

    def json(self):
        return self._payload


class _FakeSession:
    """운영 GAS/Sheets를 전혀 호출하지 않는 Fake — .get() 호출 인자를 기록만 한다."""

    def __init__(self, response_payload: dict, status_ok: bool = True):
        self._payload = response_payload
        self._status_ok = status_ok
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params or {}))
        return _FakeResponse(self._payload, self._status_ok)


_ENV_KEY = svc.GAS_WEBAPP_URL_ENV
_saved_env = os.environ.get(_ENV_KEY)

# 2-1. 환경변수 미설정 시 명시적 예외
os.environ.pop(_ENV_KEY, None)
try:
    svc.list_reservations()
    check("환경변수 미설정 시 SheetsIntegrationNotConfigured 발생", False, "예외가 발생하지 않음")
except svc.SheetsIntegrationNotConfigured:
    check("환경변수 미설정 시 SheetsIntegrationNotConfigured 발생", True)
except Exception as e:  # noqa: BLE001
    check("환경변수 미설정 시 SheetsIntegrationNotConfigured 발생", False, f"다른 예외 발생: {e!r}")

# 이후 테스트를 위해 임시(Fake) URL 설정 — 실제 네트워크 호출은 FakeSession이 가로채므로
# 이 값으로 실제 요청이 나가지 않는다.
os.environ[_ENV_KEY] = "https://example.invalid/fake-gas-endpoint-not-called"

# 2-2. list_reservations 정상 케이스
fake_list = _FakeSession({"ok": True, "count": 1, "data": [dict(_raw)]})
data = svc.list_reservations(status="PENDING_APPROVAL", session=fake_list)
check("list_reservations 정상 파싱", len(data) == 1 and data[0]["reservationNo"] == "20260726-0001")
check("list_reservations 허용 필터만 전달(status)", fake_list.calls[0][1].get("status") == "PENDING_APPROVAL")
check("list_reservations action=list 전달", fake_list.calls[0][1].get("action") == "list")

# 2-3. get_reservation 정상 케이스
fake_get = _FakeSession({"ok": True, "data": dict(_raw)})
one = svc.get_reservation("20260726-0001", session=fake_get)
check("get_reservation 정상 파싱", one is not None and one["name"] == "홍길동")
check("get_reservation no 파라미터 전달", fake_get.calls[0][1].get("no") == "20260726-0001")

# 2-4. get_reservation 빈 값 방어
try:
    svc.get_reservation("", session=fake_get)
    check("get_reservation 빈 예약번호 ValueError", False, "예외 미발생")
except ValueError:
    check("get_reservation 빈 예약번호 ValueError", True)

# 2-5. GAS 오류 응답(ok:false) → SheetsIntegrationError
fake_err = _FakeSession({"ok": False, "error": "예약 없음", "code": 404})
try:
    svc.get_reservation("NOT-EXIST", session=fake_err)
    check("GAS 오류 응답 시 SheetsIntegrationError", False, "예외 미발생")
except svc.SheetsIntegrationError as e:
    check("GAS 오류 응답 시 SheetsIntegrationError", "예약 없음" in str(e), str(e))

# 2-6. 쓰기 액션 직접 호출 차단(방어 로직) — 조회 전용 서비스가 create 등을 절대 호출하지 않음을 검증
try:
    svc._call_gas("create", {}, session=fake_list)  # noqa: SLF001 (내부 방어 로직 검증 목적)
    check("쓰기 action(create) 호출 차단", False, "예외 미발생 — 쓰기 액션이 허용됨(위험)")
except ValueError:
    check("쓰기 action(create) 호출 차단", True)

# 2-7. ping
fake_ping = _FakeSession({"ok": True, "message": "CMC Sheets API v3 정상"})
p = svc.ping(session=fake_ping)
check("ping 정상 파싱", p.get("ok") is True)

# 환경변수 원복
if _saved_env is None:
    os.environ.pop(_ENV_KEY, None)
else:
    os.environ[_ENV_KEY] = _saved_env


# ── 결과 저장 ─────────────────────────────────────────
out = Path(__file__).parent / "sprint1_query_layer_test_result.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["테스트명", "결과", "상세"])
    w.writerows(results)

fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\n총 {len(results)}건 중 PASS {len(results) - fails} / FAIL {fails}")
print(f"결과 저장: {out}")
sys.exit(1 if fails else 0)
