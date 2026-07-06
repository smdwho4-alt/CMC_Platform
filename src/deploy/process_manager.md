# CSHSP 운영 배포 — 프로세스 관리 가이드 (Sprint H)

> 대상: 병원 내부망 Windows 서버 1대 기준 파일럿 운영. 내부 검토용.

## 1. 구성 요소

| 구성 | 실행 | 포트 | 비고 |
|------|------|------|------|
| API 서버 | `python -m uvicorn src.api.api_server:app --host 127.0.0.1 --port 8600` | 8600 | Reservation Engine + Agents |
| 정적 서버 | `npx serve -p 4000 CMC_Platform_new` (또는 IIS/nginx 정적 호스팅) | 4000 | admin/, chat/, app/ |
| 알림 워커 | `python src\workers\notification_worker.py` (스케줄 실행) | — | PENDING → SENT/FAILED |

## 2. 운영 환경변수 목록

| 변수 | 필수 | 설명 |
|------|:---:|------|
| `CSHSP_DATA_DIR` | 권장 | 데이터 폴더 절대경로 (기본: 프로젝트 `data/`) |
| `ANTHROPIC_API_KEY` | 선택 | 설정 시 채팅이 Claude tool_loop 경로로 자동 전환. **코드/문서에 값 기록 금지, 서버 환경변수(시스템 속성 또는 서비스 계정)로만 설정** |
| `CSHSP_CLAUDE_MODEL` | 선택 | 기본 `claude-opus-4-8` |
| `CSHSP_CHAT_RATE` | 선택 | 채팅 요청 제한 `횟수/초` (기본 30/60) |
| `PYTHONIOENCODING` | 권장 | `utf-8` |

## 3. 프로세스 매니저 (Windows)

### 권장: NSSM (Non-Sucking Service Manager)으로 Windows 서비스 등록
```
nssm install CSHSP-API "C:\...\python.exe" "-m uvicorn src.api.api_server:app --host 127.0.0.1 --port 8600"
nssm set CSHSP-API AppDirectory "D:\CSHSP\CMC_Platform_new"
nssm set CSHSP-API AppEnvironmentExtra CSHSP_DATA_DIR=D:\CSHSP\data PYTHONIOENCODING=utf-8
nssm set CSHSP-API AppExit Default Restart        # 비정상 종료 시 자동 재시작
nssm set CSHSP-API AppStdout D:\CSHSP\logs\api.out.log
nssm set CSHSP-API AppStderr D:\CSHSP\logs\api.err.log
```
- 대안: 작업 스케줄러(로그온 없이 실행 + 실패 시 재시작), IIS + httpPlatformHandler
- 워커: 작업 스케줄러로 5분 주기 `notification_worker.py` 실행

### HTTPS
- uvicorn은 127.0.0.1 바인딩 → 앞단에 **IIS(ARR) 또는 nginx 리버스 프록시**를 두고
  거기서 TLS 종료(사내 CA 인증서) + 외부 노출 차단
- 관리자 콘솔·API는 내부망 전용, 수검자용 chat만 프록시 경유 공개 검토

## 4. 로그 정책
- API stdout/err 로그는 일 단위 로테이션(NSSM AppRotate) + 30일 보관
- **개인정보 원문 로그 금지** — 애플리케이션 로그는 privacy_logger(mask_pii) 경유
- 감사로그(audit_logs.json)는 append-only, 백업 대상

## 5. 재기동·업데이트 절차
1. `nssm stop CSHSP-API` → data/ 백업(백업 정책 참조) → 코드 교체 → 테스트 실행
   (`python tests/run_sprint_d_tests.py` 등) → `nssm start CSHSP-API`
2. health 확인: `http://127.0.0.1:8600/api/health`
