"use strict";
/**
 * Commit8-3b payload 정규화 계약 — Option B 개발용 입력 검증 가드(JS 참조구현)
 *
 * src/idempotency/payload_schema_guard.py와 동일 규칙을 독립 구현한
 * Node.js 포트다(교차검증 전용, 외부 npm 패키지 없음). 운영 라우트에
 * 연결되지 않았고, 기존 .gs 파일을 수정하지 않는다.
 *
 * JS 표준 `JSON.parse`는 object_pairs_hook 같은 훅이 없고, reviver는
 * 이미 중복이 해소된 결과에 대해서만 호출되므로 중복 키 정보가 이미
 * 소실된 뒤라 사용할 수 없다. 따라서 중복 키 탐지를 위해 **최소
 * recursive-descent JSON 파서를 직접 구현**했다(목적은 호환성 좋은
 * 범용 파서가 아니라 "중복 키를 키 단위로 감지할 수 있는" 파서).
 *
 * ## V04(1.0 vs 1) 해결 — raw JSON 경로로 이전(이번 갱신)
 * 이전 버전은 "이미 파싱된 JS 값"만 보는 `checkValue()`의
 * `!Number.isInteger(value)` 검사로 float을 걸러내려 했는데, **정수값을
 * 가진 float 리터럴**(`1.0`, `2.0` 등)은 `JSON.parse()`를 통과하는 순간
 * `1`과 완전히 동일한 `Number`가 되어(`Object.is(1.0, 1) === true`,
 * `Number.isInteger(1.0) === true`) 이 경로로는 원천적으로 걸러낼 수
 * 없었다(소수부가 실제로 0이 아닌 float, 예 `10.5`는 `Number.isInteger()`가
 * 정확히 `false`를 반환해 **이미 파싱된 객체 경로로도 정상 거절된다** —
 * V16에서 실측 확인. 문제는 "정수값을 가진 float"에만 한정됐었다).
 *
 * 이번 갱신으로 **원시 JSON 텍스트를 직접 보는 토크나이저**(아래
 * `tokenize()`)가 숫자 토큰에 소수점(`.`) 또는 지수 표기(`e`/`E`)가
 * 있는지 **문자 단위로** 검사하도록 바꿨다 — 토큰 문자열 자체(`"1.0"`)를
 * 보므로 파싱 후 값(`1`)과 무관하게 "원문에 소수점이 있었는가"를 정확히
 * 판정할 수 있다. 이것이 **raw JSON 경로**(`parseJsonStrict`)이며,
 * V04(`{"count": 1.0}`)는 이제 이 경로로 검증해 양쪽 언어가 동일하게
 * `FLOAT_OR_EXPONENT_NOT_ALLOWED`로 거절한다(RESOLVED_REJECTED).
 *
 * **단, "이미 파싱된 객체 경로"(`validatePayloadSchemaInterim`) 자체의
 * 한계는 그대로 유지된다** — 호출부가 raw JSON을 거치지 않고 이미
 * 파싱된(또는 코드에서 직접 만든) JS 객체를 이 경로에만 넘기면, 그
 * 객체의 숫자 값이 원래 `1.0`으로 쓰였는지 `1`로 쓰였는지는 **여전히
 * 구분할 수 없다**(JS 언어 자체의 한계, 코드를 고쳐서 해결 가능한
 * 문제가 아님). 이 두 경로를 섞어 쓰면 안 되는 이유이며,
 * `signing_v2_guarded.js`가 항상 raw JSON 경로를 먼저 거치도록
 * 강제하는 이유다.
 */

const SAFE_TOKEN_RE = /^[A-Za-z0-9_.\-:]{1,200}$/;
const SAFE_INTEGER_MIN = -9007199254740991;
const SAFE_INTEGER_MAX = 9007199254740991;

class PayloadSchemaUnresolvedError extends Error {
  constructor(reason, path) {
    super(`${reason} (경로: ${path})`);
    this.reason = reason;
    this.path = path;
  }
}

function checkKey(key, path) {
  if (typeof key !== "string" || !SAFE_TOKEN_RE.test(key)) {
    throw new PayloadSchemaUnresolvedError("UNICODE_OR_INVALID_OBJECT_KEY", path);
  }
}

function checkValue(value, path) {
  if (value === null) return;
  if (typeof value === "boolean") return;
  if (typeof value === "string") return;
  if (typeof value === "number") {
    if (!Number.isInteger(value)) {
      // NaN/Infinity도 Number.isInteger()가 false를 반환하므로 여기서 함께 거절된다.
      throw new PayloadSchemaUnresolvedError("FLOAT_NOT_ALLOWED", path);
    }
    if (value < SAFE_INTEGER_MIN || value > SAFE_INTEGER_MAX) {
      throw new PayloadSchemaUnresolvedError("INTEGER_OUT_OF_SAFE_RANGE", path);
    }
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, i) => checkValue(item, `${path}[${i}]`));
    return;
  }
  if (typeof value === "object") {
    validateObject(value, path);
    return;
  }
  throw new PayloadSchemaUnresolvedError("UNSUPPORTED_TYPE", path);
}

function validateObject(obj, path) {
  for (const [key, value] of Object.entries(obj)) {
    const keyPath = `${path}.${key}`;
    checkKey(key, keyPath);
    checkValue(value, keyPath);
  }
}

function validatePayloadSchemaInterim(payload) {
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    throw new PayloadSchemaUnresolvedError("TOP_LEVEL_PAYLOAD_MUST_BE_OBJECT", "$");
  }
  validateObject(payload, "$");
}

class DuplicateKeyError extends Error {}

class RawNumberFormatError extends Error {
  constructor(reason, token) {
    super(`${reason}: ${token}`);
    this.reason = reason;
    this.token = token;
  }
}

const _INT_TOKEN_RE = /^-?(0|[1-9][0-9]*)$/;

// --------------------------------------------------------------------------
// 최소 JSON 토크나이저·파서 — raw JSON 경로 전용(중복 키 탐지 + 숫자
// 토큰 형식 검증을 원시 텍스트 단계에서 함께 수행한다)
// --------------------------------------------------------------------------

function tokenize(text) {
  const tokens = [];
  let i = 0;
  const n = text.length;
  const isWS = (c) => c === " " || c === "\t" || c === "\n" || c === "\r";
  const ESCAPE_MAP = { '"': '"', "\\": "\\", "/": "/", b: "\b", f: "\f", n: "\n", r: "\r", t: "\t" };

  while (i < n) {
    const c = text[i];
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
      let j = i + 1;
      let s = "";
      while (j < n && text[j] !== '"') {
        if (text[j] === "\\") {
          const esc = text[j + 1];
          if (esc === "u") {
            const hex = text.slice(j + 2, j + 6);
            if (!/^[0-9a-fA-F]{4}$/.test(hex)) throw new SyntaxError(`잘못된 \\u 이스케이프: ${hex}`);
            s += String.fromCharCode(parseInt(hex, 16));
            j += 6;
          } else if (Object.prototype.hasOwnProperty.call(ESCAPE_MAP, esc)) {
            s += ESCAPE_MAP[esc];
            j += 2;
          } else {
            throw new SyntaxError(`잘못된 이스케이프: \\${esc}`);
          }
        } else {
          s += text[j];
          j++;
        }
      }
      if (j >= n) throw new SyntaxError("문자열이 닫히지 않음");
      tokens.push({ type: "string", value: s });
      i = j + 1;
      continue;
    }
    if (c === "-" || (c >= "0" && c <= "9")) {
      let j = i;
      if (text[j] === "-") j++;
      while (j < n && text[j] >= "0" && text[j] <= "9") j++;
      let isFloatOrExponent = false;
      if (text[j] === ".") {
        isFloatOrExponent = true;
        j++;
        while (j < n && text[j] >= "0" && text[j] <= "9") j++;
      }
      if (text[j] === "e" || text[j] === "E") {
        isFloatOrExponent = true;
        j++;
        if (text[j] === "+" || text[j] === "-") j++;
        while (j < n && text[j] >= "0" && text[j] <= "9") j++;
      }
      const rawToken = text.slice(i, j);
      // 개발 계약(raw JSON 경로 전용): 정수 토큰만 허용(-?(0|[1-9][0-9]*)).
      // 소수점·지수표기가 있으면 "이미 파싱된 값"이 아니라 토큰 문자열
      // 자체를 보고 즉시 거절한다 — 이것이 1.0과 1을 구분하는 지점이다.
      if (isFloatOrExponent) {
        throw new RawNumberFormatError("FLOAT_OR_EXPONENT_NOT_ALLOWED", rawToken);
      }
      if (!_INT_TOKEN_RE.test(rawToken)) {
        throw new RawNumberFormatError("INVALID_INTEGER_TOKEN", rawToken);
      }
      let value = Number(rawToken);
      if (Object.is(value, -0)) value = 0; // -0 정규화(JS는 -0을 별도 값으로 보존하므로 명시적으로 처리 필요)
      tokens.push({ type: "number", value });
      i = j;
      continue;
    }
    if (text.startsWith("true", i)) {
      tokens.push({ type: "literal", value: true });
      i += 4;
      continue;
    }
    if (text.startsWith("false", i)) {
      tokens.push({ type: "literal", value: false });
      i += 5;
      continue;
    }
    if (text.startsWith("null", i)) {
      tokens.push({ type: "literal", value: null });
      i += 4;
      continue;
    }
    throw new SyntaxError(`예기치 않은 문자: ${c} (위치 ${i})`);
  }
  return tokens;
}

function parseValue(tokens, posRef) {
  const tok = tokens[posRef.i];
  if (!tok) throw new SyntaxError("입력이 예기치 않게 끝남");
  if (tok.type === "{") return parseObjectTokens(tokens, posRef);
  if (tok.type === "[") return parseArrayTokens(tokens, posRef);
  if (tok.type === "string" || tok.type === "number" || tok.type === "literal") {
    posRef.i++;
    return tok.value;
  }
  throw new SyntaxError(`예기치 않은 토큰: ${tok.type}`);
}

function parseObjectTokens(tokens, posRef) {
  posRef.i++; // consume '{'
  const obj = {};
  const seen = new Set();
  if (tokens[posRef.i] && tokens[posRef.i].type === "}") {
    posRef.i++;
    return obj;
  }
  for (;;) {
    const keyTok = tokens[posRef.i];
    if (!keyTok || keyTok.type !== "string") throw new SyntaxError("객체 키는 문자열이어야 함");
    const key = keyTok.value;
    posRef.i++;
    const colon = tokens[posRef.i];
    if (!colon || colon.type !== ":") throw new SyntaxError("':' 필요");
    posRef.i++;
    const value = parseValue(tokens, posRef);
    if (seen.has(key)) {
      throw new DuplicateKeyError(`중복 object key: ${key}`);
    }
    seen.add(key);
    obj[key] = value;
    const next = tokens[posRef.i];
    if (next && next.type === ",") {
      posRef.i++;
      continue;
    }
    if (next && next.type === "}") {
      posRef.i++;
      break;
    }
    throw new SyntaxError("',' 또는 '}' 필요");
  }
  return obj;
}

function parseArrayTokens(tokens, posRef) {
  posRef.i++; // consume '['
  const arr = [];
  if (tokens[posRef.i] && tokens[posRef.i].type === "]") {
    posRef.i++;
    return arr;
  }
  for (;;) {
    arr.push(parseValue(tokens, posRef));
    const next = tokens[posRef.i];
    if (next && next.type === ",") {
      posRef.i++;
      continue;
    }
    if (next && next.type === "]") {
      posRef.i++;
      break;
    }
    throw new SyntaxError("',' 또는 ']' 필요");
  }
  return arr;
}

/**
 * **raw JSON 경로**의 유일한 진입점. 중복 object key와 숫자 토큰 형식을
 * 원시 텍스트 단계에서 함께 검사한다(`payload_schema_guard.py`의
 * `parse_json_strict()`와 동일 역할). 성공하면 검증된 JS 값을 반환한다.
 */
function parseJsonStrict(rawJsonText) {
  const tokens = tokenize(rawJsonText);
  const posRef = { i: 0 };
  const result = parseValue(tokens, posRef);
  if (posRef.i !== tokens.length) throw new SyntaxError("JSON 뒤에 불필요한 데이터가 있음");
  return result;
}

// [하위 호환용] 이전 이름 — 새 호출부는 parseJsonStrict()를 쓸 것을 권장.
const parseJsonRejectDuplicates = parseJsonStrict;

module.exports = {
  SAFE_INTEGER_MIN,
  SAFE_INTEGER_MAX,
  PayloadSchemaUnresolvedError,
  DuplicateKeyError,
  RawNumberFormatError,
  validatePayloadSchemaInterim,
  parseJsonStrict,
  parseJsonRejectDuplicates,
};
