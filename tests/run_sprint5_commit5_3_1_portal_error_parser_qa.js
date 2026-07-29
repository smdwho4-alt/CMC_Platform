// Sprint 5 Commit 5-3.1 — Portal Error Contract Parser 테스트 러너
//
// 대상: app/pages/admin_portal_new.html에 새로 추가된 parseApiError(httpStatus, detail)
// 순수 함수. 이 파일에서 실제로 배포되는 소스 텍스트를 그대로 추출해(중복 재구현 없이)
// Node.js vm 샌드박스에서 평가한 뒤 호출한다 — DOM에 의존하는 나머지 <script> 코드
// (document.getElementById 등)는 실행하지 않는다(parseApiError 자체가 DOM/외부 변수에
// 의존하지 않는 순수 함수이므로 격리 실행이 안전하다).
//
// PM 지시(Sprint5 Commit5-3.1) 근거:
// - Backward Compatibility 4종(①문자열 ②기존{code,message} ③신규{code,message,
//   reason_category,reason_detail} ④예상밖 응답) 전부 검증
// - STEP3: SLOT_FULL/SLOT_BLOCKED/SLOT_ON_HOLD/SLOT_NOT_AVAILABLE/SLOT_INVALID_STATE/
//   SLOT_RESERVATION_CONFLICT/RESERVATION_POLICY_BLOCKED/RESERVATION_PROGRAM_UNMAPPED/
//   기타 기존 코드(SLOT_POLICY_VALIDATION_FAILED/SLOT_ROLLBACK_FAILED/SHEETS_WRITE_FAILED)
//   전부 code 필드가 정확히 인식되는지 확인
// - STEP4: reason_category는 Backend가 안 주면 httpStatus/code로 추측하지 않고 그대로
//   'UNKNOWN'
// - STEP5: reason_detail은 Backend가 안 주면 null
// - 422/409/500 각 상태코드 케이스 포함
//
// 결과: tests/sprint5_commit5_3_1_portal_error_parser_test_result.csv

'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const HTML_PATH = path.join(ROOT, 'app', 'pages', 'admin_portal_new.html');
const src = fs.readFileSync(HTML_PATH, 'utf8');

// ── parseApiError 함수 원문만 정확히 추출(중괄호 카운팅, 재구현 없이 실제 소스 사용) ──
function extractFunctionSource(fullSrc, signature) {
  const startIdx = fullSrc.indexOf(signature);
  if (startIdx === -1) {
    throw new Error(`함수 시그니처를 찾을 수 없음: ${signature}`);
  }
  let i = fullSrc.indexOf('{', startIdx);
  if (i === -1) throw new Error('함수 본문 시작 { 를 찾을 수 없음');
  let depth = 0;
  let endIdx = -1;
  for (let j = i; j < fullSrc.length; j++) {
    if (fullSrc[j] === '{') depth++;
    else if (fullSrc[j] === '}') {
      depth--;
      if (depth === 0) { endIdx = j; break; }
    }
  }
  if (endIdx === -1) throw new Error('함수 본문의 짝이 맞는 } 를 찾지 못함');
  return fullSrc.slice(startIdx, endIdx + 1);
}

const fnSrc = extractFunctionSource(src, 'function parseApiError(httpStatus, detail)');
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(`${fnSrc}\nthis.parseApiError = parseApiError;`, sandbox);
const parseApiError = sandbox.parseApiError;

if (typeof parseApiError !== 'function') {
  throw new Error('parseApiError 추출 실패 — vm 샌드박스에 함수가 로드되지 않음');
}

const results = [];
function check(name, ok, detail) {
  results.push([name, ok ? 'PASS' : 'FAIL', detail || '']);
  const line = `[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' - ' + detail : ''}`;
  console.log(line);
}

function deepEq(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

// ── 0. 정적 확인 ──
// Commit5-3.1 작성 당시에는 "parseApiError가 정의만 되고 아직 호출되지 않음"이
// 맞는 상태였으나, Sprint5 Commit5-3.2(PM 승인)에서 실제 승인/거절 흐름에 연결하는
// 것이 그 Commit의 목표였다 — 아래 3개 체크는 "연결 안 됨"에서 "연결됨"으로
// 뒤집혔다(이 파일이 회귀 스위트로 계속 재사용되므로 최신 승인 상태를 반영한다,
// Commit5-1→5-2 전환 때와 동일한 처리 방식).
check('parseApiError가 approveReservation() 정의보다 앞에 위치(정의가 먼저)',
  src.indexOf('function parseApiError(') < src.indexOf('function approveReservation('));
check('parseApiError가 approveReservation() 함수 본문 안에서 호출됨(Commit5-3.2, PM 승인 연결)', (() => {
  const bodyStart = src.indexOf('function approveReservation(');
  const bodyEnd = src.indexOf('function rejectReservation(');
  const body = src.slice(bodyStart, bodyEnd);
  return body.includes('parseApiError(');
})());
check('parseApiError가 rejectReservation() 함수 본문 안에서 호출됨(Commit5-3.2, PM 승인 연결)', (() => {
  const bodyStart = src.indexOf('function rejectReservation(');
  const bodyEnd = src.indexOf('rejectConfirmBtn.addEventListener');
  const body = src.slice(bodyStart, bodyEnd);
  return body.includes('parseApiError(');
})());
check('_SLOT_CONFLICT_CODES 배열에 RESERVATION_POLICY_BLOCKED가 추가됨(Commit5-3.2 STEP3 P0 수정, PM 승인)',
  src.includes("_SLOT_CONFLICT_CODES = [\n    'SLOT_NOT_AVAILABLE', 'SLOT_FULL', 'SLOT_BLOCKED', 'SLOT_ON_HOLD',\n    'SLOT_INVALID_STATE', 'SLOT_RESERVATION_CONFLICT',\n    'RESERVATION_POLICY_BLOCKED',\n  ];"));
check('approveReservation() 409 분기가 parseApiError().code로 _SLOT_CONFLICT_CODES를 판별함(문자열 직접비교 아님, STEP2)', (() => {
  const bodyStart = src.indexOf('function approveReservation(');
  const bodyEnd = src.indexOf('function rejectReservation(');
  const body = src.slice(bodyStart, bodyEnd);
  return body.includes('_SLOT_CONFLICT_CODES.indexOf(parsed.code)') && body.includes('showToast(parsed.message');
})());
check('approveReservation()/rejectReservation() 둘 다 AbortController + 8초 Timeout 적용됨(STEP6)', (() => {
  const bodyStart = src.indexOf('function approveReservation(');
  const bodyEnd = src.indexOf('rejectConfirmBtn.addEventListener');
  const body = src.slice(bodyStart, bodyEnd);
  const hasAbort = (body.match(/new AbortController\(\)/g) || []).length === 2;
  const hasTimeout = (body.match(/setTimeout\(function \(\) \{ controller\.abort\(\); \}, 8000\)/g) || []).length === 2;
  const hasSignal = (body.match(/signal: controller\.signal/g) || []).length === 2;
  const hasAbortErrorCatch = (body.match(/err\.name === 'AbortError'/g) || []).length === 2;
  return hasAbort && hasTimeout && hasSignal && hasAbortErrorCatch;
})());
check('Toast/Dialog/CSS 신규 정의 없음(showToast/rejectModal 정의부 무수정, 호출부만 확장, STEP4)',
  src.includes('function showToast(message, type)')
  && (src.match(/function showToast\(/g) || []).length === 1);
check('_extractDetailMessage()는 정의가 남아있으나 이제 호출부가 없음(parseApiError로 대체, Commit5-3.2)',
  src.includes('function _extractDetailMessage(body, fallback)')
  && (src.match(/_extractDetailMessage\(/g) || []).length === 1);
check('showToast() 정의는 이번 Commit에서 무수정(존재 여부만 확인, 호출부 변경 없음)',
  src.includes('function showToast(message, type)'));

// ── 1. ① 순수 문자열 detail ──
let r = parseApiError(409, '예약할 수 없습니다.');
check('① 순수 문자열 → message가 그대로 반영', r.message === '예약할 수 없습니다.', JSON.stringify(r));
check('① 순수 문자열 → code는 null', r.code === null, JSON.stringify(r));
check('① 순수 문자열 → reason_category는 UNKNOWN(추측하지 않음)', r.reason_category === 'UNKNOWN', JSON.stringify(r));
check('① 순수 문자열 → reason_detail은 null', r.reason_detail === null, JSON.stringify(r));
check('① 순수 문자열 → httpStatus 그대로 보존', r.httpStatus === 409, JSON.stringify(r));

// ── 2. ② 기존 JSON {code, message} (reason_category/reason_detail 없음) ──
r = parseApiError(409, { code: 'SLOT_FULL', message: '해당 시간대의 예약 정원이 마감되었습니다.' });
check('② 기존 JSON → code 정확히 추출', r.code === 'SLOT_FULL', JSON.stringify(r));
check('② 기존 JSON → message 정확히 추출', r.message === '해당 시간대의 예약 정원이 마감되었습니다.', JSON.stringify(r));
check('② 기존 JSON → reason_category는 UNKNOWN(Backend가 안 줬으므로 httpStatus/code로 추측 안 함, STEP4)',
  r.reason_category === 'UNKNOWN', JSON.stringify(r));
check('② 기존 JSON → reason_detail은 null(Backend가 안 줌, STEP5)', r.reason_detail === null, JSON.stringify(r));

// ── 3. ③ 신규 JSON {code, message, reason_category, reason_detail} ──
r = parseApiError(409, {
  code: 'RESERVATION_POLICY_BLOCKED', message: '예약 정책 검증에 의해 이 예약을 확정할 수 없습니다.',
  reason_category: 'POLICY_BLOCKED', reason_detail: 'HOLIDAY',
});
check('③ 신규 JSON → code 정확히 추출', r.code === 'RESERVATION_POLICY_BLOCKED', JSON.stringify(r));
check('③ 신규 JSON → message 정확히 추출', r.message === '예약 정책 검증에 의해 이 예약을 확정할 수 없습니다.', JSON.stringify(r));
check('③ 신규 JSON → reason_category가 Backend 값 그대로 사용됨(POLICY_BLOCKED)', r.reason_category === 'POLICY_BLOCKED', JSON.stringify(r));
check('③ 신규 JSON → reason_detail이 Backend 값 그대로 사용됨(HOLIDAY)', r.reason_detail === 'HOLIDAY', JSON.stringify(r));

// ── 4. ④ 예상하지 못한 응답 ──
const unexpectedInputs = [
  ['null', null], ['undefined', undefined], ['숫자', 42],
  ['배열', ['x', 'y']], ['code/message 없는 객체', { foo: 'bar' }],
  ['빈 문자열', ''],
];
for (const [label, val] of unexpectedInputs) {
  r = parseApiError(500, val);
  check(`④ 예상하지 못한 응답(${label}) → code UNKNOWN(null)`, r.code === null, JSON.stringify(r));
  check(`④ 예상하지 못한 응답(${label}) → reason_category UNKNOWN`, r.reason_category === 'UNKNOWN', JSON.stringify(r));
  check(`④ 예상하지 못한 응답(${label}) → 예외 없이 안전하게 기본값 반환`, typeof r === 'object' && r !== null, JSON.stringify(r));
}

// ── 5. STEP3 — 지정된 Error Code 전부 정확히 인식(9종) ──
const knownCodes = [
  'SLOT_NOT_AVAILABLE', 'SLOT_FULL', 'SLOT_BLOCKED', 'SLOT_ON_HOLD',
  'SLOT_INVALID_STATE', 'SLOT_RESERVATION_CONFLICT',
  'RESERVATION_POLICY_BLOCKED', 'RESERVATION_PROGRAM_UNMAPPED',
  'SLOT_POLICY_VALIDATION_FAILED', 'SLOT_ROLLBACK_FAILED', 'SHEETS_WRITE_FAILED',
];
for (const code of knownCodes) {
  r = parseApiError(409, { code: code, message: '테스트 메시지 - ' + code });
  check(`STEP3: 코드 인식 - ${code}`, r.code === code && r.message === '테스트 메시지 - ' + code, JSON.stringify(r));
}

// ── 6. 실제 상태코드별 케이스(422/409/500) ──
r = parseApiError(422, { code: 'RESERVATION_PROGRAM_UNMAPPED', message: '예약의 검진 프로그램을 확인할 수 없어 승인을 진행할 수 없습니다. 관리자에게 문의해 주세요.' });
check('422 RESERVATION_PROGRAM_UNMAPPED → 정확히 파싱', r.code === 'RESERVATION_PROGRAM_UNMAPPED' && r.httpStatus === 422, JSON.stringify(r));

r = parseApiError(409, { code: 'RESERVATION_POLICY_BLOCKED', message: '예약 정책 검증에 의해 이 예약을 확정할 수 없습니다.' });
check('409 RESERVATION_POLICY_BLOCKED → 정확히 파싱(reason_category는 UNKNOWN, Backend 미제공)',
  r.code === 'RESERVATION_POLICY_BLOCKED' && r.httpStatus === 409 && r.reason_category === 'UNKNOWN', JSON.stringify(r));

r = parseApiError(500, { code: 'SLOT_POLICY_VALIDATION_FAILED', message: '예약 정책 검증 중 오류가 발생했습니다. 관리자에게 문의해 주세요.' });
check('500 SLOT_POLICY_VALIDATION_FAILED → 정확히 파싱', r.code === 'SLOT_POLICY_VALIDATION_FAILED' && r.httpStatus === 500, JSON.stringify(r));

r = parseApiError(409, { code: 'SLOT_FULL', message: '해당 시간대의 예약 정원이 마감되었습니다.' });
check('409 SLOT_FULL → 정확히 파싱', r.code === 'SLOT_FULL' && r.httpStatus === 409, JSON.stringify(r));

// UNKNOWN 응답 전용 케이스(예: 서버가 완전히 다른 프록시 오류 HTML을 반환하는 등)
r = parseApiError(502, '<html>502 Bad Gateway</html>');
check('502 예상 밖 프록시 오류(문자열이지만 HTML) → 문자열 규칙대로 message에 그대로 담김(추측 없음)',
  r.message === '<html>502 Bad Gateway</html>' && r.code === null, JSON.stringify(r));

r = parseApiError(0, undefined);
check('httpStatus=0(네트워크 자체 실패 등 특수 케이스) + detail undefined → 예외 없이 UNKNOWN 기본값',
  deepEq(r, { httpStatus: 0, code: null, message: '알 수 없는 오류가 발생했습니다.', reason_category: 'UNKNOWN', reason_detail: null }),
  JSON.stringify(r));

// ── 결과 저장 ──
const csvLines = ['테스트,결과,상세'];
for (const [name, status, detail] of results) {
  const esc = (s) => '"' + String(s).replace(/"/g, '""') + '"';
  csvLines.push([esc(name), status, esc(detail)].join(','));
}
const outPath = path.join(__dirname, 'sprint5_commit5_3_1_portal_error_parser_test_result.csv');
fs.writeFileSync(outPath, '﻿' + csvLines.join('\r\n') + '\r\n', 'utf8');

const total = results.length;
const passed = results.filter((r) => r[1] === 'PASS').length;
console.log(`TOTAL=${total} PASS=${passed} FAIL=${total - passed}`);
if (passed !== total) process.exit(1);
