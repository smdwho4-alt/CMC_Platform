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

  /* 데이터 소스 모드
   *  'local'  : localStorage 기반 (시제품)
   *  'google' : Apps Script Web App 경유 (운영)
   */
  dataSource: 'google',

  /* Apps Script Web App */
  appsScript: {
    webAppUrl:  'https://script.google.com/macros/s/AKfycbzHYWqERR8_hHxzIgCNwvrU8NLtZqu9RVuxezTBWtUKcTleAgcqRhYPX5rnHAM7uCGjng/exec',
    sheetName:  '예약현황',
    timezone:   'Asia/Seoul',
  },

  /* Google Workspace 설정 */
  google: {
    sheetsId:      '',
    sheetsRange:   '예약현황',
    sheetsVersion: 'v4',
    calendarId:    '',
    calendarColor: '#1a4f8a',
    senderEmail:   '',
    senderName:    'CMC Health Screening',
    timezone:      'Asia/Seoul',
    locale:        'ko-KR',
    clientId:      '',
    apiKey:        '',
    scopes: [
      'https://www.googleapis.com/auth/spreadsheets',
      'https://www.googleapis.com/auth/calendar',
      'https://www.googleapis.com/auth/gmail.send',
    ],
  },

  /* 알림 설정 */
  notifications: {
    emailOnReceive:    true,
    emailOnConfirm:    true,
    emailOnCancel:     true,
    calendarOnConfirm: true,
    calendarOnCancel:  true,
  },

  /* 병원 기본 정보 */
  hospital: {
    name:    '천안의료원 건강검진센터',
    tel:     '041-570-7333',
    address: '충청남도 천안시',
    url:     '',
  },

  configStorageKey: 'cmc_config_v2',

  load() {
    try {
      const saved = JSON.parse(localStorage.getItem(this.configStorageKey) || '{}');
      if (saved.dataSource) this.dataSource = saved.dataSource;
      if (saved.appsScript) Object.assign(this.appsScript, saved.appsScript);
      if (saved.google)     Object.assign(this.google, saved.google);
    } catch (e) {}
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

  setDataSource(mode) { this.dataSource = mode; this.persist(); },
  isGoogle()          { return this.dataSource === 'google'; },
  isLocal()           { return this.dataSource === 'local'; },
  hasWebAppUrl()      { return !!this.appsScript.webAppUrl; },
};
