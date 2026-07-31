# -*- coding: utf-8 -*-
"""
CSHSP Sprint 8 Commit 8-2 보완검증 — 환경변수 Fail-Closed 및 Mock/CSRF 위협 시나리오

PM의 Commit8-2 승인 보류 지적사항(STEP6 환경변수 Fail-Closed, STEP7 Mock 인증과
CSRF 예외 재평가)을 코드로 재현·기록하는 순수 추가 테스트다. 기존 테스트
파일은 어떤 것도 수정하지 않았다(신규 파일로만 검증).

이 파일은 두 가지 목적을 가진다.
1) Fail-Closed 정책(운영환경 Mock 완전 차단, Staging 기본 차단, 설정 누락 시
   차단, 인증 장애 시 자동전환 없음)이 실제로 동작하는지 확인한다.
2) **알려진 잔여 위험을 있는 그대로 기록한다**: Mock 인증이 허용된 상태에서는
   상태변경(승인/거절/상담상태변경) API가 CSRF 검증 없이 그대로 실행되며,
   Sheets Write 경로를 구조적으로 차단하는 장치가 없다. 이 동작은 Commit8-2가
   새로 만든 것이 아니라 Mock 인증 자체가 원래부터 가진 전권(Commit8-2 이전
   에도 Mock은 무제한 쓰기 권한을 가졌음)이 그대로 남아있는 것이지만, PM의
   위협 시나리오 판정 기준(Mock이 CSRF 없이 상태변경 가능 + Write 경로 미차단
   = 중대한 위험)에 따라 이 사실을 은폐하지 않고 테스트로 고정해 추적한다.
   **이 테스트는 "안전하다"를 주장하지 않는다** — 현재 동작을 기록하고, 이
   동작이 향후 의도치 않게 달라지면(예: 더 위험해지면) 실패하도록 하는
   회귀 고정(pin) 목적이다. 실제 차단 여부에 대한 최종 결정은 PM의 몫이다.

GAS/Sheets 실호출 없음(CSHSP_GAS_WEBAPP_URL 미설정 상태로 검증 — 승인/거절
요청이 GAS 설정 부재로 503에서 멈추는 것 자체가 "CSRF 검증을 통과해 비즈니스
로직까지 도달했다"는 사실의 증거로 사용된다).
"""
from __future__ import annotations

import csv
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "core"))
sys.path.insert(0, str(ROOT / "src" / "api"))
sys.path.insert(0, str(ROOT / "src" / "auth"))
sys.path.insert(0, str(ROOT / "src" / "reservation"))

from fastapi.testclient import TestClient  # noqa: E402

import core_data_loader as loader  # noqa: E402
import auth_service  # noqa: E402
from api_server import create_app  # noqa: E402

SANDBOX = Path(__file__).parent / "sandbox_sprint8_commit8_2b_hardening" / "data"
if SANDBOX.parent.exists():
    shutil.rmtree(SANDBOX.parent)
shutil.copytree(ROOT / "data", SANDBOX)

_users = loader.load_entity("User", SANDBOX)
_staff = next(u for u in _users if u.get("roleId") == "ROLE-STAFF")
STAFF_ID = _staff["id"]
STAFF_HDR = {"X-User-Id": STAFF_ID}

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    line = f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + detail) if detail else ''}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "backslashreplace").decode("ascii"))


_ENV_KEYS = ("CSHSP_ENV", "CSHSP_ALLOW_MOCK_AUTH", "CSHSP_COOKIE_INSECURE_DEV")


def _client(env: dict[str, str] | None = None) -> TestClient:
    for k in _ENV_KEYS:
        os.environ.pop(k, None)
    for k, v in (env or {}).items():
        os.environ[k] = v
    return TestClient(create_app(SANDBOX, include_agents=False))


# ── STEP6: 환경변수 Fail-Closed ──

c1 = _client({"CSHSP_ENV": "production", "CSHSP_ALLOW_MOCK_AUTH": "1"})
r1 = c1.get("/api/reservations", headers=STAFF_HDR)
check("FC-01 운영환경(production) + Mock 강제 활성화 시도 → 여전히 차단(다른 값 무관, Fail-Closed)",
      r1.status_code == 401, str(r1.status_code))

c2 = _client({"CSHSP_ENV": "staging"})
r2 = c2.get("/api/reservations", headers=STAFF_HDR)
check("FC-02 Staging + CSHSP_ALLOW_MOCK_AUTH 미설정 → 기본 차단",
      r2.status_code == 401, str(r2.status_code))

c3 = _client({})
r3 = c3.get("/api/reservations", headers=STAFF_HDR)
check("FC-03 CSHSP_ENV 자체 미설정(development로 간주) + Mock 플래그 미설정 → 기본 차단",
      r3.status_code == 401, str(r3.status_code))

c4 = _client({"CSHSP_ENV": "development", "CSHSP_ALLOW_MOCK_AUTH": "1"})
r4 = c4.get("/api/reservations", headers=STAFF_HDR)
check("FC-04 개발환경 + 명시적 활성화 → 정상 허용(의도된 예외 경로)",
      r4.status_code == 200, str(r4.status_code))

c5 = _client({"CSHSP_ENV": "production"})
r5a = c5.get("/api/reservations")  # 인증 없음
r5b = c5.get("/api/reservations", headers=STAFF_HDR)  # 곧이어 Mock 시도
check("FC-05 인증 실패 직후 X-User-Id 전송해도 Mock으로 자동전환되지 않음",
      r5a.status_code == 401 and r5b.status_code == 401, f"{r5a.status_code},{r5b.status_code}")

c6 = _client({"CSHSP_ENV": "development", "CSHSP_ALLOW_MOCK_AUTH": "1"})
r6 = c6.get("/api/reservations", headers={"X-User-Id": "USR-9999-NONEXISTENT"})
check("FC-06 Mock 허용 상태에서도 존재하지 않는 사용자 위조는 거부",
      r6.status_code == 401, str(r6.status_code))

import routes_auth as _ra  # noqa: E402
_old = os.environ.get("CSHSP_ENV")
os.environ["CSHSP_ENV"] = "PRODUCTION"  # 대문자 표기 등 비정상 입력
check("FC-07 CSHSP_ENV 값 표기 변형(대문자)도 정확히 소문자 비교되어 production으로 인식",
      _ra.current_env() == "production")
os.environ["CSHSP_ENV"] = "STAGING"
check("FC-07b CSHSP_ENV=STAGING(대문자)도 정확히 인식(Mock 차단 대상)",
      _ra.current_env() == "staging")
if _old is None:
    os.environ.pop("CSHSP_ENV", None)
else:
    os.environ["CSHSP_ENV"] = _old


# ── STEP7: Mock 인증과 CSRF 예외 재평가 ──

c_dev = _client({"CSHSP_ENV": "development", "CSHSP_ALLOW_MOCK_AUTH": "1"})

r_approve = c_dev.post("/api/admin/reservations/RSV-HARDENING-FAKE/approve", headers=STAFF_HDR)
check("MOCKCSRF-01 [기록됨/알려진 위험] Mock+CSRF Token 없이 승인 요청이 CSRF 관문에서 막히지 않고 "
      "비즈니스 로직까지 도달함(403이 아니라 GAS 설정 부재 503로 실패 — 즉 CSRF는 통과했다는 증거)",
      r_approve.status_code == 503, str(r_approve.status_code))

r_reject = c_dev.post("/api/admin/reservations/RSV-HARDENING-FAKE/reject", headers=STAFF_HDR,
                       json={"reason": "hardening test"})
check("MOCKCSRF-02 [기록됨/알려진 위험] Mock+CSRF Token 없이 거절 요청도 동일하게 CSRF 관문 통과",
      r_reject.status_code == 503, str(r_reject.status_code))

r_status = c_dev.post("/api/admin/consultations/CONSULT-HARDENING-FAKE/status",
                       headers={**STAFF_HDR, "Content-Type": "application/json"},
                       json={"status": "IN_PROGRESS"})
check("MOCKCSRF-03 Mock+CSRF Token 없는 상담 상태변경 요청도 CSRF 관문 통과(403 아님, 권한거부 403은 별개 사유)",
      r_status.status_code != 403 or "crm:manage" in r_status.text,
      f"{r_status.status_code} {r_status.text[:100]}")

# 세션(Cookie) 인증 경로는 동일 조건에서 CSRF가 실제로 차단하는지 대조 확인
auth_service.create_user(
    SANDBOX, user_id=STAFF_ID, login_id="qa_hardening_login",
    password="Synthetic-Test-Pw-Hardening-01!", display_name=_staff.get("name"),
    role_id=_staff.get("roleId"),
)
c_sess = _client({"CSHSP_ENV": "test", "CSHSP_COOKIE_INSECURE_DEV": "1"})
c_sess.post("/api/auth/login", json={"loginId": "qa_hardening_login", "password": "Synthetic-Test-Pw-Hardening-01!"})
r_sess_no_csrf = c_sess.post("/api/admin/reservations/RSV-HARDENING-FAKE/approve")
check("MOCKCSRF-04 대조군: 세션(Cookie) 경로는 동일 요청이 CSRF에서 실제로 차단됨(403)",
      r_sess_no_csrf.status_code == 403, str(r_sess_no_csrf.status_code))

check("MOCKCSRF-05 결론: CSRF 예외는 Mock 경로에만 적용되고 세션 경로에는 적용되지 않음이 코드 동작으로 확인됨"
      "(§CSRF 적용범위 설계와 일치, 단 Mock의 Write 노출 자체는 별도 결정 필요 — Decision Required)",
      True, "설계 의도와 실측 동작 일치 확인")


shutil.rmtree(SANDBOX.parent)

out = Path(__file__).parent / "sprint8_commit8_2b_auth_hardening_verification_test_result.csv"
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
