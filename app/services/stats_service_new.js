/**
 * CMC Health Screening Platform v1.0
 * app/services/stats_service_new.js — KPI 산출 서비스
 */
'use strict';

const CMC_Stats = {

  /** 전체 상태별 카운트 */
  statusCounts() {
    const all    = CMC_DB.getAll();
    const counts = { total: all.length };
    CMC.STATUS_LIST.forEach(s => { counts[s] = all.filter(r => r.status === s).length; });
    return counts;
  },

  /** 오늘 예약 목록 (시간순) */
  todaySchedule() {
    const today = CMC.today();
    return CMC_DB.getAll()
      .filter(r => r.wishDate === today && r.status !== '예약취소')
      .sort((a, b) => (a.wishTime || '').localeCompare(b.wishTime || ''));
  },

  /** 최근 N건 (접수 최신순) */
  recent(n = 10) {
    return CMC_DB.getAll().slice(0, n);
  },

  /** 이번주 요일별 예약 수 (월~일, 취소 제외) */
  weeklyData() {
    const { monStr, sunStr } = CMC.weekRange();
    const all = CMC_DB.getAll().filter(r =>
      r.wishDate >= monStr && r.wishDate <= sunStr && r.status !== '예약취소'
    );
    const labels = ['월','화','수','목','금','토','일'];
    const counts = Array(7).fill(0);
    all.forEach(r => {
      const d   = new Date(r.wishDate);
      const dow = d.getDay();                    // 0=일,1=월...6=토
      const idx = dow === 0 ? 6 : dow - 1;      // 월=0 기준으로 변환
      counts[idx]++;
    });
    return { labels, counts, max: Math.max(...counts, 1) };
  },

  /** 프로그램별 예약 수 (취소 제외) */
  programBreakdown() {
    const active = CMC_DB.getAll().filter(r => r.status !== '예약취소');
    const total  = active.length || 1;
    return CMC.PROGRAMS.map(p => {
      const cnt = active.filter(r => r.program === p.id).length;
      return { ...p, count: cnt, pct: Math.round(cnt / total * 100) };
    }).sort((a, b) => b.count - a.count);
  },

  /** 오늘 KPI 요약 */
  todayKPI() {
    const today   = CMC.today();
    const all     = CMC_DB.getAll();
    const todayR  = all.filter(r => r.wishDate === today);
    return {
      todayTotal:    todayR.length,
      todayActive:   todayR.filter(r => r.status !== '예약취소').length,
      todaySleep:    todayR.filter(r => r.sleep === '수면').length,
      todayComplete: todayR.filter(r => r.status === '검진완료').length,
    };
  },
};
