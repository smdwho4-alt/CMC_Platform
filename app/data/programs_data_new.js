/**
 * CMC Health Screening Platform v1.0
 * app/data/programs_data_new.js — 상수 데이터 정의
 *
 * 프로그램 상세 데이터는 app/data/programs_config_new.json 에서 JSON으로 관리.
 * [가격 기준: 2025.12.24 리플렛]
 *   BASIC   : 남 44만원 / 여 49만원
 *   SMART   : 남 77만원 / 여 82만원
 *   VIP     : 남 110만원 / 여 120만원
 *   PREMIUM : 남 130만원 / 여 140만원
 */
'use strict';

const CMC = {
  STORAGE_KEY: 'cheonan_reservations_v1',

  /* 문의전화 (리플렛 기준) */
  TEL: '041-570-7333',

  /* 예약 안내 문구 */
  RESERVATION_GUIDE: {
    main:    '전화 또는 내원 뿐 아니라 본원 홈페이지에서도 온라인 예약이 가능합니다.',
    confirm: '예약 확정은 해피콜(전화 확인) 이후에 가능합니다.',
    notes: [
      '조직검사 및 대장용종절제술 시행 시 비용 추가',
      '위내시경 수면비 별도(5만원) 비용 발생',
      '공단위암검진 동시 시행 시 비용청구 없음',
    ],
  },

  PROGRAMS: [
    {
      id: 'BASIC', name: 'BASIC', color: '#1565c0', bg: '#e3f2fd', icon: '🔵',
      price:        '44만원(남) / 49만원(여)',
      priceMale:    '440,000원',
      priceFemale:  '490,000원',
      desc:         '기본 종합검진 — 필수 건강진단 항목 구성. 위내시경(일반) 포함.',
      selectRule:   'A에서 2가지, B에서 2가지 선택',
    },
    {
      id: 'SMART', name: 'SMART', color: '#2e7d32', bg: '#e8f5e9', icon: '🟢',
      price:        '77만원(남) / 82만원(여)',
      priceMale:    '770,000원',
      priceFemale:  '820,000원',
      desc:         '기본검사 + 체지방분석. 초음파·CT·특수혈액검사 추가 선택.',
      selectRule:   'A에서 5가지, B에서 2가지 선택',
    },
    {
      id: 'VIP', name: 'VIP', color: '#e65100', bg: '#fff3e0', icon: '🟠',
      price:        '110만원(남) / 120만원(여)',
      priceMale:    '1,100,000원',
      priceFemale:  '1,200,000원',
      desc:         '기본검사 + 초음파·CT·MRI 추가 선택 가능 프로그램.',
      selectRule:   'A에서 5가지, B에서 1가지, C에서 3가지 선택',
    },
    {
      id: 'PREMIUM', name: 'PREMIUM', color: '#880e4f', bg: '#fce4ec', icon: '🔴',
      price:        '130만원(남) / 140만원(여)',
      priceMale:    '1,300,000원',
      priceFemale:  '1,400,000원',
      desc:         '최상위 프리미엄 검진. 대학병원급 3.0T MRI 포함. A/B/C 전 그룹 선택.',
      selectRule:   'A에서 5가지, B에서 2가지, C에서 3가지 선택',
    },
    {
      id: 'YOUNG', name: 'YOUNG', color: '#6a1b9a', bg: '#f3e5f5', icon: '🟣',
      price:        '150,000원~',
      priceMale:    '150,000원~',
      priceFemale:  '150,000원~',
      desc:         '20~30대 맞춤형 패키지',
      selectRule:   '',
    },
    {
      id: '온김에검진', name: '온김에검진', color: '#00695c', bg: '#e0f2f1', icon: '🟤',
      price:        '80,000원~',
      priceMale:    '80,000원~',
      priceFemale:  '80,000원~',
      desc:         '빠르고 간편한 핵심 검진',
      selectRule:   '',
    },
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

  today()  { return new Date().toISOString().split('T')[0]; },
  todayKR() {
    const d = new Date();
    return d.getFullYear() + '년 ' + (d.getMonth()+1) + '월 ' + d.getDate() + '일 (' + this.WEEK_DAYS[d.getDay()] + ')';
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
    return d.getFullYear() + '.' + String(d.getMonth()+1).padStart(2,'0') + '.' + String(d.getDate()).padStart(2,'0');
  },
  formatDateTime(iso) {
    if (!iso) return '-';
    const d = new Date(iso);
    return this.formatDate(iso) + ' ' + String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0');
  },
  maskPhone(p) { return String(p||'').replace(/(\d{3})-?(\d{3,4})-?(\d{4})/, '$1-****-$3'); },
  esc(s)       { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); },
};
