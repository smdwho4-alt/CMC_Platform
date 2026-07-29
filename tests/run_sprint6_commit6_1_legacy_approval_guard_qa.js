// Sprint 6 Commit6-1 — Legacy Reservation Approval Transition Guard 테스트 러너
//
// 대상: app/pages/admin_reservations_v2_new.html의 AA.saveStatus() 안에 추가된
// approvalBlocked 가드("예약확정" 전이만 차단, 그 외 검진완료/일정변경/예약취소/거절/
// 메모저장은 무영향).
//
// 중요(안전 근거): app/config_v2_new.js를 확인한 결과 dataSource:'google'과 함께
// 실제 운영 Apps Script Web App URL이 하드코딩되어 있다(script.google.com/...).
// 이 페이지를 실제 브라우저에서 로드하면 DOMContentLoaded 시점에 AA.init()이 즉시
// CMC_SheetsServiceV2.getAll()(실제 Sheets 목록 조회)을 호출하므로, 실브라우저
// 클릭 QA는 운영 데이터에 실제 네트워크 요청을 보낼 위험이 있어 이번 검증에서는
// 사용하지 않는다(운영 Sheets/GAS 변경·접근 금지 원칙). 대신 이 파일에서 실제로
// 배포되는 saveStatus() 소스 텍스트를 그대로 추출해(재구현 없이) Node.js vm
// 샌드박스에서 document/CMC_SheetsServiceV2를 가짜 객체로 주입해 완전히 오프라인으로
// 실행한다 — 실네트워크 호출 0건.
//
// 결과: tests/sprint6_commit6_1_legacy_approval_guard_test_result.csv

'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const HTML_PATH = path.join(ROOT, 'app', 'pages', 'admin_reservations_v2_new.html');
const src = fs.readFileSync(HTML_PATH, 'utf8');

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

// "async saveStatus() { ... }" 형태를 "(async function saveStatus() { ... })"로 감싸
// 독립 실행 가능한 함수 표현식으로 만든다(원문 로직은 한 글자도 바꾸지 않음).
const rawMethod = extractMethodSource(src, 'async saveStatus() {');
const wrapped = `(async function ${rawMethod.replace(/^async\s+/, '')})`;

const results = [];
function check(name, ok, detail) {
  results.push([name, ok ? 'PASS' : 'FAIL', detail || '']);
  console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' - ' + detail : ''}`);
}

// ── 0. 정적 확인 ──
check('CMC_CONFIG.dataSource가 google로 설정되어 실제 운영 GAS URL을 사용함을 확인' +
      '(그래서 이 테스트가 실브라우저 클릭 대신 오프라인 시뮬레이션을 쓰는 근거)',
  fs.readFileSync(path.join(ROOT, 'app', 'config_v2_new.js'), 'utf8').includes("dataSource: 'google'"));
check('saveStatus() 안에 approvalBlocked 가드 존재',
  rawMethod.includes("approvalBlocked = statusChanged && newStatus === '예약확정'"));
check('approvalBlocked이 true일 때 CMC_SheetsServiceV2.updateStatus 호출부와 분리된 분기(else if)로 존재',
  rawMethod.includes('if (approvalBlocked) {') && rawMethod.includes('} else if (statusChanged) {'));
check('#statusSel의 옵션 목록 자체는 무수정(검진완료/일정변경/예약취소/거절 옵션 유지)',
  src.includes('<option>예약접수</option><option>예약확정</option><option>검진완료</option>'
    + '<option>일정변경</option><option>예약취소</option><option>거절</option>'));
check('noteChanged(메모저장) 분기는 무수정(if (noteChanged) { 블록 그대로)',
  rawMethod.includes('if (noteChanged) {') && rawMethod.includes('CMC_SheetsServiceV2.update(no, this._buildNotePayload(newNote))'));

// ── 1. 오프라인 실행 하네스 ──
function makeHarness(initialStatus, initialNote) {
  const elements = {
    statusSel: { value: initialStatus },
    dNote: { value: initialNote },
  };
  const calls = { updateStatus: [], update: [] };
  const toasts = [];
  const cached = { reservationNo: 'RSV-QA-0001', status: initialStatus, note: initialNote };

  const sandbox = {
    document: { getElementById: (id) => elements[id] },
    CMC_SheetsServiceV2: {
      updateStatus: async (no, status) => { calls.updateStatus.push([no, status]); return { ok: true }; },
      update: async (no, payload) => { calls.update.push([no, payload]); return { ok: true }; },
    },
  };
  vm.createContext(sandbox);
  const fn = vm.runInContext(wrapped, sandbox);

  const thisCtx = {
    selectedNo: cached.reservationNo,
    cache: [cached],
    _buildNotePayload: (note) => ({ note }),
    render() {},
    closeModal() { thisCtx._closed = true; },
    toast(msg) { toasts.push(msg); },
    async loadAll() { thisCtx._reloaded = true; },
  };
  return { fn, thisCtx, elements, calls, toasts, cached };
}

// ── 2. "예약확정" 전이 차단(핵심 시나리오) ──
(async () => {
  const h = makeHarness('예약접수', '');
  h.elements.statusSel.value = '예약확정';
  await h.fn.call(h.thisCtx);
  check('(1) 예약확정 선택 후 저장 → CMC_SheetsServiceV2.updateStatus 호출되지 않음(핵심 차단 확인)',
    h.calls.updateStatus.length === 0, JSON.stringify(h.calls.updateStatus));
  check('(1) cached.status가 예약확정으로 바뀌지 않고 원래 값(예약접수) 유지',
    h.cached.status === '예약접수', h.cached.status);
  check('(1) statusSel.value가 원래 상태(예약접수)로 되돌려짐(화면 표시 일관성)',
    h.elements.statusSel.value === '예약접수', h.elements.statusSel.value);
  check('(1) 안내 메시지에 "Admin Portal" 및 "승인" 언급 포함(운영자 유도, 새 Business Rule 문구 아님)',
    h.toasts.some((t) => t.includes('Admin Portal') && t.includes('승인')), JSON.stringify(h.toasts));
  check('(1) 모달이 닫히지 않음(실패로 처리되어 열린 채 메시지 확인 가능)', !h.thisCtx._closed);

  // ── 3. 검진완료 정상 ──
  const h2 = makeHarness('예약확정', '');
  h2.elements.statusSel.value = '검진완료';
  await h2.fn.call(h2.thisCtx);
  check('(2) 검진완료 전이 → updateStatus 정상 호출됨(무영향 확인)',
    h2.calls.updateStatus.length === 1 && h2.calls.updateStatus[0][1] === '검진완료',
    JSON.stringify(h2.calls.updateStatus));
  check('(2) cached.status가 검진완료로 정상 반영', h2.cached.status === '검진완료');
  check('(2) 모달이 정상적으로 닫힘(성공 처리)', h2.thisCtx._closed === true);

  // ── 4. 일정변경 정상 ──
  const h3 = makeHarness('예약확정', '');
  h3.elements.statusSel.value = '일정변경';
  await h3.fn.call(h3.thisCtx);
  check('(3) 일정변경 전이 → updateStatus 정상 호출됨(무영향 확인)',
    h3.calls.updateStatus.length === 1 && h3.calls.updateStatus[0][1] === '일정변경',
    JSON.stringify(h3.calls.updateStatus));
  check('(3) cached.status가 일정변경으로 정상 반영', h3.cached.status === '일정변경');

  // ── 5. 예약취소 정상 ──
  const h4 = makeHarness('예약확정', '');
  h4.elements.statusSel.value = '예약취소';
  await h4.fn.call(h4.thisCtx);
  check('(4) 예약취소 전이 → updateStatus 정상 호출됨(무영향 확인)',
    h4.calls.updateStatus.length === 1 && h4.calls.updateStatus[0][1] === '예약취소',
    JSON.stringify(h4.calls.updateStatus));
  check('(4) cached.status가 예약취소로 정상 반영', h4.cached.status === '예약취소');

  // ── 6. 거절 정상(참고 — Admin Portal의 거절 API와는 별개 경로, Legacy 자체 기능 유지) ──
  const h5 = makeHarness('예약접수', '');
  h5.elements.statusSel.value = '거절';
  await h5.fn.call(h5.thisCtx);
  check('(5) 거절 전이 → updateStatus 정상 호출됨(무영향 확인)',
    h5.calls.updateStatus.length === 1 && h5.calls.updateStatus[0][1] === '거절',
    JSON.stringify(h5.calls.updateStatus));

  // ── 7. 메모만 변경(상태 무변경) → 예약확정 가드와 무관하게 정상 동작 ──
  const h6 = makeHarness('예약확정', '기존 메모');
  h6.elements.statusSel.value = '예약확정'; // 상태 변경 없음(그대로)
  h6.elements.dNote.value = '새 메모 내용';
  await h6.fn.call(h6.thisCtx);
  check('(6) 상태 변경 없이 메모만 변경 → updateStatus 호출 안 됨(애초에 statusChanged=false)',
    h6.calls.updateStatus.length === 0);
  check('(6) update(메모 저장)는 정상 호출됨', h6.calls.update.length === 1 && h6.calls.update[0][1].note === '새 메모 내용');
  check('(6) 모달 정상 닫힘(메모만 성공해도 성공 처리)', h6.thisCtx._closed === true);

  // ── 8. 예약확정 차단 + 메모 변경 동시 시도 → 메모는 별도로 성공, 상태만 차단 ──
  const h7 = makeHarness('예약접수', '기존 메모');
  h7.elements.statusSel.value = '예약확정';
  h7.elements.dNote.value = '동시 변경 메모';
  await h7.fn.call(h7.thisCtx);
  check('(7) 예약확정 차단되어도 메모 저장은 독립적으로 성공(update 호출됨)',
    h7.calls.update.length === 1 && h7.calls.updateStatus.length === 0);
  check('(7) 모달은 닫히지 않음(상태 실패가 있으므로 전체 성공 아님)', !h7.thisCtx._closed);
  check('(7) 안내 메시지에 메모 저장 실패 언급이 없음(메모는 실제로 성공했으므로)',
    !h7.toasts.some((t) => t.includes('메모 저장 실패')), JSON.stringify(h7.toasts));

  // ── 결과 저장 ──
  const csvLines = ['테스트,결과,상세'];
  for (const [name, status, detail] of results) {
    const esc = (s) => '"' + String(s).replace(/"/g, '""') + '"';
    csvLines.push([esc(name), status, esc(detail)].join(','));
  }
  fs.writeFileSync(
    path.join(__dirname, 'sprint6_commit6_1_legacy_approval_guard_test_result.csv'),
    '﻿' + csvLines.join('\r\n') + '\r\n', 'utf8');

  const total = results.length;
  const passed = results.filter((r) => r[1] === 'PASS').length;
  console.log(`TOTAL=${total} PASS=${passed} FAIL=${total - passed}`);
  if (passed !== total) process.exit(1);
})();
