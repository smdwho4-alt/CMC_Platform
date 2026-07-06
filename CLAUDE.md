# CLAUDE.md — CMC Platform (CSHSP) 작업 지침

이 폴더(`CMC_Platform_new`)는 천안의료원 건강검진센터 AI 예약 컨시어지 플랫폼(CSHSP) 프로젝트 루트다. 상위 폴더(건강검진)의 일반 업무자료 규칙과 별개로, 이 프로젝트에서 작업할 때는 아래 지침을 따른다.

## 현재 단계: Architecture Freeze 완료 / 구조 Freeze(v0.9.0) / Pilot 준비 중

Sprint A~I 및 Sprint 2까지 기능 개발이 완료되었고, **Architecture Freeze(Sprint 0)는 완료**되었다(SSOT 문서 5종 확정, DECISIONS.md ADR-010). Architecture Freeze 완료와 **Pilot Ready**(운영 파일럿 투입 가능 여부)는 별개로 관리하며, Pilot Ready는 아직 미충족 상태다(PROJECT_STATUS.md의 Known Issues, 특히 STEP1.5 DateFix 미배포 참조).

**프로젝트 구조는 v0.9.0 현재 상태로 Freeze되었다(DECISIONS.md ADR-011).** 이 폴더에서 작업할 때 다음을 지킨다.
- **구조 변경 작업(파일/폴더 이동, 이름변경, 신설)을 지금 수행하지 않는다.** 구조 재편이 필요해 보이는 경우에도 제안만 하고 실행하지 않으며, "Pilot 종료 후 v1.0 작업"으로 분류한다.
- 구조 관련 논의·분석은 [docs/STRUCTURE_REORG_ANALYSIS_new.md](docs/STRUCTURE_REORG_ANALYSIS_new.md)를 기준 문서로 삼는다.
- **현재 최우선 작업 순서**: ① STEP1.5 DateFix 배포+재QA → ② 전체 QA → ③ v0.9.0 Pilot Release. 이 순서를 벗어나는 작업(DEV-003 구현, 구조 재편 등)은 사용자가 명시적으로 요청하지 않는 한 먼저 진행하지 않는다.
- Architecture Freeze 완료로 신규 기능 개발(Sprint J)이 자동으로 열리는 것은 아니다. Sprint J 착수 전 ROADMAP.md의 "Sprint J 이전 필수 해결 과제"를 먼저 해소한다.
- 구조를 바꾸는 결정을 내릴 때는 [DECISIONS.md](DECISIONS.md)에 ADR로 기록한다.
- 현재 상태는 [PROJECT_STATUS.md](PROJECT_STATUS.md), 향후 계획은 [ROADMAP.md](ROADMAP.md), 구조 전반은 [ARCHITECTURE.md](ARCHITECTURE.md)를 참조한다.

## SSOT 문서 5종 (이 폴더 루트)

작업 시작 전 아래 문서를 먼저 확인한다.

| 문서 | 용도 |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 시스템 구조, 데이터 흐름, 기술 스택 |
| [ROADMAP.md](ROADMAP.md) | 완료 이력 + 향후 계획 |
| [DECISIONS.md](DECISIONS.md) | 아키텍처 의사결정 기록(ADR) |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | 현재 상태 스냅샷 (수시 갱신) |
| CLAUDE.md | 이 문서 — 작업 지침 |

구조를 바꾸거나 새 이슈를 발견하면 해당 문서를 갱신한다. 특히 `PROJECT_STATUS.md`는 상태가 바뀔 때마다 최신화한다.

## 알려진 이슈 (Known Issue, Pilot Ready 차단 요인)

**STEP1.5 DateFix가 코드는 작성되었으나 배포되지 않은 상태다** (`app/apps_script/sheets_api_v3_final.gs`). 이 프로젝트에서 예약 관련 작업을 할 때는 이 이슈가 아직 해결되지 않았다는 것을 전제로 한다. 이 이슈는 Architecture Freeze를 막지 않지만(ADR-010), Pilot Ready와 Sprint J 착수는 막는다. 상세: [PROJECT_STATUS.md](PROJECT_STATUS.md) §2, [ROADMAP.md](ROADMAP.md).

## 이 프로젝트의 파일 관리 규칙 (상위 폴더 규칙 계승)

- **기존 파일을 직접 수정하지 않는다.** 원본은 보존하고 새 버전은 `_v2`, `_v3`, `_final`, 또는 `_new` 접미사를 붙여 새 파일로 만든다. (예: `admin_reservations_new.html` → `admin_reservations_v2_new.html`)
- 예외: 이 SSOT 문서 5종(CLAUDE.md, ARCHITECTURE.md, ROADMAP.md, DECISIONS.md, PROJECT_STATUS.md)은 프로젝트 루트에 표준 파일명 그대로 유지하고 **직접 갱신(덮어쓰기)한다** — 지침 문서로서 실제로 작동해야 하기 때문 (DECISIONS.md ADR-008 참조).
- 파일 삭제·이동·이름변경은 사용자 승인 후 진행한다.
- git 저장소가 아니므로, 코드 변경 시 이전 버전 파일을 남겨 롤백 가능하게 한다.

## 이중 백엔드 주의

이 프로젝트는 **두 개의 독립적인 데이터 저장소**를 가진다.
- 환자용 예약 화면(`app/pages/reservation_v2_new.html`) → Google Sheets (Apps Script 경유)
- 관리자 콘솔(`admin/`) / Python API(`src/`) → 로컬 JSON (`data/`)

두 저장소는 **자동으로 동기화되지 않는다.** 예약 관련 기능을 수정할 때는 어느 저장소를 대상으로 하는지 먼저 확인하고, 필요하면 양쪽 모두 반영해야 하는지 사용자에게 확인한다. (ARCHITECTURE.md §7, ROADMAP.md 참조)

## 답변 언어

이 프로젝트에서도 상위 폴더 규칙에 따라 기본적으로 한글로 답변한다.

## 개인정보 취급

`data/patients.json`, `data/reservations.json`, `data/businesses.json` 등은 PII(개인정보)를 포함한다. 외부 공유/커밋용 산출물 작성 시 이름·생년월일·전화번호·주민등록번호 등을 제거하거나 마스킹한다. 세션/로그에는 대화 원문이나 PII 원문을 남기지 않는다(DECISIONS.md ADR-006 참조).
