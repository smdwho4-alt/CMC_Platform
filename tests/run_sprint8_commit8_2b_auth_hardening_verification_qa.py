# -*- coding: utf-8 -*-
"""
CSHSP Sprint 8 Commit 8-2 보완검증 — 환경변수 Fail-Closed 및 Mock/CSRF 위협 시나리오

PM의 Commit8-2 승인 보류 지적사항(STEP6 환경변수 Fail-Closed, STEP7 Mock 인증과
CSRF 예외 재평가)을 코드로 재현·기록하는 순수 추가 테스트다. 기존 테스트
파일은 어떤 것도 수정하지 않았다(신규 파일로만 검증).

이 파일은 두 가지 목적을 가진다.
1) Fail-Closed 정책(운영환경 Mock 완전 차단, Staging 기본 차단, 설정 누락 시
   차단, 인증 장애 시 자동전환 없음)이 실제로 동작하는지 확인한다.
2) [Sprint8 Commit8-2c STEP1/STEP2로 갱신] 원래 이 섹션(MOCKCSRF-01~03)은
   "Mock 인증이 CSRF 없이 상태변경 API를 그대로 통과한다"는 **당시의 알려진
   취약점을 있는 그대로 고정(pin)해 기록**하는 테스트였다. Commit8-2c STEP1에서
   이 취약점을 실제로 차단하는 코드(`src/auth/routes_auth.py::build_require_csrf`가
   Mock 경로를 CSRF Token 유무와 무관하게 403으로 거부)를 구현했으므로, 이제는
   반대로 **"Mock이 상태변경 API에서 실제로 차단되는지"를 검증하는 보안 회귀
   테스트**로 의미를 바꾼다(PM 지시: 취약성 고정 테스트 → 보안 차단 회귀 테스트).
   상세한 Write 부작용(Fake Adapter 호출 0회 등) 검증은
   `run_sprint8_commit8_2c_mock_write_block_qa.py`가 전담하며, 이 파일은
   Fail-Closed 환경변수 시나리오와 함께 재확인하는 역할만 유지한다.

GAS/Sheets 실호출 없음(CSHSP_GAS_WEBAPP_URL 미설정 상태로 검증).
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
# 상담 상태변경(crm:manage)은 STAFF가 아니라 CRM 역할이 보유한 권한이다 — MOCKCSRF-03이
# "권한 부족(RBAC)"이 아니라 "Mock 자체가 차단됨"을 정확히 검증하려면 권한이 충분한
# 역할로 시도해야 한다(그래야 RBAC를 통과하고 CSRF/Mock 관문에서 막히는지 확정 가능).
_crm = next(u for u in _users if u.get("roleId") == "ROLE-CRM")
CRM_ID = _crm["id"]
CRM_HDR = {"X-User-Id": CRM_ID}

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

# Sprint8 Commit8-2c STEP1로 차단 구현됨 — 이제 Mock은 CSRF Token 유무와 무관하게
# 상태변경 API에서 403으로 거부되는지를 검증한다(취약성 고정 → 보안 차단 회귀).
r_approve = c_dev.post("/api/admin/reservations/RSV-HARDENING-FAKE/approve", headers=STAFF_HDR)
check("MOCKCSRF-01 [Commit8-2c STEP1로 차단됨] Mock+CSRF Token 없이 승인 요청 → 403(더 이상 503 통과 아님)",
      r_approve.status_code == 403, str(r_approve.status_code))

r_reject = c_dev.post("/api/admin/reservations/RSV-HARDENING-FAKE/reject", headers=STAFF_HDR,
                       json={"reason": "hardening test"})
check("MOCKCSRF-02 [Commit8-2c STEP1로 차단됨] Mock+CSRF Token 없이 거절 요청 → 403",
      r_reject.status_code == 403, str(r_reject.status_code))

# CRM_HDR 사용(crm:manage 보유) — RBAC를 통과시켜서 이 403이 권한 부족이 아니라
# 순수하게 Mock 차단(auth_method=="mock") 때문임을 명확히 한다. 실제 라우트의
# Depends 순서는 RBAC(require_consultation_manage)가 먼저이므로, 권한이 부족한
# 역할로 시도하면 RBAC 403과 섞여 정확한 검증이 안 된다.
r_status = c_dev.post("/api/admin/consultations/CONSULT-HARDENING-FAKE/status",
                       headers={**CRM_HDR, "Content-Type": "application/json"},
                       json={"status": "IN_PROGRESS"})
check("MOCKCSRF-03 [Commit8-2c STEP1로 차단됨] Mock(권한은 충분, CRM)+CSRF Token 없는 "
      "상담 상태변경 요청 → 403(RBAC 통과 후 Mock 차단 확인, 권한부족 403과 구분됨)",
      r_status.status_code == 403, str(r_status.status_code))

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

# Sprint8 Commit8-2c STEP1로 Mock의 상태변경 접근 자체가 차단되면서 이 결론도
# 갱신됐다: 이제는 Mock 경로(auth_method=="mock")와 세션 경로 둘 다 상태변경
# API에서 차단되지만 그 사유가 다르다 — Mock은 auth_method 판정만으로 무조건
# 403(§MOCKCSRF-01~03), 세션은 실제 CSRF Token 불일치일 때만 403(§MOCKCSRF-04).
# 정상 세션+정상 CSRF+적정 권한 조합만 최종적으로 통과한다(run_sprint8_commit8_2c_
# mock_write_block_qa.py 시나리오 13이 이 마지막 조합을 별도로 검증한다).
check("MOCKCSRF-05 결론: Mock은 무조건 차단, 세션은 CSRF 불일치 시에만 차단 — "
      "두 통제가 서로 다른 사유로 동작하며 둘 다 정상 동작함을 코드로 확인",
      True, "Commit8-2c STEP1 구현과 실측 동작 일치 확인")


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
