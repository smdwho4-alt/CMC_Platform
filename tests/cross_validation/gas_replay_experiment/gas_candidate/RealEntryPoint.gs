// Sprint8 Commit8-3b — Replay 차단 격리 실측: 실제 배포용 진입점
//
// Main_doPost_stub_new.gs 하단의 "참고용 주석"(실행 불가능한 의사코드)을
// 실제로 호출 가능한 코드로 옮긴 것이다. Main_doPost_stub_new.gs 자체의
// doPost_()/doStatus_()/preprocessPublicRequest_() 로직은 바꾸지 않았다
// (이번 턴에서 그 파일에 가한 변경은 maxSkewSeconds를 서버 상수로
// 고정한 것뿐 — 별도로 기록됨).
//
// doGet과 doPost를 분리한 이유(Main_doPost_stub_new.gs 하단 주석과 동일):
// 쓰기 경로(exec)는 POST로, 읽기 경로(status)는 설계상 분리해 두고
// 싶었으나, doStatus_()도 서명 검증이 필요해 GET 쿼리 파라미터보다
// JSON 본문이 다루기 쉬워 **status도 POST로 통일**했다(Main_doPost_stub_new.gs
// 하단 주석에 이미 그렇게 명시되어 있음). 따라서 doGet(e)은 실제로는
// 아무 것도 허용하지 않는다(완전히 막아둔다 — 비인증 GET 경로를 아예
// 두지 않는다는 설계 원칙의 실제 반영).
//
// ============================================================================
// 이번 보완: 내부 오류와 "본문 형식 오류"를 구분한다
// ============================================================================
// 실측으로 발견된 문제: parseJsonStrict_()가 Replay 패키지에 정의되지
// 않아 "ReferenceError: parseJsonStrict_ is not defined"가 났는데, 기존
// catch 블록이 이 예외를 포함해 **모든** 예외를 "MALFORMED_REQUEST_BODY"
// (클라이언트의 요청 본문이 잘못됐다는 뜻)로 뭉개 버렸다. 이제
// JsonStrictParser_new.gs가 추가되어 그 특정 결함은 고쳐졌지만, 같은
// 분류 실수가 **다른 내부 결함**에서 또 일어날 수 있으므로 분류 로직
// 자체를 고친다:
//   - parseJsonStrict_/tokenize_ 등이 "입력이 실제로 이상하다"고 판단해
//     던지는 예외(DuplicateKeyError_, RawNumberFormatError_, 순수 구문
//     오류용 일반 Error)는 → MALFORMED_REQUEST_BODY(클라이언트 책임).
//   - ReferenceError/TypeError/RangeError 같은 **JS 엔진 수준 오류**
//     (존재하지 않는 함수 호출, undefined 속성 접근 등 — 전부 우리
//     코드의 결함)는 → INTERNAL_ERROR(서버 책임)로 따로 분류한다.
// 두 경우 모두 detail은 비워 둔다(err.message·스택트레이스·secret 등
// 어떤 상세 정보도 응답에 노출하지 않는다) — 요청사항 "내부 오류 응답에
// 상세 코드·secret을 노출하지 않는다"를 그대로 지킨다.
//
// 같은 원칙을 action 디스패치(doPost_/doStatus_ 호출) 구간에도 적용한다
// — 핸들러 내부에서 예기치 않은 예외가 나도 MALFORMED_REQUEST_BODY로
// 오분류되지 않고 INTERNAL_ERROR로 분류되며, detail은 비워진다.

/**
 * 파싱 단계에서 난 예외를 "클라이언트 책임(본문 형식 오류)"과 "서버
 * 책임(내부 오류)"으로 분류한다. JS 엔진이 직접 던지는 오류 타입
 * (ReferenceError/TypeError/RangeError)만 내부 오류로 본다 — 우리
 * 파서가 의도적으로 던지는 커스텀 오류(DuplicateKeyError_,
 * RawNumberFormatError_)나 순수 구문 오류(new Error(...))는 전부
 * 클라이언트 책임으로 분류한다.
 *
 * @param {*} err
 * @return {string} "INTERNAL_ERROR" | "MALFORMED_REQUEST_BODY"
 */
function classifyParseError_(err) {
  if (err instanceof ReferenceError || err instanceof TypeError || err instanceof RangeError) {
    return "INTERNAL_ERROR";
  }
  return "MALFORMED_REQUEST_BODY";
}

function respondJson_(stage, detail) {
  return ContentService.createTextOutput(
    JSON.stringify({ stage: stage, detail: detail || {} })
  ).setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  return respondJson_("METHOD_NOT_ALLOWED", {});
}

function doPost(e) {
  var body;
  try {
    body = parseJsonStrict_(e.postData.contents);
  } catch (err) {
    // detail은 항상 {}다 — err.message/스택트레이스/secret을 절대 넣지 않는다.
    return respondJson_(classifyParseError_(err), {});
  }

  try {
    var handlerName = ROUTES_ALLOWLIST_[body.action];
    var result;
    if (!handlerName) {
      result = { stage: "ACTION_INVALID", detail: { action: body.action } };
    } else if (handlerName === "doPost_") {
      result = doPost_(body);
    } else if (handlerName === "doStatus_") {
      result = doStatus_(body);
    } else {
      // ROUTES_ALLOWLIST_에 doPost_/doStatus_ 외의 값이 생기는 일은
      // 설계상 없어야 한다 — 혹시라도 생기면 안전 쪽으로 거부한다.
      result = { stage: "ACTION_INVALID", detail: { action: body.action } };
    }
    return respondJson_(result.stage, result.detail);
  } catch (err) {
    // 핸들러(doPost_/doStatus_) 내부의 예기치 않은 예외 — 원인 불문
    // INTERNAL_ERROR로만 분류한다(이것도 본문 형식 오류로 오분류하지
    // 않는다). detail은 비워 둔다.
    return respondJson_("INTERNAL_ERROR", {});
  }
}
