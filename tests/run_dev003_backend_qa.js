/**
 * DEV-003 — 백엔드 LockService 보강 회귀·신규 테스트 (Node, Apps Script 모의 실행)
 *
 * app/apps_script/sheets_api_v3_final.gs 를 실제로 로드해 doGet/doPost를 그대로 실행한다.
 * LockService를 제어 가능한 스텁으로 교체해 Lock 획득 성공/실패 두 경로를 모두 검증한다.
 *
 * 실행: node tests/run_dev003_backend_qa.js
 * 종료 코드: 0(전체 통과) / 1(실패 있음)
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const GAS_FILE = path.join(__dirname, '..', 'app', 'apps_script', 'sheets_api_v3_final.gs');
const CONFIG_FILE = path.join(__dirname, '..', 'app', 'config_v2_new.js');
const RESULT_CSV = path.join(__dirname, 'dev003_backend_qa_result.csv');

function pad(n) { return String(n).padStart(2, '0'); }
function fakeFormatDate(date, _tz, fmt) {
  const y = date.getFullYear(), mo = pad(date.getMonth() + 1), d = pad(date.getDate());
  const h = pad(date.getHours()), mi = pad(date.getMinutes()), s = pad(date.getSeconds());
  if (fmt === 'yyyy-MM-dd HH:mm:ss') return `${y}-${mo}-${d} ${h}:${mi}:${s}`;
  if (fmt === 'yyyy-MM-dd') return `${y}-${mo}-${d}`;
  if (fmt === 'HH:mm') return `${h}:${mi}`;
  if (fmt === 'yyyyMMdd') return `${y}${mo}${d}`;
  return date.toISOString();
}

function makeFakeSheet(totalCols) {
  const rows = [new Array(totalCols).fill(null).map(() => ({ value: '', format: 'General' }))]; // header row placeholder
  const rangeApi = (r0, c0, nRows, nCols) => ({
    getValues() {
      const out = [];
      for (let i = 0; i < nRows; i++) {
        const row = [];
        for (let j = 0; j < nCols; j++) row.push((rows[r0 - 1 + i] || [])[c0 - 1 + j]?.value ?? '');
        out.push(row);
      }
      return out;
    },
    setValue(v) {
      if (!rows[r0 - 1]) rows[r0 - 1] = new Array(totalCols).fill(null).map(() => ({ value: '', format: 'General' }));
      rows[r0 - 1][c0 - 1] = { value: v, format: rows[r0 - 1][c0 - 1]?.format || 'General' };
      return this;
    },
    setNumberFormat(fmt) {
      if (!rows[r0 - 1]) rows[r0 - 1] = new Array(totalCols).fill(null).map(() => ({ value: '', format: 'General' }));
      rows[r0 - 1][c0 - 1] = { value: rows[r0 - 1][c0 - 1]?.value ?? '', format: fmt };
      return this;
    },
  });
  return {
    getLastRow: () => rows.length,
    getRange: (r, c, nRows, nCols) => rangeApi(r, c, nRows || 1, nCols || 1),
    appendRow(arr) { rows.push(arr.map((v) => ({ value: v, format: 'General' }))); },
    autoResizeColumns() { return this; },
    setFrozenRows() { return this; },
    _rawCell(r, c) { return rows[r - 1][c - 1]; },
  };
}

/* Lock 제어 상태 — 테스트에서 직접 조작 */
const lockState = { forceFail: false, acquireCount: 0, releaseCount: 0 };

function loadGasSandbox() {
  const src = fs.readFileSync(GAS_FILE, 'utf8');
  const sandbox = {
    console,
    Utilities: { formatDate: fakeFormatDate },
    LockService: {
      getScriptLock: () => ({
        waitLock(ms) {
          if (lockState.forceFail) throw new Error('Lock timeout (테스트 강제 실패)');
          lockState.acquireCount++;
        },
        releaseLock() { lockState.releaseCount++; },
      }),
    },
    ContentService: {
      MimeType: { JSON: 'JSON' },
      createTextOutput: (str) => ({ _content: str, setMimeType() { return this; }, getContent() { return this._content; } }),
    },
  };
  vm.createContext(sandbox);
  const sheet = makeFakeSheet(29);
  sandbox.SpreadsheetApp = { openById: () => ({ getSheetByName: () => sheet, insertSheet: () => sheet }) };
  vm.runInContext(src, sandbox, { filename: GAS_FILE });
  return { sandbox, sheet };
}

const results = [];
function check(name, condition, detail) {
  results.push({ name, pass: !!condition, detail: detail || '' });
  console.log(`${condition ? '✅ PASS' : '❌ FAIL'} — ${name}${detail ? ' — ' + detail : ''}`);
}

function run() {
  const { sandbox, sheet } = loadGasSandbox();

  /* ── 0) 사전 준비: 예약 1건 생성 ── */
  lockState.forceFail = false;
  const createRes = JSON.parse(sandbox.doPost({ postData: { contents: JSON.stringify({
    action: 'create', data: { name: 'DEV003테스트', birth: '1985-03-03', gender: '남성', program: 'BASIC',
      wishDate: '2026-08-10', wishTime: '10:00', company: 'DEV003QA' },
  }) } }).getContent());
  check('사전준비: create 성공', createRes.ok === true, JSON.stringify(createRes));
  const no = createRes.data.reservationNo;
  const acquireAfterCreate = lockState.acquireCount;
  const releaseAfterCreate = lockState.releaseCount;

  /* ── 1) updateStatus 정상 동작 + Lock 획득/해제 각 1회 ── */
  const usRes = JSON.parse(sandbox.doPost({ postData: { contents: JSON.stringify({
    action: 'updateStatus', no, status: '예약확정',
  }) } }).getContent());
  check('updateStatus: 정상 성공', usRes.ok === true, JSON.stringify(usRes));
  check('updateStatus: Lock 1회 획득', lockState.acquireCount === acquireAfterCreate + 1, `acquireCount=${lockState.acquireCount}`);
  check('updateStatus: Lock 1회 해제', lockState.releaseCount === releaseAfterCreate + 1, `releaseCount=${lockState.releaseCount}`);

  const getAfterStatus = JSON.parse(sandbox.doGet({ parameter: { action: 'get', no } }).getContent());
  check('updateStatus: 시트에 상태 반영됨', getAfterStatus.data.status === '예약확정', getAfterStatus.data.status);
  check('updateStatus: 예약확정일 자동 기록됨(회귀)', !!getAfterStatus.data.confirmedAt, getAfterStatus.data.confirmedAt);

  /* ── 2) updateStatus — Lock 획득 실패 시 503, 시트 미변경, releaseLock 미호출 ── */
  const acquireBeforeFail = lockState.acquireCount;
  const releaseBeforeFail = lockState.releaseCount;
  lockState.forceFail = true;
  const usFailRes = JSON.parse(sandbox.doPost({ postData: { contents: JSON.stringify({
    action: 'updateStatus', no, status: '검진완료',
  }) } }).getContent());
  check('updateStatus: Lock 실패 시 503 반환', usFailRes.ok === false && usFailRes.code === 503, JSON.stringify(usFailRes));
  check('updateStatus: Lock 실패 시 acquireCount 불변', lockState.acquireCount === acquireBeforeFail, `acquireCount=${lockState.acquireCount}`);
  check('updateStatus: Lock 실패 시 releaseLock 호출 안 됨(획득한 적 없으므로)', lockState.releaseCount === releaseBeforeFail, `releaseCount=${lockState.releaseCount}`);
  lockState.forceFail = false;
  const getAfterFail = JSON.parse(sandbox.doGet({ parameter: { action: 'get', no } }).getContent());
  check('updateStatus: Lock 실패 시 시트 값 미변경(여전히 예약확정)', getAfterFail.data.status === '예약확정', getAfterFail.data.status);

  /* ── 3) update(note 단일 필드) 정상 동작 + Lock 획득/해제 각 1회 ── */
  const acquireBeforeNote = lockState.acquireCount;
  const releaseBeforeNote = lockState.releaseCount;
  const noteRes = JSON.parse(sandbox.doPost({ postData: { contents: JSON.stringify({
    action: 'update', no, data: { note: '관리자 메모 테스트' },
  }) } }).getContent());
  check('update(note): 정상 성공', noteRes.ok === true, JSON.stringify(noteRes));
  check('update(note): Lock 1회 획득', lockState.acquireCount === acquireBeforeNote + 1, `acquireCount=${lockState.acquireCount}`);
  check('update(note): Lock 1회 해제', lockState.releaseCount === releaseBeforeNote + 1, `releaseCount=${lockState.releaseCount}`);
  const getAfterNote = JSON.parse(sandbox.doGet({ parameter: { action: 'get', no } }).getContent());
  check('update(note): 특이사항 반영됨', getAfterNote.data.note === '관리자 메모 테스트', getAfterNote.data.note);

  /* ── 4) update — Lock 획득 실패 시 503, 시트 미변경 ── */
  lockState.forceFail = true;
  const noteFailRes = JSON.parse(sandbox.doPost({ postData: { contents: JSON.stringify({
    action: 'update', no, data: { note: '실패해야 하는 메모' },
  }) } }).getContent());
  check('update(note): Lock 실패 시 503 반환', noteFailRes.ok === false && noteFailRes.code === 503, JSON.stringify(noteFailRes));
  lockState.forceFail = false;
  const getAfterNoteFail = JSON.parse(sandbox.doGet({ parameter: { action: 'get', no } }).getContent());
  check('update(note): Lock 실패 시 시트 값 미변경', getAfterNoteFail.data.note === '관리자 메모 테스트', getAfterNoteFail.data.note);

  /* ── 5) 404 경로에서도 releaseLock이 호출되는지(락 누수 방지, finally 검증) ── */
  const acquireBefore404 = lockState.acquireCount;
  const releaseBefore404 = lockState.releaseCount;
  const notFoundRes = JSON.parse(sandbox.doPost({ postData: { contents: JSON.stringify({
    action: 'updateStatus', no: '20260101-9999', status: '예약확정',
  }) } }).getContent());
  check('updateStatus: 존재하지 않는 예약번호 → 404', notFoundRes.ok === false && notFoundRes.code === 404, JSON.stringify(notFoundRes));
  check('updateStatus: 404여도 Lock은 획득됨', lockState.acquireCount === acquireBefore404 + 1, `acquireCount=${lockState.acquireCount}`);
  check('updateStatus: 404여도 finally에서 Lock 해제됨(누수 없음)', lockState.releaseCount === releaseBefore404 + 1, `releaseCount=${lockState.releaseCount}`);

  /* ── 6) 회귀: create/list/summary/updateOps 로직 무변경 확인 ── */
  const listRes = JSON.parse(sandbox.doGet({ parameter: { action: 'list' } }).getContent());
  check('회귀: list 정상 동작', listRes.ok === true && listRes.count >= 1, `count=${listRes.count}`);

  const opsRes = JSON.parse(sandbox.doPost({ postData: { contents: JSON.stringify({
    action: 'updateOps', no, data: { examRoom: '1번검사실' },
  }) } }).getContent());
  check('회귀: updateOps 정상 동작(Lock 영향 없음)', opsRes.ok === true, JSON.stringify(opsRes));

  const summaryRes = JSON.parse(sandbox.doGet({ parameter: { action: 'summary', date: '2026-08-10' } }).getContent());
  check('회귀: summary 정상 동작', summaryRes.ok === true, JSON.stringify(summaryRes));

  /* ── 7) 회귀: STEP1.5 DateFix 로직 보존 확인(update 경로) ── */
  const dateFixRes = JSON.parse(sandbox.doPost({ postData: { contents: JSON.stringify({
    action: 'update', no, data: { wishDate: '2026-08-15' },
  }) } }).getContent());
  check('회귀: update 후에도 DateFix(텍스트 서식) 유지', dateFixRes.ok === true, JSON.stringify(dateFixRes));
  const wishDateRow = sheet.getLastRow(); // no가 첫 행이므로 2번 행 고정
  const wishDateCell = sheet._rawCell(2, 8); // COL.희망검진일 = 8
  check('회귀: 희망검진일 셀이 텍스트 서식(@)으로 저장됨', wishDateCell.format === '@' && wishDateCell.value === '2026-08-15', JSON.stringify(wishDateCell));

  /* ── 8) config_v2_new.js sheetName 값 정정 확인 (Task 2 산출물) ── */
  const configSrc = fs.readFileSync(CONFIG_FILE, 'utf8');
  check("config_v2_new.js: sheetName이 '종합검진_예약대장'으로 정정됨", /sheetName:\s*'종합검진_예약대장'/.test(configSrc), '정규식 매치 확인');
  check("config_v2_new.js: 정정 전 값('예약현황')이 sheetName 필드에 남아있지 않음", !/appsScript[\s\S]{0,120}sheetName:\s*'예약현황'/.test(configSrc), '정규식 불일치 확인');

  /* ── 결과 집계 ── */
  const failCount = results.filter((r) => !r.pass).length;
  const csvLines = ['name,pass,detail', ...results.map((r) => `"${r.name}",${r.pass},"${(r.detail || '').replace(/"/g, '""')}"`)];
  fs.writeFileSync(RESULT_CSV, csvLines.join('\n'), 'utf8');

  console.log('\n──────────────────────────────');
  console.log(`총 ${results.length}건 중 실패 ${failCount}건`);
  console.log(`결과 저장: ${RESULT_CSV}`);
  process.exit(failCount === 0 ? 0 : 1);
}

run();
