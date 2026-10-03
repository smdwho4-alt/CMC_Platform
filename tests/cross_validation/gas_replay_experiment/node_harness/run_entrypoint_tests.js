// entrypoint_tests.js를 저장소 경로에서 단독 실행 가능하게 만드는
// 최소 실행기. entrypoint_tests.js는 혼자 실행할 수 없다(그 파일
// 주석 참고) — gas_stubs.js와 ../gas_candidate/*.gs를 먼저 같은
// 전역 스코프에 로드한 뒤 이어서 평가(eval)해야 doGet/doPost/signV2_
// 등을 참조할 수 있다. node_gas_http_server.js의 GAS_FILE_ORDER와
// 반드시 동일한 순서를 쓴다(두 곳이 갈라지면 실행 대상이 갈라짐).
var fs = require("fs");
var path = require("path");

var HARNESS_DIR = __dirname;
var CANDIDATE_DIR = path.join(__dirname, "..", "gas_candidate");

var GAS_FILE_ORDER = [
  "AdminOnly_ManualCacheRemoval.gs",
  "ExperimentConfig.gs",
  "JsonStrictParser.gs",
  "Main_doPost_stub.gs",
  "NonceTtlBoundary.gs",
  "RealEntryPoint.gs",
  "ServerBudgetGuard.gs",
  "SignatureV2Port.gs",
  "TestKeyRegistry.gs",
  "VariantA_CacheLock.gs",
  "VariantB_PropertiesLock.gs",
];

var stubsSrc = fs.readFileSync(path.join(HARNESS_DIR, "gas_stubs.js"), "utf8");
var candidateSrc = GAS_FILE_ORDER.map(function (name) {
  return fs.readFileSync(path.join(CANDIDATE_DIR, name), "utf8");
}).join("\n\n");
var testSrc = fs.readFileSync(path.join(HARNESS_DIR, "entrypoint_tests.js"), "utf8");

// eslint-disable-next-line no-eval
eval(stubsSrc + "\n\n" + candidateSrc + "\n\n" + testSrc);
