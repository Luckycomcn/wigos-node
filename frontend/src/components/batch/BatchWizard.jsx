import { useState } from "react";
import { getStations, saveStationsBatch } from "../../api";
import { useCodelists } from "../../useCodelists";
import { blockingCellCount, changedColumns, diffRecord, splitList } from "../../batch/common";
import { idsInRows, ownIdsInRows, rowNote } from "../../batch/wigosIds";
import { duplicateWigosIds } from "../../wmdr";
import { useWigosIdAvailability } from "../../useWigosIdAvailability";
import { validateWmdrRecord } from "../../wmdrSchema";
import OperationPicker from "./OperationPicker";
import SheetGrid from "./SheetGrid";
import PreviewDialog from "./PreviewDialog";
import BatchResults from "./BatchResults";

const STEPS = [
  { id: "operation", label: "Operation" },
  { id: "edit", label: "Edit" },
  { id: "results", label: "Results" },
];

function StepBar({ step }) {
  const current = STEPS.findIndex((s) => s.id === step);
  return (
    <ol className="step-bar">
      {STEPS.map((s, i) => (
        <li key={s.id} className={i === current ? "step-current" : i < current ? "step-done" : ""}>
          <span className="step-number">{i + 1}</span> {s.label}
        </li>
      ))}
    </ol>
  );
}

// Duplicate and availability checks for WIGOS ID cells. Hooks run for every
// operation; the ID lists are only filled for the WIGOS identifiers grid.
function useWigosIdStatus(active, rows) {
  const ids = active ? idsInRows(rows) : [];
  const ownIds = active ? ownIdsInRows(rows) : [];
  const availability = useWigosIdAvailability(ids, ownIds);
  const duplicates = duplicateWigosIds(ids);

  return (row, column) => {
    if (!active) return null;
    // A station with more additional IDs than the grid shows keeps the rest.
    if (column.key === "station_name") {
      const note = rowNote(row);
      return note ? { hint: note } : null;
    }
    if (column.kind !== "wsi" && column.kind !== "wsis") return null;
    const cellIds = column.kind === "wsi" ? [row.cells[column.key]].filter(Boolean) : splitList(row.cells[column.key]);
    const duplicate = cellIds.find((id) => duplicates.has(id));
    if (duplicate) return { error: `${duplicate} is entered more than once in this batch` };
    const taken = cellIds.find((id) => availability(id) === "taken");
    if (taken) return { error: `${taken} is already registered to another station` };
    if (cellIds.some((id) => availability(id) === "checking")) return { hint: "checking…" };
    if (cellIds.some((id) => availability(id) === "error")) return { hint: "couldn't check availability" };
    return null;
  };
}

export default function BatchWizard({ stationIds, onApplied, onClose }) {
  const { codelists } = useCodelists();
  const [step, setStep] = useState("operation");
  const [operation, setOperation] = useState(null);
  const [load, setLoad] = useState({ status: "idle" });
  const [entries, setEntries] = useState([]);
  const [rows, setRows] = useState([]);
  const [selectedRows, setSelectedRows] = useState(new Set());
  const [preview, setPreview] = useState(null);
  const [results, setResults] = useState(null);

  const module = operation?.module;
  const cellStatus = useWigosIdStatus(operation?.id === "wigosIds", rows);

  async function start(nextOperation, ids) {
    setOperation(nextOperation);
    setStep("edit");
    setLoad({ status: "loading" });
    setPreview(null);
    setSelectedRows(new Set());
    try {
      const records = await getStations(ids);
      const loaded = ids.filter((id) => records[id]).map((id) => ({ stationId: id, record: records[id] }));
      setEntries(loaded);
      setRows(nextOperation.module.toRows(loaded));
      setLoad({ status: "done", missing: ids.filter((id) => !records[id]) });
    } catch (err) {
      setLoad({ status: "error", error: err.message, ids });
    }
  }

  const changedRows = rows.filter((row) => changedColumns(row, module?.columns || []).length);
  const changedCells = changedRows.reduce((sum, row) => sum + changedColumns(row, module.columns).length, 0);
  const changedStations = new Set(changedRows.map((row) => row.stationId)).size;
  const invalidCells = module ? blockingCellCount(module.columns, rows, codelists, cellStatus) : 0;
  const applyBlockedReason = !changedCells
    ? "Edit at least one cell first"
    : invalidCells
      ? "Fix the cells outlined in red first (hover a cell to see why)"
      : undefined;

  async function openPreview() {
    const updated = module.applyRows(entries, rows, codelists);
    const changes = [];
    updated.forEach((entry, i) => {
      const diff = diffRecord(entries[i].record, entry.record);
      if (!diff.length) return;
      changes.push({
        stationId: entry.stationId,
        name: entries[i].record.properties?.title,
        wsi: entries[i].record.id,
        record: entry.record,
        diff,
        schemaErrors: validateWmdrRecord(entry.record),
      });
    });
    const unchangedCount = entries.length - changes.length;
    const updates = changes.map((change) => ({ station_id: change.stationId, wmdrv2: change.record }));
    setPreview({ changes, unchangedCount, updates, dryRun: { status: changes.length ? "running" : "done", byStation: {} } });
    if (!changes.length) return;

    let dryRun;
    try {
      const response = await saveStationsBatch(updates, { dryRun: true });
      dryRun = { status: "done", byStation: Object.fromEntries(response.results.map((r) => [r.station_id, r])) };
    } catch (err) {
      dryRun = { status: "error", error: err.message, byStation: {} };
    }
    // Ignore a reply for a preview that was closed in the meantime.
    setPreview((current) => (current?.updates === updates ? { ...current, dryRun } : current));
  }

  async function apply(updates, names) {
    setPreview(null);
    setStep("results");
    setResults({ status: "running", count: updates.length, updates, names });
    try {
      const response = await saveStationsBatch(updates);
      response.results.forEach((result) => (result.station_name = names[result.station_id]));
      setResults({ status: "done", response, updates, names });
      const failedIds = response.results.filter((r) => r.status !== "ok").map((r) => r.station_id);
      onApplied(failedIds);
    } catch (err) {
      setResults({ status: "error", error: err.message, updates, names });
    }
  }

  const confirm = () => {
    const names = Object.fromEntries(preview.changes.map((change) => [change.stationId, change.name]));
    apply(preview.updates, names);
  };

  const addRows = () => {
    const { rows: next, added } = module.addRows(rows, selectedRows);
    setRows(next);
    setSelectedRows(new Set(added.map((row) => row.id)));
  };

  return (
    <div className="card batch-wizard">
      <div className="list-header">
        <h3>Batch operations{operation && step !== "operation" ? `: ${operation.name}` : ""}</h3>
        <button type="button" className="btn btn-ghost" onClick={onClose}>
          Back to stations
        </button>
      </div>
      <StepBar step={step} />

      {step === "operation" && <OperationPicker stationCount={stationIds.length} onPick={(op) => start(op, stationIds)} />}

      {step === "edit" && (
        <>
          {load.status === "loading" && <p>Loading the selected stations…</p>}
          {load.status === "error" && (
            <div className="status-message status-error">
              Couldn&apos;t load the stations: {load.error}{" "}
              <button type="button" className="btn btn-secondary" onClick={() => start(operation, load.ids)}>
                Retry
              </button>
            </div>
          )}
          {load.status === "done" && (
            <>
              {load.missing.length > 0 && (
                <div className="status-message status-warning">
                  {load.missing.length} selected {load.missing.length === 1 ? "station no longer exists" : "stations no longer exist"} and{" "}
                  {load.missing.length === 1 ? "is" : "are"} left out.
                </div>
              )}
              <SheetGrid
                key={operation.id}
                sheet={module}
                rows={rows}
                onRowsChange={setRows}
                codelists={codelists}
                cellStatus={cellStatus}
                selectedIds={selectedRows}
                onSelectedIdsChange={setSelectedRows}
                exportName={`batch-${operation.id}`}
                actions={
                  module.addRows && (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={addRows}
                      disabled={!selectedRows.size}
                      title="Adds an empty affiliation under the observation of each selected row"
                    >
                      + Add affiliation to selected observations
                    </button>
                  )
                }
              />
              <div className="batch-footer">
                <span className="batch-count">
                  {changedCells
                    ? `${changedCells} ${changedCells === 1 ? "cell" : "cells"} changed in ${changedStations} ${changedStations === 1 ? "station" : "stations"}`
                    : "No changes yet"}
                  {invalidCells > 0 && (
                    <span className="field-error">
                      {" "}
                      · {invalidCells} edited {invalidCells === 1 ? "cell is" : "cells are"} invalid (outlined in red, hover for the reason)
                    </span>
                  )}
                </span>
                <div className="form-actions">
                  <button type="button" className="btn btn-secondary" onClick={() => setStep("operation")}>
                    Change operation
                  </button>
                  <button type="button" className="btn btn-ghost" onClick={onClose}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={openPreview}
                    disabled={!!applyBlockedReason}
                    title={applyBlockedReason}
                  >
                    Apply
                  </button>
                </div>
              </div>
            </>
          )}
        </>
      )}

      {step === "results" && results && (
        <BatchResults
          state={results}
          onRetry={() => apply(results.updates, results.names)}
          onRetryFailed={(ids) => start(operation, ids)}
          onBack={onClose}
        />
      )}

      {preview && (
        <PreviewDialog
          open
          changes={preview.changes}
          unchangedCount={preview.unchangedCount}
          dryRun={preview.dryRun}
          onConfirm={confirm}
          onBack={() => setPreview(null)}
        />
      )}
    </div>
  );
}
