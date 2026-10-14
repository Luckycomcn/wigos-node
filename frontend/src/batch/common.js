import { WIGOS_ID_PATTERN } from "../wmdr";
import { codelistOptions } from "../codelists";
import { toCsv } from "../csv";

// Shared pieces of the batch operations. A grid row is
//   { id, stationId, cells: { [column]: string }, original: { [column]: string }, ...position }
// Every cell is a string, so the grid, the clipboard and CSV/XLSX files all
// handle the same values. Codelist cells hold the concept's notation.

// ---------------------------------------------------------------------------
// Columns

// Kinds: key (read-only), text, number, numbers (";"-list of numbers), date
// (interval bound), codelist, wsi, wsis (";"-list of WIGOS IDs).
export const KEY_COLUMNS = {
  wigosId: { key: "wigos_id", label: "WIGOS ID", kind: "key", width: 170 },
  stationName: { key: "station_name", label: "Station", kind: "key", width: 180 },
  observedProperty: { key: "observed_property", label: "Observed property", kind: "key", width: 200 },
};

export const isEditable = (column) => column.kind !== "key";

// A column with `lockedOnExisting` identifies existing rows (e.g. the
// programme of an affiliation) and can only be set on rows being added.
export const isCellEditable = (column, row) => isEditable(column) && !(column.lockedOnExisting && !row?.isNew);

// ---------------------------------------------------------------------------
// Lists

export const LIST_SEPARATOR = ";";

export const splitList = (text) =>
  (text ?? "")
    .split(LIST_SEPARATOR)
    .map((item) => item.trim())
    .filter(Boolean);

export const joinList = (items) => (items || []).map(String).join(LIST_SEPARATOR);

// ---------------------------------------------------------------------------
// Concepts and codelists

// Same codelist entry: on the concept URI when both have one (notations can
// collide across codelists), otherwise on the notation.
export function sameConcept(a, b) {
  if (!a || !b) return !a && !b;
  if (a.url && b.url) return a.url === b.url;
  return String(a.id ?? "") === String(b.id ?? "");
}

export const conceptCell = (concept) => (concept?.id != null ? String(concept.id) : "");

// The codelist entry a cell refers to, by notation, label or URI.
export function findCodelistOption(options, text) {
  const value = (text ?? "").trim();
  if (!value) return null;
  const lower = value.toLowerCase();
  return (
    options.find((opt) => opt.code === value) ||
    options.find((opt) => opt.label.toLowerCase() === lower) ||
    options.find((opt) => opt.id && opt.id === value) ||
    options.find((opt) => opt.code.toLowerCase() === lower) ||
    null
  );
}

function conceptFromOption(opt) {
  const concept = { id: opt.code, title: opt.label };
  if (opt.description) concept.description = opt.description;
  if (opt.id) concept.url = opt.id;
  return concept;
}

// The concept to store for a codelist cell. The previous concept is kept
// when the cell still names it, so its title/description/url aren't rewritten.
export function conceptForCell(text, options, previous) {
  const value = (text ?? "").trim();
  if (!value) return null;
  if (previous && conceptCell(previous) === value) return previous;
  const opt = findCodelistOption(options, value);
  return opt ? conceptFromOption(opt) : { id: value };
}

// Label shown in the grid for a codelist cell.
export function codelistLabel(options, text) {
  const opt = findCodelistOption(options, text);
  return opt ? opt.label : text;
}

// Normalizes a typed, pasted or imported value: codelist labels become
// notations; everything is trimmed.
export function normalizeCell(column, text, codelists) {
  const value = (text ?? "").toString().trim();
  if (column.kind === "codelist" && value) {
    const opt = findCodelistOption(codelistOptions(column.codelist, codelists), value);
    return opt ? opt.code : value;
  }
  if (column.kind === "numbers" || column.kind === "wsis") return joinList(splitList(value));
  return value;
}

// ---------------------------------------------------------------------------
// Cell validation (the schema check on the whole record runs again before saving)

// Formats allowed for an interval bound / affiliation date (wmdr2-bundled.json).
const DATE_PATTERNS = [
  /^\d{4}-\d{2}-\d{2}$/,
  /^\d{4}-\d{2}$/,
  /^\d{4}$/,
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/,
  /^T\d{2}(:\d{2})?(:\d{2})?(?:\.\d+)?Z$/,
];

const isNumber = (text) => text.trim() !== "" && !Number.isNaN(Number(text));

// Returns the reason a cell is invalid, or null.
export function cellError(column, text, codelists) {
  const value = (text ?? "").trim();
  if (!value) return column.required ? "Required" : null;
  switch (column.kind) {
    case "number":
      return isNumber(value) ? null : "Must be a number";
    case "numbers":
      return splitList(value).every(isNumber) ? null : `Must be numbers separated by "${LIST_SEPARATOR}"`;
    case "date":
      return DATE_PATTERNS.some((p) => p.test(value)) ? null : "Use YYYY-MM-DD, YYYY-MM, YYYY or a UTC timestamp";
    case "wsi":
      return WIGOS_ID_PATTERN.test(value) ? null : "Not a valid WIGOS identifier";
    case "wsis": {
      const bad = splitList(value).filter((id) => !WIGOS_ID_PATTERN.test(id));
      return bad.length ? `Not a valid WIGOS identifier: ${bad.join(", ")}` : null;
    }
    case "codelist": {
      const options = codelistOptions(column.codelist, codelists);
      // While a codelist is unavailable any notation is accepted.
      return !options.length || findCodelistOption(options, value) ? null : "Not in the codelist";
    }
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Rows

export const isCellChanged = (row, key) => (row.cells[key] ?? "") !== (row.original[key] ?? "");

export const changedColumns = (row, columns) =>
  columns.filter((column) => isEditable(column) && isCellChanged(row, column.key)).map((column) => column.key);

// Value, edit and error state of one cell. `cellStatus(row, column)` may add
// an operation's own { error, hint } (e.g. WIGOS ID availability).
export function cellState(row, column, codelists, cellStatus) {
  const value = row.cells[column.key] ?? "";
  const extra = cellStatus?.(row, column) || {};
  return {
    value,
    changed: isEditable(column) && isCellChanged(row, column.key),
    editable: isCellEditable(column, row),
    error: isEditable(column) ? cellError(column, value, codelists) || extra.error || null : null,
    hint: extra.hint || null,
  };
}

// Invalid cells that stop Apply: the ones the user changed, and any cell of
// a new row being added. A stored value that is already invalid (e.g. a
// notation missing from the codelist) is still marked, but doesn't block
// editing the rest.
export function blockingCellCount(columns, rows, codelists, cellStatus) {
  return rows.reduce((count, row) => {
    const sent = row.isNew && changedColumns(row, columns).length > 0;
    return (
      count +
      columns.filter((column) => {
        const state = cellState(row, column, codelists, cellStatus);
        return state.error && (state.changed || sent);
      }).length
    );
  }, 0);
}

export function stationKeys(entry) {
  return { wigos_id: entry.record.id || "", station_name: entry.record.properties?.title || "" };
}

export const observedPropertyLabel = (observation) =>
  observation.observedProperty?.title || conceptCell(observation.observedProperty);

// Other values a file may use for a row's key cells: the observed property
// can be given by its title (as shown), notation or URI.
export const observationAliases = (observation) => ({
  observed_property: [conceptCell(observation.observedProperty), observation.observedProperty?.url].filter(Boolean),
});

// `id` is internal (React keys, selection); files identify rows by their
// key columns instead, see sheetIO.mergeSheet.
export function makeRow(id, stationId, keys, values, extra = {}) {
  const cells = { ...keys, ...values };
  return { id, stationId, cells, original: { ...cells }, ...extra };
}

// Applies the edited rows to copies of the records. `writeRow(record, row,
// changed)` writes a row's changed cells into the record copy. Records
// without edits are returned as they are.
export function applyRowsWith(entries, rows, columns, writeRow) {
  const byStation = new Map();
  rows.forEach((row) => {
    const changed = changedColumns(row, columns);
    if (!changed.length) return;
    if (!byStation.has(row.stationId)) byStation.set(row.stationId, []);
    byStation.get(row.stationId).push({ row, changed });
  });
  return entries.map((entry) => {
    const edits = byStation.get(entry.stationId);
    if (!edits) return entry;
    const record = structuredClone(entry.record);
    edits.forEach(({ row, changed }) => writeRow(record, row, new Set(changed)));
    return { ...entry, record };
  });
}

// Sets `key` on `obj`, or removes it for an empty value.
export function setOrDelete(obj, key, value) {
  const empty = value == null || value === "" || (Array.isArray(value) && !value.length);
  if (empty) delete obj[key];
  else obj[key] = value;
}

// [start, end] with ".." for an open bound, or null when both are empty.
export function datesFromCells(start, end) {
  if (!start && !end) return null;
  return [start || "..", end || ".."];
}

export const dateCell = (value) => (value && value !== ".." ? String(value) : "");

export const toNumber = (text) => (isNumber(text) ? Number(text) : text);

// ---------------------------------------------------------------------------
// Preview and results

const pathSegment = (path, key) => (typeof key === "number" ? `${path}[${key}]` : path ? `${path}.${key}` : key);

// Leaf-level differences between two records: { path, before, after }.
// A value that is missing on one side is undefined there.
export function diffRecord(before, after, path = "") {
  const isObject = (v) => v !== null && typeof v === "object";
  if (!isObject(before) || !isObject(after) || Array.isArray(before) !== Array.isArray(after)) {
    return JSON.stringify(before) === JSON.stringify(after) ? [] : [{ path: path || "record", before, after }];
  }
  // Short arrays of plain values (coordinates, intervals, lists) read better whole.
  if (Array.isArray(before) && [...before, ...after].every((v) => !isObject(v))) {
    return JSON.stringify(before) === JSON.stringify(after) ? [] : [{ path: path || "record", before, after }];
  }
  const keys = Array.isArray(before)
    ? [...Array(Math.max(before.length, after.length)).keys()]
    : [...new Set([...Object.keys(before), ...Object.keys(after)])];
  return keys.flatMap((key) => diffRecord(before[key], after[key], pathSegment(path, key)));
}

export function resultsToCsv(results) {
  return toCsv([
    ["station_id", "station_name", "wigos_id", "status", "message", "errors"],
    ...results.map((r) => [r.station_id, r.station_name ?? "", r.wsi ?? "", r.status, r.message ?? "", (r.errors || []).join(" | ")]),
  ]);
}
