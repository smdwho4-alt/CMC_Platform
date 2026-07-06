/**
 * CMC Health Screening Platform v1.0 — Phase 3
 * app/config_new.js — Google Workspace 통합 설정
 *
 * [운영 전 필수] 아래 항목을 실제 값으로 교체 후 사용.
 * API 키 등 민감 정보는 절대 코드에 직접 입력하지 말고
 * 서버 환경변수 또는 Google Secret Manager 사용 권장.
 */
'use strict';

const CMC_CONFIG = {

  /* ── 데이터 소스 모드 ─────────────────────────────────
   *  'local'   : localStorage 기반 (시제품 기본값)
   *  'google'  : Google Workspace API 연동 (운영)
   * ──────────────────────────────────────────────────── */
  dataSource: 'local',

  /* ── Google Workspace 설정 ───────────────────────────
   *  실제 운영 시 아래 값을 Google Cloud Console에서 발급받아 입력.
   *  참고: README_platform_new.md > Google Workspace 연동 절차
   * ──────────────────────────────────────────────────── */
  google: {
    /* Google Sheets */
    sheetsId:      '',          // 예: '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms'
    sheetsRange:   'Sheet1',    // 시트명 (기본: Sheet1)
    sheetsVersion: 'v4',

    /* Google Calendar */
    calendarId:    '',          // 예: 'primary' 또는 'abc123@group.calendar.google.com'
    calendarColor: '#1a4f8a',   // 캘린더 이벤트 색상

    /* Gmail */
    senderEmail:   '',          // 발신 계정 예: 'checkup@cheonanmc.or.kr'
    senderName:    '천안의료원 건강검진센터',

    /* 공통 */
    timezone:      'Asia/Seoul',
    locale:        'ko-KR',

    /* OAuth 2.0 / Service Account
     * [보안] 실제 토큰·키는 여기에 입력하지 않는다.
     * 서버사이드(Node.js/Apps Script) 처리 또는
     * Google Identity Services(GIS) 팝업 인증 사용. */
    clientId:      '',          // Google Cloud Console OAuth 클라이언트 ID
    apiKey:        '',          // Google API Key (Sheets read-only 한정 허용)
    scopes: [
      'https://www.googleapis.com/auth/spreadsheets',
      'https://www.googleapis.com/auth/calendar',
      'https://www.googleapis.com/auth/gmail.send',
    ],
  },

  /* ── 알림 설정 ─────────────────────────────────────── */
  notifications: {
    emailOnReceive:  true,   // 예약접수 시 수검자 이메일 발송
    emailOnConfirm:  true,   // 예약확정 시 수검자 이메일 발송
    emailOnCancel:   true,   // 예약취소 시 수검자 이메일 발송
    calendarOnConfirm: true, // 예약확정 시 캘린더 이벤트 생성
    calendarOnCancel:  true, // 예약취소 시 캘린더 이벤트 삭제
  },

  /* ── 병원 기본 정보 ──────────────────────────────────  */
  hospital: {
    name:    '천안의료원 건강검진센터',
    tel:     '041-570-7777',
    address: '충청남도 천안시',
    url:     '',              // 공식 홈페이지 URL
  },

  /* ── 설정 저장키 (localStorage) ─────────────────────── */
  configStorageKey: 'cmc_config_v1',

  /* 런타임 설정 로드/저장 */
  load() {
    try {
      const saved = JSON.parse(localStorage.getItem(this.configStorageKey) || '{}');
      if (saved.dataSource) this.dataSource = saved.dataSource;
      if (saved.google)     Object.assign(this.google, saved.google);
    } catch { /* 무시 */ }
    return this;
  },

  persist() {
    localStorage.setItem(this.configStorageKey, JSON.stringify({
      dataSource: this.dataSource,
      google: {
        sheetsId:    this.google.sheetsId,
        calendarId:  this.google.calendarId,
        senderEmail: this.google.senderEmail,
        clientId:    this.google.clientId,
        apiKey:      this.google.apiKey,
      },
    }));
  },

  setDataSource(mode) {
    this.dataSource = mode;   // 'local' | 'google'
    this.persist();
  },

  isGoogle() { return this.dataSource === 'google'; },
  isLocal()  { return this.dataSource === 'local'; },
};
