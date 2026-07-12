# DEV-003 — 관리자 예약관리 Google Sheets Live 연동 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline, 이 세션에서 직접 실행) 또는 superpowers:subagent-driven-development로 태스크별 실행. 각 단계는 체크박스(`- [ ]`)로 추적한다.

**Goal:** `DEV-003_관리자예약관리_Sheets연동_Design_Final_new.md`(PM 승인 완료 설계)를 코드로 구현한다 — 관리자 예약관리 화면의 신규 버전을 만들어 목록/상세/상태변경/메모저장을 Google Sheets Live에 연결하고, 백엔드에 동시성 Lock을 보강한다.

**Architecture:** 원본 `admin_reservations_new.html`은 무수정 보존하고 `admin_reservations_v2_new.html`을 신규 생성해 `CMC_SheetsServiceV2`(기존 어댑터, 무수정 재사용)로 배선한다. 백엔드 `sheets_api_v3_final.gs`의 `_actionUpdateStatus`/`_actionUpdate`에 `_actionCreate`와 동일한 LockService 패턴을 추가한다. `config_v2_new.js`는 `sheetName` 값만 정정한다.

**Tech Stack:** 순수 HTML/CSS/JS(프레임워크 없음), Google Apps Script, Node.js(v24) `vm` 모듈 기반 테스트(외부 프레임워크 없음, 기존 `tests/run_step1_5_datefix_qa.js` 패턴 재사용).

## Global Constraints

- **Architecture Freeze 유지**: 폴더/파일 구조 신설·이동·이름변경 금지. 새 파일은 기존 명명 규칙(`_new`, `_v2_new`)만 사용.
- **기존 기능 Regression 금지**: `admin_reservations_new.html`(원본), `reservation_v2_new.html`, `admin_dashboard_*.html`은 무수정·무영향.
- **기존 Reservation 구조 재사용**: `CMC_SheetsServiceV2`, `CMC_DB`, `CMC_Stats`, `db_service_new.js`, `programs_data_new.js`의 인터페이스를 변경하지 않는다. 백엔드 액션명·응답 포맷·다른 액션(`create`/`list`/`get`/`summary`/`updateOps`) 로직 불변.
- **완료 후 단위 테스트 및 통합 테스트 수행**: 각 태스크는 Node 기반 자동 테스트로 검증한다(아래 각 태스크 참조).
- **Pilot Ready 체크리스트 검증**: `DEV-003_..._Design_Final_new.md` §11 QA Checklist 항목별로 이 세션에서 검증 가능한 범위(LOCAL 모드 + 코드 레벨)를 명시하고, GOOGLE Live 모드 항목은 사용자의 수동 배포 이후로 이월한다.
- **커밋은 사용자 확인 후에만 진행**: 이 계획의 각 태스크 마지막 "커밋" 단계는 실행 직전 사용자에게 커밋 여부를 확인한다(세션 전역 규칙 — 명시적 요청 없이 자동 커밋하지 않는다).
- **파일 삭제·이동·이름변경 금지**: 이번 계획은 신규 파일 생성 및 기존 2개 파일(`sheets_api_v3_final.gs`, `config_v2_new.js`)의 값/로직 보강만 포함한다.

---

## 현재 코드 기준선 (구현 전 확인된 사실)

- `sheets_api_v3_final.gs`: `_actionUpdateStatus`(L376), `_actionUpdate`(L447) 모두 현재 LockService 미사용. `_actionCreate`(L311)는 이미 Lock 패턴 적용됨(L317-372) — 이 패턴을 그대로 재사용한다.
- `google_sheets_service_v2_new.js`: `getAll/getOne/updateStatus/update` 인터페이스가 이미 Mock/Live 양쪽 구현되어 있음 — **무수정 재사용**.
- `config_v2_new.js`(현재 디스크 상태): `dataSource:'google'`, `webAppUrl` 값 존재, `sheetName:'예약현황'`(정정 필요 → `'종합검진_예약대장'`).
- `admin_reservations_new.html`(원본, 309줄): `CMC_DB.getAll()/findByNo()/update()` 직접 호출, `dNote`는 읽기전용 `<span>`, `optionalTests`는 배열 가정(`.join`/`.length` 사용).
- **발견한 데이터 형태 불일치(설계 문서에 명시 안 됨, 이번 구현에서 방어 처리 필요)**: Sheets `_rowToObj`(L196-208)는 `optionalTests`를 콤마로 이어붙인 **문자열**로 반환하지만, LOCAL 모드(`CMC_DB`)는 **배열**로 저장한다. 원본 코드의 `r.optionalTests.join(', ')`을 GOOGLE 모드 데이터에 그대로 쓰면 `TypeError`(문자열에는 `.join` 없음)가 난다. → 배열/문자열 모두 받아 배열로 정규화하는 헬퍼(`_optionalTestsArray`)를 추가해 상세모달·CSV 두 곳에 적용한다.
- `CMC`(전역 네임스페이스: `STATUS`/`esc`/`maskPhone`/`formatDateTime`/`today`/`STORAGE_KEY`)는 `app/data/programs_data_new.js`에 정의되어 있고 `admin_reservations_new.html`에서 최초로 로드된다 — v2에서도 동일 순서 유지 필요.

---

### Task 1: 백엔드 — `_actionUpdateStatus` / `_actionUpdate`에 LockService 보강

**Files:**
- Modify: `app/apps_script/sheets_api_v3_final.gs:376-407` (`_actionUpdateStatus`), `app/apps_script/sheets_api_v3_final.gs:447-508` (`_actionUpdate`)
- Test: `tests/run_dev003_backend_qa.js` (신규)

**Interfaces:**
- Consumes: 기존 `_getSheet()`, `COL`, `_ok()`, `_err()`, `LockService.getScriptLock()`(Apps Script 전역, `_actionCreate`가 이미 사용 중인 것과 동일 인터페이스: `.waitLock(ms)`, `.releaseLock()`)
- Produces: `_actionUpdateStatus(no, status, confirmedAt)` / `_actionUpdate(no, data)` — 응답 포맷은 기존과 동일(`{ok,data,message}` / `{ok:false,error,code}`), Lock 획득 실패 시에만 `code:503` 응답 추가.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/run_dev003_backend_qa.js` 신규 생성 (기존 `tests/run_step1_5_datefix_qa.js`의 vm 샌드박스 패턴을 확장 — LockService를 제어 가능한 스텁으로 교체):

```javascript
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
  const rows = [];
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
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `node tests/run_dev003_backend_qa.js`
Expected: FAIL — 현재 `_actionUpdateStatus`/`_actionUpdate`가 LockService를 호출하지 않으므로 "Lock 1회 획득"/"503 반환" 계열 체크가 실패한다. (`config_v2_new.js` sheetName 체크도 Task 2 완료 전이므로 함께 실패)

- [ ] **Step 3: `_actionUpdateStatus`에 Lock 보강 (`app/apps_script/sheets_api_v3_final.gs:376-407` 교체)**

```javascript
function _actionUpdateStatus(no, status, confirmedAt) {
  if (!no)     return _err('예약번호(no) 필수');
  if (!status) return _err('상태(status) 필수');

  /* [DEV-003] 동시성 보호: 행 탐색~값 변경 구간을 잠금(_actionCreate와 동일 패턴).
   * releaseLock은 finally에서 호출하여 예외·조기 return(404 등) 시에도 반드시 해제되게 한다. */
  const lock = LockService.getScriptLock();
  try { lock.waitLock(10000); }
  catch (lockErr) { return _err('동시 요청이 많아 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.', 503); }

  try {
    const sheet    = _getSheet();
    const lastRow  = sheet.getLastRow();
    if (lastRow < 2) return _err('예약 없음', 404);

    const noCol  = sheet.getRange(2, COL.예약번호, lastRow - 1, 1).getValues();
    const rowIdx = noCol.findIndex(r => r[0] === no);
    if (rowIdx === -1) return _err('예약번호 없음: ' + no, 404);

    const sheetRow = rowIdx + 2;
    sheet.getRange(sheetRow, COL.예약상태).setValue(status);

    if (status === '예약확정') {
      const confirmed = confirmedAt || Utilities.formatDate(new Date(), TIMEZONE, DATE_FORMAT);
      sheet.getRange(sheetRow, COL.예약확정일).setValue(confirmed);
    }

    /* 검진시작/종료 자동 타임스탬프 */
    const now = Utilities.formatDate(new Date(), TIMEZONE, DATE_FORMAT);
    if (status === '검진중') {
      sheet.getRange(sheetRow, COL.접수시간).setValue(now);
      sheet.getRange(sheetRow, COL.검진시작).setValue(now);
    }
    if (status === '검진완료') {
      sheet.getRange(sheetRow, COL.검진종료).setValue(now);
    }

    return _ok({ reservationNo: no, status }, { message: '상태 변경 완료' });
  } finally {
    lock.releaseLock();
  }
}
```

- [ ] **Step 4: `_actionUpdate`에 Lock 보강 (`app/apps_script/sheets_api_v3_final.gs:447-508` 교체)**

```javascript
function _actionUpdate(no, data) {
  if (!no || !data) return _err('no, data 필수');

  /* [DEV-003] 동시성 보호: updateStatus와 동일 패턴. */
  const lock = LockService.getScriptLock();
  try { lock.waitLock(10000); }
  catch (lockErr) { return _err('동시 요청이 많아 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.', 503); }

  try {
    const sheet    = _getSheet();
    const lastRow  = sheet.getLastRow();
    if (lastRow < 2) return _err('예약 없음', 404);

    const noCol  = sheet.getRange(2, COL.예약번호, lastRow - 1, 1).getValues();
    const rowIdx = noCol.findIndex(r => r[0] === no);
    if (rowIdx === -1) return _err('예약번호 없음: ' + no, 404);

    const sheetRow   = rowIdx + 2;
    const fieldToCol = {
      name:          COL.성명,
      birth:         COL.생년월일,
      phone:         COL.연락처,
      gender:        COL.성별,
      program:       COL.검진프로그램,
      wishDate:      COL.희망검진일,
      wishTime:      COL.희망시간,
      sleep:         COL.수면,
      optionalTests: COL.선택검사,
      company:       COL.사업장,
      route:         COL.예약경로,
      manager:       COL.담당자,
      status:        COL.예약상태,
      confirmedAt:   COL.예약확정일,
      smsSent:       COL.문자발송,
      note:          COL.특이사항,
      scheduledTime: COL.검진예정시간,
      checkinTime:   COL.접수시간,
      examStart:     COL.검진시작,
      examEnd:       COL.검진종료,
      examRoom:      COL.검진실,
      doctor:        COL.문진의사,
      nurse:         COL.담당간호사,
      estimatedCost: COL.예상비용,
      paymentStatus: COL.결제상태,
      resultStatus:  COL.결과발송,
      revisit:       COL.재예약여부,
    };

    /* [DateFix] 생년월일·희망검진일·희망시간은 update 경로로도 Sheets 자동 날짜변환에
     * 노출된다. create와 동일하게 텍스트('@') 서식을 강제해 셀이 다시 Date로
     * 저장되는 것을 막는다(그 외 필드는 기존과 동일하게 처리). */
    const DATE_TEXT_COLS = { birth: COL.생년월일, wishDate: COL.희망검진일, wishTime: COL.희망시간 };

    Object.entries(data).forEach(([field, value]) => {
      const col = fieldToCol[field];
      if (!col) return;
      const val   = Array.isArray(value) ? value.join(', ') : (value ?? '');
      const range = sheet.getRange(sheetRow, col);
      if (DATE_TEXT_COLS[field]) {
        range.setNumberFormat('@').setValue(String(val));
      } else {
        range.setValue(val);
      }
    });

    return _ok({ reservationNo: no }, { message: '업데이트 완료' });
  } finally {
    lock.releaseLock();
  }
}
```

- [ ] **Step 5: config_v2_new.js sheetName 값 정정 (Task 2 착수 — 이 테스트가 함께 검증하므로 여기서 같이 수행)**

`app/config_v2_new.js:25`를 다음과 같이 교체:

```javascript
    sheetName:  '종합검진_예약대장',
```

(기존: `sheetName:  '예약현황',`)

- [ ] **Step 6: 테스트 재실행 → 통과 확인**

Run: `node tests/run_dev003_backend_qa.js`
Expected: PASS — 전체 항목 통과, `tests/dev003_backend_qa_result.csv` 생성, 종료 코드 0.

- [ ] **Step 7: 커밋 (실행 전 사용자 확인 필요)**

```bash
git add app/apps_script/sheets_api_v3_final.gs app/config_v2_new.js tests/run_dev003_backend_qa.js
git commit -m "feat(DEV-003): 예약상태변경/메모저장 LockService 보강 + sheetName 값 정정"
```

---

### Task 2: 프런트엔드 — `admin_reservations_v2_new.html` 신규 생성

**Files:**
- Create: `app/pages/admin_reservations_v2_new.html`
- Test: `tests/run_dev003_frontend_qa.js` (신규)

**Interfaces:**
- Consumes: `CMC`(`app/data/programs_data_new.js` — `STATUS`, `esc`, `maskPhone`, `formatDateTime`, `today`), `CMC_CONFIG.isGoogle()/isLocal()`(`config_v2_new.js`), `CMC_SheetsServiceV2.getAll()/getOne(no)/updateStatus(no,status,confirmedAt)/update(no,patch)`(`google_sheets_service_v2_new.js`, 무수정), `CMC_DB.getAll()/initSampleIfEmpty()`(통계 카드 전용, `db_service_new.js`), `CMC_Stats.statusCounts()`(`stats_service_new.js`), `CMC_Nav.render(page)`(`nav_new.js`).
- Produces: 전역 `AA` 컨트롤러 객체 — `init()`, `loadAll()`, `getFiltered()`, `render()`, `renderStats()`, `renderTable()`, `renderPagination()`, `goPage(n)`, `openModal(no)`, `closeModal()`, `saveStatus()`, `toast(msg)`, `downloadCSV()`, `clearFilters()`, `_optionalTestsArray(v)`, `_buildNotePayload(note)`. (Task 3의 테스트가 이 이름·시그니처를 그대로 사용)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/run_dev003_frontend_qa.js` 신규 생성:

```javascript
/**
 * DEV-003 — 프런트엔드(admin_reservations_v2_new.html) AA 컨트롤러 단위 테스트 (Node, vm 모의 실행)
 *
 * HTML 파일의 마지막 인라인 <script> 블록(AA 컨트롤러)을 실제로 로드해 실행한다.
 * DOM은 getElementById 기반 최소 스텁으로 대체하고, CMC_SheetsServiceV2는
 * 시나리오별로 제어 가능한 목(mock)으로 주입한다.
 *
 * 실행: node tests/run_dev003_frontend_qa.js
 * 종료 코드: 0(전체 통과) / 1(실패 있음)
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML_FILE = path.join(__dirname, '..', 'app', 'pages', 'admin_reservations_v2_new.html');
const CMC_CORE_FILE = path.join(__dirname, '..', 'app', 'data', 'programs_data_new.js');
const RESULT_CSV = path.join(__dirname, 'dev003_frontend_qa_result.csv');

function extractInlineScript(html) {
  const matches = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
  if (!matches.length) throw new Error('인라인 <script> 블록을 찾지 못함 (AA 컨트롤러)');
  return matches[matches.length - 1][1];
}

/* ── 최소 DOM 스텁 ─────────────────────────────────────────── */
function makeFakeDom() {
  const ids = [
    'clock','searchInput','fStatus','fProg','fDateFrom','fDateTo','mainTable','pagination',
    'mNo','mStatus','dName','dBirth','dPhone','dGender','dProg','dDate','dSleep','dCompany',
    'dTests','dNote','dCreated','dUpdated','statusSel','detailModal','cmc-toast',
  ];
  const store = {};
  ids.forEach(id => { store[id] = { value: '', textContent: '', className: '', innerHTML: '', style: {}, addEventListener() {}, _t: null }; });
  const document = {
    getElementById: (id) => store[id],
    addEventListener: () => {},
  };
  return { document, store };
}

function loadAaSandbox({ isGoogle = false } = {}) {
  const html = fs.readFileSync(HTML_FILE, 'utf8');
  const script = extractInlineScript(html);
  const cmcCoreSrc = fs.readFileSync(CMC_CORE_FILE, 'utf8');

  const { document, store } = makeFakeDom();
  const calls = { updateStatus: [], update: [], getOne: [] };
  const order = [];

  const sheetsServiceMock = {
    getAllImpl: async () => ({ ok: true, data: [], source: 'mock', count: 0 }),
    getOneImpl: async (no) => ({ ok: false, error: 'not found' }),
    updateStatusImpl: async (no, status) => ({ ok: true, data: { reservationNo: no, status } }),
    updateImpl: async (no, patch) => ({ ok: true, data: { reservationNo: no } }),
    async getAll(params) { return this.getAllImpl(params); },
    async getOne(no) { calls.getOne.push(no); return this.getOneImpl(no); },
    async updateStatus(no, status, confirmedAt) { order.push('updateStatus'); calls.updateStatus.push([no, status, confirmedAt]); return this.updateStatusImpl(no, status, confirmedAt); },
    async update(no, patch) { order.push('update'); calls.update.push([no, patch]); return this.updateImpl(no, patch); },
  };

  const sandbox = {
    console,
    document,
    setInterval: () => 0,
    clearTimeout: () => {},
    setTimeout: (fn) => fn(), // toast 타이머 즉시 실행(테스트 단순화)
    CMC_CONFIG: { isGoogle: () => isGoogle, isLocal: () => !isGoogle },
    CMC_SheetsServiceV2: sheetsServiceMock,
    CMC_DB: { getAll: () => [], initSampleIfEmpty() {} },
    CMC_Stats: { statusCounts: () => ({}) },
    CMC_Nav: { render() {} },
  };
  vm.createContext(sandbox);
  vm.runInContext(cmcCoreSrc, sandbox, { filename: CMC_CORE_FILE }); // 실제 CMC 네임스페이스 로드
  vm.runInContext(script, sandbox, { filename: HTML_FILE });
  return { sandbox, store, calls, order, sheetsServiceMock };
}

const results = [];
function check(name, condition, detail) {
  results.push({ name, pass: !!condition, detail: detail || '' });
  console.log(`${condition ? '✅ PASS' : '❌ FAIL'} — ${name}${detail ? ' — ' + detail : ''}`);
}

async function run() {
  /* ── 1) optionalTests 정규화: 배열/문자열 모두 처리 ── */
  {
    const { sandbox } = loadAaSandbox();
    check('_optionalTestsArray: 배열 입력 → 그대로', JSON.stringify(sandbox.AA._optionalTestsArray(['위내시경','대장내시경'])) === JSON.stringify(['위내시경','대장내시경']));
    check('_optionalTestsArray: 콤마 문자열 입력(Sheets) → 배열로 분해', JSON.stringify(sandbox.AA._optionalTestsArray('위내시경, 대장내시경')) === JSON.stringify(['위내시경','대장내시경']));
    check('_optionalTestsArray: 빈 값 → 빈 배열', JSON.stringify(sandbox.AA._optionalTestsArray('')) === '[]');
    check('_optionalTestsArray: undefined → 빈 배열', JSON.stringify(sandbox.AA._optionalTestsArray(undefined)) === '[]');
  }

  /* ── 2) _buildNotePayload: note 단일 필드만 포함(Risk#2 방어) ── */
  {
    const { sandbox } = loadAaSandbox();
    const payload = sandbox.AA._buildNotePayload('메모내용');
    check('_buildNotePayload: note 필드만 존재', JSON.stringify(Object.keys(payload)) === JSON.stringify(['note']), JSON.stringify(payload));
    check('_buildNotePayload: 값 정확', payload.note === '메모내용');
  }

  /* ── 3) saveStatus: 상태+메모 동시 변경 → 순차 호출, note payload는 {note}만 ── */
  {
    const { sandbox, calls, order } = loadAaSandbox();
    sandbox.AA.cache = [{ reservationNo: '20260810-0001', status: '예약접수', note: '기존메모' }];
    sandbox.AA.selectedNo = '20260810-0001';
    sandbox.document.getElementById('statusSel').value = '예약확정';
    sandbox.document.getElementById('dNote').value = '새메모';
    await sandbox.AA.saveStatus();

    check('saveStatus: updateStatus가 정확한 인자로 호출됨', calls.updateStatus.length === 1 && calls.updateStatus[0][0] === '20260810-0001' && calls.updateStatus[0][1] === '예약확정', JSON.stringify(calls.updateStatus));
    check('saveStatus: update(note)가 {note} 단일 필드로만 호출됨', calls.update.length === 1 && JSON.stringify(Object.keys(calls.update[0][1])) === JSON.stringify(['note']) && calls.update[0][1].note === '새메모', JSON.stringify(calls.update));
    check('saveStatus: updateStatus가 update보다 먼저 호출됨(순차)', order[0] === 'updateStatus' && order[1] === 'update', JSON.stringify(order));
    check('saveStatus: 성공 시 모달 닫힘(selectedNo 초기화)', sandbox.AA.selectedNo === null);
  }

  /* ── 4) saveStatus: 상태변경 실패 → 롤백, 메모는 독립적으로 계속 시도됨 ── */
  {
    const { sandbox, calls } = loadAaSandbox();
    sandbox.sheetsServiceMock.updateStatusImpl = async () => ({ ok: false, error: '서버 오류' });
    sandbox.AA.cache = [{ reservationNo: '20260810-0002', status: '예약접수', note: '기존메모' }];
    sandbox.AA.selectedNo = '20260810-0002';
    sandbox.document.getElementById('statusSel').value = '예약확정';
    sandbox.document.getElementById('dNote').value = '새메모2';
    await sandbox.AA.saveStatus();

    const cached = sandbox.AA.cache.find(r => r.reservationNo === '20260810-0002');
    check('saveStatus: 상태변경 실패 시 상태 롤백됨', cached.status === '예약접수', cached.status);
    check('saveStatus: 상태변경 실패해도 메모 저장은 시도됨(독립적)', calls.update.length === 1, JSON.stringify(calls.update));
    check('saveStatus: 메모는 성공했으므로 반영됨', cached.note === '새메모2', cached.note);
    check('saveStatus: 부분 실패 시 모달 유지(selectedNo 비초기화)', sandbox.AA.selectedNo === '20260810-0002');
  }

  /* ── 5) saveStatus: 메모저장 실패 → 메모만 롤백, 상태는 반영 유지 ── */
  {
    const { sandbox, calls } = loadAaSandbox();
    sandbox.sheetsServiceMock.updateImpl = async () => ({ ok: false, error: '메모 저장 오류' });
    sandbox.AA.cache = [{ reservationNo: '20260810-0003', status: '예약접수', note: '기존메모' }];
    sandbox.AA.selectedNo = '20260810-0003';
    sandbox.document.getElementById('statusSel').value = '예약확정';
    sandbox.document.getElementById('dNote').value = '실패할메모';
    await sandbox.AA.saveStatus();

    const cached = sandbox.AA.cache.find(r => r.reservationNo === '20260810-0003');
    check('saveStatus: 메모저장 실패 시 메모 롤백됨', cached.note === '기존메모', cached.note);
    check('saveStatus: 메모저장 실패해도 상태변경은 반영 유지', cached.status === '예약확정', cached.status);
  }

  /* ── 6) saveStatus: 변경 없음 → API 호출 없이 모달만 닫힘 ── */
  {
    const { sandbox, calls } = loadAaSandbox();
    sandbox.AA.cache = [{ reservationNo: '20260810-0004', status: '예약접수', note: '메모' }];
    sandbox.AA.selectedNo = '20260810-0004';
    sandbox.document.getElementById('statusSel').value = '예약접수';
    sandbox.document.getElementById('dNote').value = '메모';
    await sandbox.AA.saveStatus();
    check('saveStatus: 변경 없으면 updateStatus 미호출', calls.updateStatus.length === 0);
    check('saveStatus: 변경 없으면 update 미호출', calls.update.length === 0);
    check('saveStatus: 변경 없어도 모달은 닫힘', sandbox.AA.selectedNo === null);
  }

  /* ── 7) loadAll: 목록 조회 실패 시 renderTable이 오류 문구를 표시(빈 결과 문구와 구분) ── */
  {
    const { sandbox, store } = loadAaSandbox();
    sandbox.sheetsServiceMock.getAllImpl = async () => ({ ok: false, error: '네트워크 오류', data: [] });
    await sandbox.AA.loadAll();
    check('loadAll: 실패 시 cache 비워짐', sandbox.AA.cache.length === 0);
    check('loadAll: 실패 시 목록 영역에 "불러오지 못했습니다" 문구 표시', store.mainTable.innerHTML.includes('불러오지 못했습니다'), store.mainTable.innerHTML);
    check('loadAll: 실패 시 신규 시각요소(spinner 등) 없이 텍스트만', !store.mainTable.innerHTML.includes('spinner') && !store.mainTable.innerHTML.includes('class="loader'));
  }

  /* ── 8) loadAll: 성공 시 필터 결과 0건이면 기존 "조회된 예약이 없습니다" 문구(회귀) ── */
  {
    const { sandbox, store } = loadAaSandbox();
    sandbox.sheetsServiceMock.getAllImpl = async () => ({ ok: true, data: [], source: 'mock', count: 0 });
    await sandbox.AA.loadAll();
    check('loadAll: 성공+빈 목록 시 기존 문구 유지(회귀)', store.mainTable.innerHTML.includes('조회된 예약이 없습니다'), store.mainTable.innerHTML);
  }

  /* ── 9) openModal: 캐시 우선 조회, 캐시에 없으면 getOne fallback ── */
  {
    const { sandbox, calls, store } = loadAaSandbox();
    sandbox.AA.cache = [{ reservationNo: '20260810-0005', status: '예약접수', note: '캐시메모', name: '캐시테스트', birth: '1990-01-01', phone: '010-1111-2222', gender: '남성', program: 'BASIC', wishDate: '2026-08-10', wishTime: '09:00', sleep: '일반', company: '', optionalTests: [], createdAt: '2026-08-01 09:00:00', updatedAt: '2026-08-01 09:00:00' }];
    await sandbox.AA.openModal('20260810-0005');
    check('openModal: 캐시에 있으면 getOne 미호출', calls.getOne.length === 0);
    check('openModal: dNote가 textarea.value로 채워짐', store.dNote.value === '캐시메모', store.dNote.value);

    sandbox.sheetsServiceMock.getOneImpl = async (no) => ({ ok: true, data: { reservationNo: no, status: '예약접수', note: '폴백메모', name: '폴백테스트', birth: '1991-01-01', phone: '010-3333-4444', gender: '여성', program: 'SMART', wishDate: '2026-08-11', wishTime: '10:00', sleep: '수면', company: '', optionalTests: '', createdAt: '2026-08-02 09:00:00', updatedAt: '2026-08-02 09:00:00' } });
    await sandbox.AA.openModal('20260810-9999');
    check('openModal: 캐시에 없으면 getOne 호출(fallback)', calls.getOne.length === 1 && calls.getOne[0] === '20260810-9999', JSON.stringify(calls.getOne));
    check('openModal: fallback 데이터로 정상 표시', store.dNote.value === '폴백메모', store.dNote.value);
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
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `node tests/run_dev003_frontend_qa.js`
Expected: FAIL — `admin_reservations_v2_new.html`이 아직 없으므로 `ENOENT` 오류로 즉시 실패.

- [ ] **Step 3: `admin_reservations_v2_new.html` 신규 생성**

원본 `app/pages/admin_reservations_new.html`(309줄)을 마크업 100% 동일하게 복제하되, 아래 두 부분만 변경한다:

**(a) 상세모달의 특이사항 표시를 `<span>`에서 `<textarea>`로 전환** (원본 127번째 줄 대체, 위치·스타일 동일 유지):

```html
        <div class="detail-row full"><span class="detail-label">특이사항</span><textarea id="dNote" class="detail-value" style="white-space:pre-wrap;width:100%;min-height:60px;resize:vertical;font:inherit;border:1px solid var(--border);border-radius:6px;padding:6px 8px"></textarea></div>
```

**(b) 스크립트 로드부 + 인라인 스크립트 전체 교체** (원본 156-307번째 줄 대체):

```html
<script src="../data/programs_data_new.js"></script>
<script src="../data/sample_data_new.js"></script>
<script src="../services/db_service_new.js"></script>
<script src="../services/stats_service_new.js"></script>
<script src="../config_v2_new.js"></script>
<script src="../services/google_sheets_service_v2_new.js"></script>
<script src="../components/nav_new.js"></script>
<script>
'use strict';
const AA = {
  page: 1, pageSize: 15, filtered: [], selectedNo: null, cache: [], loadError: false,

  async init() {
    CMC_DB.initSampleIfEmpty();
    CMC_Nav.render('admin');
    setInterval(() => { const el = document.getElementById('clock'); if(el) el.textContent = new Date().toLocaleString('ko-KR'); }, 1000);
    ['searchInput','fStatus','fProg','fDateFrom','fDateTo'].forEach(id =>
      document.getElementById(id)?.addEventListener('input', () => { this.page = 1; this.render(); }));
    await this.loadAll();
  },

  /** 예약 목록을 CMC_SheetsServiceV2에서 로드해 캐시에 저장(§7.7: 최초진입/저장성공/F5에만 호출) */
  async loadAll() {
    this.loadError = false;
    this.setListMessage('예약 목록을 불러오는 중입니다...');
    const res = await CMC_SheetsServiceV2.getAll();
    if (!res.ok) {
      this.cache = [];
      this.loadError = true;
      this.render();
      return;
    }
    this.cache = res.data || [];
    this.render();
  },

  setListMessage(msg) {
    const tbody = document.getElementById('mainTable');
    if (tbody) tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:36px;color:var(--gray-500)">${CMC.esc(msg)}</td></tr>`;
  },

  /** Sheets가 optionalTests를 콤마구분 문자열로 반환(LOCAL은 배열) — 양쪽 모두 배열로 정규화 */
  _optionalTestsArray(v) {
    if (Array.isArray(v)) return v;
    const s = String(v || '').trim();
    return s ? s.split(',').map(x => x.trim()).filter(Boolean) : [];
  },

  /** 메모 저장 payload는 반드시 이 함수를 통해서만 생성 — note 외 필드 전송 금지(설계 §7.2, Risk#2) */
  _buildNotePayload(note) { return { note }; },

  getFiltered() {
    const s  = (document.getElementById('searchInput')?.value||'').trim().toLowerCase();
    const st = document.getElementById('fStatus')?.value||'';
    const pr = document.getElementById('fProg')?.value||'';
    const f  = document.getElementById('fDateFrom')?.value||'';
    const t  = document.getElementById('fDateTo')?.value||'';
    return this.cache.filter(r => {
      if (st && r.status  !== st) return false;
      if (pr && r.program !== pr) return false;
      if (f  && r.wishDate < f)  return false;
      if (t  && r.wishDate > t)  return false;
      if (s) {
        const hay = [r.name, r.phone, r.reservationNo, r.company, r.program].join(' ').toLowerCase();
        if (!hay.includes(s)) return false;
      }
      return true;
    });
  },

  render() {
    this.filtered = this.getFiltered();
    this.renderStats(); this.renderTable(); this.renderPagination();
  },

  /** 통계 카드는 설계 §7.1에 따라 Sheets 캐시가 아닌 기존 CMC_DB/CMC_Stats(Local)를 그대로 사용 */
  renderStats() {
    const all = CMC_DB.getAll();
    const c   = CMC_Stats.statusCounts();
    document.getElementById('st-total').textContent    = all.length;
    document.getElementById('st-접수').textContent     = c['예약접수']||0;
    document.getElementById('st-확정').textContent     = c['예약확정']||0;
    document.getElementById('st-완료').textContent     = c['검진완료']||0;
    document.getElementById('st-취소변경').textContent = (c['예약취소']||0) + (c['일정변경']||0);
  },

  renderTable() {
    const tbody = document.getElementById('mainTable');
    if (this.loadError) { tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:36px;color:var(--gray-500)">예약 목록을 불러오지 못했습니다.</td></tr>'; return; }
    const start = (this.page-1)*this.pageSize;
    const pg    = this.filtered.slice(start, start+this.pageSize);
    if (!pg.length) { tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:36px;color:var(--gray-500)">조회된 예약이 없습니다.</td></tr>'; return; }
    tbody.innerHTML = pg.map(r => {
      const m = CMC.STATUS[r.status]||{};
      return `<tr>
        <td data-label="예약번호"><code style="font-size:12px;color:var(--gray-500)">${CMC.esc(r.reservationNo)}</code></td>
        <td data-label="접수일시" style="font-size:12px;color:var(--gray-500)">${CMC.formatDateTime(r.createdAt)}</td>
        <td data-label="성명" style="font-weight:700">${CMC.esc(r.name)}</td>
        <td data-label="연락처" style="font-family:monospace;font-size:13px">${CMC.maskPhone(r.phone)}</td>
        <td data-label="프로그램">${CMC.esc(r.program)}</td>
        <td data-label="검진일시" style="font-weight:700;color:var(--primary)">${CMC.esc(r.wishDate)} ${CMC.esc(r.wishTime)}</td>
        <td data-label="수면">${r.sleep==='수면'?'💤 수면':'일반'}</td>
        <td data-label="상태"><span class="status-badge ${m.cls||''}">${m.icon||''} ${CMC.esc(r.status)}</span></td>
        <td data-label="관리"><button class="btn btn-outline btn-sm" onclick="AA.openModal('${CMC.esc(r.reservationNo)}')">상세</button></td>
      </tr>`;
    }).join('');
  },

  renderPagination() {
    const wrap  = document.getElementById('pagination');
    const total = Math.ceil(this.filtered.length / this.pageSize);
    if (total <= 1) { wrap.innerHTML = `<div style="text-align:center;margin-top:12px;font-size:13px;color:var(--gray-500)">총 ${this.filtered.length}건</div>`; return; }
    let h = `<div class="pagination"><button class="page-btn" onclick="AA.goPage(${this.page-1})" ${this.page===1?'disabled':''}>‹</button>`;
    for (let i=1; i<=total; i++) {
      if (total>7 && Math.abs(i-this.page)>2 && i!==1 && i!==total) { if(i===2||i===total-1) h+='<span style="padding:0 4px">…</span>'; continue; }
      h += `<button class="page-btn ${i===this.page?'active':''}" onclick="AA.goPage(${i})">${i}</button>`;
    }
    h += `<button class="page-btn" onclick="AA.goPage(${this.page+1})" ${this.page===total?'disabled':''}>›</button><span style="font-size:13px;color:var(--gray-500);margin-left:8px">총 ${this.filtered.length}건</span></div>`;
    wrap.innerHTML = h;
  },

  goPage(n) {
    const t = Math.ceil(this.filtered.length/this.pageSize);
    if (n<1||n>t) return;
    this.page = n; this.renderTable(); this.renderPagination();
  },

  /** 상세조회: 캐시 우선, 캐시에 없으면 get 액션으로 fallback(설계 §1②-3) */
  async openModal(no) {
    let r = this.cache.find(x => x.reservationNo === no);
    if (!r) {
      const res = await CMC_SheetsServiceV2.getOne(no);
      if (!res.ok) { this.toast('예약 정보를 불러오지 못했습니다.'); return; }
      r = res.data;
    }
    this.selectedNo = no;
    const m = CMC.STATUS[r.status]||{};
    document.getElementById('mNo').textContent      = r.reservationNo;
    document.getElementById('mStatus').className    = `status-badge ${m.cls||''}`;
    document.getElementById('mStatus').textContent  = `${m.icon||''} ${r.status}`;
    document.getElementById('dName').textContent    = r.name;
    document.getElementById('dBirth').textContent   = r.birth;
    document.getElementById('dPhone').textContent   = CMC.maskPhone(r.phone);
    document.getElementById('dGender').textContent  = r.gender||'-';
    document.getElementById('dProg').textContent    = r.program;
    document.getElementById('dDate').textContent    = `${r.wishDate} ${r.wishTime}`;
    document.getElementById('dSleep').textContent   = r.sleep;
    document.getElementById('dCompany').textContent = r.company||'-';
    const ot = this._optionalTestsArray(r.optionalTests);
    document.getElementById('dTests').textContent   = ot.length ? ot.join(', ') : '없음';
    document.getElementById('dNote').value          = r.note||'';
    document.getElementById('dCreated').textContent = CMC.formatDateTime(r.createdAt);
    document.getElementById('dUpdated').textContent = CMC.formatDateTime(r.updatedAt);
    document.getElementById('statusSel').value      = r.status;
    document.getElementById('detailModal').style.display = 'flex';
  },
  closeModal() { document.getElementById('detailModal').style.display='none'; this.selectedNo=null; },

  /** 상태변경 + 메모저장(옵션 A: {note} 단일필드). 순차 호출, 각각 독립적으로 성공/실패 판정·롤백(설계 §4.2/4.3) */
  async saveStatus() {
    if (!this.selectedNo) return;
    const no = this.selectedNo;
    const cached = this.cache.find(r => r.reservationNo === no);
    if (!cached) { this.closeModal(); return; }

    const newStatus = document.getElementById('statusSel').value;
    const newNote    = document.getElementById('dNote').value;
    const statusChanged = newStatus !== cached.status;
    const noteChanged   = newNote   !== (cached.note || '');
    if (!statusChanged && !noteChanged) { this.closeModal(); return; }

    this.toast('저장 중입니다...');
    let statusOk = !statusChanged, noteOk = !noteChanged;
    let statusErr = '', noteErr = '';
    let anySuccess = false;

    if (statusChanged) {
      const prevStatus = cached.status;
      cached.status = newStatus; this.render();
      const res = await CMC_SheetsServiceV2.updateStatus(no, newStatus);
      if (res.ok) { statusOk = true; anySuccess = true; }
      else { cached.status = prevStatus; this.render(); statusErr = res.error || '알 수 없는 오류'; }
    }

    if (noteChanged) {
      const prevNote = cached.note;
      cached.note = newNote; this.render();
      const res = await CMC_SheetsServiceV2.update(no, this._buildNotePayload(newNote));
      if (res.ok) { noteOk = true; anySuccess = true; }
      else { cached.note = prevNote; this.render(); noteErr = res.error || '알 수 없는 오류'; }
    }

    if (anySuccess) await this.loadAll();

    if (statusOk && noteOk) { this.closeModal(); this.toast('저장되었습니다.'); }
    else {
      const msgs = [];
      if (!statusOk) msgs.push('상태 변경 실패: ' + statusErr);
      if (!noteOk)   msgs.push('메모 저장 실패: ' + noteErr);
      this.toast(msgs.join(' / '));
    }
  },

  toast(msg) {
    let t = document.getElementById('cmc-toast');
    t.style.display='block'; t.style.opacity='1'; t.textContent=msg;
    clearTimeout(t._t); t._t = setTimeout(() => { t.style.opacity='0'; setTimeout(()=>t.style.display='none',300); }, 2200);
  },

  downloadCSV() {
    if (!this.filtered.length) { alert('다운로드할 데이터가 없습니다.'); return; }
    const h = ['예약번호','접수일시','성명','연락처','성별','프로그램','희망검진일','희망시간','수면','선택검사','사업장','특이사항','상태'];
    const rows = this.filtered.map(r => [
      r.reservationNo, CMC.formatDateTime(r.createdAt), r.name, r.phone, r.gender||'',
      r.program, r.wishDate, r.wishTime, r.sleep,
      this._optionalTestsArray(r.optionalTests).join('|'), r.company||'', r.note||'', r.status,
    ].map(v => `"${String(v).replace(/"/g,'""')}"`));
    const csv = '﻿' + [h, ...rows].map(r=>r.join(',')).join('\r\n');
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8;'})), download: `예약목록_${CMC.today()}.csv` });
    a.click(); URL.revokeObjectURL(a.href);
  },

  clearFilters() {
    ['searchInput','fStatus','fProg','fDateFrom','fDateTo'].forEach(id => { const el=document.getElementById(id); if(el) el.value=''; });
    this.page=1; this.render();
  },
};
document.addEventListener('DOMContentLoaded', () => AA.init());
</script>
```

나머지 마크업(HTML head/style/상단바/통계카드/필터바/테이블 헤더/모달 구조/footer)은 원본과 100% 동일하게 유지한다.

- [ ] **Step 4: 테스트 재실행 → 통과 확인**

Run: `node tests/run_dev003_frontend_qa.js`
Expected: PASS — 전체 항목 통과, `tests/dev003_frontend_qa_result.csv` 생성, 종료 코드 0.

- [ ] **Step 5: 커밋 (실행 전 사용자 확인 필요)**

```bash
git add app/pages/admin_reservations_v2_new.html tests/run_dev003_frontend_qa.js
git commit -m "feat(DEV-003): admin_reservations_v2_new.html 신규 생성 — Sheets Live 연동"
```

---

### Task 3: 브라우저 수동 QA (LOCAL 모드) — UI 무결성·회귀 확인

**Files:** 없음(코드 변경 없음, 검증만)

- [ ] **Step 1: 미리보기로 `admin_reservations_v2_new.html`을 LOCAL 모드로 오픈**

`CMC_CONFIG.dataSource`가 `'google'`이면 브라우저 콘솔에서 `CMC_CONFIG.setDataSource('local'); location.reload();`로 LOCAL 전환(Design_Final §10.2 즉시 전환 롤백 경로와 동일 방법) 후 확인한다.

- [ ] **Step 2: 목록·검색·필터·페이지네이션이 원본과 동일하게 동작하는지 확인**

원본 `admin_reservations_new.html`을 같은 브라우저의 다른 탭에서 열어 나란히 비교. 통계 카드 5종 값이 두 화면에서 동일한지 확인(§7.1 — 둘 다 CMC_DB 기준이므로 같아야 함).

- [ ] **Step 3: 상세 모달 — 특이사항 textarea 레이아웃이 원본 `<span>`과 시각적으로 동일한지 확인(위치/크기/스타일, §11 UI 무결성)**

- [ ] **Step 4: 상태 변경 저장 → "저장 중입니다..." 토스트 → "저장되었습니다." 토스트 → 목록에 반영 확인**

- [ ] **Step 5: 메모(textarea) 수정 후 저장 → 목록/재오픈 시 반영 확인**

- [ ] **Step 6: 원본 `admin_reservations_new.html`, `admin_dashboard_v2_new.html`, `reservation_v2_new.html`을 각각 새로고침해 무영향(회귀 없음) 확인**

- [ ] **Step 7: 스크린샷 확보(선택) — 결과를 사용자에게 보고할 때 첨부**

---

### Task 4: 최종 보고 — DoD·QA Checklist 매핑, 변경 파일 목록, 테스트 결과 정리

- [ ] **Step 1: `DEV-003_..._Design_Final_new.md` §11 QA Checklist를 항목별로 상태 표기**

이 세션에서 검증 가능한 항목(LOCAL 모드, Node 테스트, 코드 리뷰)은 ✅, Google 실배포·2세션 동시성 등 사용자의 수동 Apps Script 재배포 이후에만 가능한 항목은 🔲(대기)로 표기해 정리한다.

- [ ] **Step 2: §12 Definition of Done 8개 항목 상태 표기**

1~7번은 이 세션에서 충족 가능(신규 파일 생성/원본 보존/Lock 보강+재배포 대기/sheetName 정정/코드 리뷰 가능 항목), 8번(승인 후 별도 세션 구현)은 이번 세션이 바로 그 세션이므로 충족.

- [ ] **Step 3: 변경 파일 목록 + 테스트 결과(PASS 건수/실패 건수) 정리해 사용자에게 보고**

`git status --short`로 최종 변경 파일 목록 확인, `tests/dev003_backend_qa_result.csv` + `tests/dev003_frontend_qa_result.csv` 요약.

---

## Self-Review 메모 (계획 작성자 자체 점검)

- **스펙 커버리지**: Design_Final §13 구현순서 1~9단계(백엔드 Lock, sheetName 정정, 화면뼈대, 스크립트로드, 목록조회, 로딩텍스트, 메모편집UI, 상태변경배선, 메모저장배선) 전부 Task 1·2에 반영됨. §13 10~13단계(Live 통합/Lock 동시성/성능/회귀의 GOOGLE 모드 부분)는 사용자의 수동 배포 이후로 이월 — Task 4에서 명시적으로 표기.
- **플레이스홀더 스캔**: 없음 — 모든 단계에 완전한 코드 포함.
- **타입/시그니처 일관성**: `AA._optionalTestsArray`, `AA._buildNotePayload`, `CMC_SheetsServiceV2.getAll/getOne/updateStatus/update` 시그니처가 Task 2 구현과 Task 2 테스트에서 동일하게 사용됨을 재확인함.
- **범위 확인**: 이 계획은 DEV-003 단일 티켓 범위로 한정되어 있으며 추가 분해가 필요한 독립 서브시스템은 없음.
