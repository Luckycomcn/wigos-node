import { resultsToCsv } from "../../batch/common";
import { csvBlob, downloadBlob } from "../../batch/sheetIO";

// `state`: { status: "running", count } | { status: "done", response } | { status: "error", error }.
export default function BatchResults({ state, onRetry, onRetryFailed, onBack }) {
  if (state.status === "running") {
    return <div className="status-message">Applying changes to {state.count} {state.count === 1 ? "station" : "stations"}…</div>;
  }

  if (state.status === "error") {
    return (
      <div>
        <div className="status-message status-error">The changes could not be sent: {state.error}</div>
        <div className="form-actions batch-actions">
          <button type="button" className="btn btn-secondary" onClick={onBack}>
            Back to stations
          </button>
          <button type="button" className="btn btn-primary" onClick={onRetry}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const { summary, results } = state.response;
  const failed = results.filter((result) => result.status !== "ok");

  return (
    <div>
      <div className={`status-message ${failed.length ? "status-error" : "status-success"}`}>
        {summary.ok} saved, {summary.error} failed.
      </div>
      <table className="stations-table batch-results">
        <thead>
          <tr>
            <th>Station</th>
            <th>WIGOS ID</th>
            <th>Result</th>
          </tr>
        </thead>
        <tbody>
          {results.map((result) => (
            <tr key={result.index}>
              <td>{result.station_name || `Station ${result.station_id}`}</td>
              <td>{result.wsi}</td>
              <td>
                {result.status === "ok" ? (
                  <span className="badge badge-ok">✓ saved</span>
                ) : (
                  <>
                    <span className="badge badge-error">✗ failed</span> {result.message}
                    {result.errors?.length > 0 && (
                      <ul className="schema-errors field-error">
                        {result.errors.map((error) => (
                          <li key={error}>{error}</li>
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="form-actions batch-actions">
        <button type="button" className="btn btn-secondary" onClick={onBack}>
          Back to stations
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => downloadBlob(csvBlob(resultsToCsv(results)), "batch-results.csv")}
        >
          Download results (CSV)
        </button>
        {failed.length > 0 && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => onRetryFailed(failed.map((result) => result.station_id))}
          >
            Retry {failed.length} failed
          </button>
        )}
      </div>
    </div>
  );
}
