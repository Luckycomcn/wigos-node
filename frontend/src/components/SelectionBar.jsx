// Same limit as MAX_BATCH_UPDATES in backend/api/views.py.
export const MAX_BATCH_STATIONS = 500;

// Shown at the top of the station list while stations are selected.
export default function SelectionBar({ count, editableCount, onSelectAll, onClear, onBatch }) {
  const tooMany = count > MAX_BATCH_STATIONS;
  return (
    <div className="selection-bar" role="region" aria-label="Selected stations">
      <span className="selection-count">
        {count} {count === 1 ? "station" : "stations"} selected
      </span>
      <button type="button" className="btn btn-link" onClick={onSelectAll} disabled={count === editableCount}>
        Select all ({editableCount})
      </button>
      <button type="button" className="btn btn-link" onClick={onClear}>
        Clear selection
      </button>
      <span className="selection-spacer" />
      {tooMany && <span className="field-error">At most {MAX_BATCH_STATIONS} stations per batch.</span>}
      <button type="button" className="btn btn-primary" onClick={onBatch} disabled={tooMany}>
        Batch operations
      </button>
    </div>
  );
}
