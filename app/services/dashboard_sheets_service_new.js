/**
 * CMC Health Screening Platform
 * app/services/dashboard_sheets_service_new.js
 *
 * 대시보드 전용 Sheets 데이터 서비스
 *
 * 동작 모드:
 *   Live  : CMC_CONFIG.appsScript.webAppUrl 설정 시
 *            -> GAS summary + list 엔드포인트 호출
 *   Local : URL 미설정 또는 GAS 오류 시
 *            -> 기존 CMC_Stats(localStorage) 폴백 (무중단)
 *
 * GAS 호출 (3-call 배치):
 *   A. GET ?action=summary               -> KPI byStatus (오늘 기준)
 *   B. GET ?action=list&dateFrom=월&dateTo=일  -> 이번주 일정
 *   C. GET ?action=list                  -> 전체 목록 (HotFix#1: 날짜 필터 제거)
 *
 * 의존성: config_v2_new.js(CMC_CONFIG), programs_data_new.js(CMC), stats_service_new.js(CMC_Stats)
 */
'use strict';

const CMC_DashboardSheets = {

  /* 내부 유틸 */

  _url() {
    return (typeof CMC_CONFIG !== 'undefined' &&
            CMC_CONFIG.appsScript &&
            CMC_CONFIG.appsScript.webAppUrl) || '';
  },

  isLive() { return !!this._url(); },

  _today() { return new Date().toISOString().split('T')[0]; },

  _weekRange() {
    const now = new Date();
    const dow = now.getDay();
    const mon = new Date(now);
    mon.setDate(now.getDate() - (dow === 0 ? 6 : dow - 1));
    const sun = new Date(mon);
    sun.setDate(mon.getDate() + 6);
    return {
      monStr: mon.toISOString().split('T')[0],
      sunStr: sun.toISOString().split('T')[0],
    };
  },

  async _get(params) {
    const url = this._url();
    const qs  = new URLSearchParams(params).toString();
    const res = await fetch(qs ? url + '?' + qs : url, { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const json = await res.json();
    if (!json.ok) throw new Error(json.error || 'GAS 응답 오류');
    return json;
  },

  /* GAS 호출 */

  /** A. 오늘 요약 (KPI byStatus) */
  async fetchSummary() {
    const json = await this._get({ action: 'summary' });
    return json.data;
  },

  /** B. 이번주 목록 (오늘 일정 + 주간 차트) */
  async fetchWeekList() {
    const { monStr, sunStr } = this._weekRange();
    const json = await this._get({ action: 'list', dateFrom: monStr, dateTo: sunStr });
    return json.data || [];
  },

  /** C. 전체 목록 (HotFix#1: 날짜 필터 제거 -> 모든 예약 표시)
   *  이전: dateFrom=30일전&dateTo=오늘 -> wishDate 밖의 예약이 누락됨
   *  수정: 필터 없이 전체 조회 -> 미래/과거 예약도 KPI에 포함
   */
  async fetchRecentList() {
    const json = await this._get({ action: 'list' });
    return json.data || [];
  },

  /**
   * 전체 배치 로드.
   * 성공: { summary, weekList, recentList, source:'sheets' }
   * 실패: { source:'local', error } -> 호출자가 localStorage 폴백 처리.
   */
  async loadAll() {
    if (!this.isLive()) return { source: 'local' };
    try {
      const [summary, weekList, recentList] = await Promise.all([
        this.fetchSummary(),
        this.fetchWeekList(),
        this.fetchRecentList(),
      ]);
      console.log('[Dashboard Sheets] Sheets 연동 성공 · ' +
        '오늘 ' + summary.total + '건 / 이번주 ' + weekList.length + '건 / 전체 ' + recentList.length + '건');
      return { summary, weekList, recentList, source: 'sheets' };
    } catch (err) {
      console.warn('[Dashboard Sheets] GAS 연결 실패 -> localStorage 폴백:', err.message);
      return { source: 'local', error: err.message };
    }
  },

  /* 데이터 변환: Sheets 데이터 -> 기존 렌더 함수 호환 형태 */

  /**
   * KPI 카드용 status 카운트
   * HotFix#1: allList(전체 예약 배열)가 있으면 누적 집계 사용.
   *           summary만 있으면 오늘 데이터만 집계 -> 미래 예약이 0으로 보이는 문제 방지.
   */
  statusCounts(summary, allList) {
    const statuses = typeof CMC !== 'undefined' ? CMC.STATUS_LIST
      : ['예약접수', '예약확정', '검진완료', '일정변경', '예약취소'];
    if (allList) {
      const counts = { total: allList.length };
      statuses.forEach(function(s) { counts[s] = allList.filter(function(r) { return r.status === s; }).length; });
      return counts;
    }
    if (!summary) return CMC_Stats.statusCounts();
    const counts = { total: summary.total || 0 };
    statuses.forEach(function(s) { counts[s] = (summary.byStatus && summary.byStatus[s]) || 0; });
    return counts;
  },

  /** 오늘 예약 KPI 요약 */
  todayKPI(summary, weekList) {
    if (!summary) return CMC_Stats.todayKPI();
    const today     = this._today();
    const todayRows = (weekList || []).filter(function(r) { return r.wishDate === today; });
    const byStatus  = summary.byStatus || {};
    const cancelled = byStatus['예약취소'] || 0;
    return {
      todayTotal:    summary.total || 0,
      todayActive:   Math.max(0, (summary.total || 0) - cancelled),
      todaySleep:    todayRows.filter(function(r) { return r.sleep === '수면' || r.sleep === '수면선택'; }).length,
      todayComplete: byStatus['검진완료'] || 0,
    };
  },

  /** 오늘 일정 목록 (시간순, 취소 제외) */
  todaySchedule(weekList) {
    if (!weekList) return CMC_Stats.todaySchedule();
    const today = this._today();
    return weekList
      .filter(function(r) { return r.wishDate === today && r.status !== '예약취소'; })
      .sort(function(a, b) { return (a.wishTime || '').localeCompare(b.wishTime || ''); });
  },

  /** 이번주 요일별 예약 수 (월~일, 취소 제외) */
  weeklyData(weekList) {
    if (!weekList) return CMC_Stats.weeklyData();
    const labels = ['월', '화', '수', '목', '금', '토', '일'];
    const counts = [0, 0, 0, 0, 0, 0, 0];
    weekList
      .filter(function(r) { return r.status !== '예약취소'; })
      .forEach(function(r) {
        const dow = new Date(r.wishDate).getDay();
        counts[dow === 0 ? 6 : dow - 1]++;
      });
    return { labels: labels, counts: counts, max: Math.max.apply(null, counts.concat([1])) };
  },

  /** 최근 N건 (접수 최신순) */
  recentN(recentList, n) {
    if (!recentList) return CMC_Stats.recent(n);
    return recentList.slice(0, n);
  },

  /** 프로그램별 예약 수 (취소 제외) */
  programBreakdown(recentList) {
    if (!recentList) return CMC_Stats.programBreakdown();
    const active  = recentList.filter(function(r) { return r.status !== '예약취소'; });
    const total   = active.length || 1;
    const programs = (typeof CMC !== 'undefined') ? CMC.PROGRAMS : [];
    return programs.map(function(p) {
      const cnt = active.filter(function(r) { return r.program === p.id; }).length;
      return Object.assign({}, p, { count: cnt, pct: Math.round(cnt / total * 100) });
    }).sort(function(a, b) { return b.count - a.count; });
  },
};
