/**
 * CMC Health Screening Platform — Sheets Web App API
 * sheets_api_v4_deploy_new.gs  ·  Version 4.0 (운영 배포용)
 *
 * ─────────────────────────────────────────────────────────────
 *  v3 → v4 변경 요약
 *  1. CONFIG 블록을 파일 최상단에 독립 분리 (수정 필요 항목만)
 *  2. doGet에 CORS preflight(OPTIONS) 우회 처리 추가
 *  3. POST 요청 Content-Type 경고 처리
 *  4. _actionList 결과 개인정보(phone·birth) 응답 포함 여부 선택자 추가
 *  5. API 버전 상수(API_VERSION) 추가, ping 응답에 포함
 *  6. 운영 배포 전 체크리스트 주석 추가
 *  핵심 로직(doGet/doPost/CRUD/DateFix) — v3와 동일, 변경 없음.
 * ─────────────────────────────────────────────────────────────
 *
 * ▣ 포함 엔드포인트
 *   GET  ?action=ping                     연결 확인
 *   GET  ?action=list[&status&dateFrom&dateTo&doctor&examRoom&paymentStatus&includePii=false]
 *   GET  ?action=get&no=YYYYMMDD-NNNN     단건 조회 (전체 필드)
 *   GET  ?action=summary[&date=YYYY-MM-DD] 당일 운영 요약 (집계값만, PII 미포함)
 *   POST {action:'create',       data:{...}}          예약 등록
 *   POST {action:'updateStatus', no, status[,confirmedAt]}  상태 변경
 *   POST {action:'updateOps',    no, data:{...}}      운영 정보 업데이트
 *   POST {action:'update',       no, data:{...}}      전체 필드 업데이트
 *
 * ▣ 보안 주의사항
 *   - SPREADSHEET_ID, SHEET_NAME은 외부 공개 금지 (소스 공개 저장소에 올리지 말 것)
 *   - 배포 시 액세스 권한: '나만' 또는 '조직 내'로 설정
 *   - 개인정보(phone·birth·name) 포함 — HTTPS 필수
 *   - 운영 DB 전환 전 반드시 테스트 환경에서 검증
 */

/* ═══════════════════════════════════════════════════════════
 *  ★★★ CONFIG — 배포 전 이 블록만 수정하세요 ★★★
 *
 *  STEP 1. 아래 SPREADSHEET_ID를 실제 Google Sheets 문서 ID로 교체.
 *          URL: https://docs.google.com/spreadsheets/d/[여기]/edit
 *          현재 값은 실제 운영 시트 ID (변경 불필요 시 유지).
 *
 *  STEP 2. SHEET_NAME은 시트 탭 이름과 정확히 일치해야 함.
 *
 *  STEP 3. INCLUDE_PII_IN_LIST:
 *          false → list 응답에서 phone·birth 제거 (대시보드용 기본값)
 *          true  → 전체 필드 포함 (관리자 전용 엔드포인트 등)
 *          (GET ?action=list&includePii=true 로 개별 요청에서 오버라이드 가능)
 * ═══════════════════════════════════════════════════════════ */
const SPREADSHEET_ID     = '1WFnsyeBpHVhG5IgZ--3T00jCe-FPUMJdgWl4m120nuU'; // ← 실제 시트 ID
const SHEET_NAME         = '종합검진_예약대장';                               // ← 시트 탭 이름
const INCLUDE_PII_IN_LIST = false;                                           // ← 목록 응답 PII 포함 여부
/* ─────────────────────── 아래는 수정하지 마세요 ─────────────────────── */
const API_VERSION = '4.0';
const TIMEZONE    = 'Asia/Seoul';
const DATE_FORMAT = 'yyyy-MM-dd HH:mm:ss';
const DATE_ONLY   = 'yyyy-MM-dd';
const TIME_FORMAT = 'HH:mm';

/* ─── 컬럼 정의 (1-indexed, 총 29개) ──────────────────
 * ── 기존 18개 ───────────────────────────────────────
 *  1.예약번호  2.접수일시  3.성명     4.생년월일   5.연락처
 *  6.성별      7.검진프로그램 8.희망검진일 9.희망시간 10.수면
 * 11.선택검사 12.사업장   13.예약경로 14.담당자    15.예약상태
 * 16.예약확정일 17.문자발송 18.특이사항
 * ── 추가 11개 (운영 DB) ─────────────────────────────
 * 19.검진예정시간 20.접수시간 21.검진시작 22.검진종료 23.검진실
 * 24.문진의사  25.담당간호사 26.예상비용 27.결제상태 28.결과발송
 * 29.재예약여부
 * ──────────────────────────────────────────────────── */
const COL = {
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

/* 개인정보 필드(list에서 INCLUDE_PII_IN_LIST=false 시 제거) */
const PII_FIELDS = ['phone', 'birth'];

/* 열거형 허용값 */
const VALID_PAYMENT_STATUS = ['미결제', '결제완료', '부분결제', '환불'];
const VALID_RESULT_STATUS  = ['미발송', '발송완료', '미수령', '수령확인'];
const VALID_REVISIT        = ['해당없음', '재예약예정', '재예약완료'];

/* ─── 출력 헬퍼 ─────────────────────────────────────────────
 * GAS ContentService는 응답 헤더 직접 설정이 불가합니다.
 * CORS는 아래 방법으로 우회:
 *   · GET 요청: URLSearchParams 사용 → 브라우저가 simple request로 처리 → CORS 불필요
 *   · POST 요청: fetch body에 Content-Type 헤더 미설정(기본 text/plain) → simple request
 *   · 배포 시 액세스 권한을 '모든 사용자'로 설정하면 익명 fetch 가능
 * ──────────────────────────────────────────────────────────── */
function _output(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
function _ok(data, extra)    { return _output(Object.assign({ ok: true, apiVersion: API_VERSION }, extra || {}, { data })); }
function _err(message, code) { return _output({ ok: false, error: message, code: code || 400, apiVersion: API_VERSION }); }

/* ─── 시트 참조 ─────────────────────────────────────────── */
function _getSheet() {
  const ss    = SpreadsheetApp.openById(SPREADSHEET_ID);
  let   sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    _initHeader(sheet);
  }
  return sheet;
}

function _initHeader(sheet) {
  const headers     = Object.keys(COL);
  const headerRange = sheet.getRange(1, 1, 1, headers.length);
  headerRange.setValues([headers]);
  headerRange.setBackground('#1a4f8a').setFontColor('#ffffff').setFontWeight('bold');
  sheet.getRange(1, 19, 1, 11).setBackground('#2e7d32');
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, headers.length);
}

/* ─── 예약번호 채번 ──────────────────────────────────────── */
function _generateNo(sheet) {
  const today   = Utilities.formatDate(new Date(), TIMEZONE, 'yyyyMMdd');
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return today + '-0001';

  const existing = sheet.getRange(2, COL.예약번호, lastRow - 1, 1).getValues()
    .map(r => r[0])
    .filter(v => String(v).startsWith(today));

  if (!existing.length) return today + '-0001';
  const max = existing.reduce((acc, v) => {
    const seq = parseInt(String(v).split('-')[1] || '0', 10);
    return seq > acc ? seq : acc;
  }, 0);
  return today + '-' + String(max + 1).padStart(4, '0');
}

/* ─── 컬럼 키 → 영문 필드명 ──────────────────────────────── */
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

/* ─── 행 → 객체 변환 [DateFix 포함] ──────────────────────── */
const DATE_ONLY_KEYS = { '생년월일': true, '희망검진일': true };
const TIME_ONLY_KEYS = { '희망시간': true };

function _rowToObj(row) {
  const obj = {};
  Object.entries(COL).forEach(([key, idx]) => {
    const val = row[idx - 1];
    if (val instanceof Date) {
      const fmt = DATE_ONLY_KEYS[key] ? DATE_ONLY : (TIME_ONLY_KEYS[key] ? TIME_FORMAT : DATE_FORMAT);
      obj[_colKeyToField(key)] = Utilities.formatDate(val, TIMEZONE, fmt);
    } else {
      obj[_colKeyToField(key)] = (val === null || val === undefined) ? '' : String(val);
    }
  });
  return obj;
}

/* PII 필드 제거 (INCLUDE_PII_IN_LIST=false 또는 includePii 파라미터 false 시) */
function _stripPii(obj) {
  const copy = Object.assign({}, obj);
  PII_FIELDS.forEach(f => delete copy[f]);
  return copy;
}

/* ─── doGet ─────────────────────────────────────────────────
 * [CORS] GET은 URLSearchParams를 통한 simple request → CORS 헤더 불필요.
 * ?action=options 로 preflight 우회 지원 (fetch polyfill 용).
 * ──────────────────────────────────────────────────────────── */
function doGet(e) {
  try {
    const action = (e && e.parameter && e.parameter.action) || 'list';

    /* OPTIONS 우회: fetch가 preflight 대신 GET으로 options를 보낼 경우 */
    if (action === 'options') return _ok({ methods: 'GET,POST', message: 'CORS preflight OK' });

    if (action === 'ping')    return _ok({ message: 'CMC Sheets API v' + API_VERSION + ' 정상', sheetName: SHEET_NAME, totalCols: TOTAL_COLS });
    if (action === 'list')    return _actionList(e.parameter);
    if (action === 'get')     return _actionGet((e.parameter || {}).no);
    if (action === 'summary') return _actionSummary(e.parameter || {});

    return _err('알 수 없는 action: ' + action);
  } catch (ex) {
    return _err('서버 오류(GET): ' + ex.message, 500);
  }
}

/* ─── doPost ────────────────────────────────────────────────
 * [CORS] POST는 Content-Type 헤더 없이(기본 text/plain) 호출해야 CORS safe.
 *   클라이언트: fetch(url, { method:'POST', body: JSON.stringify(data) })
 *   Content-Type: application/json 설정 시 preflight → GAS 미지원 → 실패.
 * ──────────────────────────────────────────────────────────── */
function doPost(e) {
  try {
    const raw    = (e && e.postData && e.postData.contents) || '{}';
    const body   = JSON.parse(raw);
    const action = body.action;

    if (action === 'create')       return _actionCreate(body.data);
    if (action === 'updateStatus') return _actionUpdateStatus(body.no, body.status, body.confirmedAt);
    if (action === 'updateOps')    return _actionUpdateOps(body.no, body.data);
    if (action === 'update')       return _actionUpdate(body.no, body.data);

    return _err('알 수 없는 action: ' + action);
  } catch (ex) {
    return _err('서버 오류(POST): ' + ex.message, 500);
  }
}

/* ─── 목록 조회 ─────────────────────────────────────────── */
function _actionList(params) {
  const sheet   = _getSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return _ok([], { count: 0 });

  const rows = sheet.getRange(2, 1, lastRow - 1, TOTAL_COLS).getValues();
  let   data = rows.filter(r => r[0] !== '').map(_rowToObj);

  /* 필터 */
  if (params.status)        data = data.filter(r => r.status === params.status);
  if (params.dateFrom)      data = data.filter(r => r.wishDate >= params.dateFrom);
  if (params.dateTo)        data = data.filter(r => r.wishDate <= params.dateTo);
  if (params.doctor)        data = data.filter(r => r.doctor === params.doctor);
  if (params.examRoom)      data = data.filter(r => r.examRoom === params.examRoom);
  if (params.paymentStatus) data = data.filter(r => r.paymentStatus === params.paymentStatus);

  /* 최신순 정렬 */
  data.sort((a, b) => (b.createdAt > a.createdAt ? 1 : -1));

  /* PII 처리: 파라미터 includePii=true 또는 CONFIG에서 INCLUDE_PII_IN_LIST=true 시 포함 */
  const showPii = (params.includePii === 'true') || INCLUDE_PII_IN_LIST;
  if (!showPii) data = data.map(_stripPii);

  return _ok(data, { count: data.length });
}

/* ─── 단건 조회 (전체 필드 포함) ────────────────────────── */
function _actionGet(no) {
  if (!no) return _err('예약번호(no) 필수');
  const sheet   = _getSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return _err('예약 없음', 404);

  const rows = sheet.getRange(2, 1, lastRow - 1, TOTAL_COLS).getValues();
  const row  = rows.find(r => String(r[0]) === String(no));
  if (!row) return _err('예약번호 없음: ' + no, 404);

  return _ok(_rowToObj(row));
}

/* ─── 당일 운영 요약 (PII 미포함, 집계값만) ─────────────── */
function _actionSummary(params) {
  const sheet   = _getSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return _ok({ total: 0, byStatus: {}, byRoom: {}, byPayment: {}, byDoctor: {}, totalEstimatedCost: 0 });

  const today = params.date || Utilities.formatDate(new Date(), TIMEZONE, DATE_ONLY);
  const rows  = sheet.getRange(2, 1, lastRow - 1, TOTAL_COLS).getValues();
  /* [DateFix] _rowToObj로 날짜 필드 정규화 후 비교 */
  const data  = rows.filter(r => r[0] !== '').map(_rowToObj).filter(r => r.wishDate === today);

  const byStatus  = {};
  const byRoom    = {};
  const byPayment = {};
  const byDoctor  = {};
  let   totalCost = 0;

  data.forEach(r => {
    byStatus[r.status]  = (byStatus[r.status]  || 0) + 1;
    if (r.examRoom)      byRoom[r.examRoom]     = (byRoom[r.examRoom]     || 0) + 1;
    if (r.paymentStatus) byPayment[r.paymentStatus] = (byPayment[r.paymentStatus] || 0) + 1;
    if (r.doctor)        byDoctor[r.doctor]     = (byDoctor[r.doctor]     || 0) + 1;
    if (r.estimatedCost) totalCost += parseFloat(String(r.estimatedCost).replace(/[^0-9.]/g, '')) || 0;
  });

  return _ok({ date: today, total: data.length, byStatus, byRoom, byPayment, byDoctor, totalEstimatedCost: totalCost });
}

/* ─── 예약 신규 등록 ─────────────────────────────────────── */
function _actionCreate(data) {
  if (!data || !data.name) return _err('성명(name) 필수');

  const sheet = _getSheet();
  const lock  = LockService.getScriptLock();
  try { lock.waitLock(10000); }
  catch (lockErr) { return _err('동시 요청 초과. 잠시 후 재시도 해주세요.', 503); }

  try {
    const no  = _generateNo(sheet);
    const now = Utilities.formatDate(new Date(), TIMEZONE, DATE_FORMAT);

    const row = new Array(TOTAL_COLS).fill('');
    row[COL.예약번호    - 1] = no;
    row[COL.접수일시    - 1] = now;
    row[COL.성명        - 1] = data.name          || '';
    row[COL.생년월일    - 1] = data.birth         || '';
    row[COL.연락처      - 1] = data.phone         || '';
    row[COL.성별        - 1] = data.gender        || '';
    row[COL.검진프로그램- 1] = data.program       || '';
    row[COL.희망검진일  - 1] = data.wishDate      || '';
    row[COL.희망시간    - 1] = data.wishTime      || '';
    row[COL.수면        - 1] = data.sleep         || '미선택';
    row[COL.선택검사    - 1] = Array.isArray(data.optionalTests)
                                ? data.optionalTests.join(', ')
                                : (data.optionalTests || '');
    row[COL.사업장      - 1] = data.company       || '';
    row[COL.예약경로    - 1] = data.route         || '온라인';
    row[COL.담당자      - 1] = data.manager       || '';
    row[COL.예약상태    - 1] = data.status        || '예약접수';
    row[COL.예약확정일  - 1] = '';
    row[COL.문자발송    - 1] = 'N';
    row[COL.특이사항    - 1] = data.note          || '';
    row[COL.검진예정시간- 1] = data.scheduledTime || '';
    row[COL.접수시간    - 1] = '';
    row[COL.검진시작    - 1] = '';
    row[COL.검진종료    - 1] = '';
    row[COL.검진실      - 1] = data.examRoom      || '';
    row[COL.문진의사    - 1] = data.doctor        || '';
    row[COL.담당간호사  - 1] = data.nurse         || '';
    row[COL.예상비용    - 1] = data.estimatedCost || '';
    row[COL.결제상태    - 1] = data.paymentStatus || '미결제';
    row[COL.결과발송    - 1] = data.resultStatus  || '미발송';
    row[COL.재예약여부  - 1] = data.revisit       || '해당없음';

    sheet.appendRow(row);

    /* [DateFix] birth·wishDate·wishTime — 텍스트 서식 강제 */
    const r = sheet.getLastRow();
    sheet.getRange(r, COL.생년월일).setNumberFormat('@').setValue(String(data.birth    || ''));
    sheet.getRange(r, COL.희망검진일).setNumberFormat('@').setValue(String(data.wishDate || ''));
    sheet.getRange(r, COL.희망시간).setNumberFormat('@').setValue(String(data.wishTime  || ''));

    return _ok({ reservationNo: no, createdAt: now }, { message: '예약 등록 완료' });
  } finally {
    lock.releaseLock();
  }
}

/* ─── 예약상태 변경 ─────────────────────────────────────── */
function _actionUpdateStatus(no, status, confirmedAt) {
  if (!no)     return _err('예약번호(no) 필수');
  if (!status) return _err('상태(status) 필수');

  const sheet   = _getSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return _err('예약 없음', 404);

  const noCol  = sheet.getRange(2, COL.예약번호, lastRow - 1, 1).getValues();
  const rowIdx = noCol.findIndex(r => r[0] === no);
  if (rowIdx === -1) return _err('예약번호 없음', 404);

  const sheetRow = rowIdx + 2;
  sheet.getRange(sheetRow, COL.예약상태).setValue(status);

  if (status === '예약확정') {
    sheet.getRange(sheetRow, COL.예약확정일).setValue(
      confirmedAt || Utilities.formatDate(new Date(), TIMEZONE, DATE_FORMAT)
    );
  }

  const now = Utilities.formatDate(new Date(), TIMEZONE, DATE_FORMAT);
  if (status === '검진중')  { sheet.getRange(sheetRow, COL.접수시간).setValue(now); sheet.getRange(sheetRow, COL.검진시작).setValue(now); }
  if (status === '검진완료') { sheet.getRange(sheetRow, COL.검진종료).setValue(now); }

  return _ok({ reservationNo: no, status }, { message: '상태 변경 완료' });
}

/* ─── 운영 정보 업데이트 ───────────────────────────────── */
function _actionUpdateOps(no, data) {
  if (!no || !data) return _err('no, data 필수');

  const sheet   = _getSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return _err('예약 없음', 404);

  const noCol  = sheet.getRange(2, COL.예약번호, lastRow - 1, 1).getValues();
  const rowIdx = noCol.findIndex(r => r[0] === no);
  if (rowIdx === -1) return _err('예약번호 없음', 404);

  const sheetRow   = rowIdx + 2;
  const opsMap = {
    scheduledTime: COL.검진예정시간, checkinTime: COL.접수시간,
    examStart:     COL.검진시작,     examEnd:     COL.검진종료,
    examRoom:      COL.검진실,       doctor:      COL.문진의사,
    nurse:         COL.담당간호사,   estimatedCost: COL.예상비용,
    paymentStatus: COL.결제상태,     resultStatus:  COL.결과발송,
    revisit:       COL.재예약여부,
  };

  Object.entries(data).forEach(([field, value]) => {
    const col = opsMap[field];
    if (col) sheet.getRange(sheetRow, col).setValue(value ?? '');
  });

  return _ok({ reservationNo: no }, { message: '운영 정보 업데이트 완료' });
}

/* ─── 전체 필드 업데이트 ───────────────────────────────── */
function _actionUpdate(no, data) {
  if (!no || !data) return _err('no, data 필수');

  const sheet   = _getSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return _err('예약 없음', 404);

  const noCol  = sheet.getRange(2, COL.예약번호, lastRow - 1, 1).getValues();
  const rowIdx = noCol.findIndex(r => r[0] === no);
  if (rowIdx === -1) return _err('예약번호 없음', 404);

  const sheetRow = rowIdx + 2;
  const fieldMap = {
    name: COL.성명, birth: COL.생년월일, phone: COL.연락처, gender: COL.성별,
    program: COL.검진프로그램, wishDate: COL.희망검진일, wishTime: COL.희망시간,
    sleep: COL.수면, optionalTests: COL.선택검사, company: COL.사업장,
    route: COL.예약경로, manager: COL.담당자, status: COL.예약상태,
    confirmedAt: COL.예약확정일, smsSent: COL.문자발송, note: COL.특이사항,
    scheduledTime: COL.검진예정시간, checkinTime: COL.접수시간,
    examStart: COL.검진시작, examEnd: COL.검진종료, examRoom: COL.검진실,
    doctor: COL.문진의사, nurse: COL.담당간호사, estimatedCost: COL.예상비용,
    paymentStatus: COL.결제상태, resultStatus: COL.결과발송, revisit: COL.재예약여부,
  };

  /* [DateFix] birth·wishDate·wishTime 텍스트 서식 강제 */
  const DATE_TEXT_COLS = { birth: COL.생년월일, wishDate: COL.희망검진일, wishTime: COL.희망시간 };

  Object.entries(data).forEach(([field, value]) => {
    const col = fieldMap[field];
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
}
