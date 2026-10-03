// Sprint8 Commit8-3b — Replay 차단 격리 실측 후보 코드
// 파일: JsonStrictParser_new.gs — 누락됐던 parseJsonStrict_ 보완
//
// *** 후보 코드 — 업로드·실행하지 않음. ***
//
// 배경: RealEntryPoint_new.gs의 doPost(e)가 parseJsonStrict_()를
// 호출하는데, 이 함수가 Replay 9파일 어디에도 정의되어 있지 않아
// 실제 GAS 배포(최소 진단 프로젝트에 수동 적용본으로 테스트)에서
// 매 요청마다 "ReferenceError: parseJsonStrict_ is not defined" →
// MALFORMED_REQUEST_BODY로 오분류되는 결함이 실측으로 확인됐다.
//
// 이 파일은 그 결함을 "새로 작성"이 아니라 **기존에 이미 있던 구현을
// 그대로 포팅**해서 고친다 — tests/cross_validation/gas/Code.gs(커밋된
// 파일, 수정하지 않음)의 raw JSON 경로 섹션과 **완전히 동일한 로직**
// (중복 키 검사, 소수점/지수 숫자 금지, -0 정규화)을 그대로 가져왔다.
// 로직을 바꾸지 않았고, 식별자 이름도 그대로다.
//
// 중요한 정확성 표기: 이 토크나이저 자체는 **실제 GAS에서 실행된 적이
// 없다.** 2026-10-03 GAS 교차검증(22/22 PASS)은 서명(signV2_)·payload
// hash 로직만 실제로 실행했고, 이 raw JSON 파서 경로(parseJsonStrict_/
// tokenize_)는 그 실행 범위에 포함되지 않았다(원본 파일 Code.gs 자체의
// 주석에도 "실제 GAS V8에서의 동작은 아직 실행하지 않았다"고 명시돼
// 있다). 이번에 추가하는 로컬 Node 기능 테스트(§doPost(e) 진입점
// 테스트)로 동작을 확인하지만, 이것도 GAS 실행 확인은 아니다 — 로컬
// 검증으로만 기록한다.
//
// 이름 충돌 확인: DuplicateKeyError_/RawNumberFormatError_/INT_TOKEN_RE_/
// tokenize_/parseValueTokens_/parseObjectTokens_/parseArrayTokens_/
// parseJsonStrict_ 8개 식별자를 기존 9개 파일 전체에서 grep했고, 전부
// "정의"가 아니라 "호출"(parseJsonStrict_ 1곳, RealEntryPoint_new.gs)
// 뿐이었다 — 충돌 없음.

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
