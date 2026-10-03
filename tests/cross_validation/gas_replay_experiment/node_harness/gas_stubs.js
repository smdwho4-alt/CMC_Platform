// GAS 서비스 테스트용 스텁 — 로컬 Node 전용, 실제 GAS를 대체하지 않는다.
// ContentService/Utilities는 실제 서명 검증(verifyV2_)이 동작하도록
// Node crypto로 HMAC/SHA-256을 실제로 계산한다(가짜 성공을 리턴하지
// 않음). CacheService/PropertiesService/LockService는 이번 테스트
// 범위(파싱 단계·서명 단계에서 끝나는 경로)에서는 호출되지 않지만,
// 혹시 도달할 경우를 대비해 최소 동작하는 Map 기반 스텁을 둔다.
var crypto = require("crypto");

global.Utilities = {
  computeHmacSha256Signature: function (str, secret) {
    var mac = crypto.createHmac("sha256", secret).update(str, "utf8").digest();
    return Array.from(mac);
  },
  computeDigest: function (_algo, str) {
    var hash = crypto.createHash("sha256").update(str, "utf8").digest();
    return Array.from(hash);
  },
  DigestAlgorithm: { SHA_256: "SHA_256" },
  Charset: { UTF_8: "UTF_8" },
  newBlob: function (str) {
    return { getBytes: function () { return Array.from(Buffer.from(str, "utf8")); } };
  },
};

global.ContentService = {
  MimeType: { JSON: "JSON" },
  createTextOutput: function (text) {
    var output = {
      _content: text,
      setMimeType: function () { return output; },
      getContent: function () { return output._content; },
    };
    return output;
  },
};

global.Logger = { log: function () {} };

function makeCacheStub() {
  var store = {};
  return {
    get: function (k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
    put: function (k, v) { store[k] = v; },
    remove: function (k) { delete store[k]; },
  };
}
function makePropsStub() {
  var store = {};
  return {
    getProperty: function (k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
    setProperty: function (k, v) { store[k] = v; },
    deleteProperty: function (k) { delete store[k]; },
  };
}
var _scriptCacheSingleton = makeCacheStub();
var _scriptPropsSingleton = makePropsStub();
global.CacheService = { getScriptCache: function () { return _scriptCacheSingleton; } };
global.PropertiesService = { getScriptProperties: function () { return _scriptPropsSingleton; } };

var _scriptLockState = { locked: false };
global.LockService = {
  getScriptLock: function () {
    return {
      tryLock: function () {
        if (_scriptLockState.locked) return false;
        _scriptLockState.locked = true;
        return true;
      },
      releaseLock: function () { _scriptLockState.locked = false; },
      hasLock: function () { return _scriptLockState.locked; },
    };
  },
};
