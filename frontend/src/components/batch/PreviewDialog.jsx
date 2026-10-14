import Dialog from "../Dialog";

const show = (value) => (value === undefined ? "—" : JSON.stringify(value));

// Lists the changes per station with the frontend schema check and the
// backend dry run. `changes`: [{ stationId, name, wsi, diff, schemaErrors }];
// `dryRun`: { status: "running" | "done" | "error", byStation, error }.
export default function PreviewDialog({ open, changes, unchangedCount, dryRun, onConfirm, onBack }) {
  const schemaFailures = changes.filter((change) => change.schemaErrors.length).length;
  const dryRunFailures =
    dryRun.status === "done" ? changes.filter((change) => dryRun.byStation[change.stationId]?.status !== "ok").length : 0;
  const canConfirm = changes.length > 0 && !schemaFailures && dryRun.status === "done" && !dryRunFailures;

  return (
    <Dialog open={open} title="Review changes" onClose={onBack} wide>
      <p className="batch-intro">
        {changes.length} {changes.length === 1 ? "station" : "stations"} will be changed
        {unchangedCount > 0 && `, ${unchangedCount} unchanged ${unchangedCount === 1 ? "station is" : "stations are"} not sent`}.
      </p>

      {dryRun.status === "running" && <div className="status-message">Checking the changes on the server…</div>}
      {dryRun.status === "error" && (
        <div className="status-message status-error">The server check failed: {dryRun.error}</div>
      )}
      {(schemaFailures > 0 || dryRunFailures > 0) && (
        <div className="status-message status-error">
          Fix the stations marked below before confirming (
          {[
            schemaFailures && `${schemaFailures} failing the schema check`,
            dryRunFailures && `${dryRunFailures} rejected by the server`,
          ]
            .filter(Boolean)
            .join(", ")}
          ).
        </div>
      )}

      <div className="preview-list">
        {changes.map((change) => {
          const server = dryRun.byStation?.[change.stationId];
          return (
            <div key={change.stationId} className="preview-station">
              <div className="preview-station-header">
                <span>
                  <strong>{change.name || `Station ${change.stationId}`}</strong>{" "}
                  <span className="preview-wsi">{change.wsi}</span>
                </span>
                <span className="preview-badges">
                  <span className={`badge ${change.schemaErrors.length ? "badge-error" : "badge-ok"}`}>
                    {change.schemaErrors.length ? "✗ schema" : "✓ schema"}
                  </span>
                  {dryRun.status === "running" && <span className="badge">server…</span>}
                  {server && (
                    <span className={`badge ${server.status === "ok" ? "badge-ok" : "badge-error"}`}>
                      {server.status === "ok" ? "✓ server" : "✗ server"}
                    </span>
                  )}
                </span>
              </div>
              <table className="preview-diff">
                <tbody>
                  {change.diff.map((entry) => (
                    <tr key={entry.path}>
                      <td className="preview-path">{entry.path}</td>
                      <td className="preview-before">{show(entry.before)}</td>
                      <td className="preview-arrow">→</td>
                      <td className="preview-after">{show(entry.after)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {change.schemaErrors.length > 0 && (
                <ul className="schema-errors field-error">
                  {change.schemaErrors.map((error) => (
                    <li key={error}>{error}</li>
                  ))}
                </ul>
              )}
              {server && server.status !== "ok" && (
                <div className="field-error">
                  {server.message}
                  {server.errors?.length > 0 && (
                    <ul className="schema-errors">
                      {server.errors.map((error) => (
                        <li key={error}>{error}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="form-actions batch-actions">
        <button type="button" className="btn btn-secondary" onClick={onBack}>
          Back to editing
        </button>
        <button type="button" className="btn btn-primary" onClick={onConfirm} disabled={!canConfirm}>
          Confirm and save {changes.length} {changes.length === 1 ? "station" : "stations"}
        </button>
      </div>
    </Dialog>
  );
}
