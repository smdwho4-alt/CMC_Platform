/**
 * STEP1.5 DateFix — 코드 레벨 회귀 테스트 (Node, Apps Script 모의 실행)
 *
 * 목적: app/apps_script/sheets_api_v3_final.gs 를 실제로 로드해
 *       Google Sheets의 "날짜처럼 보이는 문자열을 Date로 자동 변환"하는
 *       동작을 모의(mock)한 가짜 SpreadsheetApp/Utilities/LockService/ContentService
 *       위에서 doGet/doPost를 그대로 실행한다.
 *       .gs 파일 내용을 복제하지 않고 원본을 vm 샌드박스에 그대로 로드하므로,
 *       실제 배포되는 코드와 테스트 대상이 항상 일치한다.
 *
 * 실행: node tests/run_step1_5_datefix_qa.js
 * 종료 코드: 0(전체 통과) / 1(실패 있음)
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const GAS_FILE = path.join(__dirname, '..', 'app', 'apps_script', 'sheets_api_v3_final.gs');
const RESULT_CSV = path.join(__dirname, 'step1_5_datefix_qa_result.csv');

/* ── Google Sheets 자동 날짜변환 모의 ─────────────────────────
 * 셀 서식이 '@'(텍스트)로 강제되지 않은 상태에서 날짜/시간처럼 보이는
 * 문자열이 setValue/appendRow로 들어오면 Sheets가 Date로 자동 변환한다.
 * wishTime처럼 "HH:mm"만 있는 값은 스프레드시트 기준일(1899-12-30)의
 * datetime으로 저장되는 실제 버그를 그대로 재현한다.
 *
 * 주의: vm 샌드박스는 host(Node)와 별개의 realm이므로, 여기서 생성하는
 * Date 객체는 반드시 샌드박스 자체의 Date 생성자(DateCtor)를 사용해야
 * .gs 코드 내부의 `val instanceof Date` 검사가 올바르게 동작한다.
 * (host의 Date로 만들면 서로 다른 realm이라 instanceof가 항상 false가 됨) */
function makeAutoConvert(DateCtor) {
  return function autoConvert(raw) {
    if (typeof raw !== 'string') return raw;
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
      const [y, m, d] = raw.split('-').map(Number);
      return new DateCtor(y, m - 1, d, 0, 0, 0);
    }
    if (/^\d{2}:\d{2}$/.test(raw)) {
      const [hh, mm] = raw.split(':').map(Number);
      return new DateCtor(1899, 11, 30, hh, mm, 0);
    }
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(raw)) {
      const [datePart, timePart] = raw.split(' ');
      const [y, m, d] = datePart.split('-').map(Number);
      const [hh, mm, ss] = timePart.split(':').map(Number);
      return new DateCtor(y, m - 1, d, hh, mm, ss);
    }
    return raw;
  };
}

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

/* ── 가짜 시트(Cell 배열) ───────────────────────────────────── */
function makeFakeSheet(totalCols, DateCtor) {
  const autoConvert = makeAutoConvert(DateCtor);
  const rows = [new Array(totalCols).fill(null).map(() => ({ value: '', format: 'General' }))]; // header row placeholder

  function cellSetValue(cell, raw) {
    if (cell.format === '@') {
      cell.value = String(raw);
    } else {
      cell.value = autoConvert(raw);
    }
  }

  const rangeApi = (r0, c0, nRows, nCols) => ({
    getValues() {
      const out = [];
      for (let i = 0; i < nRows; i++) {
        const row = [];
        for (let j = 0; j < nCols; j++) row.push(rows[r0 - 1 + i][c0 - 1 + j].value);
        out.push(row);
      }
      return out;
    },
    setValues(values) {
      values.forEach((row, i) => row.forEach((v, j) => { rows[r0 - 1 + i][c0 - 1 + j] = { value: v, format: 'General' }; }));
      return this;
    },
    setValue(v) {
      cellSetValue(rows[r0 - 1][c0 - 1], v);
      return this;
    },
    setNumberFormat(fmt) {
      for (let i = 0; i < nRows; i++) for (let j = 0; j < nCols; j++) rows[r0 - 1 + i][c0 - 1 + j].format = fmt;
      return this;
    },
    setBackground() { return this; },
    setFontColor() { return this; },
    setFontWeight() { return this; },
  });

  return {
    getLastRow: () => rows.length,
    getRange: (r, c, nRows, nCols) => rangeApi(r, c, nRows || 1, nCols || 1),
    appendRow(arr) {
      rows.push(arr.map((v) => ({ value: autoConvert(v), format: 'General' })));
    },
    autoResizeColumns() { return this; },
    setFrozenRows() { return this; },
    /* 테스트 검증용: 셀의 실제 저장 타입(Date 인지 문자열인지) 확인 */
    _rawCell(r, c) { return rows[r - 1][c - 1]; },
    _autoConvert: autoConvert,
    _DateCtor: DateCtor,
  };
}

function loadGasSandbox() {
  const src = fs.readFileSync(GAS_FILE, 'utf8');

  const sandbox = {
    console,
    Utilities: { formatDate: fakeFormatDate },
    LockService: { getScriptLock: () => ({ waitLock() {}, releaseLock() {} }) },
    ContentService: {
      MimeType: { JSON: 'JSON' },
      createTextOutput: (str) => ({
        _content: str,
        setMimeType() { return this; },
        getContent() { return this._content; },
      }),
    },
  };
  vm.createContext(sandbox);
  /* 샌드박스 자체의 Date 생성자를 확보 — host Date와는 다른 realm이므로
   * 가짜 시트가 만드는 Date 객체도 반드시 이 생성자를 사용해야 .gs 내부의
   * `instanceof Date` 검사가 정상 동작한다. */
  const SandboxDate = vm.runInContext('Date', sandbox);
  const sheet = makeFakeSheet(29, SandboxDate);
  sandbox.SpreadsheetApp = {
    openById: () => ({
      getSheetByName: () => sheet,
      insertSheet: () => sheet,
    }),
  };
  vm.runInContext(src, sandbox, { filename: GAS_FILE });
  return { sandbox, sheet };
}

/* ── 테스트 러너 ─────────────────────────────────────────────── */
const results = [];
function check(name, condition, detail) {
  results.push({ name, pass: !!condition, detail: detail || '' });
  console.log(`${condition ? '✅ PASS' : '❌ FAIL'} — ${name}${detail ? ' — ' + detail : ''}`);
}

function run() {
  const { sandbox, sheet } = loadGasSandbox();

  /* 1) create — 신규 예약: birth/wishDate/wishTime 텍스트 저장 확인 */
  const createReq = { postData: { contents: JSON.stringify({
    action: 'create',
    data: { name: '자동QA', birth: '1980-05-05', gender: '남성', program: 'SMART',
            wishDate: '2026-07-20', wishTime: '09:00', company: '자동QA사업장' },
  }) } };
  const createRes = JSON.parse(sandbox.doPost(createReq).getContent());
  check('create 호출 성공', createRes.ok === true, JSON.stringify(createRes));
  const no = createRes.data && createRes.data.reservationNo;

  const getRes1 = JSON.parse(sandbox.doGet({ parameter: { action: 'get', no } }).getContent());
  check('get: birth 포맷 정상 (시간 없음)', getRes1.data.birth === '1980-05-05', getRes1.data.birth);
  check('get: wishDate 포맷 정상 (시간 없음)', getRes1.data.wishDate === '2026-07-20', getRes1.data.wishDate);
  check('get: wishTime 포맷 정상 (1899 에폭 없음)', getRes1.data.wishTime === '09:00', getRes1.data.wishTime);

  /* 2) create 직후 시트 원본 셀이 실제로 텍스트로 저장됐는지 확인 (표시값이 아니라 원본 타입) */
  const lastRow = sheet.getLastRow();
  const birthCell = sheet._rawCell(lastRow, 4); // COL.생년월일 = 4
  check('시트 원본: 생년월일 셀이 문자열로 저장됨(Date 아님)', typeof birthCell.value === 'string' && birthCell.value === '1980-05-05', String(birthCell.value));

  /* 3) summary — 당일 통계 매칭 확인 (원본 raw 비교 시 실패했던 케이스) */
  const summaryRes1 = JSON.parse(sandbox.doGet({ parameter: { action: 'summary', date: '2026-07-20' } }).getContent());
  check('summary: 신규 예약이 당일 통계에 포함됨', summaryRes1.data.total === 1, `total=${summaryRes1.data.total}`);

  /* 3-1) update가 "레거시 행"(STEP1.5 배포 이전에 생성되어 셀 서식이 아직 자동/Date인 행)을
   *      수정할 때도 텍스트로 강제되는지 확인. create 시점에는 이미 텍스트로 저장되므로
   *      (사이트 서식이 sticky) 이 시나리오는 반드시 "이미 Date로 저장된 셀"을 인위로
   *      만들어야만 _actionUpdate의 방어 로직 유무를 실제로 구분할 수 있다. */
  const legacyCreateReq = { postData: { contents: JSON.stringify({
    action: 'create',
    data: { name: '레거시행', birth: '1990-01-01', gender: '여성', program: 'BASIC',
            wishDate: '2026-07-21', wishTime: '11:00', company: '레거시QA' },
  }) } };
  const legacyCreateRes = JSON.parse(sandbox.doPost(legacyCreateReq).getContent());
  const legacyNo = legacyCreateRes.data && legacyCreateRes.data.reservationNo;
  const legacyRowNum = sheet.getLastRow();
  /* 강제로 "구버전 버그처럼 서식이 자동(General)이고 값이 Date인" 상태로 되돌려
   * STEP1.5 배포 이전에 만들어진 레거시 행을 재현한다. */
  const legacyWishCell = sheet._rawCell(legacyRowNum, 8); // COL.희망검진일 = 8
  legacyWishCell.format = 'General';
  legacyWishCell.value = sheet._autoConvert('2026-07-21');
  check('사전조건: 레거시 행의 희망검진일 셀이 Date 타입으로 재현됨', legacyWishCell.value instanceof sheet._DateCtor, String(legacyWishCell.value));

  const legacyUpdateReq = { postData: { contents: JSON.stringify({
    action: 'update', no: legacyNo, data: { wishDate: '2026-07-22' },
  }) } };
  sandbox.doPost(legacyUpdateReq);
  const legacyWishCellAfter = sheet._rawCell(legacyRowNum, 8);
  check('update: 레거시(Date 타입) 행을 수정하면 텍스트로 강제 전환됨 (_actionUpdate DateFix)',
    typeof legacyWishCellAfter.value === 'string' && legacyWishCellAfter.value === '2026-07-22',
    String(legacyWishCellAfter.value));

  const legacySummary = JSON.parse(sandbox.doGet({ parameter: { action: 'summary', date: '2026-07-22' } }).getContent());
  check('summary: 레거시 행 수정 후 새 날짜로 정상 집계됨', legacySummary.data.total === 1, `total=${legacySummary.data.total}`);

  /* 4) update — wishDate를 변경해도 텍스트 유지되는지 확인 (구버전 코드였다면 Date로 재변환되어 재발했을 결함) */
  const updateReq = { postData: { contents: JSON.stringify({
    action: 'update', no, data: { wishDate: '2026-08-01' },
  }) } };
  const updateRes = JSON.parse(sandbox.doPost(updateReq).getContent());
  check('update 호출 성공', updateRes.ok === true, JSON.stringify(updateRes));

  const wishDateCellAfterUpdate = sheet._rawCell(lastRow, 8); // COL.희망검진일 = 8
  check('update 후: 희망검진일 셀이 여전히 문자열로 저장됨(Date로 재변환되지 않음)',
    typeof wishDateCellAfterUpdate.value === 'string' && wishDateCellAfterUpdate.value === '2026-08-01',
    String(wishDateCellAfterUpdate.value));

  const summaryRes2 = JSON.parse(sandbox.doGet({ parameter: { action: 'summary', date: '2026-08-01' } }).getContent());
  check('summary: update 이후에도 새 희망일자로 정상 매칭됨', summaryRes2.data.total === 1, `total=${summaryRes2.data.total}`);
  const summaryOld = JSON.parse(sandbox.doGet({ parameter: { action: 'summary', date: '2026-07-20' } }).getContent());
  check('summary: 이전 희망일자에는 더 이상 집계되지 않음', summaryOld.data.total === 0, `total=${summaryOld.data.total}`);

  /* 5) 레거시 손상 데이터(과거 버그로 Date 타입으로 저장된 행) 시뮬레이션
   *    — 이런 행이 남아있어도 summary가 죽지 않고(예외 없이) 정상 필터링하는지 확인 */
  sheet.getRange(sheet.getLastRow(), 1, 1, 1); // no-op to ensure API shape
  const legacyRowIdx = sheet.getLastRow() + 1;
  // 직접 raw row push로 "Date로 저장된 레거시 행"을 재현 (appendRow는 autoConvert를 타므로 그대로 사용)
  sandbox.doPost({ postData: { contents: JSON.stringify({
    action: 'create',
    data: { name: '레거시시뮬', birth: '1975-01-01', gender: '여성', program: 'BASIC',
            wishDate: '2026-08-01', wishTime: '10:30', company: '레거시QA' },
  }) } });
  const legacyRow = sheet.getLastRow();
  // 강제로 셀 포맷을 되돌려 "구버전 버그처럼 Date로 저장된" 상태를 재현
  const legacyBirthCell = sheet._rawCell(legacyRow, 4);
  const legacyWishDateCell = sheet._rawCell(legacyRow, 8);
  legacyBirthCell.format = 'General'; legacyBirthCell.value = sheet._autoConvert('1975-01-01');
  legacyWishDateCell.format = 'General'; legacyWishDateCell.value = sheet._autoConvert('2026-08-01');

  const summaryRes3 = JSON.parse(sandbox.doGet({ parameter: { action: 'summary', date: '2026-08-01' } }).getContent());
  check('summary: 레거시(Date 타입) 손상 데이터도 _rowToObj 정규화로 정상 집계됨', summaryRes3.data.total === 2, `total=${summaryRes3.data.total}`);

  const getLegacy = JSON.parse(sandbox.doGet({ parameter: { action: 'get', no: `${no.split('-')[0]}-` + String(Number(no.split('-')[1]) + 2).padStart(4, '0') } }).getContent());
  if (getLegacy.ok) {
    check('get: 레거시(Date 타입) 데이터도 표시 시 정상 포맷으로 변환됨', getLegacy.data.wishDate === '2026-08-01', getLegacy.data.wishDate);
  }

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
