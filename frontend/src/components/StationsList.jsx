import { useEffect, useState } from "react";
import { listMyStations } from "../api";

export default function StationsList({ onNew, onEdit }) {
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
        <table className="stations-table">
          <thead>
            <tr>
              <th>WIGOS identifier</th>
              <th>Name</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {stations.map((station) => (
              <tr key={station.wsi}>
                <td>{station.wsi}</td>
                <td>{station.name}</td>
                <td>
                  <button type="button" className="btn btn-secondary" onClick={() => onEdit(station.wsi)}>
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
