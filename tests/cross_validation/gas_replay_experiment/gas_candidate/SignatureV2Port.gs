// Sprint8 Commit8-3b — Replay 차단 격리 실측 후보 코드
// 파일: SignatureV2Port_new.gs
//
// *** 후보 코드 — 업로드·실행하지 않음. GAS에 올려본 적이 없다. ***
//
// 목적: 서명 검증(verifyV2_)을 nonce 가드보다 먼저 수행해야 한다는
// 보안 경계(서명 검증 → nonce 소비 → 업무 실행)를 후보 코드 수준에서도
// 지키기 위한 최소 서명 검증 함수.
//
// 해시/서명 하위 로직(bytesToHex_/stringToUtf8Bytes_/stableStringify_/
// computePayloadHash_/buildCanonicalStringV2_/signV2_)은 이미 2026-10-03
// 실제 GAS V8 런타임에서 실행·검증된 tests/cross_validation/gas/Code.gs와
// 동일한 알고리즘을 그대로 가져온 것이다(그 파일을 수정하지 않았고,
// 이 파일은 완전히 별도의 새 실험 패키지 사본이다). 서명 로직을 다시
// 설계하지 않고 이미 검증된 것을 재사용함으로써, 이번 실험의 초점인
// nonce 가드(Cache/Lock vs Properties/Lock) 비교에 불필요한 리스크를
// 추가하지 않는다.
//
// verifyV2_()는 이번 실험을 위해 새로 추가한 것이며, signing_v2.py의
// verify_v2()(src/idempotency/signing_v2.py)와 동일한 검사 순서·delta
// 공식을 따른다. 단, 이번 실험 범위에서는 키 레지스트리(KeyRegistry,
// ACTIVE/GRACE/REVOKED)와 전체 필드 형식 검증(FIELD_PATTERNS)을
// 생략한 단순화 버전이다 — 실제 운영 배포 전에는 signing_v2.py의
// 전체 검사 순서(① protocolVersion ② 필드 형식 ③ 키 조회
// ④ 서명 일치 ⑤ timestamp 허용범위)를 빠짐없이 포팅해야 한다
// (이 파일은 그 전부를 포팅한 것이 아니다 — Open Question으로 남김).

var ALGORITHM_LITERAL = "CMC-HMAC-SHA256";
var SUPPORTED_PROTOCOL_VERSION = "2";

function bytesToHex_(bytes) {
  var out = "";
  for (var i = 0; i < bytes.length; i++) {
    var v = (bytes[i] + 256) % 256;
    var h = v.toString(16);
    out += h.length === 1 ? "0" + h : h;
  }
  return out;
}

function stringToUtf8Bytes_(str) {
  return Utilities.newBlob(str).getBytes();
}

function stableStringify_(value) {
  if (value === null) return "null";
  var t = typeof value;
  if (t === "number" || t === "boolean") return JSON.stringify(value);
  if (t === "string") return JSON.stringify(value);
  if (Array.isArray(value)) {
    return "[" + value.map(stableStringify_).join(",") + "]";
  }
  if (t === "object") {
    var keys = Object.keys(value).sort();
    var parts = keys.map(function (k) {
      return JSON.stringify(k) + ":" + stableStringify_(value[k]);
    });
    return "{" + parts.join(",") + "}";
  }
  throw new TypeError("직렬화할 수 없는 값: " + String(value));
}

function computePayloadHash_(payload) {
  var sortedJsonString = stableStringify_(payload).normalize("NFC");
  var digestBytes = Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256, sortedJsonString, Utilities.Charset.UTF_8
  );
  return bytesToHex_(digestBytes);
}

function buildCanonicalStringV2_(fields) {
  return [
    ALGORITHM_LITERAL,
    SUPPORTED_PROTOCOL_VERSION,
    fields.method,
    fields.operation,
    fields.timestamp,
    fields.nonce,
    fields.idempotencyKey,
    fields.keyId,
    fields.payloadHash,
  ].join("\n");
}

function signV2_(args) {
  var payloadHash = computePayloadHash_(args.payload);
  var canonical = buildCanonicalStringV2_({
    method: args.method, operation: args.operation, timestamp: args.timestamp, nonce: args.nonce,
    idempotencyKey: args.idempotencyKey, keyId: args.keyId, payloadHash: payloadHash,
  });
  var sigBytes = Utilities.computeHmacSha256Signature(canonical, args.secret, Utilities.Charset.UTF_8);
  return { payloadHash: payloadHash, canonical: canonical, signature: bytesToHex_(sigBytes) };
}

// 상수시간에 가까운 비교 — GAS는 공식적으로 상수시간 비교를 보장하지
// 않는다(이번 조사에서 확인하지 못함, 공백). 길이를 먼저 비교하지 않고
// 끝까지 순회해 타이밍 차이를 줄이는 best-effort 구현일 뿐, Python
// hmac.compare_digest()와 동급의 보장이 있다고 주장하지 않는다.
function constantTimeEqualsBestEffort_(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  var maxLen = Math.max(a.length, b.length);
  var diff = a.length === b.length ? 0 : 1;
  for (var i = 0; i < maxLen; i++) {
    var ca = i < a.length ? a.charCodeAt(i) : 0;
    var cb = i < b.length ? b.charCodeAt(i) : 0;
    diff |= ca ^ cb;
  }
  return diff === 0;
}

/**
 * 실험용 단순화 서명 검증. 반환: { classification, keyId }
 * classification: "ACCEPTED" | "SIGNATURE_MISMATCH" | "TIMESTAMP_EXPIRED" | "TIMESTAMP_FUTURE"
 *
 * signing_v2.py verify_v2()와 동일한 delta 공식을 쓴다:
 *   delta = now - timestamp
 *   delta >  maxSkewSeconds  → TIMESTAMP_EXPIRED (너무 과거)
 *   delta < -maxSkewSeconds  → TIMESTAMP_FUTURE  (너무 미래)
 *   그 외(경계 포함)         → 통과
 */
function verifyV2_(args) {
  var expected = signV2_({
    secret: args.secret, method: args.method, operation: args.operation, timestamp: args.timestamp,
    nonce: args.nonce, idempotencyKey: args.idempotencyKey, keyId: args.keyId, payload: args.payload,
  }).signature;

  if (!constantTimeEqualsBestEffort_(expected, args.signature)) {
    return { classification: "SIGNATURE_MISMATCH", keyId: args.keyId };
  }

  var ts = parseFloat(args.timestamp);
  var delta = args.now - ts;
  if (delta > args.maxSkewSeconds) {
    return { classification: "TIMESTAMP_EXPIRED", keyId: args.keyId };
  }
  if (delta < -args.maxSkewSeconds) {
    return { classification: "TIMESTAMP_FUTURE", keyId: args.keyId };
  }
  return { classification: "ACCEPTED", keyId: args.keyId };
}
