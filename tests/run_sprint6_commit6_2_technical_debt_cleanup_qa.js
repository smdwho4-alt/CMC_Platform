// Sprint 6 Commit6-2 — Technical Debt Cleanup 테스트 러너
//
// 대상:
// - TD-S5-01: app/pages/admin_portal_new.html의 _extractDetailMessage() 삭제 확인
//   (parseApiError()로 일원화) — 별도 검증은 run_sprint5_commit5_3_1_portal_error_parser_qa.js
//   에서 갱신된 정적 체크로 이미 수행하므로, 여기서는 교차 확인만 한다.
// - TD-S5-02: app/pages/admin_reservations_v2_new.html의 renderStats()가 CMC_DB(localStorage
//   샘플)가 아니라 this.cache(실제 Sheets 데이터, loadAll()이 채운 전체 목록)를 사용하도록
//   수정됐는지 오프라인(vm 샌드박스)으로 검증한다. 실제 배포 소스를 그대로 추출해 실행하며
//   실네트워크 호출은 없다(Commit6-1 QA와 동일한 안전 원칙 — config_v2_new.js의 실제
//   운영 GAS URL 때문에 실브라우저 클릭 QA는 사용하지 않는다).
//
// 결과: tests/sprint6_commit6_2_technical_debt_cleanup_test_result.csv

'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const ADMIN_PORTAL_PATH = path.join(ROOT, 'app', 'pages', 'admin_portal_new.html');
const LEGACY_PATH = path.join(ROOT, 'app', 'pages', 'admin_reservations_v2_new.html');
const adminSrc = fs.readFileSync(ADMIN_PORTAL_PATH, 'utf8');
const legacySrc = fs.readFileSync(LEGACY_PATH, 'utf8');

function extractMethodSource(fullSrc, signature) {
  const startIdx = fullSrc.indexOf(signature);
  if (startIdx === -1) throw new Error(`시그니처를 찾을 수 없음: ${signature}`);
  let i = fullSrc.indexOf('{', startIdx);
  let depth = 0, endIdx = -1;
  for (let j = i; j < fullSrc.length; j++) {
    if (fullSrc[j] === '{') depth++;
    else if (fullSrc[j] === '}') { depth--; if (depth === 0) { endIdx = j; break; } }
  }
  if (endIdx === -1) throw new Error('본문의 짝이 맞는 }를 찾지 못함');
  return fullSrc.slice(startIdx, endIdx + 1);
}

const results = [];
function check(name, ok, detail) {
  results.push([name, ok ? 'PASS' : 'FAIL', detail || '']);
  console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' - ' + detail : ''}`);
}

// ── TD-S5-01: admin_portal_new.html ──
check('TD-S5-01: _extractDetailMessage() 함수 정의가 admin_portal_new.html에서 삭제됨',
  !adminSrc.includes('function _extractDetailMessage(body, fallback)'));
check('TD-S5-01: parseApiError()는 그대로 존재(대체 함수 무수정)',
  adminSrc.includes('function parseApiError(httpStatus, detail)'));
check('TD-S5-01: approveReservation()/rejectReservation()이 여전히 parseApiError만 사용(회귀 없음)', (() => {
  const bodyStart = adminSrc.indexOf('function approveReservation(');
  const bodyEnd = adminSrc.indexOf('rejectConfirmBtn.addEventListener');
  const body = adminSrc.slice(bodyStart, bodyEnd);
  return body.includes('parseApiError(') && !body.includes('_extractDetailMessage(');
})());

// ── TD-S5-02: admin_reservations_v2_new.html ──
check('TD-S5-02: renderStats()가 CMC_DB.getAll()을 더 이상 사용하지 않음', (() => {
  const method = extractMethodSource(legacySrc, 'renderStats() {');
  return !method.includes('CMC_DB.getAll()') && !method.includes('CMC_Stats.statusCounts()');
})());
check('TD-S5-02: renderStats()가 this.cache를 데이터 소스로 사용함', (() => {
  const method = extractMethodSource(legacySrc, 'renderStats() {');
  return method.includes('const all = this.cache');
})());
check('TD-S5-02: 다른 곳(예: openModal/saveStatus)의 CMC_DB/CMC_Stats 사용은 무변경(범위 밖 확대 변경 없음)',
  legacySrc.includes('CMC_DB.initSampleIfEmpty()'));

// ── TD-S5-02 실제 집계 동작(오프라인 실행, 실제 배포 소스 그대로) ──
const rawRenderStats = extractMethodSource(legacySrc, 'renderStats() {');
const wrapped = `(function ${rawRenderStats})`;
const elements = {
  'st-total': { textContent: '' }, 'st-접수': { textContent: '' }, 'st-확정': { textContent: '' },
  'st-완료': { textContent: '' }, 'st-취소변경': { textContent: '' },
};
const sandbox = { document: { getElementById: (id) => elements[id] } };
vm.createContext(sandbox);
const renderStats = vm.runInContext(wrapped, sandbox);

const fakeCache = [
  { reservationNo: 'R1', status: '예약접수' },
  { reservationNo: 'R2', status: '예약접수' },
  { reservationNo: 'R3', status: '예약확정' },
  { reservationNo: 'R4', status: '검진완료' },
  { reservationNo: 'R5', status: '예약취소' },
  { reservationNo: 'R6', status: '일정변경' },
  { reservationNo: 'R7', status: '거절' },
];
renderStats.call({ cache: fakeCache });

check('TD-S5-02: 전체 건수(7건)가 this.cache.length 그대로 반영',
  elements['st-total'].textContent === 7, String(elements['st-total'].textContent));
check('TD-S5-02: 예약접수 카운트(2건) 정확', elements['st-접수'].textContent === 2, String(elements['st-접수'].textContent));
check('TD-S5-02: 예약확정 카운트(1건) 정확', elements['st-확정'].textContent === 1, String(elements['st-확정'].textContent));
check('TD-S5-02: 검진완료 카운트(1건) 정확', elements['st-완료'].textContent === 1, String(elements['st-완료'].textContent));
check('TD-S5-02: 취소·변경 합산(예약취소1+일정변경1=2건) 정확',
  elements['st-취소변경'].textContent === 2, String(elements['st-취소변경'].textContent));

// 캐시가 비어 있을 때(초기 로딩 실패 등) 예외 없이 0으로 처리되는지
const elements2 = {
  'st-total': { textContent: '' }, 'st-접수': { textContent: '' }, 'st-확정': { textContent: '' },
  'st-완료': { textContent: '' }, 'st-취소변경': { textContent: '' },
};
const sandbox2 = { document: { getElementById: (id) => elements2[id] } };
vm.createContext(sandbox2);
const renderStats2 = vm.runInContext(wrapped, sandbox2);
renderStats2.call({ cache: [] });
check('TD-S5-02: 빈 cache에서도 예외 없이 전부 0 처리',
  elements2['st-total'].textContent === 0 && elements2['st-접수'].textContent === 0);

// ── 결과 저장 ──
const csvLines = ['테스트,결과,상세'];
for (const [name, status, detail] of results) {
  const esc = (s) => '"' + String(s).replace(/"/g, '""') + '"';
  csvLines.push([esc(name), status, esc(detail)].join(','));
}
fs.writeFileSync(
  path.join(__dirname, 'sprint6_commit6_2_technical_debt_cleanup_test_result.csv'),
  '﻿' + csvLines.join('\r\n') + '\r\n', 'utf8');

const total = results.length;
const passed = results.filter((r) => r[1] === 'PASS').length;
console.log(`TOTAL=${total} PASS=${passed} FAIL=${total - passed}`);
if (passed !== total) process.exit(1);
