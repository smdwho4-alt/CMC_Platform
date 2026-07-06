/**
 * CMC Health Screening Platform v1.0
 * app/data/programs_data_new.js — 상수 데이터 정의
 */
'use strict';

const CMC = {
  STORAGE_KEY: 'cheonan_reservations_v1',   // v1.0 데이터 호환 유지

  PROGRAMS: [
    { id: 'BASIC',   name: 'BASIC',   color: '#1565c0', bg: '#e3f2fd', price: '120,000원~', desc: '기본 건강검진 패키지',        icon: '🔵' },
    { id: 'SMART',   name: 'SMART',   color: '#2e7d32', bg: '#e8f5e9', price: '180,000원~', desc: '중급 종합검진 패키지',        icon: '🟢' },
    { id: 'VIP',     name: 'VIP',     color: '#e65100', bg: '#fff3e0', price: '280,000원~', desc: '3.0T MRI 포함 고급 패키지',  icon: '🟠' },
    { id: 'PREMIUM', name: 'PREMIUM', color: '#880e4f', bg: '#fce4ec', price: '450,000원~', desc: '프리미엄 전체 정밀 패키지',  icon: '🔴' },
    { id: 'YOUNG',   name: 'YOUNG',   color: '#6a1b9a', bg: '#f3e5f5', price: '150,000원~', desc: '20~30대 맞춤형 패키지',      icon: '🟣' },
    { id: '온김에검진', name: '온김에검진', color: '#00695c', bg: '#e0f2f1', price: '80,000원~', desc: '빠르고 간편한 핵심 검진', icon: '🟤' },
  ],

  STATUS: {
    '예약접수': { cls: 'status-접수', icon: '📋', color: '#1565c0', bg: '#e3f2fd' },
    '예약확정': { cls: 'status-확정', icon: '✅', color: '#2e7d32', bg: '#e8f5e9' },
    '검진완료': { cls: 'status-완료', icon: '🏥', color: '#4527a0', bg: '#ede7f6' },
    '일정변경': { cls: 'status-변경', icon: '🔄', color: '#e65100', bg: '#fff3e0' },
    '예약취소': { cls: 'status-취소', icon: '❌', color: '#c62828', bg: '#ffebee' },
  },

  STATUS_LIST: ['예약접수', '예약확정', '검진완료', '일정변경', '예약취소'],

  TIME_SLOTS: ['08:00','08:30','09:00','09:30','10:00','10:30','11:00','13:00','13:30','14:00'],

  OPTIONAL_TESTS: [
    '갑상선 초음파','복부 초음파','심장 초음파','경동맥 초음파',
    '뇌 MRI','척추 MRI','관절 MRI',
    '저선량 흉부 CT','복부 CT',
    '대장내시경(수면)','위내시경(수면)',
    '골밀도 검사','체성분 분석','안저 검사(망막)',
    '남성 전립선 초음파','여성 유방 초음파','부인과 초음파',
    'HPV 검사','심전도(정밀)','폐기능 검사',
  ],

  WEEK_DAYS: ['일','월','화','수','목','금','토'],

  /* 날짜 유틸 */
  today()  { return new Date().toISOString().split('T')[0]; },
  todayKR() {
    const d = new Date();
    return `${d.getFullYear()}년 ${d.getMonth()+1}월 ${d.getDate()}일 (${this.WEEK_DAYS[d.getDay()]})`;
  },
  weekRange() {
    const now = new Date();
    const day = now.getDay();
    const mon = new Date(now); mon.setDate(now.getDate() - (day === 0 ? 6 : day - 1));
    const sun = new Date(mon); sun.setDate(mon.getDate() + 6);
    return { mon, sun,
      monStr: mon.toISOString().split('T')[0],
      sunStr: sun.toISOString().split('T')[0],
    };
  },
  formatDate(iso) {
    if (!iso) return '-';
    const d = new Date(iso);
    return `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getDate()).padStart(2,'0')}`;
  },
  formatDateTime(iso) {
    if (!iso) return '-';
    const d = new Date(iso);
    return `${this.formatDate(iso)} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
  },
  maskPhone(p) { return String(p||'').replace(/(\d{3})-?(\d{3,4})-?(\d{4})/, '$1-****-$3'); },
  esc(s)       { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); },
};
