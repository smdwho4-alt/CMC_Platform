"use strict";
/**
 * Commit8-3b payload 정규화 계약 — 요청별 스키마 가드(JS 참조구현)
 *
 * src/idempotency/request_payload_schemas.py와 동일 레지스트리를
 * 독립 구현한 Node.js 포트다(교차검증 전용). 조사 근거·자유형 dict
 * 제외·미등록 operation 거절 원칙은 Python 쪽 모듈 docstring과 동일.
 */

class RequestSchemaError extends Error {
  constructor(reason, fieldName, detail) {
    const msg = reason + (fieldName ? ` (field: ${fieldName})` : "") + (detail ? ` ${detail}` : "");
    super(msg);
    this.reason = reason;
    this.field = fieldName || null;
  }
}

function field(name, required, types, opts) {
  opts = opts || {};
  return {
    name,
    required,
    types, // 예: ["string"], ["number"], ["boolean"]
    allowsNull: !!opts.allowsNull,
    minLen: opts.minLen === undefined ? null : opts.minLen,
    maxLen: opts.maxLen === undefined ? null : opts.maxLen,
  };
}

const SCHEMAS = {
  reservation_create: {
    source: "src/api/api_server.py:75 ReservationCreate",
    fields: [
      field("patientId", true, ["string"]),
      field("programId", true, ["string"]),
      field("requestedDate", true, ["string"]),
      field("requestedTime", true, ["string"]),
      field("slotId", true, ["string"]),
      field("channel", false, ["string"]),
      field("allowWaiting", false, ["boolean"]),
      field("memo", false, ["string"], { allowsNull: true }),
    ],
  },
  reservation_cancel: {
    source: "src/api/api_server.py:86 ReasonBody",
    fields: [field("reason", false, ["string"])],
  },
  reservation_change: {
    source: "src/api/api_server.py:90 ChangeBody",
    fields: [
      field("newSlotId", true, ["string"]),
      field("newDate", true, ["string"]),
      field("newTime", true, ["string"]),
      field("reason", false, ["string"]),
    ],
  },
  slot_generate: {
    source: "src/api/api_server.py:97 SlotGenerateBody",
    fields: [
      field("startDate", true, ["string"]),
      field("endDate", true, ["string"]),
      field("roomId", false, ["string"]),
      // capacity: 실제 모델에 범위 제약 없음 — 공통 가드의 안전정수범위
      // 이상을 임의로 요구하지 않는다.
      field("capacity", false, ["number"]),
    ],
  },
  consultation_status_update: {
    source: "src/api/routes_admin_portal.py:112 ConsultationStatusBody",
    fields: [field("status", true, ["string"]), field("handledBy", false, ["string"], { allowsNull: true })],
  },
  reservation_reject: {
    source: "src/api/routes_admin_portal.py:126 RejectReservationBody",
    fields: [
      // 실제 코드(_validate_reason)가 길이 2~200자를 명시적으로 검증함
      // — 그 범위를 그대로 재확인(발명 아님).
      field("reason", true, ["string"], { minLen: 2, maxLen: 200 }),
    ],
  },
  questionnaire_review: {
    source: "src/api/api_server.py:119 QReviewBody",
    fields: [field("decision", true, ["string"]), field("note", false, ["string"])],
  },
  crm_notification: {
    source: "src/api/api_server.py:124 CrmNotificationBody",
    fields: [
      field("patientId", true, ["string"]),
      field("reservationId", false, ["string"], { allowsNull: true }),
      field("type", false, ["string"]),
      field("templateCode", false, ["string"]),
      field("content", true, ["string"]),
      field("crmCategory", false, ["string"]),
      field("crmSummary", false, ["string"], { allowsNull: true }),
    ],
  },
};

function jsTypeOf(value) {
  if (typeof value === "boolean") return "boolean";
  if (typeof value === "number") return "number";
  if (typeof value === "string") return "string";
  return typeof value;
}

function validateRequestSchema(operation, payload) {
  const schema = SCHEMAS[operation];
  if (!schema) {
    throw new RequestSchemaError("UNKNOWN_OPERATION", null, `operation=${operation}`);
  }

  const allowedNames = new Set(schema.fields.map((f) => f.name));
  for (const key of Object.keys(payload)) {
    if (!allowedNames.has(key)) {
      throw new RequestSchemaError("UNREGISTERED_FIELD", key, `(operation=${operation})`);
    }
  }

  for (const f of schema.fields) {
    if (!Object.prototype.hasOwnProperty.call(payload, f.name)) {
      if (f.required) {
        throw new RequestSchemaError("REQUIRED_FIELD_MISSING", f.name, `(operation=${operation})`);
      }
      continue;
    }
    const value = payload[f.name];
    if (value === null) {
      if (!f.allowsNull) {
        throw new RequestSchemaError("NULL_NOT_ALLOWED", f.name);
      }
      continue;
    }
    const actualType = jsTypeOf(value);
    if (!f.types.includes(actualType)) {
      throw new RequestSchemaError("FIELD_TYPE_MISMATCH", f.name);
    }
    if (actualType === "string") {
      if (f.minLen !== null && value.length < f.minLen) {
        throw new RequestSchemaError("FIELD_TOO_SHORT", f.name, `min=${f.minLen}`);
      }
      if (f.maxLen !== null && value.length > f.maxLen) {
        throw new RequestSchemaError("FIELD_TOO_LONG", f.name, `max=${f.maxLen}`);
      }
    }
  }
}

function listKnownOperations() {
  return Object.keys(SCHEMAS).sort();
}

module.exports = { RequestSchemaError, validateRequestSchema, listKnownOperations, SCHEMAS };
