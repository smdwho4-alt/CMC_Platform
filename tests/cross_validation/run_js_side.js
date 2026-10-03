"use strict";
/**
 * Commit8-3b HMAC v2 Python/JS 교차검증 — JS(Node.js) 측 실행기
 *
 * fixtures_v2.json/keys_v2.json을 동일하게 읽어 reference_signing_v2.js로
 * 벡터별 중간값·최종값을 js_output.json에 기록한다. Node 표준 crypto만
 * 사용, 합성 테스트 키만 사용, 네트워크·GAS 접근 없음.
 */
const fs = require("fs");
const path = require("path");
const ref = require("./reference_signing_v2.js");
const guard = require("./payload_schema_guard.js");

const HERE = __dirname;

function runGuardOnPayload(payload) {
  // **이미 파싱된 객체 경로**. "원문에 소수점이 있었는가"를 구분하지
  // 못한다는 한계가 있다(payload_schema_guard.js docstring 재확인) —
  // V04처럼 그 구분이 필요한 입력은 runRawGuard()를 대신 써야 한다.
  try {
    guard.validatePayloadSchemaInterim(payload);
    return { accepted: true };
  } catch (e) {
    if (e instanceof guard.PayloadSchemaUnresolvedError) {
      return { accepted: false, reason: e.reason, path: e.path };
    }
    throw e;
  }
}

function runRawGuard(rawJsonText) {
  // **raw JSON 경로**. 중복 키 + 숫자 토큰 형식(소수점·지수 금지)을
  // 원시 텍스트 단계에서 함께 검사한다.
  try {
    const parsed = guard.parseJsonStrict(rawJsonText);
    return { accepted: true, parsed };
  } catch (e) {
    if (e instanceof guard.DuplicateKeyError) {
      return { accepted: false, reason: "DUPLICATE_KEY", message: e.message };
    }
    if (e instanceof guard.RawNumberFormatError) {
      return { accepted: false, reason: e.reason, token: e.token };
    }
    throw e;
  }
}

function runGuardOnlyVector(vec) {
  const entry = { id: vec.id };
  if (vec.rawJsonDuplicateCheck) {
    entry.guardResult = runRawGuard(vec.rawJsonText);
    return entry;
  }
  if (Object.prototype.hasOwnProperty.call(vec, "guardDirectPayload")) {
    entry.guardResult = runGuardOnPayload(vec.guardDirectPayload);
    return entry;
  }
  entry.guardResult = runGuardOnPayload(vec.sign.payload);
  return entry;
}

function flipLastHexChar(hexstr) {
  const last = hexstr[hexstr.length - 1];
  const newLast = last === "0" ? "1" : "0";
  return hexstr.slice(0, -1) + newLast;
}

function buildRegistry(keysCfg) {
  const registry = new ref.KeyRegistry();
  for (const k of keysCfg.keys) {
    registry.register({
      key_id: k.key_id,
      secret: k.secret,
      state: k.state,
      grace_expires_at: Object.prototype.hasOwnProperty.call(k, "grace_expires_at") ? k.grace_expires_at : undefined,
    });
  }
  return registry;
}

function deepClone(v) {
  return JSON.parse(JSON.stringify(v));
}

function run() {
  const fixtures = JSON.parse(fs.readFileSync(path.join(HERE, "fixtures_v2.json"), "utf8"));
  const keysCfg = JSON.parse(fs.readFileSync(path.join(HERE, "keys_v2.json"), "utf8"));
  const secretsByKeyId = {};
  for (const k of keysCfg.keys) secretsByKeyId[k.key_id] = k.secret;
  const now = keysCfg.now;
  const maxSkew = keysCfg.max_skew_seconds;

  const results = [];
  for (const vec of fixtures.vectors) {
    const vid = vec.id;

    if (vec.guardOnly) {
      results.push(runGuardOnlyVector(vec));
      continue;
    }

    const s = vec.sign;
    const secret = secretsByKeyId[s.secretKeyId];
    const entry = { id: vid };

    // Option B 가드(참고용 — reference_signing_v2.js 호출 흐름 자체는
    // 가드와 무관하게 그대로 진행한다. Python 쪽과 동일하게 가드
    // 판정만 병행 기록한다. "rawJsonText"가 있으면(V04) raw JSON
    // 경로로, 없으면 이미 파싱된 객체 경로로 검사한다.
    entry.guardResult = Object.prototype.hasOwnProperty.call(vec, "rawJsonText")
      ? runRawGuard(vec.rawJsonText)
      : runGuardOnPayload(s.payload);

    if (vec.legacyParsedObjectPathStillUnresolved) {
      entry.legacyParsedObjectPathGuardResult = runGuardOnPayload(s.payload);
    }

    // payload 정규화 자체는 nonce 등 다른 필드의 형식 오류와 무관하게 항상
    // 먼저 계산한다(Python run_python_side.py의 _manual_payload_normalization과
    // 동일한 순서 — canonical string 생성 실패가 payload 정규화 결과 보고를
    // 가리지 않도록 함).
    const { sortedJsonString, sortedJsonUtf8Hex, payloadHash: payloadHashManual } = ref.computePayloadHash(s.payload);
    entry.payloadNormalizationResult = sortedJsonString;
    entry.payloadUtf8Hex = sortedJsonUtf8Hex;
    entry.payloadHashManual = payloadHashManual;

    let signOut;
    try {
      signOut = ref.signV2({
        secret,
        method: s.method,
        operation: s.operation,
        timestamp: s.timestamp,
        nonce: s.nonce,
        idempotencyKey: s.idempotencyKey,
        keyId: s.keyId,
        payload: s.payload,
      });
    } catch (e) {
      if (e instanceof ref.FieldFormatError) {
        entry.payloadHash = null;
        entry.canonicalString = null;
        entry.canonicalUtf8Hex = null;
        entry.signature = null;
        entry.signError = `FieldFormatError: ${e.message}`;
        entry.verifyResult = null;
        results.push(entry);
        continue;
      }
      throw e;
    }

    entry.payloadHash = signOut.payloadHash;
    entry.canonicalString = signOut.canonical;
    entry.canonicalUtf8Hex = signOut.canonicalUtf8Hex;
    entry.signature = signOut.signature;
    entry.signError = null;

    let signatureForVerify = signOut.signature;
    if (vec.tamperSignatureLastHexChar) {
      signatureForVerify = flipLastHexChar(signOut.signature);
    }
    entry.signatureUsedForVerify = signatureForVerify;

    const overrides = vec.verifyOverrides || {};
    const vMethod = "method" in overrides ? overrides.method : s.method;
    const vOperation = "operation" in overrides ? overrides.operation : s.operation;
    const vTimestamp = "timestamp" in overrides ? overrides.timestamp : s.timestamp;
    const vNonce = "nonce" in overrides ? overrides.nonce : s.nonce;
    const vIdempotencyKey = "idempotencyKey" in overrides ? overrides.idempotencyKey : s.idempotencyKey;
    const vKeyId = "keyId" in overrides ? overrides.keyId : s.keyId;
    const vPayload = "payload" in overrides ? overrides.payload : deepClone(s.payload);
    const vProtocolVersion = "protocolVersion" in overrides ? overrides.protocolVersion : ref.SUPPORTED_PROTOCOL_VERSION;

    const registry = buildRegistry(keysCfg);
    const result = ref.verifyV2({
      registry,
      protocolVersion: vProtocolVersion,
      method: vMethod,
      operation: vOperation,
      timestamp: vTimestamp,
      nonce: vNonce,
      idempotencyKey: vIdempotencyKey,
      keyId: vKeyId,
      payload: vPayload,
      signature: signatureForVerify,
      now,
      maxSkewSeconds: maxSkew,
    });
    entry.verifyResult = { classification: result.classification, keyId: result.keyId };
    results.push(entry);
  }

  const outPath = path.join(HERE, "js_output.json");
  fs.writeFileSync(outPath, JSON.stringify(results, null, 2), "utf8");
  console.log(`wrote ${outPath} (${results.length} vectors)`);
}

run();
