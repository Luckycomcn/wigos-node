import { useEffect, useState } from "react";
import { CODELISTS, loadCodelist } from "./codelists";

// Loads the named codelists once. Each name maps to [] until it has loaded
// (or when it fails to load); `loaded` is true once all of them are in.
export function useCodelists(names = Object.keys(CODELISTS)) {
  const key = names.join(" ");
  const [state, setState] = useState(() => ({
    loaded: false,
    codelists: Object.fromEntries(names.map((name) => [name, []])),
  }));

  useEffect(() => {
    let cancelled = false;
    const list = key.split(" ").filter(Boolean);
    Promise.all(list.map((name) => loadCodelist(CODELISTS[name]))).then((lists) => {
      if (!cancelled) setState({ loaded: true, codelists: Object.fromEntries(list.map((name, i) => [name, lists[i]])) });
    });
    return () => {
      cancelled = true;
    };
  }, [key]);

  return state;
}
