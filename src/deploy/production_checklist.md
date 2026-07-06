# CSHSP 운영 전 점검표 (Production Checklist — Sprint H)

> 파일럿 개시 전 검진센터 담당자·전산 담당자가 함께 체크. 내부 검토용.

## A. 인프라
- [ ] 서버 확보 (내부망 Windows, Python 3.14, Node/serve 또는 IIS)
- [ ] API(8600)·정적(4000) 서비스 등록 및 자동 재시작 설정 (process_manager.md)
- [ ] HTTPS 리버스 프록시(사내 CA) 구성, uvicorn 127.0.0.1 바인딩 확인
- [ ] 방화벽: 관리자 콘솔·API 내부망 한정, 외부 공개 범위 결정
- [ ] 시간 동기화(NTP) — 예약/감사로그 시각 정합

## B. 환경변수·보안
- [ ] `CSHSP_DATA_DIR` 운영 데이터 경로 지정
- [ ] `ANTHROPIC_API_KEY` — 사용 여부 결정. 사용 시 서버 환경변수로만 설정 (코드·문서·채팅에 값 기록 금지)
- [ ] `CSHSP_CHAT_RATE` 운영값 결정 (기본 30/60)
- [ ] Rate Limit 동작 확인 (429), PII 마스킹 로그 확인
- [ ] 직원 계정(users.json) 실계정으로 교체, QA 더미 계정 비활성(status INACTIVE)
- [ ] Mock 인증(X-User-Id) 한계 공지 — 파일럿은 내부망 한정, 정식 오픈 전 실인증 필수

## C. 데이터
- [ ] data/ QA 더미 정리: 환자·예약 더미 삭제 여부 결정 (감사로그는 보존)
- [ ] 실제 프로그램·수가 반영 (programs.json / optional_tests.json — 수가 미등록 원칙 유지)
- [ ] 연간 공휴일·휴진일 schedules.json 등록
- [ ] 운영 기간 Slot 생성 (`POST /api/slots/generate` 또는 slot_generator)
- [ ] `python src/core/data_validator.py` 오류 0건
- [ ] 백업 스케줄 등록 + 1회 수동 백업/복구 리허설 (backup_policy.md)

## D. 기능 검증 (파일럿 전일)
- [ ] 전체 테스트 스위트 PASS: run_sprint_b/d/e/f/g/h_tests.py
- [ ] 시나리오 리허설: 신청→승인→알림(PENDING→SENT)→문진→검토 (Sprint F 문서 §8)
- [ ] AI 확정 차단 확인 (AI 계정 approve 403)
- [ ] 의료질문 차단 + "의료진 상담 필요" 안내 확인
- [ ] 본인확인 전 개인정보 미표시 확인
- [ ] admin 콘솔 ?mode=live 정상 (승인/거절/HOLD해제)
- [ ] 채팅 위젯 (chat/) 예약 신청·안내 정상

## E. 운영 준비
- [ ] 직원 교육 (파일럿 시나리오 문서 배포, 30분 실습)
- [ ] 장애 대응 매뉴얼 비치 + 담당자 연락망 (Failure_Response_Manual)
- [ ] 알림 발송 정책 확정 — 파일럿은 Mock(PENDING 큐)까지, 실발송 연동 시점 결정
- [ ] 파일럿 기간·범위·성공 기준 확정 (Pilot_Operation_Scenario)
- [ ] 병원 개인정보보호 책임자 검토 (수집·보관·백업·마스킹 정책)

## F. 개시 후 일일 점검 (파일럿 기간)
- [ ] 아침: health 확인, 승인 대기함·대시보드 확인
- [ ] 저녁: 알림 워커 결과, Safety 차단 이력, 백업 성공 확인
- [ ] 주간: AI 상담 통계 리뷰 (전환율·차단 유형), 피드백 취합
