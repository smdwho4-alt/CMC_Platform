"use strict";
/**
 * Commit8-3b payload 정규화 계약 — 서명 전 개발용 검증 wrapper(JS 참조구현)
 *
 * src/idempotency/signing_v2_guarded.py와 동일한 체이닝을 독립 구현한
 * Node.js 포트다(교차검증 전용). reference_signing_v2.js(기존 함수,
 * 미수정)를 그대로 호출한다 — 이 파일도 기존 .gs 파일을 수정하지
 * 않는다.
 */
const guard = require("./payload_schema_guard.js");
const reqSchemas = require("./request_payload_schemas.js");
const ref = require("./reference_signing_v2.js");

class GuardedSigningError extends Error {
  constructor(stage, reason, detail) {
    super(`[${stage}] ${reason}` + (detail ? ` — ${detail}` : ""));
    this.stage = stage;
    this.reason = reason;
  }
}

function validateAndNormalizePayload(rawJsonText, operation) {
  let payload;
  try {
    payload = guard.parseJsonStrict(rawJsonText);
  } catch (e) {
    if (e instanceof guard.DuplicateKeyError) {
      throw new GuardedSigningError("RAW_JSON", "DUPLICATE_KEY", e.message);
    }
    if (e instanceof guard.RawNumberFormatError) {
      throw new GuardedSigningError("RAW_JSON", e.reason, e.message);
    }
    throw e;
  }

  try {
    guard.validatePayloadSchemaInterim(payload);
  } catch (e) {
    if (e instanceof guard.PayloadSchemaUnresolvedError) {
      throw new GuardedSigningError("COMMON_TYPE_GUARD", e.reason, e.message);
    }
    throw e;
  }

  try {
    reqSchemas.validateRequestSchema(operation, payload);
  } catch (e) {
    if (e instanceof reqSchemas.RequestSchemaError) {
      throw new GuardedSigningError("REQUEST_SCHEMA", e.reason, e.message);
    }
    throw e;
  }

  return payload;
}

function computePayloadHashGuarded(rawJsonText, operation) {
  const payload = validateAndNormalizePayload(rawJsonText, operation);
  return ref.computePayloadHash(payload).payloadHash;
}

function signV2Guarded({ rawJsonText, operation, secret, method, timestamp, nonce, idempotencyKey, keyId }) {
  const payload = validateAndNormalizePayload(rawJsonText, operation);
  return ref.signV2({
    secret, method, operation, timestamp, nonce, idempotencyKey, keyId, payload,
  }).signature;
}

module.exports = {
  GuardedSigningError,
  validateAndNormalizePayload,
  computePayloadHashGuarded,
  signV2Guarded,
};
