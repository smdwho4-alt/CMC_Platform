/**
 * CMC Health Screening Platform v1.0 — Phase 3
 * app/services/google_sheets_service_new.js
 *
 * Google Sheets API v4 Adapter
 *  - Mock 모드: localStorage 데이터를 그대로 사용 (시제품)
 *  - Live 모드: Google Sheets API v4 호출 (운영 전 clientId·apiKey 설정 필요)
 *
 * 인터페이스는 동일하므로 CMC_CONFIG.dataSource 전환만으로 모드 교체 가능.
 */
'use strict';

const CMC_SheetsService = {

  /* ── 내부 상태 ── */
  _mockDelay: 400,   // Mock 응답 지연(ms) — 실제 API 체감 시뮬레이션

  /* ─────────────────────────────────────────────────────────
     공개 인터페이스 (Live / Mock 공통)
  ───────────────────────────────────────────────────────── */

  /** 전체 예약 목록 조회 */
  async getAll() {
    return CMC_CONFIG.isGoogle() ? this._liveGetAll() : this._mockGetAll();
  },

  /** 예약 1건 추가 */
  async append(reservation) {
    return CMC_CONFIG.isGoogle() ? this._liveAppend(reservation) : this._mockAppend(reservation);
  },

  /** 예약 상태 업데이트 */
  async updateStatus(reservationNo, status) {
    return CMC_CONFIG.isGoogle() ? this._liveUpdate(reservationNo, { status }) : this._mockUpdate(reservationNo, { status });
  },

  /** 예약 전체 필드 업데이트 */
  async update(reservationNo, patch) {
    return CMC_CONFIG.isGoogle() ? this._liveUpdate(reservationNo, patch) : this._mockUpdate(reservationNo, patch);
  },

  /** 연결 상태 테스트 */
  async ping() {
    if (!CMC_CONFIG.isGoogle()) return { ok: true, mode: 'mock', message: 'Mock 모드 — localStorage 사용 중' };
    return this._livePing();
  },

  /* ─────────────────────────────────────────────────────────
     Mock 구현 (localStorage 위임)
  ───────────────────────────────────────────────────────── */

  _delay() { return new Promise(r => setTimeout(r, this._mockDelay)); },

  async _mockGetAll() {
    await this._delay();
    const data = CMC_DB.getAll();
    console.log(`[SheetsService Mock] getAll → ${data.length}건`);
    return { ok: true, data, source: 'local', count: data.length };
  },

  async _mockAppend(reservation) {
    await this._delay();
    const saved = CMC_DB.add(reservation);
    console.log(`[SheetsService Mock] append → ${reservation.reservationNo}`);
    return { ok: true, data: saved, source: 'local', rowIndex: CMC_DB.getAll().length };
  },

  async _mockUpdate(reservationNo, patch) {
    await this._delay();
    const updated = CMC_DB.update(reservationNo, patch);
    console.log(`[SheetsService Mock] update → ${reservationNo}`, patch);
    return { ok: !!updated, data: updated, source: 'local' };
  },

  /* ─────────────────────────────────────────────────────────
     Live 구현 (Google Sheets API v4)
     [운영 전 구현 필요] — 현재 Stub 상태
  ───────────────────────────────────────────────────────── */

  _sheetsUrl(method = '') {
    const id = CMC_CONFIG.google.sheetsId;
    const base = `https://sheets.googleapis.com/v4/spreadsheets/${id}`;
    return method ? `${base}/${method}` : base;
  },

  async _getToken() {
    /* [구현 필요]
     * Google Identity Services (GIS) 또는 서버사이드 OAuth 토큰 반환.
     * 예: gapi.auth2.getAuthInstance().currentUser.get().getAuthResponse().access_token
     */
    throw new Error('Google OAuth 토큰 미설정 — CMC_CONFIG.google.clientId 확인 필요');
  },

  async _liveGetAll() {
    const token = await this._getToken();
    const range  = encodeURIComponent(`${CMC_CONFIG.google.sheetsRange}!A:Z`);
    const res    = await fetch(`${this._sheetsUrl('values/' + range)}?key=${CMC_CONFIG.google.apiKey}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error(`Sheets API 오류: ${res.status} ${res.statusText}`);
    const body = await res.json();
    const [header, ...rows] = body.values || [];
    const data = rows.map(row => {
      const obj = {};
      (header || []).forEach((k, i) => { obj[k] = row[i] ?? ''; });
      return obj;
    });
    return { ok: true, data, source: 'google', count: data.length };
  },

  async _liveAppend(reservation) {
    const token  = await this._getToken();
    const range  = encodeURIComponent(`${CMC_CONFIG.google.sheetsRange}!A:Z`);
    const values = [this._toRow(reservation)];
    const res    = await fetch(`${this._sheetsUrl('values/' + range + ':append')}?valueInputOption=USER_ENTERED`, {
      method:  'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body:    JSON.stringify({ values }),
    });
    if (!res.ok) throw new Error(`Sheets append 오류: ${res.status}`);
    return { ok: true, data: reservation, source: 'google' };
  },

  async _liveUpdate(reservationNo, patch) {
    /* [구현 필요]
     * 1. 시트에서 reservationNo로 행 번호 검색
     * 2. 해당 행의 변경 필드를 batchUpdate로 업데이트
     */
    throw new Error('Live update 미구현 — 운영 전 서버사이드 Apps Script 사용 권장');
  },

  async _livePing() {
    try {
      const token = await this._getToken();
      const res   = await fetch(this._sheetsUrl(), {
        headers: { Authorization: `Bearer ${token}` },
      });
      return res.ok
        ? { ok: true, mode: 'live', message: 'Google Sheets 연결 성공', sheetsId: CMC_CONFIG.google.sheetsId }
        : { ok: false, mode: 'live', message: `연결 실패: ${res.status}` };
    } catch (e) {
      return { ok: false, mode: 'live', message: e.message };
    }
  },

  /* 예약 객체 → 시트 행 변환 */
  _toRow(r) {
    return [
      r.reservationNo, r.createdAt, r.updatedAt, r.status,
      r.name, r.birth, r.phone, r.gender, r.program,
      r.wishDate, r.wishTime, r.sleep,
      (r.optionalTests || []).join('|'), r.company, r.note,
    ];
  },

  /* 시트 행 → 예약 객체 변환 */
  _fromRow(row) {
    const keys = ['reservationNo','createdAt','updatedAt','status','name','birth','phone',
                  'gender','program','wishDate','wishTime','sleep','optionalTests','company','note'];
    const obj  = {};
    keys.forEach((k, i) => { obj[k] = row[i] ?? ''; });
    if (typeof obj.optionalTests === 'string') obj.optionalTests = obj.optionalTests ? obj.optionalTests.split('|') : [];
    return obj;
  },

  /* ── 헤더 행 정의 (시트 초기화 시 사용) ── */
  SHEET_HEADERS: ['예약번호','접수일시','수정일시','상태','성명','생년월일','연락처','성별',
                  '프로그램','희망검진일','희망시간','수면여부','선택검사','사업장','특이사항'],
};
