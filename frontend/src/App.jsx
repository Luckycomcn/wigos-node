import { useEffect, useState } from "react";
import WmdrForm from "./components/WmdrForm";
import StationsList from "./components/StationsList";
import LoginPage from "./components/LoginPage";
import { fetchCurrentUser, initCsrf, logout } from "./auth";

export default function App() {
  const [view, setView] = useState({ mode: "list" });
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
              />
            )}
            {view.mode !== "list" && (
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
