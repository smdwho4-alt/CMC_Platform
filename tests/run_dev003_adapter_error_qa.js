/**
 * DEV-003 — 어댑터 error 필드 전달 검증 (Node, fetch 모의)
 *
 * google_sheets_service_v2_new.js의 _liveUpdateStatus/_liveUpdate가 백엔드의
 * {ok:false, error:'...', code:503} 응답에서 error 문자열을 그대로 전달하는지 확인한다.
 * 실제 네트워크 호출 없이 global.fetch를 스텁으로 교체해 검증한다.
 *
 * 실행: node tests/run_dev003_adapter_error_qa.js
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const CONFIG_FILE  = path.join(__dirname, '..', 'app', 'config_v2_new.js');
const ADAPTER_FILE = path.join(__dirname, '..', 'app', 'services', 'google_sheets_service_v2_new.js');
const RESULT_CSV   = path.join(__dirname, 'dev003_adapter_error_qa_result.csv');

function loadSandbox(fetchImpl) {
  const sandbox = { console, fetch: fetchImpl, URLSearchParams };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(CONFIG_FILE, 'utf8'), sandbox, { filename: CONFIG_FILE });
  vm.runInContext(fs.readFileSync(ADAPTER_FILE, 'utf8'), sandbox, { filename: ADAPTER_FILE });
  sandbox.CMC_CONFIG = vm.runInContext('CMC_CONFIG', sandbox);
  sandbox.CMC_SheetsServiceV2 = vm.runInContext('CMC_SheetsServiceV2', sandbox);
  sandbox.CMC_CONFIG.dataSource = 'google';
  sandbox.CMC_CONFIG.appsScript.webAppUrl = 'https://example.invalid/exec';
  return sandbox;
}

const results = [];
function check(name, condition, detail) {
  results.push({ name, pass: !!condition, detail: detail || '' });
  console.log(`${condition ? '✅ PASS' : '❌ FAIL'} — ${name}${detail ? ' — ' + detail : ''}`);
}

async function run() {
  const lockErrorBody = { ok: false, error: '동시 요청이 많아 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.', code: 503 };
  const fetchStub = async () => ({ ok: true, status: 200, json: async () => lockErrorBody });

  const s1 = loadSandbox(fetchStub);
  const r1 = await s1.CMC_SheetsServiceV2.updateStatus('20260810-0001', '예약확정');
  check('_liveUpdateStatus: 실패 시 error 문자열이 전달됨', r1.error === lockErrorBody.error, JSON.stringify(r1));
  check('_liveUpdateStatus: ok가 false로 전달됨', r1.ok === false, JSON.stringify(r1));

  const s2 = loadSandbox(fetchStub);
  const r2 = await s2.CMC_SheetsServiceV2.update('20260810-0001', { note: '메모' });
  check('_liveUpdate: 실패 시 error 문자열이 전달됨', r2.error === lockErrorBody.error, JSON.stringify(r2));

  const successBody = { ok: true, data: { reservationNo: '20260810-0001', status: '예약확정' }, message: '상태 변경 완료' };
  const fetchStubOk = async () => ({ ok: true, status: 200, json: async () => successBody });
  const s3 = loadSandbox(fetchStubOk);
  const r3 = await s3.CMC_SheetsServiceV2.updateStatus('20260810-0001', '예약확정');
  check('_liveUpdateStatus: 성공 시 error는 undefined(불필요한 필드 없음)', r3.error === undefined, JSON.stringify(r3));
  check('_liveUpdateStatus: 성공 시 data가 정상 전달됨', r3.data.reservationNo === '20260810-0001', JSON.stringify(r3));

  const failCount = results.filter(r => !r.pass).length;
  fs.writeFileSync(RESULT_CSV, ['name,pass,detail', ...results.map(r => `"${r.name}",${r.pass},"${(r.detail||'').replace(/"/g,'""')}"`)].join('\n'), 'utf8');
  console.log(`\n총 ${results.length}건 중 실패 ${failCount}건`);
  process.exit(failCount === 0 ? 0 : 1);
}
run();
