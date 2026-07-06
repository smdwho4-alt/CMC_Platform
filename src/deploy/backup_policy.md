# CSHSP 백업 정책 (Sprint H)

> 대상: `data/` 폴더 (20개 Entity JSON + sessions/ai_events/chat_histories). 내부 검토용.

## 1. 백업 대상·주기

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

## 3. 복구 절차 (RTO 30분 목표)
1. `nssm stop CSHSP-API`
2. 손상 확인: `python -c "import json; json.load(open('data/reservations.json', encoding='utf-8'))"`
3. `data/`를 `data_broken_YYYYMMDD/`로 이름 변경 (삭제 금지)
4. 최신 스냅샷 복사 → `data/`
5. 무결성 검증: `python src/core/data_validator.py` (오류 0건 확인)
6. `nssm start CSHSP-API` → health 확인 → 백업 시점 이후 예약은 감사로그 대조로 수기 복원

## 4. 점검
- 월 1회 복구 리허설 (스냅샷 → 임시 폴더 복원 → validator 실행)
- 백업 성공 여부 일일 확인 (스케줄러 결과 + 폴더 존재)
