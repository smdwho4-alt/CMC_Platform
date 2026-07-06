/**
 * CMC Health Screening Platform v1.0 — Phase 4
 * app/apps_script/sheets_api_new.gs
 *
 * Google Apps Script — Sheets Web App API
 * 배포: 앱스 스크립트 편집기 > 배포 > 새 배포 > 웹 앱
 *
 * [보안] 이 스크립트는 서비스 계정 또는 Google 계정 권한으로 실행.
 * 운영 전 실행 권한을 '나만' 또는 '조직 내'로 제한할 것.
 * 개인정보(연락처, 생년월일)가 포함되므로 HTTPS 필수.
 */

/* ─── 설정 ─────────────────────────────────────────── */
const SHEET_NAME   = '예약현황';
const TIMEZONE     = 'Asia/Seoul';
const DATE_FORMAT  = 'yyyy-MM-dd HH:mm:ss';
const DATE_ONLY    = 'yyyy-MM-dd';

/* ─── 컬럼 정의 (1-indexed) ────────────────────────── */
const COL = {
  예약번호:   1,
  접수일시:   2,
  성명:       3,
  생년월일:   4,
  연락처:     5,
  성별:       6,
  검진프로그램: 7,
  희망검진일: 8,
  희망시간:   9,
  수면:      10,
  선택검사:  11,
  사업장:    12,
  예약경로:  13,
  담당자:    14,
  예약상태:  15,
  예약확정일: 16,
  문자발송:  17,
  특이사항:  18,
};
const TOTAL_COLS = 18;

/* ─── CORS 헤더 ─────────────────────────────────────── */
function _corsOutput(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}

function _ok(data, extra) {
  return _corsOutput(Object.assign({ ok: true }, extra || {}, { data }));
}

function _err(message, code) {
  return _corsOutput({ ok: false, error: message, code: code || 400 });
}

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
  sheet.getRange(1, 1, 1, headers.length)
    .setBackground('#1a4f8a')
    .setFontColor('#ffffff')
    .setFontWeight('bold');
  sheet.setFrozenRows(1);
}

/* ─── 예약번호 자동 생성 ─────────────────────────────
 *  형식: YYYYMMDD-NNNN (예: 20260701-0001)
 * ────────────────────────────────────────────────── */
function _generateNo(sheet) {
  const today = Utilities.formatDate(new Date(), TIMEZONE, 'yyyyMMdd');
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

/* 컬럼 한글 키 → 영문 필드명 매핑 */
function _colKeyToField(key) {
  const map = {
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
  };
  return map[key] || key;
}

/* ─── doGet — 예약 목록 조회 ────────────────────────── */
function doGet(e) {
  try {
    const action = (e.parameter && e.parameter.action) || 'list';

    if (action === 'list') {
      return _actionList(e.parameter);
    }
    if (action === 'get') {
      return _actionGet(e.parameter.no);
    }
    if (action === 'ping') {
      return _ok({ message: 'CMC Sheets API 정상', sheetName: SHEET_NAME });
    }

    return _err('알 수 없는 action: ' + action);
  } catch (ex) {
    return _err('서버 오류: ' + ex.message, 500);
  }
}

/* ─── doPost — 예약 등록 / 상태변경 ───────────────────  */
function doPost(e) {
  try {
    const body   = JSON.parse(e.postData.contents || '{}');
    const action = body.action;

    if (action === 'create') return _actionCreate(body.data);
    if (action === 'updateStatus') return _actionUpdateStatus(body.no, body.status, body.confirmedAt);
    if (action === 'update') return _actionUpdate(body.no, body.data);

    return _err('알 수 없는 action: ' + action);
  } catch (ex) {
    return _err('서버 오류: ' + ex.message, 500);
  }
}

/* ─── 내부 액션: 목록 조회 ────────────────────────────── */
function _actionList(params) {
  const sheet   = _getSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return _ok([], { count: 0 });

  const rows = sheet.getRange(2, 1, lastRow - 1, TOTAL_COLS).getValues();
  let data   = rows
    .filter(r => r[0] !== '')   // 빈 행 제외
    .map(_rowToObj);

  /* 필터: 상태 */
  if (params && params.status) {
    data = data.filter(r => r.status === params.status);
  }
  /* 필터: 날짜 범위 */
  if (params && params.dateFrom) {
    data = data.filter(r => r.wishDate >= params.dateFrom);
  }
  if (params && params.dateTo) {
    data = data.filter(r => r.wishDate <= params.dateTo);
  }
  /* 최신순 정렬 */
  data.sort((a, b) => (b.createdAt > a.createdAt ? 1 : -1));

  return _ok(data, { count: data.length });
}

/* ─── 내부 액션: 단건 조회 ────────────────────────────── */
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

/* ─── 내부 액션: 예약 신규 등록 ───────────────────────── */
function _actionCreate(data) {
  if (!data || !data.name) return _err('성명(name) 필수');
  const sheet = _getSheet();
  const no    = _generateNo(sheet);
  const now   = Utilities.formatDate(new Date(), TIMEZONE, DATE_FORMAT);

  const row = new Array(TOTAL_COLS).fill('');
  row[COL.예약번호   - 1] = no;
  row[COL.접수일시   - 1] = now;
  row[COL.성명       - 1] = data.name        || '';
  row[COL.생년월일   - 1] = data.birth       || '';
  row[COL.연락처     - 1] = data.phone       || '';
  row[COL.성별       - 1] = data.gender      || '';
  row[COL.검진프로그램- 1] = data.program    || '';
  row[COL.희망검진일 - 1] = data.wishDate    || '';
  row[COL.희망시간   - 1] = data.wishTime    || '';
  row[COL.수면       - 1] = data.sleep       || '미선택';
  row[COL.선택검사   - 1] = Array.isArray(data.optionalTests)
                              ? data.optionalTests.join(', ')
                              : (data.optionalTests || '');
  row[COL.사업장     - 1] = data.company     || '';
  row[COL.예약경로   - 1] = data.route       || '온라인';
  row[COL.담당자     - 1] = data.manager     || '';
  row[COL.예약상태   - 1] = data.status      || '예약접수';
  row[COL.예약확정일 - 1] = '';
  row[COL.문자발송   - 1] = 'N';
  row[COL.특이사항   - 1] = data.note        || '';

  sheet.appendRow(row);
  return _ok({ reservationNo: no, createdAt: now }, { message: '예약 등록 완료' });
}

/* ─── 내부 액션: 상태 변경 ────────────────────────────── */
function _actionUpdateStatus(no, status, confirmedAt) {
  if (!no)     return _err('예약번호(no) 필수');
  if (!status) return _err('상태(status) 필수');

  const sheet   = _getSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return _err('예약 없음', 404);

  const noCol = sheet.getRange(2, COL.예약번호, lastRow - 1, 1).getValues();
  const rowIdx = noCol.findIndex(r => r[0] === no);
  if (rowIdx === -1) return _err('예약번호 없음: ' + no, 404);

  const sheetRow = rowIdx + 2;  // 헤더 1행 + 0-index 보정
  sheet.getRange(sheetRow, COL.예약상태).setValue(status);

  if (status === '예약확정') {
    const confirmed = confirmedAt ||
      Utilities.formatDate(new Date(), TIMEZONE, DATE_FORMAT);
    sheet.getRange(sheetRow, COL.예약확정일).setValue(confirmed);
  }

  return _ok({ reservationNo: no, status }, { message: '상태 변경 완료' });
}

/* ─── 내부 액션: 전체 필드 업데이트 ──────────────────── */
function _actionUpdate(no, data) {
  if (!no)   return _err('예약번호(no) 필수');
  if (!data) return _err('data 필수');

  const sheet   = _getSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return _err('예약 없음', 404);

  const noCol  = sheet.getRange(2, COL.예약번호, lastRow - 1, 1).getValues();
  const rowIdx = noCol.findIndex(r => r[0] === no);
  if (rowIdx === -1) return _err('예약번호 없음: ' + no, 404);

  const sheetRow = rowIdx + 2;
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
  };

  Object.entries(data).forEach(([field, value]) => {
    const col = fieldToCol[field];
    if (!col) return;
    const val = Array.isArray(value) ? value.join(', ') : value;
    sheet.getRange(sheetRow, col).setValue(val);
  });

  return _ok({ reservationNo: no }, { message: '업데이트 완료' });
}
