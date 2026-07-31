# CSHSP 백업 정책 (Sprint H, Sprint7 Commit7-4에서 Google Sheets SSOT 반영 갱신)

> 최초 대상: `data/` 폴더 (20개 Entity JSON + sessions/ai_events/chat_histories). 내부 검토용.
> **Sprint7 Commit7-4 갱신 안내**: 최초 작성 시점(Sprint H)에는 예약(Reservation) 데이터도 `data/reservations.json`이 원장이었으나, ADR-013(Sprint4)으로 **예약 SSOT가 Google Sheets로 이전**됐다. 아래 §1~4(로컬 JSON 백업)는 `Patient`/`CRM`/`AuditLog` 등 여전히 로컬 JSON이 원장인 19개 Entity에 대해서는 그대로 유효하다. **예약 데이터 백업은 §5(신설)를 함께 참조할 것** — 로컬 JSON 백업만으로는 예약 데이터가 보호되지 않는다.

## 1. 백업 대상·주기(로컬 JSON, Reservation 제외 19개 Entity + Reservation 로컬 사본)

| 대상 | 주기 | 보존 | 방법 |
|------|------|------|------|
| `data/*.json` 전체 | **일 1회 (검진 종료 후 18:30)** | 30일 | 날짜 폴더 스냅샷 복사 |
| `data/audit_logs.json` | 일 1회 (동일 스냅샷) | **1년** (감사 목적 별도 보관) | 스냅샷에서 분리 보관 |
| 코드(프로젝트 폴더) | 배포 시마다 | 최근 5개 버전 | 배포 전 zip |
| 예약 변동 실시간 보호 | 상시 | — | 쓰기 잠금(.cshsp.lock) + 임시파일 교체 저장으로 파일 파손 방지 |

예시 (작업 스케줄러 일일 실행):
```powershell
$d = Get-Date -Format 'yyyyMMdd'
Copy-Item -Recurse D:\CSHSP\data "D:\CSHSP\backup\$d"
Get-ChildItem D:\CSHSP\backup | Where-Object { $_.Name -lt (Get-Date).AddDays(-30).ToString('yyyyMMdd') } | Remove-Item -Recurse
```

## 2. 개인정보 보호
- 백업본은 환자 더미/실데이터를 포함 → **백업 드라이브는 BitLocker 암호화 + 접근권한 검진센터 담당자 한정**
- 외부 반출 금지, 클라우드 업로드 시 병원 개인정보처리방침 검토 선행
- 세션(sessions.json)·대화(chat_histories.json)는 백업 제외 가능(휘발성 상태) — 포함 시 동일 보호
- **⛔ 개인정보를 GitHub(원격 저장소)에 저장하지 않는다** — 백업 스냅샷·실제 운영 Sheets 사본을 이 프로젝트 저장소에 커밋하지 않는다(Sprint7 Commit7-4에서 명문화, 이전에도 암묵적으로 지켜진 원칙이나 문서에 명시되지 않았었음)
- **⛔ 실제 운영 Google Sheets 사본을 저장소에 커밋하지 않는다**(§5 참조 — Sheets 백업은 별도 위치·별도 절차)

## 3. 복구 절차 (RTO 30분 목표, 로컬 JSON 대상)
1. `nssm stop CSHSP-API`
2. 손상 확인: `python -c "import json; json.load(open('data/reservations.json', encoding='utf-8'))"` (⚠ 이 파일은 더 이상 예약의 SSOT가 아니며 로컬 사본/Fixture 용도다 — Sheets 손상 여부는 이 검사로 알 수 없다, §5 참조)
3. `data/`를 `data_broken_YYYYMMDD/`로 이름 변경 (삭제 금지)
4. 최신 스냅샷 복사 → `data/`
5. 무결성 검증: `python src/core/data_validator.py` (오류 0건 확인) — **실제로 2026-07-29 재실행해 확인함**(`tests/run_backup_restore_rehearsal.py`, 9/9 PASS, `Operation_Readiness_Assessment_v1.0.md` §3-3)
6. `nssm start CSHSP-API` → health 확인 → 백업 시점 이후 예약은 감사로그 대조로 수기 복원

## 4. 점검(로컬 JSON)
- 월 1회 복구 리허설 (스냅샷 → 임시 폴더 복원 → validator 실행)
- 백업 성공 여부 일일 확인 (스케줄러 결과 + 폴더 존재)

## 5. Google Sheets(예약 SSOT) 백업 — 신설, Sprint7 Commit7-4

ADR-013(Sprint4)으로 예약(Reservation) 데이터의 SSOT가 Google Sheets로 이전됐으나, **이 정책 문서에는 그동안 Sheets 백업 항목이 없었다**(`Operation_Readiness_Assessment_v1.0.md` Gap #6에서 확인된 공백). 이번 갱신에서 확인 가능한 사실과 **미확정 사항을 명확히 구분**해 기록한다(추측으로 정책을 만들지 않음).

### 5-1. 확인된 사실
- Google Sheets는 자체적으로 **버전 기록(파일 히스토리)** 기능을 제공한다(Google Workspace 표준 기능) — 별도 구현 없이도 일정 기간 이전 상태로 되돌아볼 수 있는 최소한의 안전망은 존재한다.
- `google_sheets_service_v2_new.js`/GAS(`sheets_api_v3_final.gs`)의 쓰기 액션(`updateStatus`/`update`)은 이전 값을 별도로 보존하지 않고 덮어쓴다(코드로 확인, `Legacy_Stage3_PhaseB_Design_v1.0.md` §6) — 애플리케이션 레벨의 변경 이력 저장은 없다.

### 5-2. Decision Required(이 문서에서 임의로 확정하지 않음)
- [ ] Sheets 버전 기록을 몇 일치 보존할지, 별도 정기 내보내기(CSV export 등)를 추가할지 — **미확정**
- [ ] Sheets 백업/복구 책임자 — **미확정**(§3의 로컬 JSON 복구 책임자도 동일하게 미확정 상태, `CSHSP_Failure_Response_Manual.md` §3 연락망 참조)
- [ ] Sheets 복구 시 "성공 기준"(예: 행 수 대조, 감사로그 대조) — **미확정**, 로컬 JSON의 §3-5(validator 0건) 같은 명확한 기준이 Sheets에는 아직 없음
- [ ] 보존 기간 — 로컬 JSON은 30일/1년(§1)로 명확하나 **Sheets 자체 버전 기록의 보존 기간은 Google Workspace 관리자 설정에 따라 다르며 이 프로젝트에서 확인되지 않음**

### 5-3. 임시 권고(정책 확정 전까지, 강제 아님)
- 대규모 데이터 변경(예: 일괄 상태 수정) 전에는 수동으로 시트를 사본으로 복사해 두는 것을 권장(Google Sheets 자체 기능, "사본 만들기")
- 이 사본은 로컬 JSON 백업과 동일하게 **저장소에 커밋하지 않는다**(§2)
