/**
 * CMC Health Screening Platform v1.0
 * app/services/db_service_new.js — 데이터 CRUD 레이어
 *
 * [보안 주의] v1.0 시제품: localStorage 임시 사용.
 * 실제 운영 시 REST API + 서버 DB로 전환 필요.
 */
'use strict';

const CMC_DB = {

  getAll() {
    try { return JSON.parse(localStorage.getItem(CMC.STORAGE_KEY) || '[]'); }
    catch { return []; }
  },

  save(list) {
    localStorage.setItem(CMC.STORAGE_KEY, JSON.stringify(list));
  },

  add(reservation) {
    const list = this.getAll();
    list.unshift(reservation);
    this.save(list);
    return reservation;
  },

  update(reservationNo, patch) {
    const list = this.getAll();
    const idx  = list.findIndex(r => r.reservationNo === reservationNo);
    if (idx === -1) return null;
    list[idx] = { ...list[idx], ...patch, updatedAt: new Date().toISOString() };
    this.save(list);
    return list[idx];
  },

  findByNo(no) {
    return this.getAll().find(r => r.reservationNo === no) || null;
  },

  generateNo() {
    const ymd  = CMC.today().replace(/-/g, '');
    const list = this.getAll();
    const cnt  = list.filter(r => r.reservationNo?.startsWith(ymd)).length;
    return `${ymd}-${String(cnt + 1).padStart(4, '0')}`;
  },

  /** v1.0 샘플 데이터가 없을 때 자동 초기화 */
  initSampleIfEmpty() {
    if (this.getAll().length > 0) return;
    if (typeof CMC_generateSampleData === 'function') {
      this.save(CMC_generateSampleData());
    }
  },
};
