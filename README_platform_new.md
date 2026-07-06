# CMC Health Screening Platform v1.0

> **천안의료원 건강검진센터 예약관리시스템 Phase 2**  
> 시제품(Prototype) — 실제 운영 전 보완사항 확인 필요

---

## 프로젝트 구조

```
CMC_Platform_new/
├── index.html                          ← 진입점 (대시보드로 자동 리다이렉트)
├── app/
│   ├── pages/
│   │   ├── admin_dashboard_new.html    ← 운영 대시보드 (메인)
│   │   ├── reservation_new.html        ← 수검자 예약 신청
│   │   └── admin_reservations_new.html ← 관리자 예약 목록·상태관리
│   ├── components/
│   │   └── nav_new.js                  ← 공통 네비게이션 주입
│   ├── services/
│   │   ├── db_service_new.js           ← 데이터 CRUD (localStorage 기반)
│   │   └── stats_service_new.js        ← KPI 산출 로직
│   ├── data/
│   │   ├── programs_data_new.js        ← 프로그램·상수 정의
│   │   └── sample_data_new.js          ← 샘플 데이터 생성기 (40건)
│   ├── styles/
│   │   ├── main_style_new.css          ← 공통 스타일
│   │   └── dashboard_style_new.css     ← 대시보드 전용 스타일
│   └── assets/                         ← 이미지·아이콘 (향후 사용)
└── README_platform_new.md
```

---

## 브라우저 실행

1. `CMC_Platform_new` 폴더를 웹 서버로 서빙  
   (로컬: VSCode Live Server / npx serve / Python http.server)
2. `index.html` 접속 → 자동으로 대시보드로 이동

**또는 직접 접속:**

| 화면 | 경로 |
|------|------|
| 대시보드 | `app/pages/admin_dashboard_new.html` |
| 예약 신청 | `app/pages/reservation_new.html` |
| 예약 관리 | `app/pages/admin_reservations_new.html` |

> **참고:** file:// 프로토콜로 HTML 직접 열기 시 일부 브라우저에서 모듈 로딩 오류 발생 가능. `npx serve` 사용 권장.

---

## 대시보드 기능

| 영역 | 내용 |
|------|------|
| KPI 카드 5개 | 오늘 예약 / 예약접수 / 예약확정 / 검진완료 / 예약취소 |
| 오늘 일정 | 당일 예약 시간순 목록, 수면여부·상태 뱃지 |
| 이번주 예약현황 | 월~일 요일별 막대 차트 (취소 제외, 오늘 강조) |
| 최근 예약목록 | 접수 최신 10건 테이블 |
| 프로그램별 현황 | BASIC~온김에검진 건수·비율 수평 바차트 |

---

## v1.0 → v2.0 업그레이드 로드맵

### 1순위 (운영 전 필수)

| 항목 | 현재 | 목표 |
|------|------|------|
| 데이터 저장 | localStorage | REST API + MySQL/PostgreSQL |
| 인증 | 없음 | JWT 로그인 + 권한 분리 |
| 통신 보안 | HTTP | HTTPS (SSL 인증서) |
| 개인정보 마스킹 | 부분 적용 | 역할별 완전 마스킹 정책 |

### 2순위 (운영 편의)

| 항목 | 방향 |
|------|------|
| SMS/이메일 자동발송 | Zapier + CoolSMS / SendGrid |
| Google Sheets 연동 | Apps Script Webhook |
| Google Calendar 연동 | 예약확정 시 이벤트 자동 생성 |
| 카카오 알림톡 | 접수·확정·취소 자동 발송 |
| 중복 예약 방지 | 날짜·시간별 정원 관리 |

### 3순위 (고도화)

| 항목 | 방향 |
|------|------|
| 월별 실적 통계 | 차트 라이브러리 연동 (Chart.js) |
| HIS 연동 | 검진 결과 자동 연계 |
| 공공 홈페이지 삽입 | iframe 또는 API 방식 |

---

## Phase 변경이력

| Phase | 내용 |
|-------|------|
| v1.0 Phase 1 | HTML/CSS/JS 단일 파일 구성, 기본 예약·관리 기능 |
| **v1.0 Phase 2** | **플랫폼 구조 리팩터링, 대시보드 신설, 서비스 레이어 분리** |

---

## 기술 스택

| 항목 | 내용 |
|------|------|
| 언어 | HTML5, CSS3, Vanilla JavaScript (ES6+) |
| 외부 의존성 | 없음 (Zero dependencies) |
| 데이터 | localStorage (시제품) |
| 브라우저 | Chrome, Edge, Safari, Firefox 최신 버전 |
| 반응형 | 360px ~ 1280px+ |

---

*CMC Health Screening Platform v1.0 | Phase 2 | 2026-07-01*  
*천안의료원 건강검진센터*
