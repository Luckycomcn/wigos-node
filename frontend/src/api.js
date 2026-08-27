import { parseCsv } from "./csv";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function getHello() {
  const res = await fetch(`${API_URL}/api/hello/`);
  if (!res.ok) {
    throw new Error(`API request failed: ${res.status}`);
  }
  return res.json();
}

export async function saveStation(wigosIdentifier, record) {
  const res = await fetch(`${API_URL}/api/wmdrv2/${encodeURIComponent(wigosIdentifier)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(record),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || `API request failed: ${res.status}`);
  }
  return data;
}

export async function getStation(wigosIdentifier) {
  const res = await fetch(`${API_URL}/api/wmdrv2/${encodeURIComponent(wigosIdentifier)}`);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || `API request failed: ${res.status}`);
  }
  return data;
}

export async function listMyStations() {
  const res = await fetch(`${API_URL}/api/my_stations/`);
  if (!res.ok) {
    throw new Error(`API request failed: ${res.status}`);
  }
  return res.json();
}

export async function getCodelist(scheme) {
  const res = await fetch(`${API_URL}/api/codelists/${scheme}.csv`);
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
