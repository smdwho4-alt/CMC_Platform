# -*- coding: utf-8 -*-
"""
Commit8-3b HMAC v2 Python/JS 교차검증 — Python 측 실행기

fixtures_v2.json/keys_v2.json을 읽어 실제 src/idempotency/signing_v2.py
(운영 후보 격리 구현)를 호출해 벡터별 중간값·최종값을 python_output.json에
기록한다. 합성 테스트 키만 사용하며 네트워크·GAS 접근 없음.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT / "src" / "idempotency"))

import signing_v2 as sv2  # noqa: E402
import payload_schema_guard as guard  # noqa: E402


def _flip_last_hex_char(hexstr: str) -> str:
    """서명 변조 규칙(Python/JS 공통): 마지막 문자가 '0'이면 '1'로,
    그 외에는 '0'으로 바꾼다 — 결정적이며 두 언어가 동일 규칙을 쓴다."""
    last = hexstr[-1]
    new_last = "1" if last == "0" else "0"
    return hexstr[:-1] + new_last


def _manual_payload_normalization(payload):
    """signing_v2.compute_payload_hash()와 동일한 절차를 harness가 독립적으로
    재현해 중간값(정렬된 JSON 문자열·UTF-8 hex)을 보고용으로 노출한다
    (signing_v2.py는 최종 hex digest만 반환하므로)."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    normalized = unicodedata.normalize("NFC", serialized)
    utf8_bytes = normalized.encode("utf-8")
    return normalized, utf8_bytes.hex(), hashlib.sha256(utf8_bytes).hexdigest()


def _build_registry(keys_cfg):
    registry = sv2.KeyRegistry()
    for k in keys_cfg["keys"]:
        registry.register(
            sv2.KeyRecord(
                key_id=k["key_id"], secret=k["secret"], state=k["state"],
                grace_expires_at=k.get("grace_expires_at"),
            )
        )
    return registry


def _run_guard_on_payload(payload):
    """**이미 파싱된 객체 경로**. payload 하나에 공통 타입 가드를
    적용해 결과를 dict로 반환한다. 통과하면 {"accepted": True}, 거절되면
    {"accepted": False, "reason": ..., "path": ...}. 이 경로는 "원문에
    소수점이 있었는가"를 구분하지 못한다는 한계가 있다(모듈 docstring
    재확인) — V04처럼 그 구분이 필요한 입력은 `_run_raw_guard()`를
    대신 써야 한다."""
    try:
        guard.validate_payload_schema_interim(payload)
        return {"accepted": True}
    except guard.PayloadSchemaUnresolvedError as e:
        return {"accepted": False, "reason": e.reason, "path": e.path}


def _run_raw_guard(raw_json_text):
    """**raw JSON 경로**. 중복 키 + 숫자 토큰 형식(소수점·지수 금지)을
    원시 텍스트 단계에서 함께 검사한다. V04(1.0 vs 1)처럼 "이미 파싱된
    객체 경로"로는 복구 불가능한 정보가 필요한 벡터는 반드시 이 함수를
    써야 한다."""
    try:
        parsed = guard.parse_json_strict(raw_json_text)
        return {"accepted": True, "parsed": parsed}
    except guard.DuplicateKeyError as e:
        return {"accepted": False, "reason": "DUPLICATE_KEY", "message": str(e)}
    except guard.RawNumberFormatError as e:
        return {"accepted": False, "reason": e.reason, "token": e.token}


def _run_guard_only_vector(vec):
    """guardOnly 벡터(V15~V21류) 전용 처리 — sign/verify를 거치지 않고
    가드 결과만 기록한다."""
    entry = {"id": vec["id"]}
    if vec.get("rawJsonDuplicateCheck"):
        entry["guardResult"] = _run_raw_guard(vec["rawJsonText"])
        return entry
    if "guardDirectPayload" in vec:
        entry["guardResult"] = _run_guard_on_payload(vec["guardDirectPayload"])
        return entry
    # 일반 payload에 가드만 적용(V15/V16/V17 — 이미 파싱된 객체 경로로
    # 충분한 벡터들. 소수부가 0이 아닌 float(V16)은 이 경로로도 정상
    # 거절된다 — 한계는 "정수값을 가진 float"에만 한정됨, 모듈
    # docstring 재확인)
    entry["guardResult"] = _run_guard_on_payload(vec["sign"]["payload"])
    return entry


def run():
    fixtures = json.loads((_HERE / "fixtures_v2.json").read_text(encoding="utf-8"))
    keys_cfg = json.loads((_HERE / "keys_v2.json").read_text(encoding="utf-8"))
    secrets_by_key_id = {k["key_id"]: k["secret"] for k in keys_cfg["keys"]}
    now = keys_cfg["now"]
    max_skew = keys_cfg["max_skew_seconds"]

    results = []
    for vec in fixtures["vectors"]:
        vid = vec["id"]

        if vec.get("guardOnly"):
            results.append(_run_guard_only_vector(vec))
            continue

        s = vec["sign"]
        secret = secrets_by_key_id[s["secretKeyId"]]

        entry = {"id": vid}

        # 0) Option B 가드(참고용 — signing_v2.py 호출 흐름 자체는 가드와
        # 무관하게 그대로 진행한다. 가드를 "통과하지 못하면 서명 단계로
        # 가지 않는다"는 식으로 실제 배선하는 것은 이번 범위가 아니다 —
        # 여기서는 가드가 이 입력에 대해 어떤 판정을 내리는지만 병행
        # 기록해, 기존 cross-validation 결과와 나란히 비교할 수 있게 한다.
        # "rawJsonText"가 있는 벡터(V04)는 raw JSON 경로로, 없는 벡터는
        # 이미 파싱된 객체 경로로 검사한다(두 경로를 구분 — 작업지시 1번).
        if "rawJsonText" in vec:
            entry["guardResult"] = _run_raw_guard(vec["rawJsonText"])
        else:
            entry["guardResult"] = _run_guard_on_payload(s["payload"])

        # 참고 기록용: "이미 파싱된 객체 경로"만 썼다면 어떤 결과가
        # 나왔을지도 함께 남긴다(V04의 한계가 실제로 남아 있음을 보여주는
        # 역사적 비교 — legacyParsedObjectPathStillUnresolved 벡터 전용).
        if vec.get("legacyParsedObjectPathStillUnresolved"):
            entry["legacyParsedObjectPathGuardResult"] = _run_guard_on_payload(s["payload"])

        # 1) 보고용 중간값(독립 재현) — 실제 payload 정규화 결과·UTF-8 hex·payloadHash
        norm_str, norm_hex, payload_hash_manual = _manual_payload_normalization(s["payload"])
        entry["payloadNormalizationResult"] = norm_str
        entry["payloadUtf8Hex"] = norm_hex
        entry["payloadHashManual"] = payload_hash_manual

        # 2) 실제 구현 호출(sign)
        try:
            payload_hash = sv2.compute_payload_hash(s["payload"])
            canonical = sv2.build_canonical_string_v2(
                method=s["method"], operation=s["operation"], timestamp=s["timestamp"],
                nonce=s["nonce"], idempotency_key=s["idempotencyKey"], key_id=s["keyId"],
                payload_hash=payload_hash,
            )
            signature = sv2.sign_v2(
                secret=secret, method=s["method"], operation=s["operation"], timestamp=s["timestamp"],
                nonce=s["nonce"], idempotency_key=s["idempotencyKey"], key_id=s["keyId"], payload=s["payload"],
            )
            entry["payloadHash"] = payload_hash
            entry["canonicalString"] = canonical
            entry["canonicalUtf8Hex"] = canonical.encode("utf-8").hex()
            entry["signature"] = signature
            entry["signError"] = None
        except sv2.FieldFormatError as e:
            entry["payloadHash"] = None
            entry["canonicalString"] = None
            entry["canonicalUtf8Hex"] = None
            entry["signature"] = None
            entry["signError"] = f"FieldFormatError: {e}"
            entry["verifyResult"] = None
            results.append(entry)
            continue

        # 3) tamperSignatureLastHexChar 처리(결정적 규칙, JS와 동일)
        signature_for_verify = signature
        if vec.get("tamperSignatureLastHexChar"):
            signature_for_verify = _flip_last_hex_char(signature)
        entry["signatureUsedForVerify"] = signature_for_verify

        # 4) verifyOverrides 적용
        overrides = vec.get("verifyOverrides", {})
        v_method = overrides.get("method", s["method"])
        v_operation = overrides.get("operation", s["operation"])
        v_timestamp = overrides.get("timestamp", s["timestamp"])
        v_nonce = overrides.get("nonce", s["nonce"])
        v_idempotency_key = overrides.get("idempotencyKey", s["idempotencyKey"])
        v_key_id = overrides.get("keyId", s["keyId"])
        v_payload = overrides.get("payload", copy.deepcopy(s["payload"]))
        v_protocol_version = overrides.get("protocolVersion", sv2.SUPPORTED_PROTOCOL_VERSION)

        registry = _build_registry(keys_cfg)
        result = sv2.verify_v2(
            registry=registry, protocol_version=v_protocol_version, method=v_method, operation=v_operation,
            timestamp=v_timestamp, nonce=v_nonce, idempotency_key=v_idempotency_key, key_id=v_key_id,
            payload=v_payload, signature=signature_for_verify, now=now, max_skew_seconds=max_skew,
        )
        entry["verifyResult"] = {"classification": result.classification, "keyId": result.key_id}
        results.append(entry)

    out_path = _HERE / "python_output.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path} ({len(results)} vectors)")


if __name__ == "__main__":
    run()
