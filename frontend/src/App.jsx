import { useEffect, useState } from "react";
import WmdrForm from "./components/WmdrForm";
import StationsList from "./components/StationsList";
import LoginPage from "./components/LoginPage";
import BatchWizard from "./components/batch/BatchWizard";
import { fetchCurrentUser, initCsrf, logout } from "./auth";

export default function App() {
  const [view, setView] = useState({ mode: "list" });
  // Station IDs ticked in the list; kept here so they survive the batch wizard.
  const [selected, setSelected] = useState(new Set());
  const [auth, setAuth] = useState({ status: "loading", user: null });

  useEffect(() => {
    initCsrf()
      .then(fetchCurrentUser)
      .then((user) =>
        setAuth({ status: user ? "authenticated" : "anonymous", user })
      )
      .catch(() => setAuth({ status: "anonymous", user: null }));
  }, []);

  useEffect(() => {
    const onUnauthenticated = () => setAuth({ status: "anonymous", user: null });
    window.addEventListener("auth:unauthenticated", onUnauthenticated);
    return () =>
      window.removeEventListener("auth:unauthenticated", onUnauthenticated);
  }, []);

  async function handleLogout() {
    await logout();
    setAuth({ status: "anonymous", user: null });
    setView({ mode: "list" });
    setSelected(new Set());
  }

  return (
    <div>
      <header className="app-header">
        <h1>WMDR Station Record Builder</h1>
        <p>Fill in station metadata and generate a WIGOS-conformant GeoJSON record.</p>
        {auth.status === "authenticated" && (
          <div
            style={{
              display: "flex",
              gap: 8,
              alignItems: "center",
              marginTop: 8,
            }}
          >
            <span>{auth.user.email || auth.user.username}</span>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleLogout}
            >
              Log out
            </button>
          </div>
        )}
      </header>
      <main className="app-main">
        {auth.status === "loading" && <p>Loading…</p>}

        {auth.status === "anonymous" && (
          <LoginPage
            onSuccess={(user) => setAuth({ status: "authenticated", user })}
          />
        )}

        {auth.status === "authenticated" && (
          <>
            {view.mode === "list" && (
              <StationsList
                onNew={() => setView({ mode: "new" })}
                onEdit={(stationId) => setView({ mode: "edit", stationId })}
                selected={selected}
                onSelectedChange={setSelected}
                onBatch={(stationIds) => setView({ mode: "batch", stationIds })}
              />
            )}
            {view.mode === "batch" && (
              <BatchWizard
                stationIds={view.stationIds}
                // Only the stations that failed stay selected.
                onApplied={(failedIds) => setSelected(new Set(failedIds))}
                onClose={() => setView({ mode: "list" })}
              />
            )}
            {(view.mode === "new" || view.mode === "edit") && (
              <WmdrForm
                key={view.mode === "edit" ? view.stationId : "new"}
                stationId={view.mode === "edit" ? view.stationId : null}
                onSaved={() => setView({ mode: "list" })}
                onCancel={() => setView({ mode: "list" })}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}
