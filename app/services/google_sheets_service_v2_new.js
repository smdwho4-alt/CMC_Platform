/**
 * CMC Health Screening Platform v1.0 — Phase 4
 * app/services/google_sheets_service_v2_new.js
 *
 * Google Sheets 어댑터 v2 — Apps Script Web App 방식
 *
 * Phase 3 google_sheets_service_new.js와 인터페이스 동일.
 * 차이점: Live 모드에서 Sheets API 직접 호출 대신
 *         Apps Script Web App(doGet/doPost)을 경유.
 *
 * 모드 선택:
 *   CMC_CONFIG.isLocal()   → Mock (localStorage, Phase 1~3 동일)
 *   CMC_CONFIG.isGoogle()  → Live (Apps Script Web App URL 경유)
 *
 * [보안] Web App URL이 노출되면 누구나 데이터에 접근 가능.
 *        Apps Script 배포 시 '액세스 권한'을 '조직 내' 또는
 *        '나만'으로 설정할 것. 운영 전 반드시 확인.
 */
'use strict';

const CMC_SheetsServiceV2 = {

  _mockDelay: 400,

  /* ─────────────────────────────────────────────────────────
     공개 인터페이스 (Mock / Live 공통)
  ───────────────────────────────────────────────────────── */

  /** 전체 예약 목록 조회 */
  async getAll(params) {
    return CMC_CONFIG.isGoogle() ? this._liveGetAll(params) : this._mockGetAll();
  },

  /** 예약 단건 조회 */
  async getOne(reservationNo) {
    return CMC_CONFIG.isGoogle() ? this._liveGetOne(reservationNo) : this._mockGetOne(reservationNo);
  },

  /** 예약 신규 등록 */
  async create(reservation) {
    return CMC_CONFIG.isGoogle() ? this._liveCreate(reservation) : this._mockCreate(reservation);
  },

  /** 예약 상태 변경 */
  async updateStatus(reservationNo, status, confirmedAt) {
    return CMC_CONFIG.isGoogle()
      ? this._liveUpdateStatus(reservationNo, status, confirmedAt)
      : this._mockUpdateStatus(reservationNo, status);
  },

  /** 예약 전체 필드 업데이트 */
  async update(reservationNo, patch) {
    return CMC_CONFIG.isGoogle() ? this._liveUpdate(reservationNo, patch) : this._mockUpdate(reservationNo, patch);
  },

  /** 연결 테스트 (ping) */
  async ping() {
    if (!CMC_CONFIG.isGoogle()) {
      return { ok: true, mode: 'mock', message: 'Mock 모드 — localStorage 사용 중' };
    }
    if (!CMC_CONFIG.hasWebAppUrl()) {
      return { ok: false, mode: 'live', message: 'Apps Script Web App URL이 설정되지 않았습니다.' };
    }
    return this._livePing();
  },

  /* ─────────────────────────────────────────────────────────
     Mock 구현 (localStorage 위임 — Phase 1~3 동일)
  ───────────────────────────────────────────────────────── */

  _delay() { return new Promise(r => setTimeout(r, this._mockDelay)); },

  async _mockGetAll() {
    await this._delay();
    const data = CMC_DB.getAll();
    console.log(`[SheetsV2 Mock] getAll → ${data.length}건`);
    return { ok: true, data, source: 'local', count: data.length };
  },

  async _mockGetOne(no) {
    await this._delay();
    const item = CMC_DB.findByNo(no);
    if (!item) return { ok: false, error: '예약번호 없음: ' + no, code: 404 };
    return { ok: true, data: item, source: 'local' };
  },

  async _mockCreate(reservation) {
    await this._delay();
    const saved = CMC_DB.add(reservation);
    console.log(`[SheetsV2 Mock] create → ${reservation.reservationNo}`);
    return { ok: true, data: saved, source: 'local', message: '예약 등록 완료' };
  },

  async _mockUpdateStatus(no, status) {
    await this._delay();
    const updated = CMC_DB.update(no, { status });
    console.log(`[SheetsV2 Mock] updateStatus → ${no} : ${status}`);
    return { ok: !!updated, data: updated, source: 'local' };
  },

  async _mockUpdate(no, patch) {
    await this._delay();
    const updated = CMC_DB.update(no, patch);
    console.log(`[SheetsV2 Mock] update → ${no}`, patch);
    return { ok: !!updated, data: updated, source: 'local' };
  },

  /* ─────────────────────────────────────────────────────────
     Live 구현 — Apps Script Web App 경유
  ───────────────────────────────────────────────────────── */

  _url() {
    const u = CMC_CONFIG.appsScript.webAppUrl;
    if (!u) throw new Error('Apps Script Web App URL 미설정 — config_v2_new.js 확인');
    return u;
  },

  /** GET 요청 헬퍼 */
  async _get(params) {
    const qs  = new URLSearchParams(params).toString();
    const res = await fetch(`${this._url()}?${qs}`);
    if (!res.ok) throw new Error(`Apps Script GET 오류: ${res.status}`);
    return res.json();
  },

  /** POST 요청 헬퍼 */
  async _post(body) {
    const res = await fetch(this._url(), {
      method:  'POST',
      /* Apps Script doPost는 Content-Type text/plain으로 받아야
         함 (CORS preflight 없이 처리 가능). body는 JSON 문자열. */
      headers: { 'Content-Type': 'text/plain;charset=utf-8' },
      body:    JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Apps Script POST 오류: ${res.status}`);
    return res.json();
  },

  async _liveGetAll(params) {
    try {
      const query = Object.assign({ action: 'list' }, params || {});
      const res   = await this._get(query);
      console.log(`[SheetsV2 Live] getAll → ${res.count}건`);
      return { ok: res.ok, data: res.data || [], source: 'google', count: res.count || 0 };
    } catch (e) {
      return { ok: false, error: e.message, source: 'google', data: [] };
    }
  },

  async _liveGetOne(no) {
    try {
      const res = await this._get({ action: 'get', no });
      return { ok: res.ok, data: res.data, source: 'google' };
    } catch (e) {
      return { ok: false, error: e.message, source: 'google' };
    }
  },

  async _liveCreate(reservation) {
    try {
      const res = await this._post({ action: 'create', data: reservation });
      console.log(`[SheetsV2 Live] create → ${res.data?.reservationNo}`);
      return { ok: res.ok, data: res.data, source: 'google', message: res.message };
    } catch (e) {
      return { ok: false, error: e.message, source: 'google' };
    }
  },

  async _liveUpdateStatus(no, status, confirmedAt) {
    try {
      const res = await this._post({ action: 'updateStatus', no, status, confirmedAt });
      console.log(`[SheetsV2 Live] updateStatus → ${no} : ${status}`);
      return { ok: res.ok, data: res.data, source: 'google', message: res.message, error: res.error };
    } catch (e) {
      return { ok: false, error: e.message, source: 'google' };
    }
  },

  async _liveUpdate(no, patch) {
    try {
      const res = await this._post({ action: 'update', no, data: patch });
      console.log(`[SheetsV2 Live] update → ${no}`);
      return { ok: res.ok, data: res.data, source: 'google', message: res.message, error: res.error };
    } catch (e) {
      return { ok: false, error: e.message, source: 'google' };
    }
  },

  async _livePing() {
    try {
      const res = await this._get({ action: 'ping' });
      return {
        ok:      res.ok,
        mode:    'live',
        message: res.ok
          ? `Apps Script 연결 성공 (시트: ${CMC_CONFIG.appsScript.sheetName})`
          : (res.error || '연결 실패'),
      };
    } catch (e) {
      return { ok: false, mode: 'live', message: e.message };
    }
  },
};
