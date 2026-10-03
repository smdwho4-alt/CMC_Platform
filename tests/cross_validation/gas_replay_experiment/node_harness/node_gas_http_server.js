// 실제 GAS 코드(../gas_candidate/, 스텁 포함)를 실제 HTTP 서버로 감싼다 —
// 기존(수정하지 않은) Python 드라이버가 실제 와이어 형식 그대로 이
// 서버를 때릴 수 있게 하기 위함이다. 이것도 GAS가 아니다 — 로컬 Node
// 기반 E2E 검증용이다.
//
// gas_candidate/*.gs를 매번 직접 읽어서 연결한다(별도로 미리 만들어둔
// "병합 산출물" 파일에 의존하지 않는다) — 이렇게 하면 저장소에는
// gas_candidate/의 개별 소스만 남고, 이 서버는 항상 그 소스 그대로를
// 실행한다(소스와 실행 대상이 갈라질 일이 없음).
require("./gas_stubs.js");
var fs = require("fs");
var path = require("path");
var http = require("http");

var GAS_CANDIDATE_DIR = path.join(__dirname, "..", "gas_candidate");
// GAS가 프로젝트의 모든 .gs를 하나의 전역 스코프로 합치는 것과 동일한
// 순서(알파벳순, clasp filePushOrder:[] 기본값과 동일하게 추정) —
// 로컬 검증에서 실제로 이 순서로 중복 선언·초기화 오류 없음을 확인했다.
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

var concatenatedSrc = GAS_FILE_ORDER.map(function (name) {
  return fs.readFileSync(path.join(GAS_CANDIDATE_DIR, name), "utf8");
}).join("\n\n");
// eslint-disable-next-line no-eval
eval(concatenatedSrc); // doPost/doGet/doPost_/doStatus_ 등이 이 스코프에 선언됨

var server = http.createServer(function (req, res) {
  if (req.method === "GET") {
    var out = doGet({});
    var body = out.getContent();
    res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
    res.end(body);
    return;
  }
  if (req.method === "POST") {
    var chunks = [];
    req.on("data", function (c) { chunks.push(c); });
    req.on("end", function () {
      var contents = Buffer.concat(chunks).toString("utf8");
      var out = doPost({ postData: { contents: contents } });
      var body = out.getContent();
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(body);
    });
    return;
  }
  res.writeHead(405);
  res.end();
});

var port = process.env.NODE_GAS_SERVER_PORT ? parseInt(process.env.NODE_GAS_SERVER_PORT, 10) : 0;
server.listen(port, "127.0.0.1", function () {
  console.log("NODE_GAS_HTTP_SERVER_LISTENING_ON=" + server.address().port);
});
