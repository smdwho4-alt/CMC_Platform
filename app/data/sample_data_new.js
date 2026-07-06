/**
 * CMC Health Screening Platform v1.0
 * app/data/sample_data_new.js — 샘플 데이터 생성기
 */
'use strict';

function CMC_generateSampleData() {
  const names    = ['김민준','이서연','박도윤','최지우','정예린','강현우','윤서아','임준혁','오하은','신태양','문지호','한소율','조민서','백지훈','송아름'];
  const companies= ['(주)천안제조','충청남도청','천안시청','한국전력 천안지사','삼성 디스플레이','','','코스모화학','천안교육청','','(주)천안물산','현대제철 당진',''];
  const notes    = ['','','당뇨 기왕력 있음','혈압약(아므로디핀) 복용 중','','','임신 가능성 확인 필요','','','조영제 알레르기 있음','','',''];
  const statuses = ['예약접수','예약접수','예약접수','예약확정','예약확정','예약확정','예약확정','검진완료','검진완료','검진완료','일정변경','예약취소'];
  const programs = CMC.PROGRAMS.map(p => p.id);
  const optional = CMC.OPTIONAL_TESTS;
  const slots    = CMC.TIME_SLOTS;

  const today = new Date();
  const todayStr = today.toISOString().split('T')[0];

  return Array.from({ length: 40 }, (_, i) => {
    // 접수일 — 최근 30일 사이 분산
    const created = new Date(today);
    created.setDate(today.getDate() - Math.floor(i * 0.75));

    // 희망검진일 — 오늘 기준 -5 ~ +20일 분산 (오늘 날짜 포함)
    const wishOffset = (i % 10) - 2;   // -2 ~ +7
    const wish = new Date(today);
    wish.setDate(today.getDate() + wishOffset);
    const wishDate = wish.toISOString().split('T')[0];

    const ymd = created.toISOString().slice(0,10).replace(/-/g,'');
    const seq  = String(i + 1).padStart(4, '0');

    return {
      reservationNo: `${ymd}-${seq}`,
      createdAt:     created.toISOString(),
      updatedAt:     created.toISOString(),
      status:        statuses[i % statuses.length],
      name:          names[i % names.length],
      birth:         `${1955 + (i * 2) % 45}-${String((i%12)+1).padStart(2,'0')}-${String((i%28)+1).padStart(2,'0')}`,
      phone:         `010-${String(1000 + i*37).padStart(4,'0').slice(0,4)}-${String(2000 + i*19).padStart(4,'0').slice(0,4)}`,
      gender:        i % 2 === 0 ? '남' : '여',
      program:       programs[i % programs.length],
      wishDate,
      wishTime:      slots[i % slots.length],
      sleep:         i % 3 === 0 ? '수면' : '일반',
      optionalTests: i % 4 === 0
        ? [optional[i % optional.length], optional[(i+5) % optional.length]]
        : [],
      company:       companies[i % companies.length],
      note:          notes[i % notes.length],
    };
  });
}
