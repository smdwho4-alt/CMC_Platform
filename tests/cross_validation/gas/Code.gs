// Commit8-3b 격리 GAS 교차검증 패키지 — Code.gs
//
// tests/cross_validation/reference_signing_v2.js + payload_schema_guard.js의
// 순수 JS 로직을 GAS V8 런타임으로 포팅한 것이다. Node 전용 API
// (require/module.exports/Buffer/crypto)를 전부 제거하고, 암호화·UTF-8
// 변환은 Apps Script 내장 Utilities 서비스로 대체했다.
//
// 사용 서비스: Utilities, Logger만 사용한다.
// 사용하지 않는 서비스: SpreadsheetApp, DriveApp, UrlFetchApp,
// CacheService, PropertiesService — 코드 어디에도 호출이 없다(아래
// 전체가 이 파일의 전부이며, 다른 숨은 호출은 없다).
//
// 이 파일은 운영 .gs 파일(app/apps_script/*.gs)을 수정한 것이 아니라
// 완전히 새로운 격리 테스트 프로젝트 전용 사본이다.

var ALGORITHM_LITERAL = "CMC-HMAC-SHA256";
var SUPPORTED_PROTOCOL_VERSION = "2";

var SAFE_TOKEN_RE = /^[A-Za-z0-9_.\-:]{1,200}$/;
var TIMESTAMP_RE = /^\d+(\.\d+)?$/;
var PAYLOAD_HASH_RE = /^[0-9a-f]{64}$/;
var VALID_METHODS = { GET: true, POST: true, PUT: true, PATCH: true, DELETE: true };

var SAFE_INTEGER_MIN = -9007199254740991;
var SAFE_INTEGER_MAX = 9007199254740991;

// --------------------------------------------------------------------------
// UTF-8 바이트·hex 변환 — Utilities.compute*가 반환하는 byte[]는 부호
// 있는 byte(-128~127)다. Python bytes.hex()/Node Buffer.toString('hex')와
// 같은 비부호 hex 문자열로 맞추려면 각 byte를 (b+256)%256으로 변환한 뒤
// 2자리 16진수로 패딩해야 한다 — 이 변환을 빠뜨리면 음수 byte가 있을 때
// 마이너스 부호가 섞인 잘못된 hex가 나온다.
// --------------------------------------------------------------------------

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
  // Utilities.newBlob(string)은 기본적으로 UTF-8로 인코딩한다(Apps
  // Script 공식 동작) — Node의 Buffer.from(str, 'utf8')과 동일 목적.
  return Utilities.newBlob(str).getBytes();
}

// --------------------------------------------------------------------------
// 필드 형식 검증(signing_v2.py / reference_signing_v2.js와 동일 규칙)
// --------------------------------------------------------------------------

function FieldFormatError_(message) {
  this.name = "FieldFormatError_";
  this.message = message;
}
FieldFormatError_.prototype = Object.create(Error.prototype);

function validateField_(name, value) {
  if (value === null || value === undefined) {
    throw new FieldFormatError_("필수 필드 누락: " + name);
  }
  if (typeof value !== "string") {
    throw new FieldFormatError_(name + "은 문자열이어야 함");
  }
  if (name === "method") {
    if (!VALID_METHODS[value]) {
      throw new FieldFormatError_("허용되지 않는 method: " + value);
    }
    return value;
  }
  var pattern = name === "timestamp" ? TIMESTAMP_RE : name === "payload_hash" ? PAYLOAD_HASH_RE : SAFE_TOKEN_RE;
  if (!pattern.test(value)) {
    throw new FieldFormatError_("허용되지 않는 " + name + " 형식");
  }
  return value;
}

// --------------------------------------------------------------------------
// payload 정규화(sort_keys + compact + NFC) — reference_signing_v2.js의
// stableStringify()와 동일 로직(V8 엔진 공통, Node 전용 API 없음).
// --------------------------------------------------------------------------

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
  var utf8Bytes = stringToUtf8Bytes_(sortedJsonString);
  var digestBytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, sortedJsonString, Utilities.Charset.UTF_8);
  return {
    sortedJsonString: sortedJsonString,
    sortedJsonUtf8Hex: bytesToHex_(utf8Bytes),
    payloadHash: bytesToHex_(digestBytes),
  };
}

function buildCanonicalStringV2_(fields) {
  var method = validateField_("method", typeof fields.method === "string" ? fields.method.toUpperCase() : fields.method);
  var operation = validateField_("operation", fields.operation);
  var timestamp = validateField_("timestamp", fields.timestamp);
  var nonce = validateField_("nonce", fields.nonce);
  var idempotencyKey = validateField_("idempotency_key", fields.idempotencyKey);
  var keyId = validateField_("key_id", fields.keyId);
  var payloadHash = validateField_("payload_hash", fields.payloadHash);
  return [ALGORITHM_LITERAL, SUPPORTED_PROTOCOL_VERSION, method, operation, timestamp, nonce, idempotencyKey, keyId, payloadHash].join("\n");
}

function signV2_(args) {
  var hashResult = computePayloadHash_(args.payload);
  var canonical = buildCanonicalStringV2_({
    method: args.method, operation: args.operation, timestamp: args.timestamp, nonce: args.nonce,
    idempotencyKey: args.idempotencyKey, keyId: args.keyId, payloadHash: hashResult.payloadHash,
  });
  var canonicalUtf8Bytes = stringToUtf8Bytes_(canonical);
  var sigBytes = Utilities.computeHmacSha256Signature(canonical, args.secret, Utilities.Charset.UTF_8);
  return {
    sortedJsonString: hashResult.sortedJsonString,
    sortedJsonUtf8Hex: hashResult.sortedJsonUtf8Hex,
    payloadHash: hashResult.payloadHash,
    canonical: canonical,
    canonicalUtf8Hex: bytesToHex_(canonicalUtf8Bytes),
    signature: bytesToHex_(sigBytes),
  };
}

// --------------------------------------------------------------------------
// Option B 공통 타입 가드(이미 파싱된 객체 경로) — payload_schema_guard.js
// validatePayloadSchemaInterim()과 동일 로직.
// --------------------------------------------------------------------------

function PayloadSchemaUnresolvedError_(reason, path) {
  this.name = "PayloadSchemaUnresolvedError_";
  this.reason = reason;
  this.path = path;
  this.message = reason + " (경로: " + path + ")";
}
PayloadSchemaUnresolvedError_.prototype = Object.create(Error.prototype);

function checkKey_(key, path) {
  if (typeof key !== "string" || !SAFE_TOKEN_RE.test(key)) {
    throw new PayloadSchemaUnresolvedError_("UNICODE_OR_INVALID_OBJECT_KEY", path);
  }
}

function checkValue_(value, path) {
  if (value === null) return;
  if (typeof value === "boolean") return;
  if (typeof value === "string") return;
  if (typeof value === "number") {
    if (!Number.isInteger(value)) {
      throw new PayloadSchemaUnresolvedError_("FLOAT_NOT_ALLOWED", path);
    }
    if (value < SAFE_INTEGER_MIN || value > SAFE_INTEGER_MAX) {
      throw new PayloadSchemaUnresolvedError_("INTEGER_OUT_OF_SAFE_RANGE", path);
    }
    return;
  }
  if (Array.isArray(value)) {
    value.forEach(function (item, i) {
      checkValue_(item, path + "[" + i + "]");
    });
    return;
  }
  if (typeof value === "object") {
    validateObject_(value, path);
    return;
  }
  throw new PayloadSchemaUnresolvedError_("UNSUPPORTED_TYPE", path);
}

function validateObject_(obj, path) {
  Object.keys(obj).forEach(function (key) {
    var keyPath = path + "." + key;
    checkKey_(key, keyPath);
    checkValue_(obj[key], keyPath);
  });
}

function validatePayloadSchemaInterim_(payload) {
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    throw new PayloadSchemaUnresolvedError_("TOP_LEVEL_PAYLOAD_MUST_BE_OBJECT", "$");
  }
  validateObject_(payload, "$");
}

// --------------------------------------------------------------------------
// raw JSON 경로 — 중복 키 + 숫자 토큰 형식(소수점·지수 금지, -0 정규화)을
// 원시 텍스트 단계에서 검사한다. payload_schema_guard.js의 커스텀
// 토크나이저와 동일 로직(V8 엔진 공통이라 포팅에 구조 변경이 필요
// 없었다 — 가설이었으나 로컬 구문검사로는 "문법이 유효하다"까지만
// 확인했고, 실제 GAS V8에서의 동작은 아직 실행하지 않았다).
// --------------------------------------------------------------------------

function DuplicateKeyError_(message) {
  this.name = "DuplicateKeyError_";
  this.message = message;
}
DuplicateKeyError_.prototype = Object.create(Error.prototype);

function RawNumberFormatError_(reason, token) {
  this.name = "RawNumberFormatError_";
  this.reason = reason;
  this.token = token;
  this.message = reason + ": " + token;
}
RawNumberFormatError_.prototype = Object.create(Error.prototype);

var INT_TOKEN_RE_ = /^-?(0|[1-9][0-9]*)$/;

function tokenize_(text) {
  var tokens = [];
  var i = 0;
  var n = text.length;
  var isWS = function (c) {
    return c === " " || c === "\t" || c === "\n" || c === "\r";
  };
  var ESCAPE_MAP = { '"': '"', "\\": "\\", "/": "/", b: "\b", f: "\f", n: "\n", r: "\r", t: "\t" };

  while (i < n) {
    var c = text[i];
    if (isWS(c)) {
      i++;
      continue;
    }
    if (c === "{" || c === "}" || c === "[" || c === "]" || c === ":" || c === ",") {
      tokens.push({ type: c });
      i++;
      continue;
    }
    if (c === '"') {
      var j = i + 1;
      var s = "";
      while (j < n && text[j] !== '"') {
        if (text[j] === "\\") {
          var esc = text[j + 1];
          if (esc === "u") {
            var hex = text.slice(j + 2, j + 6);
            if (!/^[0-9a-fA-F]{4}$/.test(hex)) throw new Error("잘못된 \\u 이스케이프: " + hex);
            s += String.fromCharCode(parseInt(hex, 16));
            j += 6;
          } else if (Object.prototype.hasOwnProperty.call(ESCAPE_MAP, esc)) {
            s += ESCAPE_MAP[esc];
            j += 2;
          } else {
            throw new Error("잘못된 이스케이프: \\" + esc);
          }
        } else {
          s += text[j];
          j++;
        }
      }
      if (j >= n) throw new Error("문자열이 닫히지 않음");
      tokens.push({ type: "string", value: s });
      i = j + 1;
      continue;
    }
    if (c === "-" || (c >= "0" && c <= "9")) {
      var k = i;
      if (text[k] === "-") k++;
      while (k < n && text[k] >= "0" && text[k] <= "9") k++;
      var isFloatOrExponent = false;
      if (text[k] === ".") {
        isFloatOrExponent = true;
        k++;
        while (k < n && text[k] >= "0" && text[k] <= "9") k++;
      }
      if (text[k] === "e" || text[k] === "E") {
        isFloatOrExponent = true;
        k++;
        if (text[k] === "+" || text[k] === "-") k++;
        while (k < n && text[k] >= "0" && text[k] <= "9") k++;
      }
      var rawToken = text.slice(i, k);
      if (isFloatOrExponent) {
        throw new RawNumberFormatError_("FLOAT_OR_EXPONENT_NOT_ALLOWED", rawToken);
      }
      if (!INT_TOKEN_RE_.test(rawToken)) {
        throw new RawNumberFormatError_("INVALID_INTEGER_TOKEN", rawToken);
      }
      var value = Number(rawToken);
      if (Object.is(value, -0)) value = 0;
      tokens.push({ type: "number", value: value });
      i = k;
      continue;
    }
    if (text.indexOf("true", i) === i) {
      tokens.push({ type: "literal", value: true });
      i += 4;
      continue;
    }
    if (text.indexOf("false", i) === i) {
      tokens.push({ type: "literal", value: false });
      i += 5;
      continue;
    }
    if (text.indexOf("null", i) === i) {
      tokens.push({ type: "literal", value: null });
      i += 4;
      continue;
    }
    throw new Error("예기치 않은 문자: " + c + " (위치 " + i + ")");
  }
  return tokens;
}

function parseValueTokens_(tokens, posRef) {
  var tok = tokens[posRef.i];
  if (!tok) throw new Error("입력이 예기치 않게 끝남");
  if (tok.type === "{") return parseObjectTokens_(tokens, posRef);
  if (tok.type === "[") return parseArrayTokens_(tokens, posRef);
  if (tok.type === "string" || tok.type === "number" || tok.type === "literal") {
    posRef.i++;
    return tok.value;
  }
  throw new Error("예기치 않은 토큰: " + tok.type);
}

function parseObjectTokens_(tokens, posRef) {
  posRef.i++;
  var obj = {};
  var seen = {};
  if (tokens[posRef.i] && tokens[posRef.i].type === "}") {
    posRef.i++;
    return obj;
  }
  for (;;) {
    var keyTok = tokens[posRef.i];
    if (!keyTok || keyTok.type !== "string") throw new Error("객체 키는 문자열이어야 함");
    var key = keyTok.value;
    posRef.i++;
    var colon = tokens[posRef.i];
    if (!colon || colon.type !== ":") throw new Error("':' 필요");
    posRef.i++;
    var value = parseValueTokens_(tokens, posRef);
    if (Object.prototype.hasOwnProperty.call(seen, key)) {
      throw new DuplicateKeyError_("중복 object key: " + key);
    }
    seen[key] = true;
    obj[key] = value;
    var next = tokens[posRef.i];
    if (next && next.type === ",") {
      posRef.i++;
      continue;
    }
    if (next && next.type === "}") {
      posRef.i++;
      break;
    }
    throw new Error("',' 또는 '}' 필요");
  }
  return obj;
}

function parseArrayTokens_(tokens, posRef) {
  posRef.i++;
  var arr = [];
  if (tokens[posRef.i] && tokens[posRef.i].type === "]") {
    posRef.i++;
    return arr;
  }
  for (;;) {
    arr.push(parseValueTokens_(tokens, posRef));
    var next = tokens[posRef.i];
    if (next && next.type === ",") {
      posRef.i++;
      continue;
    }
    if (next && next.type === "]") {
      posRef.i++;
      break;
    }
    throw new Error("',' 또는 ']' 필요");
  }
  return arr;
}

function parseJsonStrict_(rawJsonText) {
  var tokens = tokenize_(rawJsonText);
  var posRef = { i: 0 };
  var result = parseValueTokens_(tokens, posRef);
  if (posRef.i !== tokens.length) throw new Error("JSON 뒤에 불필요한 데이터가 있음");
  return result;
}
