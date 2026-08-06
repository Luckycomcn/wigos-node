import WmdrForm from "./components/WmdrForm";

export default function App() {
  return (
    <div>
      <header className="app-header">
        <h1>WMDR Station Record Builder</h1>
        <p>Fill in station metadata and generate a WIGOS-conformant GeoJSON record.</p>
      </header>
      <main className="app-main">
        <WmdrForm />
      </main>
    </div>
  );
}
