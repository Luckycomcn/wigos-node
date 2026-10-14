import { useEffect, useMemo, useRef, useState } from "react";
import { cellState, codelistLabel, findCodelistOption, isCellChanged, isCellEditable, isEditable, normalizeCell } from "../../batch/common";
import { exportSheet, importSheet } from "../../batch/sheetIO";
import { CODELISTS, codelistOptions } from "../../codelists";

// An Excel-like grid over batch rows (see src/batch/common.js). Key columns
// are read-only; every other cell is edited in place. Rows are never added
// or removed here, apart from an operation's own `actions`.
//
// Keyboard: arrows/Tab move, Enter/F2 or typing edits, Esc cancels, Delete
// clears. A tab-separated block pasted from Excel fills from the active cell.

const CHECKBOX_WIDTH = 36;

function displayValue(column, value, codelists) {
  if (column.kind === "codelist" && value) return codelistLabel(codelistOptions(column.codelist, codelists), value);
  return value;
}

// <option>s of a codelist column, grouped like the station form. A value
// that isn't in the codelist is kept as an extra option so it stays visible.
function CodelistOptions({ column, codelists, value }) {
  const list = codelists[column.codelist] || [];
  const grouped = typeof CODELISTS[column.codelist] !== "string";
  const renderOption = (opt) => (
    <option key={`${opt.id}|${opt.code}`} value={opt.code}>
      {opt.label === opt.code ? opt.label : `${opt.label} (${opt.code})`}
    </option>
  );
  const unknown = value && !findCodelistOption(codelistOptions(column.codelist, codelists), value);
  return (
    <>
      {unknown && <option value={value}>{value} (not in the codelist)</option>}
      {grouped
        ? list.map((group) => (
            <optgroup key={group.label} label={group.label}>
              {group.options.map(renderOption)}
            </optgroup>
          ))
        : list.map(renderOption)}
    </>
  );
}

const editorKeyDown = (onCommit, onCancel) => (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    onCommit(e.shiftKey ? "up" : "down");
  } else if (e.key === "Tab") {
    e.preventDefault();
    onCommit(e.shiftKey ? "left" : "right");
  } else if (e.key === "Escape") {
    e.preventDefault();
    e.stopPropagation();
    onCancel();
  }
};

// Controlled by the grid, so a click elsewhere can commit the value.
function CellEditor({ column, value, codelists, onChange, onCommit, onCancel }) {
  const selectRef = useRef(null);

  // Open the list straight away; showPicker needs a recent click or key press
  // and isn't supported everywhere, so failures are ignored.
  useEffect(() => {
    try {
      selectRef.current?.showPicker?.();
    } catch {
      /* the select is focused, which is enough */
    }
  }, []);

  if (column.kind === "codelist") {
    return (
      <select
        ref={selectRef}
        className="sheet-editor"
        autoFocus
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={() => onCommit(null)}
        onKeyDown={editorKeyDown(onCommit, onCancel)}
      >
        <option value="">(empty)</option>
        <CodelistOptions column={column} codelists={codelists} value={value} />
      </select>
    );
  }
  return (
    <input
      className="sheet-editor"
      autoFocus
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onBlur={() => onCommit(null)}
      onKeyDown={editorKeyDown(onCommit, onCancel)}
    />
  );
}

// Sets one value in every selected row: picking from the list applies it
// straight away; a typed value applies with Enter or the Set button.
function FillInput({ column, codelists, onFill }) {
  const [value, setValue] = useState("");
  const label = `Fill ${column.label} in the selected rows`;

  if (column.kind === "codelist") {
    return (
      <select
        className="sheet-fill"
        value=""
        aria-label={label}
        onChange={(e) => onFill(e.target.value === "__empty__" ? "" : e.target.value)}
      >
        <option value="">Set for selected…</option>
        <option value="__empty__">(empty)</option>
        <CodelistOptions column={column} codelists={codelists} value="" />
      </select>
    );
  }

  const fill = () => {
    onFill(value);
    setValue("");
  };
  return (
    <div className="sheet-fill-text">
      <input
        className="sheet-fill"
        value={value}
        placeholder="Set for selected…"
        aria-label={label}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            fill();
          }
        }}
      />
      <button type="button" className="sheet-fill-button" onClick={fill} title={label}>
        Set
      </button>
    </div>
  );
}

export default function SheetGrid({
  sheet,
  rows,
  onRowsChange,
  codelists,
  cellStatus,
  selectedIds,
  onSelectedIdsChange,
  actions,
  exportName = "batch",
}) {
  const { columns } = sheet;
  const containerRef = useRef(null);
  const fileRef = useRef(null);
  const [active, setActive] = useState({ r: 0, c: 0 });
  const [editing, setEditing] = useState(null); // { value } while a cell is edited
  const editingRef = useRef(null);
  editingRef.current = editing;
  const [filter, setFilter] = useState("");
  const [importState, setImportState] = useState(null);

  const keyColumns = columns.filter((column) => !isEditable(column));
  const visibleRows = useMemo(() => {
    const terms = filter.toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) return rows;
    return rows.filter((row) => {
      const haystack = keyColumns.map((column) => row.cells[column.key] ?? "").join(" ").toLowerCase();
      return terms.every((term) => haystack.includes(term));
    });
  }, [rows, filter, keyColumns]);

  // Sticky offsets for the checkbox and key columns.
  const stickyLeft = useMemo(() => {
    const offsets = {};
    let left = CHECKBOX_WIDTH;
    columns.forEach((column) => {
      if (isEditable(column)) return;
      offsets[column.key] = left;
      left += column.width || 140;
    });
    return offsets;
  }, [columns]);

  const r = Math.min(active.r, Math.max(visibleRows.length - 1, 0));
  const c = Math.min(active.c, columns.length - 1);
  const activeRow = visibleRows[r];
  const activeColumn = columns[c];

  useEffect(() => {
    containerRef.current?.querySelector(`[data-cell="${r}:${c}"]`)?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [r, c]);


  // updates: [{ rowId, key, value }]; values are normalized here.
  function setCells(updates) {
    const byRow = new Map();
    updates.forEach(({ rowId, key, value }) => {
      const column = columns.find((col) => col.key === key);
      if (!column || !isCellEditable(column, rows.find((row) => row.id === rowId))) return;
      if (!byRow.has(rowId)) byRow.set(rowId, {});
      byRow.get(rowId)[key] = normalizeCell(column, value, codelists);
    });
    if (!byRow.size) return;
    onRowsChange(rows.map((row) => (byRow.has(row.id) ? { ...row, cells: { ...row.cells, ...byRow.get(row.id) } } : row)));
  }

  function move(direction) {
    const deltas = { up: [-1, 0], down: [1, 0], left: [0, -1], right: [0, 1] };
    const [dr, dc] = deltas[direction] || [0, 0];
    setActive({
      r: Math.min(Math.max(r + dr, 0), Math.max(visibleRows.length - 1, 0)),
      c: Math.min(Math.max(c + dc, 0), columns.length - 1),
    });
  }

  function startEditing(initial) {
    if (!activeRow || !isCellEditable(activeColumn, activeRow)) return;
    // A dropdown can't start from a typed character; it opens on the current value.
    if (activeColumn.kind === "codelist") initial = undefined;
    setEditing({ value: initial ?? activeRow.cells[activeColumn.key] ?? "" });
  }

  // The ref guards against committing twice (Enter, then the blur it causes).
  function stopEditing(commit, direction) {
    const current = editingRef.current;
    if (!current) return;
    editingRef.current = null;
    setEditing(null);
    if (commit && activeRow) setCells([{ rowId: activeRow.id, key: activeColumn.key, value: current.value }]);
    containerRef.current?.focus();
    if (direction) move(direction);
  }

  function handleKeyDown(e) {
    if (editing || e.target !== containerRef.current) return;
    const arrows = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right" };
    if (arrows[e.key]) {
      e.preventDefault();
      move(arrows[e.key]);
    } else if (e.key === "Tab") {
      e.preventDefault();
      move(e.shiftKey ? "left" : "right");
    } else if (e.key === "Enter" || e.key === "F2") {
      e.preventDefault();
      startEditing();
    } else if ((e.key === "Delete" || e.key === "Backspace") && activeRow && isCellEditable(activeColumn, activeRow)) {
      e.preventDefault();
      setCells([{ rowId: activeRow.id, key: activeColumn.key, value: "" }]);
    } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      startEditing(e.key);
    }
  }

  function handlePaste(e) {
    if (editing || !activeRow) return;
    const text = e.clipboardData.getData("text/plain");
    if (!text) return;
    e.preventDefault();
    const lines = text.replace(/\r?\n$/, "").split(/\r?\n/);
    const updates = [];
    // Rows beyond the last one are ignored, never added.
    lines.forEach((line, i) => {
      const row = visibleRows[r + i];
      if (!row) return;
      line.split("\t").forEach((value, j) => {
        const column = columns[c + j];
        if (column && isCellEditable(column, row)) updates.push({ rowId: row.id, key: column.key, value });
      });
    });
    setCells(updates);
  }

  function handleCopy(e) {
    if (editing || !activeRow) return;
    e.preventDefault();
    e.clipboardData.setData("text/plain", activeRow.cells[activeColumn.key] ?? "");
  }

  function fill(column, value) {
    setCells(rows.filter((row) => selectedIds.has(row.id)).map((row) => ({ rowId: row.id, key: column.key, value })));
  }

  function resetCell() {
    if (!activeRow || !isCellEditable(activeColumn, activeRow)) return;
    setCells([{ rowId: activeRow.id, key: activeColumn.key, value: activeRow.original[activeColumn.key] ?? "" }]);
  }

  async function handleImport(file) {
    setImportState({ status: "loading" });
    try {
      const { rows: next, report } = await importSheet(file, sheet, rows, codelists);
      if (!report.error) onRowsChange(next);
      setImportState({ status: "done", file: file.name, report });
    } catch (err) {
      setImportState({ status: "done", file: file.name, report: { error: `Couldn't read the file: ${err.message}` } });
    }
  }

  const allVisibleSelected = visibleRows.length > 0 && visibleRows.every((row) => selectedIds.has(row.id));
  const toggleAll = () => {
    const next = new Set(selectedIds);
    visibleRows.forEach((row) => (allVisibleSelected ? next.delete(row.id) : next.add(row.id)));
    onSelectedIdsChange(next);
  };
  const toggleRow = (id) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onSelectedIdsChange(next);
  };

  const tableWidth = CHECKBOX_WIDTH + columns.reduce((sum, column) => sum + (column.width || 140), 0);
  const activeChanged = activeRow && isEditable(activeColumn) && isCellChanged(activeRow, activeColumn.key);
  const anyChanged = rows.some((row) => columns.some((column) => isEditable(column) && isCellChanged(row, column.key)));

  return (
    <div className="sheet">
      <div className="sheet-toolbar">
        <input
          className="field-input sheet-filter"
          type="search"
          placeholder="Filter rows…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label="Filter rows by station, WIGOS ID or observed property"
        />
        {actions}
        <span className="sheet-toolbar-spacer" />
        <button type="button" className="btn btn-ghost" onClick={resetCell} disabled={!activeChanged}>
          Reset cell
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={!anyChanged}
          onClick={() => onRowsChange(rows.map((row) => ({ ...row, cells: { ...row.original } })))}
        >
          Reset all
        </button>
        <button type="button" className="btn btn-secondary" onClick={() => fileRef.current?.click()}>
          Import CSV/Excel
        </button>
        <input
          ref={fileRef}
          type="file"
          hidden
          accept=".csv,.xlsx,.xls,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) handleImport(file);
          }}
        />
        <button type="button" className="btn btn-secondary" onClick={() => exportSheet(columns, rows, "csv", exportName)}>
          Export CSV
        </button>
        <button type="button" className="btn btn-secondary" onClick={() => exportSheet(columns, rows, "xlsx", exportName)}>
          Export Excel
        </button>
      </div>

      {importState?.status === "loading" && <div className="status-message">Importing…</div>}
      {importState?.status === "done" && <ImportReport state={importState} onClose={() => setImportState(null)} />}


      <div
        className="sheet-scroll"
        ref={containerRef}
        tabIndex={0}
        role="grid"
        aria-rowcount={visibleRows.length}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onCopy={handleCopy}
      >
        <table className="sheet-table" style={{ width: tableWidth }}>
          <colgroup>
            <col style={{ width: CHECKBOX_WIDTH }} />
            {columns.map((column) => (
              <col key={column.key} style={{ width: column.width || 140 }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <th className="sheet-sticky sheet-check" style={{ left: 0 }}>
                <input type="checkbox" checked={allVisibleSelected} onChange={toggleAll} aria-label="Select all rows" />
              </th>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={isEditable(column) ? "" : "sheet-sticky sheet-key"}
                  style={isEditable(column) ? undefined : { left: stickyLeft[column.key] }}
                  title={column.key}
                >
                  {column.label}
                  {column.required && <span className="required">*</span>}
                </th>
              ))}
            </tr>
            {selectedIds.size > 0 && (
              <tr className="sheet-fill-row">
                <th className="sheet-sticky sheet-check" style={{ left: 0 }} />
                {columns.map((column) =>
                  isEditable(column) ? (
                    <th key={column.key}>
                      <FillInput column={column} codelists={codelists} onFill={(value) => fill(column, value)} />
                    </th>
                  ) : (
                    <th key={column.key} className="sheet-sticky sheet-key" style={{ left: stickyLeft[column.key] }}>
                      {column === keyColumns[keyColumns.length - 1] && (
                        <span className="sheet-fill-label">Fill {selectedIds.size} selected →</span>
                      )}
                    </th>
                  )
                )}
              </tr>
            )}
          </thead>
          <tbody>
            {visibleRows.length === 0 && (
              <tr>
                <td colSpan={columns.length + 1} className="sheet-empty">
                  {rows.length ? "No rows match the filter." : "Nothing to edit for the selected stations."}
                </td>
              </tr>
            )}
            {visibleRows.map((row, ri) => (
              <tr key={row.id} className={`${selectedIds.has(row.id) ? "sheet-row-selected" : ""}${row.isNew ? " sheet-row-new" : ""}`}>
                <td className="sheet-sticky sheet-check" style={{ left: 0 }}>
                  <input
                    type="checkbox"
                    checked={selectedIds.has(row.id)}
                    onChange={() => toggleRow(row.id)}
                    aria-label={`Select row ${row.id}`}
                  />
                </td>
                {columns.map((column, ci) => {
                  const state = cellState(row, column, codelists, cellStatus);
                  const isActive = ri === r && ci === c;
                  const classes = [
                    "sheet-cell",
                    isEditable(column) ? "" : "sheet-sticky sheet-key",
                    isEditable(column) && !state.editable ? "sheet-locked" : "",
                    state.changed ? "sheet-changed" : "",
                    state.error ? "sheet-invalid" : "",
                    isActive ? "sheet-active" : "",
                  ].filter(Boolean);
                  const title = [
                    isEditable(column) && !state.editable ? "Identifies this row; it can only be set on added rows" : null,
                    state.error,
                    state.hint,
                    state.changed ? `Was: ${displayValue(column, row.original[column.key] ?? "", codelists) || "(empty)"}` : null,
                    column.kind === "codelist" && state.value ? `Notation: ${state.value}` : null,
                  ]
                    .filter(Boolean)
                    .join("\n");
                  return (
                    <td
                      key={column.key}
                      data-cell={`${ri}:${ci}`}
                      className={classes.join(" ")}
                      style={isEditable(column) ? undefined : { left: stickyLeft[column.key] }}
                      title={title || undefined}
                      onMouseDown={(e) => {
                        if (isActive && editing) return;
                        e.preventDefault();
                        stopEditing(true);
                        setActive({ r: ri, c: ci });
                        containerRef.current?.focus();
                      }}
                      onDoubleClick={() => state.editable && setEditing({ value: state.value })}
                    >
                      {isActive && editing ? (
                        <CellEditor
                          column={column}
                          value={editing.value}
                          codelists={codelists}
                          onChange={(value) => setEditing({ value })}
                          onCommit={(direction) => stopEditing(true, direction)}
                          onCancel={() => stopEditing(false)}
                        />
                      ) : (
                        <span className="sheet-value">
                          {displayValue(column, state.value, codelists)}
                          {state.hint && <span className="sheet-hint"> · {state.hint}</span>}
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="sheet-help">
        Click a cell and type to edit; Enter or Tab confirms, Esc cancels. Paste a block copied from Excel to fill from the
        selected cell. Lists are separated by &quot;;&quot;.
        {filter && ` Showing ${visibleRows.length} of ${rows.length} rows.`}
      </div>
    </div>
  );
}

function ImportReport({ state, onClose }) {
  const { report } = state;
  if (report.error) {
    return (
      <div className="status-message status-error sheet-import-report">
        <span>
          {state.file}: {report.error}
        </span>
        <button type="button" className="dialog-close" onClick={onClose} aria-label="Dismiss">
          &times;
        </button>
      </div>
    );
  }
  return (
    <div className={`status-message ${report.unmatched.length || report.unknownHeaders.length ? "status-warning" : "status-success"} sheet-import-report`}>
      <div>
        <strong>{state.file}</strong>: {report.matched} rows matched, {report.changedCells} cells changed
        {report.added > 0 && `, ${report.added} rows added`}.
        {report.unmatched.length > 0 && (
          <div>
            {report.unmatched.length} rows not matched to a station in this batch and ignored:{" "}
            {report.unmatched.slice(0, 10).join(", ")}
            {report.unmatched.length > 10 && "…"}
          </div>
        )}
        {report.unknownHeaders.length > 0 && <div>Unknown columns ignored: {report.unknownHeaders.join(", ")}</div>}
      </div>
      <button type="button" className="dialog-close" onClick={onClose} aria-label="Dismiss">
        &times;
      </button>
    </div>
  );
}
