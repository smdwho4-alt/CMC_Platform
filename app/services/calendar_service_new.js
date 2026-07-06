/**
 * CMC Health Screening Platform v1.0 — Phase 3
 * app/services/calendar_service_new.js
 *
 * Google Calendar API Adapter
 *  - Mock 모드: 이벤트 객체를 생성하고 localStorage에 임시 기록
 *  - Live 모드: Google Calendar API v3 호출 (운영 전 설정 필요)
 */
'use strict';

const CMC_CalendarService = {

  STORAGE_KEY: 'cmc_calendar_events_v1',
  _mockDelay: 350,

  /* ─────────────────────────────────────────────────────────
     공개 인터페이스
  ───────────────────────────────────────────────────────── */

  /** 예약확정 이벤트 생성 */
  async createEvent(reservation) {
    const event = this._buildEvent(reservation);
    return CMC_CONFIG.isGoogle() ? this._liveCreate(event) : this._mockCreate(event);
  },

  /** 이벤트 취소 (이벤트 ID 필요) */
  async deleteEvent(eventId) {
    return CMC_CONFIG.isGoogle() ? this._liveDelete(eventId) : this._mockDelete(eventId);
  },

  /** 이번주 이벤트 목록 */
  async listWeek() {
    const { monStr, sunStr } = CMC.weekRange();
    return CMC_CONFIG.isGoogle()
      ? this._liveList(monStr, sunStr)
      : this._mockList(monStr, sunStr);
  },

  /** 오늘 이벤트 목록 */
  async listToday() {
    const today = CMC.today();
    return CMC_CONFIG.isGoogle()
      ? this._liveList(today, today)
      : this._mockList(today, today);
  },

  /** 연결 테스트 */
  async ping() {
    if (!CMC_CONFIG.isGoogle()) return { ok: true, mode: 'mock', message: 'Mock 모드 — localStorage 사용 중' };
    return this._livePing();
  },

  /* ─────────────────────────────────────────────────────────
     이벤트 객체 빌더
  ───────────────────────────────────────────────────────── */

  _buildEvent(reservation) {
    const startDT = `${reservation.wishDate}T${reservation.wishTime || '09:00'}:00`;
    const endHour  = this._addMinutes(reservation.wishTime || '09:00', 120);
    const endDT    = `${reservation.wishDate}T${endHour}:00`;

    return {
      summary:     `[${reservation.program}] ${reservation.name} 건강검진`,
      description: [
        `예약번호: ${reservation.reservationNo}`,
        `프로그램: ${reservation.program}`,
        `수검자:  ${reservation.name} (${reservation.gender || ''})`,
        `연락처:  ${reservation.phone}`,
        `수면여부: ${reservation.sleep}`,
        reservation.optionalTests?.length ? `선택검사: ${reservation.optionalTests.join(', ')}` : '',
        reservation.company  ? `사업장: ${reservation.company}` : '',
        reservation.note     ? `특이사항: ${reservation.note}` : '',
      ].filter(Boolean).join('\n'),
      start: {
        dateTime: startDT,
        timeZone: CMC_CONFIG.google.timezone,
      },
      end: {
        dateTime: endDT,
        timeZone: CMC_CONFIG.google.timezone,
      },
      colorId:    '1',         // Google Calendar 색상 코드 (파란색)
      status:     'confirmed',
      reminders: {
        useDefault: false,
        overrides:  [
          { method: 'popup', minutes: 60 },    // 1시간 전 알림
          { method: 'email', minutes: 1440 },  // 하루 전 이메일
        ],
      },
      extendedProperties: {
        private: { reservationNo: reservation.reservationNo, cmcSystem: 'v1' },
      },
    };
  },

  _addMinutes(time, minutes) {
    const [h, m] = time.split(':').map(Number);
    const total  = h * 60 + m + minutes;
    return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
  },

  /* ─────────────────────────────────────────────────────────
     Mock 구현
  ───────────────────────────────────────────────────────── */

  _delay() { return new Promise(r => setTimeout(r, this._mockDelay)); },

  _getStored() {
    try { return JSON.parse(localStorage.getItem(this.STORAGE_KEY) || '[]'); }
    catch { return []; }
  },
  _saveStored(list) { localStorage.setItem(this.STORAGE_KEY, JSON.stringify(list)); },

  async _mockCreate(event) {
    await this._delay();
    const mockId  = `mock_evt_${Date.now()}`;
    const stored  = this._getStored();
    stored.push({ id: mockId, ...event, createdAt: new Date().toISOString() });
    this._saveStored(stored);
    console.log(`[CalendarService Mock] createEvent → ${mockId}`, event.summary);
    return { ok: true, eventId: mockId, event, source: 'local', htmlLink: '#mock-calendar-event' };
  },

  async _mockDelete(eventId) {
    await this._delay();
    const stored  = this._getStored().filter(e => e.id !== eventId);
    this._saveStored(stored);
    console.log(`[CalendarService Mock] deleteEvent → ${eventId}`);
    return { ok: true, eventId, source: 'local' };
  },

  async _mockList(from, to) {
    await this._delay();
    const all = this._getStored().filter(e => {
      const d = (e.start?.dateTime || '').slice(0, 10);
      return d >= from && d <= to;
    });
    console.log(`[CalendarService Mock] listEvents ${from}~${to} → ${all.length}건`);
    return { ok: true, events: all, source: 'local', count: all.length };
  },

  /* ─────────────────────────────────────────────────────────
     Live 구현 (Google Calendar API v3)
     [운영 전 구현 필요]
  ───────────────────────────────────────────────────────── */

  _calUrl(path = '') {
    const cid = encodeURIComponent(CMC_CONFIG.google.calendarId || 'primary');
    return `https://www.googleapis.com/calendar/v3/calendars/${cid}/events${path}`;
  },

  async _getToken() {
    throw new Error('Google OAuth 토큰 미설정 — CMC_CONFIG.google.clientId 확인 필요');
  },

  async _liveCreate(event) {
    const token = await this._getToken();
    const res   = await fetch(this._calUrl(), {
      method:  'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body:    JSON.stringify(event),
    });
    if (!res.ok) throw new Error(`Calendar API 오류: ${res.status}`);
    const body = await res.json();
    return { ok: true, eventId: body.id, event: body, source: 'google', htmlLink: body.htmlLink };
  },

  async _liveDelete(eventId) {
    const token = await this._getToken();
    const res   = await fetch(this._calUrl(`/${eventId}`), {
      method:  'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    return { ok: res.ok || res.status === 410, eventId, source: 'google' };
  },

  async _liveList(from, to) {
    const token   = await this._getToken();
    const timeMin = encodeURIComponent(`${from}T00:00:00+09:00`);
    const timeMax = encodeURIComponent(`${to}T23:59:59+09:00`);
    const res     = await fetch(`${this._calUrl()}?timeMin=${timeMin}&timeMax=${timeMax}&singleEvents=true&orderBy=startTime`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error(`Calendar list 오류: ${res.status}`);
    const body = await res.json();
    return { ok: true, events: body.items || [], source: 'google', count: body.items?.length || 0 };
  },

  async _livePing() {
    try {
      const token = await this._getToken();
      const res   = await fetch(this._calUrl(), { headers: { Authorization: `Bearer ${token}` } });
      return res.ok
        ? { ok: true, mode: 'live', message: 'Google Calendar 연결 성공' }
        : { ok: false, mode: 'live', message: `연결 실패: ${res.status}` };
    } catch (e) {
      return { ok: false, mode: 'live', message: e.message };
    }
  },
};
