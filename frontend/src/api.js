import { parseCsv } from "./csv";
import { csrfHeader } from "./auth";

const API_URL = import.meta.env.VITE_API_URL || "";

// Notify the app when the session is gone so it can drop back to the login page.
function handle401(res) {
  if (res.status === 401) {
    window.dispatchEvent(new Event("auth:unauthenticated"));
  }
  return res;
}

export async function getHello() {
  const res = handle401(await fetch(`${API_URL}/api/hello/`, { credentials: "include" }));
  if (!res.ok) {
    throw new Error(`API request failed: ${res.status}`);
  }
  return res.json();
}

export async function saveStation(stationId, record) {
  const url = stationId == null ? `${API_URL}/api/wmdrv2/` : `${API_URL}/api/wmdrv2/${encodeURIComponent(stationId)}`;
  const res = handle401(await fetch(url, {
    method: stationId == null ? "POST" : "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...csrfHeader() },
    body: JSON.stringify(record),
  }));
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || `API request failed: ${res.status}`);
  }
  return data;
}

export async function getStation(stationId) {
  const res = handle401(await fetch(`${API_URL}/api/wmdrv2/${encodeURIComponent(stationId)}`, {
    credentials: "include",
  }));
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || `API request failed: ${res.status}`);
  }
  return data;
}

export async function listMyStations() {
  const res = handle401(await fetch(`${API_URL}/api/my_stations/`, { credentials: "include" }));
  if (!res.ok) {
    throw new Error(`API request failed: ${res.status}`);
  }
  return res.json();
}

export async function listMyIssuers() {
  const res = handle401(await fetch(`${API_URL}/api/my_issuer_of_identifiers/`, {
    credentials: "include",
  }));
  if (!res.ok) {
    throw new Error(`API request failed: ${res.status}`);
  }
  return res.json();
}

export async function getCodelist(scheme) {
  const res = await fetch(`${API_URL}/api/codelists/${scheme}.csv`, { credentials: "include" });
  if (!res.ok) {
    throw new Error(`Failed to load codelist ${scheme}: ${res.status}`);
  }
  const text = await res.text();
  return parseCsv(text)
    .map((row) => ({
      code: row["skos:notation"],
      label: row["rdfs:label"] || row["skos:notation"],
      id: (row["@id"] || "").replace(/^<|>$/g, ""),
    }))
    .filter((entry) => entry.code);
}
