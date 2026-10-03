# -*- coding: utf-8 -*-
"""
Commit8-3b HMAC v2 Python/JS 교차검증 — 결과 비교기(Option B 가드 반영판)

python_output.json과 js_output.json을 벡터별로 비교해 세 가지 결과 중
하나로 분류한다:

- MATCH: Option B 가드가 입력을 통과시켰고(또는 가드 대상이 아니고),
  Python/JS의 payloadHash·canonical bytes·HMAC·검증 결과가 전부 일치함.
- RESOLVED_REJECTED: 과거에는 언어 간 불일치(UNRESOLVED)를 내던 입력이,
  Option B 가드를 거치면 **두 언어가 동일한 사유로 일관되게 거절**해
  서명 경로 자체에 도달하지 않음을 확인함(= 모호성이 "해소"됨).
- UNRESOLVED: 가드 판정이 두 언어 간에 다르거나, 가드를 통과했는데
  해시/서명이 불일치하거나, fixture가 예상한 가드 결과와 실제 결과가
  다른 경우 — 전부 재검토가 필요한 상태로 보고한다(조용히 넘기지 않음).

이 스크립트의 **exit code 0은 "현재 분류 기준을 충족했다"는 뜻일 뿐**,
payload 정규화 계약 전체가 운영 정책으로 확정됐다는 뜻이 아니다
(CROSS_VALIDATION_REPORT.md 상단 고지 재확인).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent

FIELDS_TO_COMPARE = [
    "payloadNormalizationResult",
    "payloadUtf8Hex",
    "payloadHash",
    "canonicalString",
    "canonicalUtf8Hex",
    "signature",
    "signError",
]


def load(name):
    return json.loads((_HERE / name).read_text(encoding="utf-8"))


def _guard_results_consistent(gp, gj):
    """두 언어의 guardResult가 "같은 판정"인지 확인한다. accepted bool과
    (거절 시) reason이 같으면 일치로 본다. path/message의 정확한 문자열
    까지는 요구하지 않는다(거절 사유 코드가 핵심)."""
    if gp.get("accepted") != gj.get("accepted"):
        return False
    if gp.get("accepted") is False and gp.get("reason") != gj.get("reason"):
        return False
    return True


def classify_guard_only(vid, p, j, vec):
    gp = p.get("guardResult", {})
    gj = j.get("guardResult", {})
    consistent = _guard_results_consistent(gp, gj)
    expected_outcome = vec.get("expectedGuardOutcome")
    expected_reason = vec.get("expectedGuardReason")

    if not consistent:
        return "UNRESOLVED", f"가드 판정이 언어 간 불일치: py={gp} js={gj}"

    actual_outcome = "ACCEPTED" if gp.get("accepted") else "REJECTED"
    if expected_outcome and actual_outcome != expected_outcome:
        return "UNRESOLVED", f"fixture 기대 가드결과({expected_outcome})와 실제({actual_outcome}) 불일치"
    if expected_reason and gp.get("reason") != expected_reason:
        return "UNRESOLVED", f"fixture 기대 거절사유({expected_reason})와 실제({gp.get('reason')}) 불일치"

    if actual_outcome == "REJECTED":
        return "RESOLVED_REJECTED", f"양쪽 언어 모두 동일 사유({gp.get('reason')})로 일관되게 거절"
    return "MATCH", "양쪽 언어 모두 가드 통과(ACCEPTED)로 일치"


def classify_normal(vid, p, j, vec):
    gp = p.get("guardResult", {})
    gj = j.get("guardResult", {})
    consistent = _guard_results_consistent(gp, gj)
    expected_outcome = vec.get("expectedGuardOutcome")

    if not consistent:
        return "UNRESOLVED", f"가드 판정이 언어 간 불일치: py={gp} js={gj}"

    actual_outcome = "ACCEPTED" if gp.get("accepted") else "REJECTED"

    if actual_outcome == "REJECTED":
        if expected_outcome == "REJECTED":
            return "RESOLVED_REJECTED", f"가드가 서명 경로 진입 전 일관되게 거절({gp.get('reason')}) — 과거 해시 불일치 쟁점이 더 이상 발생하지 않음"
        return "UNRESOLVED", f"가드가 예상(ACCEPTED) 밖으로 거절함({gp.get('reason')}) — 회귀 여부 확인 필요"

    # 가드 ACCEPTED — 기존 해시/canonical/서명/검증 결과 비교로 진행
    if expected_outcome == "REJECTED":
        return "UNRESOLVED", "가드가 예상(REJECTED)과 달리 통과시킴 — 가드 규칙 재검토 필요"

    field_diffs = [f for f in FIELDS_TO_COMPARE if p.get(f) != j.get(f)]
    verify_p = p.get("verifyResult")
    verify_j = j.get("verifyResult")
    verify_match = verify_p == verify_j

    if field_diffs or not verify_match:
        determinacy = vec.get("determinacy")
        if determinacy == "UNRESOLVED":
            # 가드를 거치지 않았다면 나타났을 예전 불일치 — 이 분기에
            # 도달한다는 것 자체가 이례적이다(가드 ACCEPTED인데 기존
            # UNRESOLVED 벡터라는 조합은 현재 fixture에 없음, 방어적 처리).
            return "UNRESOLVED", f"가드 통과 후에도 필드 불일치: {field_diffs}, verify_py={verify_p}, verify_js={verify_j}"
        return "UNRESOLVED", f"DETERMINED 벡터인데 불일치 발생(회귀): fields={field_diffs} verify_py={verify_p} verify_js={verify_j}"

    return "MATCH", f"가드 통과 + 해시/서명/검증 전부 일치(verify={verify_p})"


def main():
    fixtures = load("fixtures_v2.json")
    vec_by_id = {v["id"]: v for v in fixtures["vectors"]}
    py = {e["id"]: e for e in load("python_output.json")}
    js = {e["id"]: e for e in load("js_output.json")}

    report_lines = []
    counts = {"MATCH": 0, "RESOLVED_REJECTED": 0, "UNRESOLVED": 0}
    unresolved_ids = []

    for vid, vec in vec_by_id.items():
        p = py.get(vid)
        j = js.get(vid)
        if p is None or j is None:
            counts["UNRESOLVED"] += 1
            unresolved_ids.append(vid)
            report_lines.append(f"[{vid}] UNRESOLVED — MISSING in one output (py={p is not None}, js={j is not None})")
            continue

        if vec.get("guardOnly"):
            label, detail = classify_guard_only(vid, p, j, vec)
        else:
            label, detail = classify_normal(vid, p, j, vec)

        counts[label] += 1
        if label == "UNRESOLVED":
            unresolved_ids.append(vid)
        report_lines.append(f"[{vid}] {label} — {detail}")

    print("\n".join(report_lines))
    print()
    print(f"총 {len(vec_by_id)}개 벡터")
    print(f"MATCH: {counts['MATCH']}건")
    print(f"RESOLVED_REJECTED: {counts['RESOLVED_REJECTED']}건")
    print(f"UNRESOLVED: {counts['UNRESOLVED']}건" + (f" ({', '.join(unresolved_ids)})" if unresolved_ids else ""))
    print()
    print("주의: 이 exit code는 '현재 분류 기준 충족 여부'일 뿐, payload 정규화")
    print("계약이 운영 정책으로 확정됐다는 뜻이 아니다.")

    sys.exit(1 if counts["UNRESOLVED"] else 0)


if __name__ == "__main__":
    main()
