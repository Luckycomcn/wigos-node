const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function getHello() {
  const res = await fetch(`${API_URL}/api/hello/`);
  if (!res.ok) {
    throw new Error(`API request failed: ${res.status}`);
  }
  return res.json();
}

export async function submitGeoJson(feature) {
  const res = await fetch(`${API_URL}/api/geojson/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(feature),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || `API request failed: ${res.status}`);
  }
  return data;
}
