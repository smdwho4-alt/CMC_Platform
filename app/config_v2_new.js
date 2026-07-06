/**
 * CMC Health Screening Platform v1.0 — Phase 4
 * app/config_v2_new.js — Google Workspace 통합 설정 v2
 *
 * Phase 3 config_new.js를 확장.
 * Apps Script Web App URL 항목 추가.
 * 기존 config_new.js는 보존.
 *
 * [보안] API 키, Web App URL 등 민감 정보는 코드에 직접 입력 금지.
 *        운영 환경에서는 서버사이드 환경변수 또는 Google Secret Manager 사용.
 */
'use strict';

const CMC_CONFIG = {

  /* ── 데이터 소스 모드 ─────────────────────────────────
   *  'local'        : localStorage 기반 (시제품 기본값)
   *  'google'       : Apps Script Web App 경유 (운영)
   * ──────────────────────────────────────────────────── */
  dataSource: 'google',

  /* ── Apps Script Web App ────────────────────────────
   *  Phase 4 핵심: 클라이언트 → Apps Script → Google Sheets
   *  배포 후 발급되는 URL을 아래에 입력.
   *  형식: https://script.google.com/macros/s/[SCRIPT_ID]/exec
   * ──────────────────────────────────────────────────── */
  appsScript: {
    webAppUrl:  'https://script.google.com/macros/s/AKfycbzHYWqERR8_hHxzIgCNwvrU8NLtZqu9RVuxezTBWtUKcTleAgcqRhYPX5rnHAM7uCGjng/exec', // Apps Script 배포 후 발급 URL (필수)
    sheetName:  '예약현황',  // Google Sheets 시트명
    timezone:   'Asia/Seoul',
  },

  /* ── Google Workspace 설정 (직접 API 방식 — Phase 3 호환) ── */
  google: {
    /* Google Sheets (직접 API — Apps Script 방식 사용 시 불필요) */
    sheetsId:      '',
    sheetsRange:   '예약현황',
    sheetsVersion: 'v4',

    /* Google Calendar */
    calendarId:    '',
    calendarColor: '#1a4f8a',

    /* Gmail */
    senderEmail:   '',
    senderName:    '천안의료원 건강검진센터',

    /* 공통 */
    timezone:      'Asia/Seoul',
    locale:        'ko-KR',

    /* OAuth — 클라이언트사이드 사용 시 보안 위험 존재.
     * Apps Script 방식에서는 이 항목이 필요 없음. */
    clientId:      '',
    apiKey:        '',
    scopes: [
      'https://www.googleapis.com/auth/spreadsheets',
      'https://www.googleapis.com/auth/calendar',
      'https://www.googleapis.com/auth/gmail.send',
    ],
  },

  /* ── 알림 설정 ─────────────────────────────────────── */
  notifications: {
    emailOnReceive:    true,
    emailOnConfirm:    true,
    emailOnCancel:     true,
    calendarOnConfirm: true,
    calendarOnCancel:  true,
  },

  /* ── 병원 기본 정보 ──────────────────────────────────  */
  hospital: {
    name:    '천안의료원 건강검진센터',
    tel:     '041-570-7777',
    address: '충청남도 천안시',
    url:     '',
  },

  /* ── 설정 저장키 ─────────────────────────────────────── */
  configStorageKey: 'cmc_config_v2',

  /* ── 런타임 메서드 ───────────────────────────────────── */

  load() {
    try {
      const saved = JSON.parse(localStorage.getItem(this.configStorageKey) || '{}');
      if (saved.dataSource) this.dataSource = saved.dataSource;
      if (saved.appsScript) Object.assign(this.appsScript, saved.appsScript);
      if (saved.google)     Object.assign(this.google, saved.google);
    } catch { /* 무시 */ }
    return this;
  },

  persist() {
    localStorage.setItem(this.configStorageKey, JSON.stringify({
      dataSource: this.dataSource,
      appsScript: {
        webAppUrl: this.appsScript.webAppUrl,
        sheetName: this.appsScript.sheetName,
      },
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
    this.dataSource = mode;
    this.persist();
  },

  isGoogle()       { return this.dataSource === 'google'; },
  isLocal()      