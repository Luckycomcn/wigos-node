import { useState } from "react";
import { login } from "../auth";

export default function LoginPage({ onSuccess }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await login(username, password);
      onSuccess?.(user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="card"
      onSubmit={handleSubmit}
      style={{ maxWidth: 420, margin: "0 auto" }}
    >
      <h3>Sign in</h3>
      {error && <div className="status-message status-error">{error}</div>}

      <div className="field">
        <label>Email or username</label>
        <input
          className="field-input"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          autoFocus
        />
      </div>

      <div className="field">
        <label>Password</label>
        <input
          className="field-input"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
      </div>

      <button
        type="submit"
        className="btn btn-primary"
        disabled={busy || !username || !password}
      >
        {busy ? "Signing in…" : "Sign in"}
      </button>

      <p style={{ marginTop: 12, fontSize: 13 }}>
        Or use the <a href="/api/auth/login/?next=/">Django login page</a>.
      </p>
    </form>
  );
}
