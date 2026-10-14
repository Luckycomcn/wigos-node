import { parseCsvRows, toCsv } from "../csv";
import { isCellEditable, isEditable, normalizeCell } from "./common";

// CSV / Excel export and import of a batch grid. Files have one column per
// grid column, headed by the column key. Import updates the grid rows it
// matches on the operation's key columns (see mergeSheet); it never adds
// stations, observations or configurations.

// SheetJS is only downloaded when a user exports or imports an Excel file.
const loadXlsx = () => import("xlsx");

export function sheetTable(columns, rows) {
  return [columns.map((column) => column.key), ...rows.map((row) => columns.map((column) => row.cells[column.key] ?? ""))];
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

// The BOM makes Excel open the CSV as UTF-8.
export const csvBlob = (text) => new Blob(["﻿", text], { type: "text/csv;charset=utf-8" });

export async function exportSheet(columns, rows, format, basename) {
  const table = sheetTable(columns, rows);
  if (format === "csv") {
    downloadBlob(csvBlob(toCsv(table)), `${basename}.csv`);
    return;
  }
  const XLSX = await loadXlsx();
  // Every cell is written as text so Excel doesn't turn IDs or dates into numbers.
  const sheet = XLSX.utils.aoa_to_sheet(table.map((row) => row.map((value) => ({ t: "s", v: String(value) }))));
  sheet["!cols"] = columns.map((column) => ({ wch: Math.max(10, Math.round((column.width || 140) / 7)) }));
  const book = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book, sheet, "Batch");
  XLSX.writeFile(book, `${basename}.xlsx`);
}

// File -> rows of strings (first sheet for Excel files).
export async function readSheet(file) {
  if (/\.csv$/i.test(file.name) || file.type === "text/csv") {
    return parseCsvRows(await file.text());
  }
  const XLSX = await loadXlsx();
  const book = XLSX.read(await file.arrayBuffer());
  const sheet = book.Sheets[book.SheetNames[0]];
  return XLSX.utils.sheet_to_json(sheet, { header: 1, raw: false, defval: "" }).map((row) => row.map(String));
}

// Applies an imported table to the grid rows. `sheet` is the operation
// module: its `columns`, the `importKeys` that identify a row, and optionally
// `importParentKeys` + `newRowFor` to add rows (affiliations: a programme and
// start date the observation doesn't have yet). Headers may be column keys or
// labels. Returns the updated rows and a report:
//   { matched, added, changedCells, unmatched: [descriptions], unknownHeaders, error }
export function mergeSheet(table, sheet, rows, codelists) {
  const { columns, importKeys, importParentKeys, newRowFor } = sheet;
  const [header = [], ...body] = table;
  const byName = new Map();
  columns.forEach((column) => {
    byName.set(column.key.toLowerCase(), column);
    byName.set(column.label.toLowerCase(), column);
  });
  const fileColumns = header.map((name) => byName.get(String(name).trim().toLowerCase()) || null);
  const report = {
    matched: 0,
    added: 0,
    changedCells: 0,
    unmatched: [],
    unknownHeaders: header.filter((name, i) => String(name).trim() && !fileColumns[i]).map(String),
    error: null,
  };

  const columnOf = (key) => columns.find((column) => column.key === key);
  const indexOf = (key) => fileColumns.findIndex((column) => column?.key === key);
  const missing = importKeys.filter((key) => indexOf(key) < 0);
  if (missing.length) {
    const names = missing.map((key) => `"${key}"`).join(", ");
    return { rows, report: { ...report, error: `The file needs the ${names} ${missing.length === 1 ? "column" : "columns"} to match its rows to the grid.` } };
  }

  // Keys compare trimmed and case-insensitively; codelist keys by notation.
  const keyValue = (key, raw) => {
    const column = columnOf(key);
    const value = column.kind === "codelist" ? normalizeCell(column, raw, codelists) : raw;
    return String(value ?? "").trim().toLowerCase();
  };
  const rowHas = (row, key, fileValue) =>
    [row.cells[key], ...(row.aliases?.[key] || [])].some((candidate) => keyValue(key, candidate) === fileValue);
  const matching = (keys, fileKeys) => rows.find((row) => keys.every((key) => rowHas(row, key, fileKeys[key])));

  const updates = new Map(); // row id -> values
  const additions = []; // { template, values }
  body.forEach((cells, line) => {
    if (cells.every((cell) => !String(cell ?? "").trim())) return;
    const fileKeys = Object.fromEntries(importKeys.map((key) => [key, keyValue(key, cells[indexOf(key)])]));
    const values = {};
    fileColumns.forEach((column, i) => {
      if (column && isEditable(column)) values[column.key] = normalizeCell(column, cells[i], codelists);
    });

    const row = matching(importKeys, fileKeys);
    if (row) {
      updates.set(row.id, values);
      return;
    }
    const template = importParentKeys && newRowFor && matching(importParentKeys, fileKeys);
    if (template) {
      additions.push({ template, values });
      return;
    }
    const described = importKeys.map((key) => String(cells[indexOf(key)] ?? "").trim()).filter(Boolean).join(" / ");
    report.unmatched.push(described || `line ${line + 2}`);
  });

  // Only the cells a row allows are written (e.g. not an existing
  // affiliation's programme or start date).
  const writable = (row, values) =>
    Object.fromEntries(Object.entries(values).filter(([key]) => isCellEditable(columnOf(key), row)));

  let next = rows.map((row) => {
    if (!updates.has(row.id)) return row;
    report.matched += 1;
    const values = writable(row, updates.get(row.id));
    const changed = Object.keys(values).filter((key) => values[key] !== (row.cells[key] ?? ""));
    report.changedCells += changed.length;
    return changed.length ? { ...row, cells: { ...row.cells, ...values } } : row;
  });

  // New rows go after the last row of the same parent (e.g. the observation).
  additions.forEach(({ template, values }) => {
    const row = newRowFor(template, next);
    const filled = { ...row, cells: { ...row.cells, ...writable(row, values) } };
    const parentOf = (r) => importParentKeys.map((key) => r.cells[key]).join("\u0000");
    const last = next.reduce((index, r, i) => (r.stationId === template.stationId && parentOf(r) === parentOf(template) ? i : index), -1);
    next = [...next.slice(0, last + 1), filled, ...next.slice(last + 1)];
    report.added += 1;
  });

  return { rows: next, report };
}

export async function importSheet(file, sheet, rows, codelists) {
  return mergeSheet(await readSheet(file), sheet, rows, codelists);
}
