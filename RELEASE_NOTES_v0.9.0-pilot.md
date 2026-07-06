# Release Notes — v0.9.0-pilot

**릴리스일**: 2026-07-04
**릴리스 유형**: Architecture Freeze / Release 준비 (기능 변경 없음)
**대상 단계**: Pilot 운영 준비

---

## 1. 이 릴리스의 성격

v0.9.0-pilot은 **Sprint A~I 및 Sprint 2까지의 기능 개발分을 그대로 확정**하고, Architecture Freeze(Sprint 0)를 완료한 뒤 문서·릴리스 체계를 정리한 버전이다. **이번 릴리스에서 기능 코드는 수정하지 않았다.** 신규 추가된 것은 SSOT 문서 5종과 표준 릴리스 산출물(README/CHANGELOG/LICENSE/.gitignore/requirements.txt/.env.example)뿐이다.

버전 넘버링 원칙:
- `0.9.x` — Architecture Freeze 이후, Pilot Ready 전제조건 충족 전 단계
- `1.0.0` — Pilot Ready 전제조건(아래 §4) 충족 후 정식 Pilot 개시 시점에 부여 예정

## 2. 포함된 기능 (Sprint A~I, Sprint 2 누적)

- 20-Entity Core Data Layer, 예약 상태머신 기반 Reservation Engine
- 관리자 콘솔(7개 메뉴), RBAC
- FastAPI REST API(36 엔드포인트)
- 규칙 기반 + Claude API 하이브리드 AI 컨시어지 에이전트, 3중 방어(Safety Guard/Tool 화이트리스트/RBAC)
- AI 채팅 위젯(SSE 스트리밍), 운영 대시보드(KPI/검사실/AI 추천)
- Google Sheets(Apps Script) 연동 예약 화면
- 백업·복구 절차, 장애 대응 매뉴얼, 파일럿 운영 절차 문서

상세 변경 이력은 [CHANGELOG.md](CHANGELOG.md), 구조는 [ARCHITECTURE.md](ARCHITECTURE.md) 참조.

## 3. 이번 릴리스에서 신규 작성된 문서

| 문서 | 목적 |
|---|---|
| README.md | 프로젝트 소개, 실행 방법, 폴더 구조, 로드맵 |
| CHANGELOG.md | Sprint A~I 변경 이력 |
| LICENSE | 천안의료원 내부 전용(Proprietary) 라이선스 |
| .gitignore | Python 캐시, 운영 데이터(PII), 로그 등 제외 규칙 |
| requirements.txt | fastapi, uvicorn, pydantic, anthropic |
| .env.example | 환경변수 템플릿 (실제 값 없음) |
| RELEASE_NOTES_v0.9.0-pilot.md | 이 문서 |
| PILOT_READINESS_REVIEW.md | Pilot 운영 시작 전 최종 검토 보고서 |

## 4. Known Issues (Pilot Ready 전제조건 — 미해결)

이 릴리스에는 알려진 미해결 이슈가 포함되어 있다. Architecture Freeze는 이 이슈와 무관하게 완료되었으나(DECISIONS.md ADR-010), **Pilot 운영 개시 전에는 반드시 해결**해야 한다.

1. **STEP1.5 DateFix 미배포 (Critical)** — Google Sheets 저장 시 birth/wishDate/wishTime 필드 자동 날짜변환 오류. 수정 코드는 작성 완료(`app/apps_script/sheets_api_v3_final.gs`)했으나 Apps Script 배포가 반영되지 않음. 재QA 1차 실패 확인됨.
2. **DEV-003 미구현** — 관리자 예약관리 Sheets 연동(`admin_reservations_v2_new.html`). 설계는 Final 확정, 코드 미작성.
3. **더미 데이터/계정 미정리** — `data/reservations.json` QA 더미, `data/users.json` 더미 계정 3개(USR-0001~0003).

상세: [PROJECT_STATUS.md](PROJECT_STATUS.md) §2, [ROADMAP.md](ROADMAP.md) "Sprint J 이전 필수 해결 과제".

## 5. 보안/설정 관련 주의사항

- `app/apps_script/sheets_api_v3_final.gs`에 운영 Google Sheets의 `SPREADSHEET_ID`가 하드코딩되어 있다. 이 값은 민감 정보이므로 외부 공개 저장소에는 절대 커밋하지 않는다. 향후 git 도입 시 이 값을 환경변수/설정 파일 분리로 전환하는 것을 권장한다(§8 참조).
- `ANTHROPIC_API_KEY`는 코드/문서에 값을 기록하지 않고 서버 환경변수로만 설정한다.
- 관리자 인증(로그인)과 HTTPS는 아직 구현되지 않았다. 운영(정식 Go-Live) 전 필수.

## 6. Git Tag 생성 준비 (문서화만, 실제 명령 미실행)

이 프로젝트는 현재 git 저장소가 아니다(git init 미수행). 향후 git 도입 시 아래 절차로 태그를 생성한다.

```bash
# 1) 저장소 초기화 (아직 수행하지 않음 — 사용자 승인 필요)
git init

# 2) .gitignore 확인 후 최초 커밋
git add .
git commit -m "v0.9.0-pilot: Architecture Freeze + Release 준비"

# 3) 태그 생성
git tag -a v0.9.0-pilot -m "Architecture Freeze 완료, Pilot 준비 단계. Known Issue: STEP1.5 DateFix 미배포"

# 4) (원격 저장소 연결 시) 푸시 — 내부 전용이므로 외부 공개 저장소 사용 금지
# git push origin v0.9.0-pilot
```

> **주의**: `git init`과 최초 커밋은 이번 작업 범위에 포함되지 않았다. 실행 여부는 사용자 승인 후 별도로 진행한다. 커밋 전 `data/*.json`(개인정보 포함)과 `app/apps_script/sheets_api_v3_final.gs`의 `SPREADSHEET_ID`가 `.gitignore` 또는 별도 조치로 제외/치환되었는지 반드시 재확인한다.

## 7. 다음 릴리스 전망 (v1.0.0)

§4의 Pilot Ready 전제조건이 모두 충족되면 `v1.0.0`(정식 Pilot 개시)을 검토한다. 상세 계획은 [ROADMAP.md](ROADMAP.md) 참조.
