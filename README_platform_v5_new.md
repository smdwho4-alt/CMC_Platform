# CMC Health Screening Platform — Sprint 2 README

> **Sprint 2**: 검진센터 운영 Dashboard v3 개발  
> Phase 1~4.5 파일은 모두 유지됨 — 기존 파일 삭제 없음

---

## Sprint 2 신규 파일

| 파일 | 설명 |
|------|------|
| `app/pages/admin_dashboard_v3_new.html` | 운영 대시보드 v3 — 7개 섹션 메인 화면 |
| `app/services/dashboard_service_v2_new.js` | KPI/통계/대기현황/AI추천 서비스 |
| `app/styles/dashboard_style_v2_new.css` | 운영센터 다크 테마 스타일 (반응형, 대형모니터) |
| `README_platform_v5_new.md` | 이 문서 |

---

## Dashboard v3 구성 (7개 섹션)

### ① 상단 KPI (6개 카드)

| KPI | 설명 | 색상 |
|-----|------|------|
| 오늘 예약 | 전체 예약 건수 | 파랑 |
| 오늘 접수 | 내원 확인 건수 (검진중+완료) | 초록 |
| 현재 대기 | 대기 중 건수 (접수+확정) | 노랑 |
| 검진 진행 | 현재 검진중 건수 | 주황 |
| 검진 완료 | 오늘 완료 건수 | 보라 |
| 예약 취소 | 오늘 취소 건수 | 빨강 |

### ② 프로그램별 현황

오늘 수검자 기준 프로그램(BASIC·SMART·VIP·PREMIUM·YOUNG·온김에검진)별 건수 및 비율 바 표시.

### ③ 검사실 운영 현황

| 검사실 | 대기 인원 계산 방식 |
|--------|-------------------|
| 접수·문진·채혈·방사선·초음파·CT·MRI·내시경 | 검진중 수검자의 희망시간 + 프로그램별 검사실 소요시간 기반 현재 위치 추정 |

- 대기 3명 이상: 노랑 강조 표시
- 대기 0명: 초록 (여유)
- `examRoom` 컬럼 직접 설정 시 우선 사용

### ④ 오늘 일정

- 희망시간 순 정렬
- 수검자명, 프로그램, 사업장, 배정 검진실 표시
- 상태별 색상 점 (접수/확정/진행중/완료/취소/변경)

### ⑤ 사업장 일정

탭 전환 (오늘 / 내일 / 이번주), 사업장명 + 날짜 + 수검자 수 표시.

### ⑥ 공지사항

- 관리자 직접 입력 (Enter 또는 등록 버튼)
- localStorage 저장 (최대 20건)
- X 버튼으로 삭제

### ⑦ AI 운영 추천 (규칙 기반)

| 분석 규칙 | 예시 메시지 | 우선순위 |
|-----------|------------|--------|
| 대기 5명 이상 | "현재 대기 X명 — 접수 속도 조정 권고" | 긴급 |
| MRI 대기 2명 이상 | "MRI 대기 X명 — 수검자 안내 권고" | 긴급 |
| 내시경 대기 | "수면 동의서 사전 확인 권고" | 주의 |
| 09:00 집중 시간 | "접수 인력 추가 배치 권고" | 주의 |
| VIP/PREMIUM 수검자 | "담당 간호사 배정 확인 권고" | 주의 |
| 완료 후 미결제 | "결제 안내 필요" | 긴급 |
| 오후 결과 미발송 | "오늘 중 결과 발송 처리 권고" | 주의 |
| 이상 없음 | "운영 상황 양호" | 참고 |

---

## 자동 갱신

- 30초마다 자동 새로고침 (하단 카운트다운 바 표시)
- 우상단 🔄 버튼으로 즉시 새로고침
- 실시간 시계 (초 단위 업데이트)

---

## 운영 Mock 데이터

오늘 날짜 기준 예약 데이터가 없을 경우, `CMC_DashboardV2._injectOperationMock()` 이 자동으로 12건의 운영 샘플 데이터를 생성합니다.

| 수검자 | 프로그램 | 시간 | 상태 |
|--------|---------|------|------|
| 박도윤 | VIP | 08:30 | 검진완료 |
| 김지수 | PREMIUM | 08:30 | 검진중 (내시경) |
| 이준혁 | BASIC | 09:00 | 검진중 (채혈) |
| 최민아 | SMART | 09:00 | 검진중 (방사선) |
| 정수현 | VIP | 09:00 | 예약확정 |
| … (12건) | | | |

---

## 전체 파일 구조 (Phase 1~Sprint 2 누적)

```
CMC_Platform_new/
├── app/
│   ├── pages/
│   │   ├── admin_dashboard_new.html         ← [Phase 2]
│   │   ├── admin_dashboard_v2_new.html      ← [Phase 3]
│   │   ├── admin_dashboard_v3_new.html      ← [Sprint 2] ★ 메인 운영 대시보드
│   │   ├── reservation_new.html
│   │   └── admin_reservations_new.html
│   ├── services/
│   │   ├── db_service_new.js
│   │   ├── stats_service_new.js
│   │   ├── dashboard_service_v2_new.js      ← [Sprint 2] ★ KPI/검사실/AI 서비스
│   │   ├── google_sheets_service_new.js
│   │   ├── google_sheets_service_v2_new.js
│   │   ├── calendar_service_new.js
│   │   └── gmail_service_new.js
│   ├── styles/
│   │   ├── main_style_new.css
│   │   ├── dashboard_style_new.css
│   │   └── dashboard_style_v2_new.css       ← [Sprint 2] ★ 다크 운영센터 테마
│   ├── apps_script/
│   │   ├── sheets_api_new.gs
│   │   └── sheets_api_v2_new.gs
│   ├── docs/
│   │   ├── erd_new.html
│   │   ├── workflow_new.html
│   │   └── sheets_structure_new.html
│   ├── data/
│   │   ├── programs_data_new.js
│   │   └── sample_data_new.js
│   ├── components/
│   │   └── nav_new.js
│   ├── config_new.js
│   └── config_v2_new.js
├── index.html
├── README_platform_new.md      ← [Phase 2]
├── README_platform_v2_new.md   ← [Phase 3]
├── README_platform_v3_new.md   ← [Phase 4]
├── README_platform_v4_new.md   ← [Phase 4.5]
└── README_platform_v5_new.md   ← [Sprint 2] 이 문서
```

---

## 접속 방법

```
로컬 서버 실행 후:
http://localhost:4000/app/pages/admin_dashboard_v3_new.html
```

---

## dashboard_service_v2_new.js API

```javascript
CMC_DashboardV2.todayKPI()
// → { todayTotal, checkedIn, waiting, inProgress, completed, cancelled }

CMC_DashboardV2.programStats()
// → [{ name, count, pct, color, icon }, ...]

CMC_DashboardV2.examRoomStatus()
// → [{ id, icon, order, waiting, pct }, ...] (8개 검사실)

CMC_DashboardV2.todaySchedule()
// → 오늘 예약 목록 (취소 제외, 시간순)

CMC_DashboardV2.companySchedule('today'|'tomorrow'|'week')
// → [{ date, company, count }, ...]

CMC_DashboardV2.getAIRecommendations()
// → [{ icon, text, priority:'high'|'mid'|'low' }, ...]  최대 5개

CMC_DashboardV2.addNotice(text)
CMC_DashboardV2.deleteNotice(id)
CMC_DashboardV2.getNotices()
```

---

## 반응형 지원

| 화면 너비 | 레이아웃 |
|----------|---------|
| 1920px+ | 3열 + KPI 6열, 대형 폰트 |
| 1440px+ | 3열 KPI + 3열 메인 |
| 1400px 이하 | KPI 3열 + 메인 2열 |
| 900px 이하 | 1열 스택 |
| 768px 이하 | KPI 2열 |

---

## 개발 로드맵

| Sprint | 내용 | 상태 |
|--------|------|------|
| Phase 1~4.5 | 예약관리·Sheets 연동 기반 구축 | ✅ 완료 |
| **Sprint 2** | **운영 Dashboard v3 (7개 섹션)** | ✅ 완료 |
| Sprint 3 | 검사실별 실시간 상태 입력 UI, 결제 처리 화면 | 예정 |
| Sprint 4 | HIS 연동, 카카오 알림톡, 통계 리포트 | 예정 |

---

*CMC Health Screening Platform Sprint 2 | 2026-07-01 | 천안의료원 건강검진센터*
