/**
 * CMC Health Screening Platform v1.0 — Phase 4.5 (Backend v3)
 * app/apps_script/sheets_api_v3_new.gs
 *
 * Google Apps Script — Sheets Web App API v3
 * sheets_api_v2_new.gs를 복제 (기존 v2 파일 보존).
 *
 * v3 변경사항 (딱 1가지, 구조 변경 없음):
 *   · _actionCreate 의 예약번호 채번(_generateNo) ~ appendRow 구간에
 *     LockService.getScriptLock() 적용 → 동시 요청 시 예약번호 중복 방지.
 *   · 그 외 라우팅·컬럼·스키마·응답 형식은 v2와 100% 동일.
 *
 * [배포] 이 파일(v3)을 Apps Script에 붙여넣어 배포한다. (v2 대신)
 * [보안] 배포 시 액세스 권한을 '조직 내' 또는 '나만'으로 설정.
 *        개인정보(연락처·생년월일·진료기록)가 포함되므로 HTTPS 필수.
 */

/* ─── 설정 ─────────────────────────────────────────── */
const SHEET_NAME   = '예약현황';
const TIMEZONE     = 'Asia/Seoul';
const DATE_FORMAT  = 'yyyy-MM-dd HH:mm:ss';
const DATE_ONLY    = 'yyyy-MM-dd';
const TIME_FORMAT  = 'HH:mm';

/* ─── 컬럼 정의 (1-indexed, 총 29개) ──────────────────
 * ── 기존 18개 (Phase 4) ─────────────────────────────
 *  1.예약번호  2.접수일시  3.성명     4.생년월일   5.연락처
 *  6.성별      7.검진프로그램 8.희망검진일 9.희망시간 10.수면
 * 11.선택검사 12.사업장   13.예약경로 14.담당자    15.예약상태
 * 16.예약확정일 17.문자발송 18.특이사항
 * ── 추가 11개 (Phase 4.5) ───────────────────────────
 * 19.검진예정시간 20.접수시간 21.검진시작 22.검진종료 23.검진실
 * 24.문진의사  25.담당간호사 26.예상비용 27.결제상태 28.결과발송
 * 29.재예약여부
 * ──────────────────────────────────────────────────── */
const COL = {
  /* ── 예약 정보 (기존) ── */
  예약번호:      1,
  접수일시:      2,
  성명:          3,
  생년월일:      4,
  연락처:        5,
  성별:          6,
  검진프로그램:  7,
  희망검진일:    8,
  희망시간:      9,
  수면:         10,
  선택검사:     11,
  사업장:       12,
  예약경로:     13,
  담당자:       14,
  예약상태:     15,
  예약확정일:   16,
  문자발송:     17,
  특이사항:     18,
  /* ── 운영 정보 (Phase 4.5 추가) ── */
  검진예정시간:  19,
  접수시간:     20,
  검진시작:     21,
  검진종료:     22,
  검진실:       23,
  문진의사:     24,
  담당간호사:   25,
  예상비용:     26,
  결제상태:     27,
  결과발송:     28,
  재예약여부:   29,
};
const TOTAL_COLS = 29;

/* ─── 결제상태·결과발송·재예약여부 허용값 ─────────────── */
const VALID_PAYMENT_STATUS = ['미결제', '결제완료', '부분결제', '환불'];
const VALID_RESULT_STATUS  = ['미발송', '발송완료', '미수령', '수령확인'];
const VALID_REVISIT        = ['해당없음', '재예약예정', '재예약완료'];

/* ─── CORS 출력 헬퍼 ────────────────────────────────── */
function _corsOutput(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
function _ok(data, extra)    { return _corsOutput(Object.assign({ ok: true  }, extra || {}, { data })); }
function _err(message, code) { return _corsOutput({ ok: false, error: message, code: code || 400 }); }

/* ─── 시트 참조 ─────────────────────────────────────── */
function _getSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    _initHeader(sheet);
  }
  return sheet;
}

function _initHeader(sheet) {
  const headers = Object.keys(COL);
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);

  /* 헤더 스타일 */
  const headerRange = sheet.getRange(1, 1, 1, headers.length);
  headerRange.setBackground('#1a4f8a').setFontColor('#ffffff').setFontWeight('bold');

  /* 운영 컬럼(19~29) 구분 색상 */
  sheet.getRange(1, 19, 1, 11).setBackground('#2e7d32');
  sheet.setFrozenRows(1);

  /* 열 너비 자동 조정 */
  sheet.autoResizeColumns(1, headers.length);
}

/* ─── 예약번호 자동 생성 ─────────────────────────────
 *  형식: YYYYMMDD-NNNN (예: 20260701-0001)
 * ────────────────────────────────────────────────── */
function _generateNo(sheet) {
  const today   = Utilities.formatDate(new Date(), TIMEZONE, 'yyyyMMdd');
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return today + '-0001';

  const existing = sheet.getRange(2, COL.예약번호, lastRow - 1, 1).getValues()
    .map(r => r[0])
    .filter(v => String(v).startsWith(today));

  if (existing.length === 0) return today + '-0001';
  const max = existing.reduce((acc, v) => {
    const seq = parseInt(String(v).split('-')[1] || '0', 10);
    return seq > acc ? seq : acc;
  }, 0);
  return today + '-' + String(max + 1).padStart(4, '0');
}

/* ─── 컬럼 키 → 영문 필드명 매핑 ────────────────────── */
function _colKeyToField(key) {
  const map = {
    /* 기존 18개 */
    '예약번호':     'reservationNo',
    '접수일시':     'createdAt',
    '성명':         'name',
    '생년월일':     'birth',
    '연락처':       'phone',
    '성별':         'gender',
    '검진프로그램': 'program',
    '희망검진일':   'wishDate',
    '희망시간':     'wishTime',
    '수면':         'sleep',
    '선택검사':     'optionalTests',
    '사업장':       'company',
    '예약경로':     'route',
    '담당자':       'manager',
    '예약상태':     'status',
    '예약확정일':   'confirmedAt',
    '문자발송':     'smsSent',
    '특이사항':     'note',
    /* 추가 11개 */
    '검진예정시간': 'scheduledTime',
    '접수시간':     'checkinTime',
    '검진시작':     'examStart',
    '검진종료':     'examEnd',
    '검진실':       'examRoom',
    '문진의사':     'doctor',
    '담당간호사':   'nurse',
    '예상비용':     'estimatedCost',
    '결제상태':     'paymentStatus',
    '결과발송':     'resultStatus',
    '재예약여부':   'revisit',
  };
  return map[key] || key;
}

/* ─── 행 → 객체 변환 ────────────────────────────────── */
function _rowToObj(row) {
  const obj = {};
  Object.entries(COL).forEach(([key, idx]) => {
    const val = row[idx - 1];
    obj[_colKeyToField(key)] = (val instanceof Date)
      ? Utilities.formatDate(val, TIMEZONE, DATE_FORMAT)
      : (val === null || val === undefined ? '' : String(val));
  });
  return obj;
}

/* ─── doGet ─────────────────────────────────────────── */
function doGet(e) {
  try {
    const action = (e.parameter && e.parameter.action) || 'list';
    if (action === 'list')    return _actionList(e.parameter);
    if (action === 'get')     return _actionGet(e.parameter.no);
    if (action === 'summary') return _actionSummary(e.parameter);
    if (action === 'ping')    return _ok({ message: 'CMC Sheets API v3 정상', sheetName: SHEET_NAME, totalCols: TOTAL_COLS });
    return _err('알 수 없는 action: ' + action);
  } catch (ex) {
    return _err('서버 오류: ' + ex.message, 500);
  }
}

/* ─── doPost ────────────────────────────────────────── */
function doPost(e) {
  try {
    const body   = JSON.parse(e.postData.contents || '{}');
    const action = body.action;
    if (action === 'create')        return _actionCreate(body.data);
    if (action === 'updateStatus')  return _actionUpdateStatus(body.no, body.status, body.confirmedAt);
    if (action === 'updateOps')     return _actionUpdateOps(body.no, body.data);
    if (action === 'update')        return _actionUpdate(body.no, body.data);
    return _err('알 수 없는 action: ' + action);
  } catch (ex) {
    return _err('서버 오류: ' + ex.message, 500);
  }
}

/* ─── 목록 조회 ─────────────────────────────────────── */
function _actionList(params) {
  const sheet   = _getSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return _ok([], { count: 0 });

  const rows = sheet.getRange(2, 1, lastRow - 1, TOTAL_COLS).getValues();
  let data   = rows.filter(r => r[0] !== '').map(_rowToObj);

  if (params.status)   data = data.filter(r => r.status === params.status);
  if (params.dateFrom) data = data.filter(r => r.wishDate >= params.dateFrom);
  if (params.dateTo)   data = data.filter(r => r.wishDate <= params.dateTo);
  if (params.doctor)   data = data.filter(r => r.doctor === params.doctor);
  if (params.examRoom) data = data.filter(r => r.examRoom === params.examRoom);
  if (params.paymentStatus) data = data.filter(r => r.paymentStatus === params.paymentStatus);

  data.sort((a, b) => (b.createdAt > a.createdAt ? 1 : -1));
  return _ok(data, { count: data.length });
}

/* ─── 단건 조회 ─────────────────────────────────────── */
function _actionGet(no) {
  if (!no) return _err('예약번호(no) 필수');
  const sheet   = _getSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return _err('예약 없음', 404);
  const rows = sheet.getRange(2, 1, lastRow - 1, TOTAL_COLS).getValues();
  const row  = rows.find(r => r[0] === no);
  if (!row) return _err('예약번호 없음: ' + no, 404);
  return _ok(_rowToObj(row));
}

/* ─── 운영 현황 요약 (당일 대시보드용) ──────────────── */
function _actionSummary(params) {
  const sheet   = _getSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return _ok({ total: 0, byStatus: {}, byRoom: {}, byPayment: {} });

  const today = params.date || Utilities.formatDate(new Date(), TIMEZONE, DATE_ONLY);
  const rows  = sheet.getRange(2, 1, lastRow - 1, TOTAL_COLS).getValues();
  const data  = rows.filter(r => r[0] !== '' && String(r[COL.희망검진일 - 1]) === today).map(_rowToObj);

  const byStatus  = {};
  const byRoom    = {};
  const byPayment = {};
  const byDoctor  = {};
  let totalCost   = 0;

  data.forEach(r => {
    byStatus[r.status]         = (byStatus[r.status]         || 0) + 1;
    if (r.examRoom)  byRoom[r.examRoom]   = (byRoom[r.examRoom]   || 0) + 1;
    if (r.paymentStatus) byPayment[r.paymentStatus] = (byPayment[r.paymentStatus] || 0) + 1;
    if (r.doctor)    byDoctor[r.doctor]   = (byDoctor[r.doctor]   || 0) + 1;
    if (r.estimatedCost) totalCost += parseFloat(String(r.estimatedCost).replace(/[^0-9.]/g, '')) || 0;
  });

  return _ok({
    date: today,
    total: data.length,
    byStatus,
    byRoom,
    byPayment,
    byDoctor,
    totalEstimatedCost: totalCost,
  });
}

/* ─── 예약 신규 등록 ────────────────────────────────── */
function _actionCreate(data) {
  if (!data || !data.name) return _err('성명(name) 필수');
  const sheet = _getSheet();

  /* [v3] 동시성 보호: 예약번호 채번(_generateNo)~appendRow 구간을 잠금.
   *      releaseLock은 finally에서 호출하여 예외 발생 시에도 반드시 해제되게 한다. */
  const lock = LockService.getScriptLock();
  try { lock.waitLock(10000); }
  catch (lockErr) { return _err('동시 요청이 많아 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.', 503); }

  try {
    const no    = _generateNo(sheet);
    const now   = Utilities.formatDate(new Date(), TIMEZONE, DATE_FORMAT);

    const row = new Array(TOTAL_COLS).fill('');
    /* 기존 18개 */
    row[COL.예약번호    - 1] = no;
    row[COL.접수일시    - 1] = now;
    row[COL.성명        - 1] = data.name         || '';
    row[COL.생년월일    - 1] = data.birth        || '';
    row[COL.연락처      - 1] = data.phone        || '';
    row[COL.성별        - 1] = data.gender       || '';
    row[COL.검진프로그램- 1] = data.program      || '';
    row[COL.희망검진일  - 1] = data.wishDate     || '';
    row[COL.희망시간    - 1] = data.wishTime     || '';
    row[COL.수면        - 1] = data.sleep        || '미선택';
    row[COL.선택검사    - 1] = Array.isArray(data.optionalTests)
                                ? data.optionalTests.join(', ')
                                : (data.optionalTests || '');
    row[COL.사업장      - 1] = data.company      || '';
    row[COL.예약경로    - 1] = data.route        || '온라인';
    row[COL.담당자      - 1] = data.manager      || '';
    row[COL.예약상태    - 1] = data.status       || '예약접수';
    row[COL.예약확정일  - 1] = '';
    row[COL.문자발송    - 1] = 'N';
    row[COL.특이사항    - 1] = data.note         || '';
    /* 추가 11개 — 기본값 */
    row[COL.검진예정시간- 1] = data.scheduledTime  || '';
    row[COL.접수시간    - 1] = '';
    row[COL.검진시작    - 1] = '';
    row[COL.검진종료    - 1] = '';
    row[COL.검진실      - 1] = data.examRoom       || '';
    row[COL.문진의사    - 1] = data.doctor         || '';
    row[COL.담당간호사  - 1] = data.nurse          || '';
    row[COL.예상비용    - 1] = data.estimatedCost  || '';
    row[COL.결제상태    - 1] = data.paymentStatus  || '미결제';
    row[COL.결과발송    - 1] = data.resultStatus   || '미발송';
    row[COL.재예약여부  - 1] = data.revisit        || '해당없음';

    sheet.appendRow(row);
    return _ok({ reservationNo: no, createdAt: now }, { message: '예약 등록 완료' });
  } finally {
    lock.releaseLock();
  }
}

/* ─── 예약상태 변경 ─────────────────────────────────── */
function _actionUpdateStatus(no, status, confirmedAt) {
  if (!no)     return _err('예약번호(no) 필수');
  if (!status) return _err('상태(status) 필수');

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
}

/* ─── 운영 정보 업데이트 (Phase 4.5 전용) ──────────── */
function _actionUpdateOps(no, data) {
  if (!no)   return _err('예약번호(no) 필수');
  if (!data) return _err('data 필수');

  const sheet    = _getSheet();
  const lastRow  = sheet.getLastRow();
  if (lastRow < 2) return _err('예약 없음', 404);

  const noCol  = sheet.getRange(2, COL.예약번호, lastRow - 1, 1).getValues();
  const rowIdx = noCol.findIndex(r => r[0] === no);
  if (rowIdx === -1) return _err('예약번호 없음: ' + no, 404);

  const sheetRow = rowIdx + 2;
  const opsFieldToCol = {
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

  Object.entries(data).forEach(([field, value]) => {
    const col = opsFieldToCol[field];
    if (!col) return;
    sheet.getRange(sheetRow, col).setValue(value ?? '');
  });

  return _ok({ reservationNo: no }, { message: '운영 정보 업데이트 완료' });
}

/* ─── 전체 필드 업데이트 ───────────────────────────── */
function _actionUpdate(no, data) {
  if (!no || !data) return _err('no, data 필수');

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

  Object.entries(data).forEach(([field, value]) => {
    const col = fieldToCol[field];
    if (!col) return;
    const val = Array.isArray(value) ? value.join(', ') : (value ?? '');
    sheet.getRange(sheetRow, col).setValue(val);
  });

  return _ok({ reservationNo: no }, { message: '업데이트 완료' });
}
