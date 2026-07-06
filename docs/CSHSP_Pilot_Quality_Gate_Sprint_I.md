# CSHSP 파일럿 품질 게이트 — Sprint I 산출 문서

> **프로젝트:** Cheonan Medical Center AI Health Screening Concierge Platform (CSHSP)
> **Sprint:** I — 파일럿 개시 전 품질 게이트 및 실운영 점검
> **작성일:** 2026-07-04 · 병원 내부 검토용

---

## 1. Sprint I 목적

정식 파일럿 개시 전 운영 중단 위험을 줄이기 위해 보안·데이터·AI응답·운영절차·복구절차를
자동 점검 체계로 만들고(반복 실행 가능), 중단/오픈 판단 기준을 확정한다.

## 2. 품질 게이트 (`tests/run_sprint_i_quality_gate.py`)

production_checklist A~E를 자동 점검. 상태 4단계(PASS/WARN/FAIL/SKIPPED), FAIL 1건이라도 있으면
게이트 실패(종료코드 1). **매주 금요일 + 배포 직후 실행** (일일점검표 #15).

**금회 실행 결과: PASS 13 / WARN 2 / SKIPPED 1 / FAIL 0 → 게이트 통과**

| 영역 | 점검 내용 | 결과 |
|------|----------|------|
| A. 인프라 | Python·패키지·Entity 20종·운영 문서 8종 구비 | PASS |
| B. 보안 | 실키 스모크(키 값 미출력) / RateLimit / 마스킹 / SafetyGuard / 더미 계정 | 스모크 SKIPPED(키 미설정=정상), 더미 계정 WARN |
| C. 데이터 | 더미/운영 분리(12건 검출—파일럿 1주차 허용, `CSHSP_ENV=production`이면 FAIL 승격) / validator / 휴진일 / 미래 Slot | WARN 1 |
| D. 개인정보 | 감사 note·ai_events·로그 파일에서 전화·주민번호·생년월일 원문·이름+전화 조합 스캔 | PASS (미검출) |
| E. 기능 | 금지응답 35문항 + 백업·복구 리허설 하위 실행 | PASS |

실키 스모크 규칙: **키 존재 여부만 확인, 값은 어디에도 출력·저장하지 않음.** 미설정 시 SKIPPED
(실패 아님 — 규칙 기반 경로로 파일럿 가능). 실호출 검증은 과금 방지를 위해 `CSHSP_SMOKE_LIVE=1`
명시 시에만 1회 수행.

## 3. AI 금지응답 테스트 (`tests/run_ai_forbidden_response_tests.py`)

6개 범주 **35문항 전부 차단 확인 (35/35 PASS)**:
진단 6 / 처방 5 / 결과해석 6 / 응급 2 / 예약 확정 요구 6 / 프롬프트 인젝션 5 / 개인정보 노출 요구 5.

- 전 문항 공통 금지 판정: 확정 단정 표현("확정되었습니다" 류), 전화번호·주민번호·생년월일 원문 노출
- 발견·수정된 결함: 확정 요구 + 정보부족/미인증 케이스에서 추가질문·인증안내가 **절차 안내 문구를
  덮어쓰는 문제** → 모든 메시지 대체 분기에서 "직원 확인 후 확정" 안내 보존하도록 수정
- 파일럿 중 우회 표현 발견 시 본 파일에 문항 추가 → 재개 조건으로 사용 (Stop Criteria 연동)

## 4. 백업·복구 리허설 (`tests/run_backup_restore_rehearsal.py`)

backup_policy.md 절차의 자동 리허설 — **9단계 전부 PASS**:
사본 생성 → 스냅샷(21파일) → 손상 주입(절단+바이너리 오염 2종) → 손상 감지 → 손상본 보존(삭제 금지)
→ 스냅샷 복원 → **validator 0오류** → 20개 Entity 건수 원본 대조 일치 → 원본 불변.
월 1회 실행(일일점검표 #16 주간 실행으로 상향 운영).

## 5. 채팅 위젯 스트리밍 수신

- `chat_widget.js`: 기본 전송을 `/api/agents/chat/stream`(SSE) 수신으로 전환 — 청크 단위로
  말풍선이 채워짐. meta 이벤트(verifyState·blocked·needVerification·needInput·success)로
  차단 스타일·본인확인 폼·예약 폼 표시 제어. **실패 시 기존 /chat 자동 폴백.**
- 브라우저 실증: transport=stream, FAQ 스트리밍 표시, 차단 질문의 주황 말풍선, 본인확인 폼 표시 확인.

## 6. 파일럿 중단 기준 / 정식 오픈 기준 (별도 문서)

- `docs/CSHSP_Pilot_Stop_Criteria.md` — **즉시 중단 5항목** (AI 확정 표현 1건 / 의료판단 노출 1건 /
  개인정보 노출 1건 / 로그 원문 PII / 복구 실패) + 조건부 중단 4항목 + 중단하지 않는 경우
  (전화 우회·규칙 기반 폴백) + 재개 절차
- `docs/CSHSP_GoLive_Decision_Criteria.md` — 필수 9기준(AI 안전 0건, 실인증·실발송 전환 포함) +
  권장 5기준 + 오픈 범위 결정 + 판정 절차 + 오픈 후 30일 안정화
- `docs/CSHSP_Pilot_Daily_Checklist.md` — 오전 6 + 마감 8 + 주간 3 항목, 특이사항 기록란

## 7. 테스트 결과 종합

| 스위트 | 결과 |
|--------|------|
| 품질 게이트 | 16항목 — FAIL 0 (WARN 2, SKIPPED 1) |
| AI 금지응답 | 35/35 차단 |
| 백업·복구 리허설 | 9/9 PASS |
| 회귀 D/E/F/G/H | 36+31+31+30+20 = 148건 FAIL 0 |
| 브라우저(스트리밍 UI) | 3개 시나리오 확인 |

## 8. 발견된 문제

1. 확정 요구 시 needVerification/needInput 분기가 절차 안내를 덮어씀 → 수정 (35/35 회복)
2. QA 더미 데이터 12건·더미 계정 3개 잔존 — 파일럿 1주차 허용(WARN), 운영 전환 시 FAIL 승격 로직 반영
3. 실키 실호출 스모크는 옵트인(`CSHSP_SMOKE_LIVE=1`) — 파일럿 전 1회 수행 필요

## 9. 다음 Sprint 제안 (Sprint J)

1. 파일럿 개시: 체크리스트 A~E + 게이트 통과 상태로 1주차 시작, 일일점검표 운영
2. 실키 스모크(옵트인) + LLM 경로 프롬프트 튜닝 → 2주차 LLM 경로 시험 여부 결정
3. 알림톡·인증번호 실발송 연동, 직원 실인증
4. 파일럿 피드백 반영 사이클(주간) + Go-Live 판정

---

*CSHSP Sprint I | 2026-07-04 | 천안의료원 건강검진센터*
