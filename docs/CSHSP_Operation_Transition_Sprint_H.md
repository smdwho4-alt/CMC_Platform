# CSHSP 운영 전환 및 파일럿 준비 — Sprint H 산출 문서

> **프로젝트:** Cheonan Medical Center AI Health Screening Concierge Platform (CSHSP)
> **Sprint:** H — 운영 전환 (LLM 경로·멀티턴·스트리밍·배포·파일럿)
> **작성일:** 2026-07-03 · 병원 내부 검토용

---

## 1. Sprint H 목적

Sprint A~G 산출물을 실제 직원 파일럿 운영이 가능한 상태로 정리한다:
채팅의 Claude tool_loop 기본 경로 전환(Key 감지), 멀티턴 히스토리, 스트리밍 구조,
배포·백업·장애 대응·파일럿 문서 일체.

## 2. 운영 전환 구조

```
ANTHROPIC_API_KEY 설정 여부 (환경변수만 — 코드 하드코딩 금지)
 ├─ 있음 → api_server가 ClaudeClient 자동 주입
 │         chat → Safety Guard 선차단 → run_tool_loop(멀티턴 히스토리) → 도구 allowlist
 └─ 없음 → 기존 규칙 기반 오케스트레이터 유지 (Mock 모드 — 서비스 중단 없음)
```
- **장애 시 폴백**: Key 환경변수 제거 후 재시작만으로 규칙 기반 복귀 (Failure Manual C-2)
- 어느 경로든 불변: AI 확정 불가(도구 부재+차단+API 403), 의료판단 차단, 본인확인 게이트,
  Rate Limit, PII 마스킹 감사기록

## 3. 멀티턴·스트리밍

- `src/agents/conversation_manager.py` — 세션별 히스토리를 `data/chat_histories.json`에 영속화.
  최대 30메시지, 트리밍은 일반 user 턴 경계에서 수행(tool_use/tool_result 짝 보존).
  히스토리는 로그가 아닌 운영 대화 상태로 취급(로그 미출력, 백업 시 민감데이터 동일 보호).
- `POST /api/agents/chat/stream` — SSE(meta→data 청크→done). 현재는 완성 응답 분할 전송이며,
  실 토큰 스트리밍은 claude_client에 messages.stream 어댑터 추가 지점 1곳으로 표기.

## 4. 실연동 교체 지점 (확정)

| 항목 | 위치 | 교체 내용 |
|------|------|----------|
| 인증번호 발송 | `routes_agents.py` verify의 `MOCK_VERIFY_CODE` 발급 라인 | SMS 발급 API 호출 + 난수 코드 |
| 알림톡/SMS 발송 | `notification_worker.default_mock_sender` | 카카오 알림톡/SMS API sender 함수 |
| 세션 저장소 | `routes_agents.py`의 `FileSessionStore(...)` 1줄 | RedisSessionStore(get/set/delete) |
| LLM 스트리밍 | `chat_stream` 내부 gen() | SDK messages.stream 이벤트 중계 |

## 5. 배포·백업·점검 문서

- `src/deploy/process_manager.md` — NSSM 서비스 등록, HTTPS 리버스 프록시(내부망 TLS 종료),
  운영 환경변수 5종 목록, 로그 로테이션(개인정보 원문 금지), 재기동 절차
- `src/deploy/backup_policy.md` — data/ 일일 스냅샷(30일)·감사로그 1년, BitLocker 암호화,
  RTO 30분 복구 절차(validator 검증 포함), 월 1회 복구 리허설
- `src/deploy/production_checklist.md` — 인프라/보안/데이터/기능검증/운영준비/일일점검 6개 영역
  40여 항목 (QA 더미 정리·실계정 교체·개인정보 책임자 검토 포함)

## 6. 파일럿·장애 대응

- `docs/CSHSP_Pilot_Operation_Scenario.md` — 2주 파일럿, 역할별 시나리오 5종(수검자/직원/문진/콜센터/전산),
  성공 기준(AI 오동작 0건 등)과 **중단 기준**(확정 표현·개인정보 노출 시 채팅만 차단 가능) 명시
- `docs/CSHSP_Failure_Response_Manual.md` — 증상별 7개 절차(서버 무응답/데이터 손상/채팅 오류/
  AI 이상 응답/알림 적체/RateLimit/포트 충돌), P1~P3 보고 체계, 전화 우회 접수 원칙

## 7. SQLite 이관 검토

`docs/SQLite_Migration_Plan.md` — **파일럿은 JSON 유지 권고**, 이관 트리거 4종
(다중 프로세스·1만건·잠금 충돌·통계 질의) 정의. 읽기(core_data_loader)/쓰기(json_store) 2모듈로
교체 지점이 수렴되어 있어 어댑터 방식 1~2일 이관 계획과 리스크 대응 수록.

## 8. 테스트 결과

**Sprint H 20/20 PASS** + 회귀 D 36 / E 31 / F 31 / G 30 — **누적 148건 FAIL 0**.
요구 10개 시나리오 전부 포함: Key 없음 규칙 경로 / Key 존재 live 선택(실호출 없음) /
tool_loop 경로 전환 / 멀티턴([1→3] 메시지 증가+파일 영속화) / LLM 경로 Safety 선차단(LLM 미호출) /
마스킹 유지 / AI 확정 도구 차단+예약 불변 / Rate Limit 429 / SSE 스트리밍 / 운영 문서 6종 검증.

## 9. 발견된 문제 / 보완

1. 실 Claude API 경로는 실키 부재로 transport 계층까지만 검증 — 파일럿 전 실키로 스모크 테스트 1회 필요
2. 스트리밍은 프로토콜 준비 단계 (완성 응답 분할) — 실 토큰 스트리밍은 SDK 어댑터 추가 후
3. Mock 인증(X-User-Id)·Mock 인증번호는 내부망 파일럿 한정 — 정식 오픈 전 실인증 필수 (체크리스트 B 명시)
4. 채팅 위젯은 아직 /chat(비스트리밍) 사용 — 위젯의 스트리밍 수신 전환은 Sprint I

## 10. 다음 Sprint 제안 (Sprint I)

| 우선순위 | 작업 |
|:---:|------|
| 1 | 실키 스모크 테스트 + 위젯 스트리밍 수신 전환 + 실사용 프롬프트 튜닝 |
| 2 | 파일럿 개시 (체크리스트 A~E 완료 후) 및 주간 피드백 반영 사이클 |
| 3 | 알림톡/인증번호 실발송 연동 (교체 지점 2곳) |
| 4 | 실인증(직원 로그인) 도입 — require_user 의존성 교체 |
| 5 | 파일럿 결과 기반 정식 오픈 판정 및 SQLite 이관 트리거 점검 |

---

*CSHSP Sprint H | 2026-07-03 | 천안의료원 건강검진센터*
