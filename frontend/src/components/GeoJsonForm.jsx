import { useState } from "react";
import { GEOMETRY_TYPES, MIN_POINTS, buildGeoJsonFeature } from "../geojson";
import { submitGeoJson } from "../api";

const emptyPoint = () => ({ lat: "", lng: "" });

export default function GeoJsonForm() {
  const [geometryType, setGeometryType] = useState("Point");
  const [name, setName] = useState("");
  const [points, setPoints] = useState([emptyPoint()]);
  const [submitState, setSubmitState] = useState({ status: "idle" });

  const handleGeometryTypeChange = (nextType) => {
    setGeometryType(nextType);
    const minPoints = MIN_POINTS[nextType];
    setPoints((prev) =>
      prev.length >= minPoints ? prev : [...prev, ...Array(minPoints - prev.length).fill(null).map(emptyPoint)]
    );
  };

  const updatePoint = (index, field, value) => {
    setPoints((prev) => prev.map((p, i) => (i === index ? { ...p, [field]: value } : p)));
  };

  const addPoint = () => setPoints((prev) => [...prev, emptyPoint()]);

  const removePoint = (index) => {
    setPoints((prev) => {
      const next = prev.filter((_, i) => i !== index);
      return next.length >= MIN_POINTS[geometryType] ? next : prev;
    });
  };

  const isValid =
    points.length >= MIN_POINTS[geometryType] &&
    points.every((p) => p.lat !== "" && p.lng !== "" && !Number.isNaN(Number(p.lat)) && !Number.isNaN(Number(p.lng)));

  const feature = isValid
    ? buildGeoJsonFeature(geometryType, points, name ? { name } : {})
    : null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!feature) return;
    setSubmitState({ status: "loading" });
    try {
      const data = await submitGeoJson(feature);
      setSubmitState({ status: "success", data });
    } catch (err) {
      setSubmitState({ status: "error", error: err.message });
    }
  };

  return (
    <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap" }}>
      <form onSubmit={handleSubmit} style={{ minWidth: "320px" }}>
        <div style={{ marginBottom: "1rem" }}>
          <label>
            Geometry type{" "}
            <select value={geometryType} onChange={(e) => handleGeometryTypeChange(e.target.value)}>
              {GEOMETRY_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div style={{ marginBottom: "1rem" }}>
          <label>
            Name (optional){" "}
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Feature name" />
          </label>
        </div>

        {points.map((p, i) => (
          <div key={i} style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem", alignItems: "center" }}>
            <input
              type="number"
              step="any"
              placeholder="Latitude"
              value={p.lat}
              onChange={(e) => updatePoint(i, "lat", e.target.value)}
              style={{ width: "120px" }}
            />
            <input
              type="number"
              step="any"
              placeholder="Longitude"
              value={p.lng}
              onChange={(e) => updatePoint(i, "lng", e.target.value)}
              style={{ width: "120px" }}
            />
            <button
              type="button"
              onClick={() => removePoint(i)}
              disabled={points.length <= MIN_POINTS[geometryType]}
            >
              Remove
            </button>
          </div>
        ))}

        <button type="button" onClick={addPoint} style={{ marginBottom: "1rem" }}>
          Add point
        </button>

        <div>
          <button type="submit" disabled={!isValid || submitState.status === "loading"}>
            {submitState.status === "loading" ? "Submitting..." : "Submit GeoJSON"}
          </button>
        </div>

        {submitState.status === "success" && (
          <p style={{ color: "green" }}>Submitted successfully.</p>
        )}
        {submitState.status === "error" && (
          <p style={{ color: "red" }}>Error: {submitState.error}</p>
        )}
      </form>

      <div>
        <h3>GeoJSON preview</h3>
        <pre
          style={{
            background: "#1e1e1e",
            color: "#d4d4d4",
            padding: "1rem",
            borderRadius: "4px",
            minWidth: "320px",
            minHeight: "200px",
          }}
        >
          {feature ? JSON.stringify(feature, null, 2) : "Fill in all points to preview GeoJSON"}
        </pre>
      </div>
    </div>
  );
}
