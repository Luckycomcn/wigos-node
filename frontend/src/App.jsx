import { useState } from "react";
import WmdrForm from "./components/WmdrForm";
import StationsList from "./components/StationsList";

export default function App() {
  const [view, setView] = useState({ mode: "list" });

  return (
    <div>
      <header className="app-header">
        <h1>WMDR Station Record Builder</h1>
        <p>Fill in station metadata and generate a WIGOS-conformant GeoJSON record.</p>
      </header>
      <main className="app-main">
        {view.mode === "list" && (
          <StationsList
            onNew={() => setView({ mode: "new" })}
            onEdit={(id) => setView({ mode: "edit", id })}
          />
        )}
        {view.mode !== "list" && (
          <WmdrForm
            key={view.mode === "edit" ? view.id : "new"}
            stationId={view.mode === "edit" ? view.id : null}
            onSaved={() => setView({ mode: "list" })}
            onCancel={() => setView({ mode: "list" })}
          />
        )}
      </main>
    </div>
  );
}
