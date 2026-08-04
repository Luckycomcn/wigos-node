import GeoJsonForm from "./components/GeoJsonForm";

export default function App() {
  return (
    <div style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <h1>GeoJSON builder</h1>
      <GeoJsonForm />
    </div>
  );
}
