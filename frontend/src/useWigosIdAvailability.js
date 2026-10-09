import { useEffect, useState } from "react";
import { checkWigosIdentifiers } from "./api";
import { wigosIdsToCheck } from "./wmdr";

const DEBOUNCE_MS = 400;

// Looks up whether WIGOS IDs are already registered to a station. Returns a
// function giving each ID's status: null (not checked: malformed, empty or one
// of `ownIds`), "checking", "available", "taken" or "error".
//
// Results are cached per ID, so a reply that arrives after the user has moved
// on is still correct for the ID it was about. Failed lookups are retried the
// next time the set of IDs to check changes.
export function useWigosIdAvailability(ids, ownIds) {
  const [results, setResults] = useState({});
  const checkable = wigosIdsToCheck(ids, ownIds);
  const pendingKey = checkable
    .filter((id) => results[id] === undefined || results[id] === "error")
    .join(" ");

  useEffect(() => {
    if (!pendingKey) return;
    const batch = pendingKey.split(" ");
    const timer = setTimeout(() => {
      checkWigosIdentifiers(batch)
        .then((taken) => batch.map((id) => [id, taken[id] ? "taken" : "available"]))
        .catch(() => batch.map((id) => [id, "error"]))
        .then((entries) => setResults((prev) => ({ ...prev, ...Object.fromEntries(entries) })));
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [pendingKey]);

  return (id) => (checkable.includes(id) ? results[id] ?? "checking" : null);
}
