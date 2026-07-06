/**
 * CMC Health Screening Platform — Sprint 2
 * app/services/dashboard_service_v2_new.js
 *
 * 운영 대시보드 전용 서비스
 * - KPI 계산 (6개 지표)
 * - 프로그램별 통계
 * - 검사실 대기현황 (시간 기반 시뮬레이션)
 * - 사업장 일정 (오늘/내일/이번주)
 * - 공지사항 CRUD
 * - AI 운영 추천 (규칙 기반)
 */
'use strict';

const CMC_DashboardV2 = {

  /* ── 검사실 정의 ──────────────────────────────────── */
  ROOMS: [
    { id: '접수',   icon: '📋', order: 1 },
    { id: '문진',   icon: '👨‍⚕️', order: 2 },
    { id: '채혈',   icon: '🩸', order: 3 },
    { id: '방사선', icon: '🔬', order: 4 },
    { id: '초음파', icon: '📡', order: 5 },
    { id: 'CT',     icon: '🖥️', order: 6 },
    { id: 'MRI',    icon: '🧲', order: 7 },
    { id: '내시경', icon: '🔭', order: 8 },
  ],

  /* 프로그램별 검사실 순서 + 각 검사실 소요시간(분) */
  PROGRAM_FLOW: {
    'BASIC':    { rooms: ['접수','문진','채혈','방사선'], mins: [5,15,10,15] },
    'SMART':    { rooms: ['접수','문진','채혈','방사선','초음파'], mins: [5,15,10,15,20] },
    'VIP':      { rooms: ['접수','문진','채혈','방사선','초음파','내시경'], mins: [5,15,10,15,20,30] },
    'PREMIUM':  { rooms: ['접수','문진','채혈','방사선','초음파','CT','MRI','내시경'], mins: [5,15,10,15,20,30,45,30] },
    'YOUNG':    { rooms: ['접수','문진','채혈','방사선'], mins: [5,15,10,15] },
    '온김에검진': { rooms: ['접수','채혈','방사선'], mins: [5,10,15] },
  },

  NOTICE_KEY: 'cmc_notices_v1',
  OPS_MOCK_KEY: 'cmc_ops_mock_v1',

  /* ── 기준 날짜 유틸 ────────────────────────────────── */
  _today()    { return new Date().toISOString().slice(0, 10); },
  _tomorrow() {
    const d = new Date(); d.setDate(d.getDate() + 1);
    return d.toISOString().slice(0, 10);
  },
  _weekEnd() {
    const d = new Date(); d.setDate(d.getDate() + 6);
    return d.toISOString().slice(0, 10);
  },

  /* ── 오늘 전체 데이터 조회 ─────────────────────────── */
  _todayAll() {
    const today = this._today();
    const all   = CMC_DB.getAll();
    let data    = all.filter(r => r.wishDate === today);
    /* 오늘 데이터가 없으면 운영 Mock 자동 주입 */
    if (data.length === 0) {
      this._injectOperationMock();
      data = CMC_DB.getAll().filter(r => r.wishDate === today);
    }
    return data;
  },

  /* ────────────────────────────────────────────────────
     1. KPI 계산 (6개)
  ──────────────────────────────────────────────────── */
  todayKPI() {
    const data = this._todayAll();
    const statusOf = s => data.filter(r => r.status === s).length;
    const inExam   = statusOf('검진중');
    const checkedIn = data.filter(r =>
      r.status === '검진중' || r.status === '검진완료'
    ).length;
    const waiting  = data.filter(r =>
      r.status === '예약확정' || r.status === '예약접수'
    ).length;

    return {
      todayTotal:  data.length,
      checkedIn,
      waiting,
      inProgress:  inExam,
      completed:   statusOf('검진완료'),
      cancelled:   statusOf('예약취소'),
    };
  },

  /* ────────────────────────────────────────────────────
     2. 프로그램별 현황
  ──────────────────────────────────────────────────── */
  programStats() {
    const data  = this._todayAll();
    const total = data.length || 1;
    const names = Object.keys(this.PROGRAM_FLOW);

    return names.map(name => {
      const count = data.filter(r => r.program === name).length;
      return {
        name,
        count,
        pct: Math.round(count / total * 100),
        color: this._programColor(name),
        icon:  this._programIcon(name),
      };
    }).sort((a, b) => b.count - a.count);
  },

  _programColor(name) {
    const map = {
      'BASIC': '#3b82f6', 'SMART': '#06b6d4', 'VIP': '#8b5cf6',
      'PREMIUM': '#f59e0b', 'YOUNG': '#10b981', '온김에검진': '#f97316',
    };
    return map[name] || '#64748b';
  },

  _programIcon(name) {
    const map = {
      'BASIC': '🔵', 'SMART': '🟢', 'VIP': '💜',
      'PREMIUM': '🌟', 'YOUNG': '🟡', '온김에검진': '🟠',
    };
    return map[name] || '⚪';
  },

  /* ────────────────────────────────────────────────────
     3. 검사실 대기현황 (시간 기반 추정)
  ──────────────────────────────────────────────────── */
  examRoomStatus() {
    const data    = this._todayAll();
    const inExam  = data.filter(r => r.status === '검진중');
    const counts  = {};
    this.ROOMS.forEach(r => { counts[r.id] = 0; });

    const nowMins = new Date().getHours() * 60 + new Date().getMinutes();

    inExam.forEach(person => {
      /* examRoom 컬럼이 직접 지정된 경우 우선 사용 */
      if (person.examRoom && counts[person.examRoom] !== undefined) {
        counts[person.examRoom]++;
        return;
      }
      /* 프로그램 기반 현재 검사실 추정 */
      const flow = this.PROGRAM_FLOW[person.program];
      if (!flow) { counts['접수']++; return; }

      /* 검진 시작 시각 추정: wishTime 기준 */
      const [h, m] = (person.wishTime || '09:00').split(':').map(Number);
      const startMins = h * 60 + m;
      const elapsed   = nowMins - startMins;   // 경과 분

      let cumulative = 0;
      let roomIdx = 0;
      for (let i = 0; i < flow.mins.length; i++) {
        cumulative += flow.mins[i];
        if (elapsed <= cumulative) { roomIdx = i; break; }
        if (i === flow.mins.length - 1) roomIdx = i;
      }
      const currentRoom = flow.rooms[roomIdx];
      if (currentRoom && counts[currentRoom] !== undefined) {
        counts[currentRoom]++;
      }
    });

    const max = Math.max(...Object.values(counts), 1);
    return this.ROOMS.map(r => ({
      ...r,
      waiting: counts[r.id] || 0,
      pct:     Math.round((counts[r.id] || 0) / max * 100),
    }));
  },

  /* ────────────────────────────────────────────────────
     4. 오늘 일정 (시간순)
  ──────────────────────────────────────────────────── */
  todaySchedule() {
    const data = this._todayAll();
    return data
      .filter(r => r.status !== '예약취소')
      .sort((a, b) => (a.wishTime > b.wishTime ? 1 : -1));
  },

  /* ────────────────────────────────────────────────────
     5. 사업장 일정
  ──────────────────────────────────────────────────── */
  companySchedule(range = 'today') {
    const all = CMC_DB.getAll();
    let from, to;

    if (range === 'today') {
      from = to = this._today();
    } else if (range === 'tomorrow') {
      from = to = this._tomorrow();
    } else {
      from = this._today();
      to   = this._weekEnd();
    }

    const rows = all.filter(r =>
      r.company && r.wishDate >= from && r.wishDate <= to &&
      r.status !== '예약취소'
    );

    /* 사업장별로 그룹 */
    const map = {};
    rows.forEach(r => {
      const key = r.wishDate + '|' + r.company;
      if (!map[key]) map[key] = { date: r.wishDate, company: r.company, count: 0 };
      map[key].count++;
    });

    return Object.values(map).sort((a, b) =>
      a.date !== b.date ? (a.date > b.date ? 1 : -1) : a.company.localeCompare(b.company)
    );
  },

  /* ────────────────────────────────────────────────────
     6. 공지사항 CRUD
  ──────────────────────────────────────────────────── */
  getNotices() {
    try { return JSON.parse(localStorage.getItem(this.NOTICE_KEY) || '[]'); }
    catch { return []; }
  },

  addNotice(text) {
    if (!text || !text.trim()) return;
    const notices = this.getNotices();
    notices.unshift({
      id:   Date.now(),
      text: text.trim(),
      date: new Date().toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' }),
    });
    if (notices.length > 20) notices.splice(20);
    localStorage.setItem(this.NOTICE_KEY, JSON.stringify(notices));
  },

  deleteNotice(id) {
    const notices = this.getNotices().filter(n => n.id !== id);
    localStorage.setItem(this.NOTICE_KEY, JSON.stringify(notices));
  },

  /* ────────────────────────────────────────────────────
     7. AI 운영 추천 (규칙 기반)
  ──────────────────────────────────────────────────── */
  getAIRecommendations() {
    const data   = this._todayAll();
    const kpi    = this.todayKPI();
    const rooms  = this.examRoomStatus();
    const hour   = new Date().getHours();
    const minute = new Date().getMinutes();
    const recs   = [];

    /* 대기 인원 경고 */
    if (kpi.waiting >= 5) {
      recs.push({ icon: '⚠️', text: `현재 대기 ${kpi.waiting}명 — 접수 속도를 높이거나 일정 조정이 필요합니다.`, priority: 'high' });
    }

    /* MRI 대기 */
    const mriRoom = rooms.find(r => r.id === 'MRI');
    if (mriRoom && mriRoom.waiting >= 2) {
      recs.push({ icon: '🧲', text: `MRI 대기 ${mriRoom.waiting}명 — 대기시간 40~60분 예상. 수검자 안내 권고.`, priority: 'high' });
    }

    /* 내시경 대기 */
    const endo = rooms.find(r => r.id === '내시경');
    if (endo && endo.waiting >= 2) {
      recs.push({ icon: '🔭', text: `내시경 대기 ${endo.waiting}명 — 수면 동의서 사전 확인 권고.`, priority: 'mid' });
    }

    /* 오전 집중 시간대 알림 */
    if (hour === 9 && minute < 30) {
      recs.push({ icon: '📈', text: '09:00~10:00 예약 집중 시간대 — 접수 인력 추가 배치 권고.', priority: 'mid' });
    }
    if (hour === 10 && minute < 30) {
      recs.push({ icon: '🩸', text: '10:30 이후 채혈 대기 증가 예상 — 채혈 인력 확인 권고.', priority: 'mid' });
    }

    /* 프리미엄 수검자 알림 */
    const premiumToday = data.filter(r => r.program === 'PREMIUM' || r.program === 'VIP');
    if (premiumToday.length > 0) {
      recs.push({ icon: '⭐', text: `VIP/PREMIUM 수검자 ${premiumToday.length}명 — 담당 간호사 배정 확인 권고.`, priority: 'mid' });
    }

    /* 미결제 알림 */
    const unpaid = data.filter(r => r.paymentStatus === '미결제' && r.status === '검진완료');
    if (unpaid.length > 0) {
      recs.push({ icon: '💳', text: `검진 완료 후 미결제 ${unpaid.length}건 — 결제 안내가 필요합니다.`, priority: 'high' });
    }

    /* 오후 결과발송 알림 */
    if (hour >= 15) {
      const noResult = data.filter(r => r.status === '검진완료' && (!r.resultStatus || r.resultStatus === '미발송'));
      if (noResult.length > 0) {
        recs.push({ icon: '📬', text: `결과 미발송 ${noResult.length}건 — 오늘 중 결과 발송 처리 권고.`, priority: 'mid' });
      }
    }

    /* 전반적으로 순조로운 경우 */
    if (recs.length === 0) {
      recs.push({ icon: '✅', text: '현재 운영 상황 양호 — 특별한 조치가 필요하지 않습니다.', priority: 'low' });
      if (kpi.completed > 0) {
        recs.push({ icon: '🎉', text: `오늘 검진 완료 ${kpi.completed}명 — 수고하셨습니다.`, priority: 'low' });
      }
    }

    return recs.slice(0, 5);   // 최대 5개
  },

  /* ────────────────────────────────────────────────────
     운영 Mock 데이터 자동 주입 (오늘 데이터 없을 때)
  ──────────────────────────────────────────────────── */
  _injectOperationMock() {
    const today = this._today();
    const todayCompact = today.replace(/-/g, '');
    const now   = new Date();
    const nowStr = now.toISOString().replace('T', ' ').slice(0, 19);

    const templates = [
      { name:'박도윤', birth:'1975-04-12', phone:'010-1111-2222', gender:'남', program:'VIP',      wishTime:'08:30', sleep:'미선택', status:'검진완료',  company:'천안시청',    examRoom:'MRI',  paymentStatus:'결제완료', resultStatus:'발송완료', route:'협약' },
      { name:'김지수', birth:'1988-09-23', phone:'010-2222-3333', gender:'여', program:'PREMIUM',  wishTime:'08:30', sleep:'수면선택', status:'검진중',  company:'',           examRoom:'내시경', paymentStatus:'미결제',  resultStatus:'미발송', route:'온라인' },
      { name:'이준혁', birth:'1992-03-08', phone:'010-3333-4444', gender:'남', program:'BASIC',    wishTime:'09:00', sleep:'미선택', status:'검진중',   company:'한국전력',   examRoom:'채혈',  paymentStatus:'미결제',  resultStatus:'미발송', route:'협약' },
      { name:'최민아', birth:'1985-07-15', phone:'010-4444-5555', gender:'여', program:'SMART',    wishTime:'09:00', sleep:'미선택', status:'검진중',   company:'',           examRoom:'방사선', paymentStatus:'미결제',  resultStatus:'미발송', route:'전화' },
      { name:'정수현', birth:'1970-11-30', phone:'010-5555-6666', gender:'남', program:'VIP',      wishTime:'09:00', sleep:'미선택', status:'예약확정', company:'충남도청',   examRoom:'',     paymentStatus:'미결제',  resultStatus:'미발송', route:'협약' },
      { name:'강은지', birth:'1995-02-20', phone:'010-6666-7777', gender:'여', program:'YOUNG',    wishTime:'09:30', sleep:'미선택', status:'예약확정', company:'',           examRoom:'',     paymentStatus:'미결제',  resultStatus:'미발송', route:'온라인' },
      { name:'조민서', birth:'1968-06-14', phone:'010-7777-8888', gender:'여', program:'BASIC',    wishTime:'09:30', sleep:'수면선택', status:'예약확정', company:'천안산업',  examRoom:'',     paymentStatus:'미결제',  resultStatus:'미발송', route:'협약' },
      { name:'임준혁', birth:'1980-12-05', phone:'010-8888-9999', gender:'남', program:'PREMIUM',  wishTime:'10:00', sleep:'미선택', status:'예약확정', company:'',           examRoom:'',     paymentStatus:'미결제',  resultStatus:'미발송', route:'온라인' },
      { name:'한소라', birth:'1978-08-18', phone:'010-9999-0000', gender:'여', program:'SMART',    wishTime:'10:00', sleep:'미선택', status:'예약접수', company:'아산병원',   examRoom:'',     paymentStatus:'미결제',  resultStatus:'미발송', route:'전화' },
      { name:'윤태양', birth:'2000-01-01', phone:'010-1234-5678', gender:'남', program:'YOUNG',    wishTime:'10:30', sleep:'미선택', status:'예약접수', company:'',           examRoom:'',     paymentStatus:'미결제',  resultStatus:'미발송', route:'온라인' },
      { name:'서지원', birth:'1983-05-25', phone:'010-2345-6789', gender:'여', program:'VIP',      wishTime:'10:30', sleep:'미선택', status:'예약접수', company:'삼성전자',   examRoom:'',     paymentStatus:'미결제',  resultStatus:'미발송', route:'협약' },
      { name:'오병철', birth:'1960-03-17', phone:'010-3456-7890', gender:'남', program:'온김에검진', wishTime:'11:00', sleep:'미선택', status:'예약접수', company:'',         examRoom:'',     paymentStatus:'미결제',  resultStatus:'미발송', route:'방문' },
    ];

    templates.forEach((t, i) => {
      const no = `${todayCompact}-${String(i + 1).padStart(4, '0')}`;
      const base = {
        reservationNo: no,
        createdAt:     today + ' 07:00:00',
        updatedAt:     nowStr,
        wishDate:      today,
        optionalTests: [],
        note:          '',
        smsSent:       'Y',
        confirmedAt:   t.status !== '예약접수' ? today + ' 08:00:00' : '',
        scheduledTime: t.wishTime,
        checkinTime:   t.status === '검진중' || t.status === '검진완료' ? today + ' ' + t.wishTime + ':00' : '',
        examStart:     t.status === '검진중' || t.status === '검진완료' ? today + ' ' + t.wishTime + ':05' : '',
        examEnd:       t.status === '검진완료' ? today + ' ' + t.wishTime.split(':')[0] + ':55:00' : '',
        nurse:         ['박간호사','김간호사','이간호사'][i % 3],
        doctor:        ['이의사','최의사','박의사'][i % 3],
        estimatedCost: ['120000','250000','450000','650000','150000','120000'][i % 6],
        revisit:       '해당없음',
        manager:       '김담당',
      };
      CMC_DB.add({ ...t, ...base });
    });
  },
};
