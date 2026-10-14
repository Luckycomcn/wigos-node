import { useEffect, useState } from "react";
import { listMyStations } from "../api";
import StationsMap from "./StationsMap";
import SelectionBar from "./SelectionBar";

// `selected` (a Set of station IDs) is kept by the parent so it survives a
// trip to the batch wizard and back.
export default function StationsList({ onNew, onEdit, selected, onSelectedChange, onBatch }) {
  const [stations, setStations] = useState([]);
  const [loadState, setLoadState] = useState({ status: "loading" });

  useEffect(() => {
    listMyStations()
      .then((data) => {
        setStations(data);
        setLoadState({ status: "success" });
      })
      .catch((err) => setLoadState({ status: "error", error: err.message }));
  }, []);

  const editableIds = stations.filter((station) => station.can_edit).map((station) => station.station_id);
  // Only stations still listed and editable count as selected.
  const selectedIds = editableIds.filter((id) => selected.has(id));

  const toggle = (id) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onSelectedChange(next);
  };

  return (
    <div className="card">
      <div className="list-header">
        <h3>My stations</h3>
        <button type="button" className="btn btn-primary" onClick={onNew}>
          + New station
        </button>
      </div>

      {loadState.status === "loading" && <p>Loading stations...</p>}
      {loadState.status === "error" && (
        <div className="status-message status-error">Error: {loadState.error}</div>
      )}
      {loadState.status === "success" && stations.length === 0 && <p>No stations saved yet.</p>}

      {stations.length > 0 && (
        <>
          <StationsMap stations={stations} />
          {selectedIds.length > 0 && (
            <SelectionBar
              count={selectedIds.length}
              editableCount={editableIds.length}
              onSelectAll={() => onSelectedChange(new Set(editableIds))}
              onClear={() => onSelectedChange(new Set())}
              onBatch={() => onBatch(selectedIds)}
            />
          )}
          <table className="stations-table">
            <thead>
              <tr>
                <th className="select-col">
                  <input
                    type="checkbox"
                    aria-label="Select all editable stations"
                    checked={editableIds.length > 0 && selectedIds.length === editableIds.length}
                    disabled={!editableIds.length}
                    onChange={(e) => onSelectedChange(new Set(e.target.checked ? editableIds : []))}
                  />
                </th>
                <th>WIGOS identifier</th>
                <th>Name</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {stations.map((station) => (
                <tr key={station.station_id} className={selected.has(station.station_id) && station.can_edit ? "row-selected" : ""}>
                  <td className="select-col">
                    <input
                      type="checkbox"
                      aria-label={`Select ${station.name || station.wsi}`}
                      checked={station.can_edit && selected.has(station.station_id)}
                      disabled={!station.can_edit}
                      title={station.can_edit ? undefined : "You don't have permission to edit this station"}
                      onChange={() => toggle(station.station_id)}
                    />
                  </td>
                  <td>{station.wsi}</td>
                  <td>{station.name}</td>
                  <td>
                    <button type="button" className="btn btn-secondary" onClick={() => onEdit(station.station_id)}>
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
