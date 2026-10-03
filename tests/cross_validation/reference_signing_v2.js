"use strict";
/**
 * Commit8-3b HMAC Canonical String v2 — JavaScript 참조 구현(교차검증 전용)
 *
 * src/idempotency/signing_v2.py(Python, 운영 후보 격리 구현)와 동일한
 * docs/Commit8_3b_HMAC_Nonce_V2_Contract_Draft.md 계약을 기준으로 독립
 * 작성한 Node.js 포트다. Node.js 표준 `crypto` 모듈만 사용하며, 외부 npm
 * 패키지·네트워크 접근이 없다. 합성 테스트 키만 사용한다(실제 GAS
 * PropertiesService·CacheService·Sheets에 접근하지 않는다).
 *
 * 이 파일은 기존 GAS 코드(.gs)나 src/auth/service_hmac.py를 수정하지
 * 않으며, 운영 라우트에 연결되지 않는다. Node crypto로 이 파일이
 * 통과하더라도 **실제 GAS Utilities(Utilities.computeHmacSha256Signature 등)
 * 검증을 대체하지 않는다** — GAS Rhino/V8 런타임의 실제 동작은 별도
 * 격리 환경에서 PM 승인 하에 확인해야 한다(CROSS_VALIDATION_REPORT.md
 * "실제 GAS 교차검증에 남은 사항" 참조).
 */
const crypto = require("crypto");

const ALGORITHM_LITERAL = "CMC-HMAC-SHA256";
const SUPPORTED_PROTOCOL_VERSION = "2";

const SAFE_TOKEN_RE = /^[A-Za-z0-9_.\-:]{1,200}$/;
const TIMESTAMP_RE = /^\d+(\.\d+)?$/;
const PAYLOAD_HASH_RE = /^[0-9a-f]{64}$/;
const VALID_METHODS = new Set(["GET", "POST", "PUT", "PATCH", "DELETE"]);

const FIELD_PATTERNS = {
  method: VALID_METHODS, // 집합 멤버십 검사(정규식이 아님) — signing_v2.py와 동일
  operation: SAFE_TOKEN_RE,
  timestamp: TIMESTAMP_RE,
  nonce: SAFE_TOKEN_RE,
  idempotency_key: SAFE_TOKEN_RE,
  key_id: SAFE_TOKEN_RE,
  payload_hash: PAYLOAD_HASH_RE,
};

class FieldFormatError extends Error {}

function validateField(name, value) {
  if (value === null || value === undefined) {
    throw new FieldFormatError(`필수 필드 누락: ${name}`);
  }
  if (typeof value !== "string") {
    throw new FieldFormatError(`${name}은 문자열이어야 함`);
  }
  const pattern = FIELD_PATTERNS[name];
  if (name === "method") {
    if (!pattern.has(value)) {
      throw new FieldFormatError(`허용되지 않는 method: ${value}`);
    }
  } else {
    if (!pattern.test(value)) {
      throw new FieldFormatError(`허용되지 않는 ${name} 형식`);
    }
  }
  return value;
}

/**
 * Python `json.dumps(payload, sort_keys=True, separators=(",", ":"),
 * ensure_ascii=False)`와 동일한 compact·키정렬 직렬화를 재현한다.
 *
 * 알려진 교차언어 한계(둘 다 의도적으로 "고치지" 않음 — 계약 공백을
 * 조용히 봉합하면 실제 불일치를 숨기게 되므로):
 *  1) 숫자: JS는 정수/실수 구분이 없는 단일 Number 타입이라 1.0과 1이
 *     동일하게 "1"로 직렬화된다. Python은 float 1.0을 "1.0"으로 보존한다.
 *  2) 키 정렬: 이 함수는 JS 기본 문자열 비교(`<`, UTF-16 코드 유닛 기준)로
 *     정렬한다 — Python의 코드포인트 기준 정렬과 U+E000~U+FFFF vs
 *     surrogate pair 구간에서 다른 순서를 낼 수 있다(V13 벡터 참조).
 */
function stableStringify(value) {
  if (value === null) return "null";
  const t = typeof value;
  if (t === "number" || t === "boolean") return JSON.stringify(value);
  if (t === "string") return JSON.stringify(value);
  if (Array.isArray(value)) {
    return "[" + value.map(stableStringify).join(",") + "]";
  }
  if (t === "object") {
    const keys = Object.keys(value).sort(); // UTF-16 코드 유닛 기준(한계 명시, 위 docstring)
    const parts = keys.map((k) => JSON.stringify(k) + ":" + stableStringify(value[k]));
    return "{" + parts.join(",") + "}";
  }
  throw new TypeError(`직렬화할 수 없는 값: ${String(value)}`);
}

function computePayloadHash(payload) {
  const sortedJsonString = stableStringify(payload);
  const normalized = sortedJsonString.normalize("NFC");
  const utf8Bytes = Buffer.from(normalized, "utf8");
  const payloadHash = crypto.createHash("sha256").update(utf8Bytes).digest("hex");
  return {
    sortedJsonString: normalized,
    sortedJsonUtf8Hex: utf8Bytes.toString("hex"),
    payloadHash,
  };
}

function buildCanonicalStringV2({ method, operation, timestamp, nonce, idempotencyKey, keyId, payloadHash }) {
  const m = validateField("method", typeof method === "string" ? method.toUpperCase() : method);
  const op = validateField("operation", operation);
  const ts = validateField("timestamp", timestamp);
  const n = validateField("nonce", nonce);
  const idem = validateField("idempotency_key", idempotencyKey);
  const kid = validateField("key_id", keyId);
  const ph = validateField("payload_hash", payloadHash);
  return [ALGORITHM_LITERAL, SUPPORTED_PROTOCOL_VERSION, m, op, ts, n, idem, kid, ph].join("\n");
}

function signV2({ secret, method, operation, timestamp, nonce, idempotencyKey, keyId, payload }) {
  const { sortedJsonString, sortedJsonUtf8Hex, payloadHash } = computePayloadHash(payload);
  const canonical = buildCanonicalStringV2({ method, operation, timestamp, nonce, idempotencyKey, keyId, payloadHash });
  const canonicalUtf8Hex = Buffer.from(canonical, "utf8").toString("hex");
  const signature = crypto
    .createHmac("sha256", Buffer.from(secret, "utf8"))
    .update(Buffer.from(canonical, "utf8"))
    .digest("hex");
  return { sortedJsonString, sortedJsonUtf8Hex, payloadHash, canonical, canonicalUtf8Hex, signature };
}

class KeyResolutionError extends Error {
  constructor(reason) {
    super(reason);
    this.reason = reason;
  }
}

class KeyRegistry {
  constructor() {
    this._keys = new Map();
  }

  register(record) {
    if (!["ACTIVE", "GRACE", "REVOKED"].includes(record.state)) {
      throw new Error(`알 수 없는 key state: ${record.state}`);
    }
    if (record.state === "GRACE" && record.grace_expires_at === undefined) {
      throw new Error("GRACE 상태 키는 grace_expires_at이 필요함");
    }
    this._keys.set(record.key_id, record);
  }

  resolve(keyId, now) {
    const record = this._keys.get(keyId);
    if (record === undefined) {
      throw new KeyResolutionError("UNKNOWN_KEY_ID");
    }
    if (record.state === "REVOKED") {
      throw new KeyResolutionError("KEY_REVOKED");
    }
    if (record.state === "GRACE" && now > record.grace_expires_at) {
      throw new KeyResolutionError("KEY_GRACE_EXPIRED");
    }
    return record;
  }
}

function constantTimeEquals(a, b) {
  const bufA = Buffer.from(a, "utf8");
  const bufB = Buffer.from(b, "utf8");
  if (bufA.length !== bufB.length) {
    // 길이가 다르면 timingSafeEqual이 예외를 던지므로, 더미 비교 후 false 반환
    // (길이 노출 자체는 signing_v2.py의 hmac.compare_digest와 동일한 한계).
    crypto.timingSafeEqual(bufA, bufA);
    return false;
  }
  return crypto.timingSafeEqual(bufA, bufB);
}

function verifyV2({
  registry,
  protocolVersion,
  method,
  operation,
  timestamp,
  nonce,
  idempotencyKey,
  keyId,
  payload,
  signature,
  now,
  maxSkewSeconds,
}) {
  if (protocolVersion !== SUPPORTED_PROTOCOL_VERSION) {
    return { classification: "PROTOCOL_VERSION_MISMATCH", keyId: null };
  }

  let methodU = typeof method === "string" ? method.toUpperCase() : method;
  try {
    validateField("method", methodU);
    validateField("operation", operation);
    validateField("timestamp", timestamp);
    validateField("nonce", nonce);
    validateField("idempotency_key", idempotencyKey);
    validateField("key_id", keyId);
  } catch (e) {
    if (e instanceof FieldFormatError) return { classification: "FIELD_FORMAT_INVALID", keyId: null };
    throw e;
  }

  let keyRecord;
  try {
    keyRecord = registry.resolve(keyId, now);
  } catch (e) {
    if (e instanceof KeyResolutionError) return { classification: e.reason, keyId };
    throw e;
  }

  const { payloadHash } = computePayloadHash(payload);
  let canonical;
  try {
    canonical = buildCanonicalStringV2({ method: methodU, operation, timestamp, nonce, idempotencyKey, keyId, payloadHash });
  } catch (e) {
    if (e instanceof FieldFormatError) return { classification: "FIELD_FORMAT_INVALID", keyId };
    throw e;
  }

  const expectedSignature = crypto
    .createHmac("sha256", Buffer.from(keyRecord.secret, "utf8"))
    .update(Buffer.from(canonical, "utf8"))
    .digest("hex");
  if (!constantTimeEquals(expectedSignature, signature)) {
    return { classification: "SIGNATURE_MISMATCH", keyId };
  }

  const ts = parseFloat(timestamp);
  const delta = now - ts;
  if (delta > maxSkewSeconds) return { classification: "TIMESTAMP_EXPIRED", keyId };
  if (delta < -maxSkewSeconds) return { classification: "TIMESTAMP_FUTURE", keyId };

  return { classification: "ACCEPTED", keyId };
}

// 테스트 전용 기본값 — 운영 확정값이 아니다(signing_v2.py의
// TEST_DEFAULT_MAX_SKEW_SECONDS와 동일 원칙).
const TEST_DEFAULT_MAX_SKEW_SECONDS = 120;

module.exports = {
  ALGORITHM_LITERAL,
  SUPPORTED_PROTOCOL_VERSION,
  TEST_DEFAULT_MAX_SKEW_SECONDS,
  FieldFormatError,
  KeyResolutionError,
  KeyRegistry,
  validateField,
  stableStringify,
  computePayloadHash,
  buildCanonicalStringV2,
  signV2,
  verifyV2,
};
