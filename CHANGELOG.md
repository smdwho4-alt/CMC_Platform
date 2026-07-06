# CHANGELOG.md — CMC Platform (CSHSP)

이 문서는 Phase 1부터 현재까지의 주요 변경사항을 기록한다. 형식은 [Keep a Changelog](https://keepachangelog.com/) 관례를 참고하되, git 태그가 없던 기간은 Phase/Sprint 단위로 정리한다.

---

## [v0.9.0-pilot] — 2026-07-04

### Added
- SSOT 문서 5종 신설: `CLAUDE.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `DECISIONS.md`, `PROJECT_STATUS.md`
- 릴리스 준비 문서: `README.md`, `CHANGELOG.md`, `LICENSE`, `.gitignore`, `requirements.txt`, `.env.example`, `RELEASE_NOTES_v0.9.0-pilot.md`, `PILOT_READINESS_REVIEW.md`

### Changed
- 프로젝트 상태를 "Architecture Freeze 완료 / Pilot 준비 중"으로 전환

### Notes
- 기능 변경 없음(Architecture Freeze 및 Release 준비 전용 릴리스)
- Known Issue: STEP1.5 DateFix 미배포 (PROJECT_STATUS.md 참조, Pilot Ready 차단 요인이며 Architecture Freeze는 차단하지 않음 — DECISIONS.md ADR-010)

---

## Sprint I — 품질 게이트 (Quality Gate)

- 자동 점검 16항목 도입: 인프라/보안/데이터/개인정보/기능 5영역
- 결과: PASS (FAIL 0, WARN 2 — 더미 계정/더미 데이터, SKIPPED 1 — 실키 미설정)
- 회귀 테스트 통합: Sprint A/B/D(36)/E(31)/F(31)/G(30)/H(20) = 148/148 PASS
- AI 금지응답 테스트 35/35 차단 확인
- 백업·복구 리허설 9/9 PASS

## Sprint H — 파일럿 전환 (Operation Transition)

- 파일럿 운영 절차 수립: 일일 체크리스트, 중단 기준(Stop Criteria), Go-Live 판정 기준
- 장애 대응 매뉴얼(P1/P2/P3) 작성
- 백업 정책(`backup_policy.md`), 프로세스 관리(`process_manager.md`), 운영 전 체크리스트(`production_checklist.md`) 문서화
- 알림 발송 워커(`notification_worker.py`) 추가 (Mock 발송)

## Sprint G — Claude API 연동

- `claude_client.py` 추가 — Anthropic Claude API 연동, `ANTHROPIC_API_KEY` 설정 시 자동 활성화
- `tool_loop.py` — 수동 Tool-use 루프, 8종 Function Tool 정의(`function_tools.py`)
- `slot_extractor.py` — 자연어 → 예약 슬롯 추출
- `session_store.py` — 세션 영속화(파일/메모리), 대화 원문 미저장 원칙 적용
- Rate Limit(`rate_limit.py`, 기본 30회/60초), PII 마스킹 로그(`privacy_logger.py`) 추가
- AI 상담 통계 대시보드(`ai_metrics.py`, `admin/ai_dashboard.html`) 추가
- API Key 미설정 시 규칙 기반 오케스트레이터로 자동 폴백

## Sprint F — AI Chat Widget

- `chat/chat_widget.js` — SSE 스트리밍 기반 채팅 위젯
- 차단(blocked)/본인확인(needVerification)/추가입력(needInput)/성공(success) meta 이벤트 처리
- 예약 폼·본인확인 폼 위젯 내 표시

## Sprint E — 규칙 기반 AI 에이전트

- `agent_orchestrator.py` — 단일 진입점, 의도 분류 후 서브에이전트 위임
- 서브에이전트 5종: `reservation_agent`, `recommendation_agent`, `questionnaire_agent`, `crm_agent`, `operation_agent`
- `safety_guard.py` — 35개 금지응답 카테고리 필터
- AI는 예약을 `PENDING_APPROVAL`까지만 생성 가능(직접 확정 불가) — 3중 방어 원칙 확립

## Sprint D — API Layer

- FastAPI 기반 REST API 서버(`api_server.py`, 포트 8600) 구축, 36개 엔드포인트
- `routes_agents.py` — 채팅/AI 라우터
- `file_lock.py` — 다중 프로세스 파일 잠금(FileJsonLock)

## Sprint C — Admin Console

- 관리자 콘솔(SPA) 신설: 대시보드/승인대기/목록/상세/Slot/일정/감사로그 7개 메뉴
- Mock API 어댑터(`admin_api.js`)로 `reservation_engine.py` 로직을 JS에서 미러링
- 문진 검토 화면(`questionnaire_review.html`) 추가
- RBAC 적용: ROLE-STAFF만 승인 가능, ROLE-AI-AGENT는 승인 불가

## Sprint B — Reservation Engine

- `reservation_engine.py` — 예약 상태머신(PENDING_APPROVAL → CONFIRMED/REJECTED → COMPLETED/CANCELLED), 권한 검증
- `slot_generator.py`, `alternative_slot_recommender.py` — Slot 생성 및 대체시간 추천(최대 5개)
- `reservation_audit.py` — 모든 상태 전이를 append-only 감사로그로 기록

## Sprint A — Core Data Layer

- 20 Entity 데이터 모델 확정, JSON 파일 기반 저장소 구축(`data/`)
- `core_data_loader.py`, `data_validator.py` — 로더 및 스키마/무결성 검증

---

## Phase 1 ~ Phase 4.5 (Sprint 이전, 프론트엔드 중심 개발)

| Phase | 내용 |
|---|---|
| Phase 1 | 예약 UI, localStorage 기반 저장 |
| Phase 2 | 대시보드, 관리자 콘솔 초안, 컴포넌트화 |
| Phase 3 | Google Sheets/Calendar/Gmail API 직접 연동(GWS 어댑터) |
| Phase 4 | Google Apps Script Web App 경유 연동으로 전환 (18컬럼 예약DB) |
| Phase 4.5 | 예약 시트 29컬럼으로 확장(접수·검진·결제·결과), ERD/워크플로우 문서화 |
| STEP0-1 | 예약 쓰기 경로 배선 및 검증 완료 |
| STEP1.5 | DateFix QA — 날짜/시간 포맷 결함 발견, 수정 코드 작성 (배포는 미반영, 현재도 유효한 Known Issue) |
