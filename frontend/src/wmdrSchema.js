import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import { translate } from "./i18n/plain";
// Copy of backend/api/schemas/wmdr2-bundled.json (wmo-im/wmdr2 schemas/wmdr2-bundled.json).
// The frontend container only mounts ./frontend, so it can't import the backend copy.
import schema from "./schemas/wmdr2-bundled.json";

// strict: false because the bundled schema uses the non-standard "example" keyword.
const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
const validate = ajv.compile(schema);

// "/properties/contacts/0/phones/0/value" -> "contacts[1].phones[1].value".
// Indices are 1-based to match the "Contact 1" style labels in the form, and
// the leading "properties" segment is dropped since that's where most fields live.
const COORDINATE_NAMES = ["longitude", "latitude", "height"];

function formatPath(instancePath, missingProperty) {
  const segments = instancePath.split("/").filter(Boolean);
  if (missingProperty) segments.push(missingProperty);
  if (segments[0] === "properties" && segments.length > 1) segments.shift();
  const last = segments.length - 1;
  if (segments[last - 1] === "coordinates" && COORDINATE_NAMES[segments[last]]) {
    segments.splice(last - 1, 2, COORDINATE_NAMES[segments[last]]);
  }
  return segments.reduce(
    (path, segment) => (/^\d+$/.test(segment) ? `${path}[${Number(segment) + 1}]` : path ? `${path}.${segment}` : segment),
    ""
  ) || "record";
}

function isNoise(error) {
  // Combinators only report "must match a schema"; the useful error is the
  // branch-specific one alongside it.
  if (["oneOf", "anyOf", "allOf"].includes(error.keyword)) return true;
  // Concepts and times are `oneOf: [object, null]`, so every invalid object
  // also fails the null branch - that failure isn't worth showing.
  if (error.keyword === "enum" && error.params.allowedValues?.length === 1 && error.params.allowedValues[0] === null) {
    return true;
  }
  return false;
}

// JSON Schema type and format names that occur in wmdr2-bundled.json, mapped to
// the message keys that name them in the UI language.
const TYPE_NAMES = {
  string: "schema.typeString",
  number: "schema.typeNumber",
  integer: "schema.typeInteger",
  object: "schema.typeObject",
  array: "schema.typeArray",
  boolean: "schema.typeBoolean",
  null: "schema.typeNull",
};

// Date and time, URI, email — the formats the bundled schema uses.
const FORMAT_NAMES = {
  date: "schema.formatDate",
  "date-time": "schema.formatDateTime",
  uri: "schema.formatUri",
  email: "schema.formatEmail",
};

// Every keyword wmdr2-bundled.json actually uses is covered here; anything
// else falls back to ajv's own English wording rather than being dropped,
// since a validator error is better shown than swallowed.
function formatMessage(error) {
  switch (error.keyword) {
    case "required":
      return translate("schema.required");
    case "pattern":
      return translate("schema.pattern");
    case "minItems":
      return translate("schema.minItems", { limit: error.params.limit });
    case "maxItems":
      return translate("schema.maxItems", { limit: error.params.limit });
    case "contains":
      return translate("schema.contains");
    case "uniqueItems":
      return translate("schema.uniqueItems");
    case "format":
      return translate("schema.format", { format: translate(FORMAT_NAMES[error.params.format] || "schema.formatOther") });
    case "enum":
      return translate("schema.enum", { values: (error.params.allowedValues || []).join(", ") });
    case "const":
      return translate("schema.const", { value: error.params.allowedValue });
    case "additionalProperties":
      return translate("schema.additionalProperties", { property: error.params.additionalProperty });
    case "type": {
      const types = Array.isArray(error.params.type) ? error.params.type : [error.params.type];
      const names = types.map((type) => translate(TYPE_NAMES[type] || "schema.typeOther")).join(translate("schema.or"));
      return translate("schema.type", { type: names });
    }
    default:
      return error.message;
  }
}

// Returns a list of human-readable errors, empty when the record is valid.
export function validateWmdrRecord(record) {
  if (validate(record)) return [];
  const messages = validate.errors
    .filter((error) => !isNoise(error))
    .map((error) => `${formatPath(error.instancePath, error.params.missingProperty)} ${formatMessage(error)}`);
  return [...new Set(messages)];
}
