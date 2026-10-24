import { getCodelist } from "./api";

// Codelists (cached by the backend, see populate_codelists) behind each
// concept field: a scheme name for a single list, or labelled schemes for a
// field whose concepts come from several lists, shown as option groups.
// The labels are message keys (translated where the groups are rendered), so
// the option-group headings follow the UI language.
export const CODELISTS = {
  observedProperty: [
    { scheme: "ObservedVariableAtmosphere", label: "opt.atmosphere" },
    { scheme: "ObservedVariableOcean", label: "opt.ocean" },
    { scheme: "ObservedVariableTerrestrial", label: "opt.terrestrial" },
    { scheme: "ObservedVariableOuterSpace", label: "opt.outerSpace" },
    { scheme: "ObservedVariableEarth", label: "opt.earth" },
  ],
  observedGeometry: "Geometry",
  programAffiliation: "ProgramAffiliation",
  reportingStatus: "ReportingStatus",
  observingMethod: [
    { scheme: "ObservingMethodAtmosphere", label: "opt.atmosphere" },
    { scheme: "ObservingMethodOcean", label: "opt.ocean" },
    { scheme: "ObservingMethodTerrestrial", label: "opt.terrestrial" },
  ],
  operatingStatus: "InstrumentOperatingStatus",
  sourceOfObservation: "SourceOfObservation",
  unit: "unit",
  referenceSurface: "ReferenceSurfaceType",
};

const sortByLabel = (options) => [...options].sort((a, b) => a.label.localeCompare(b.label));

export function loadCodelist(spec) {
  if (typeof spec === "string") return getCodelist(spec).then(sortByLabel).catch(() => []);
  return Promise.all(
    spec.map(({ scheme, label }) =>
      getCodelist(scheme)
        .then((options) => ({ label, options: sortByLabel(options) }))
        .catch(() => ({ label, options: [] }))
    )
  );
}

// `options` for a single list, `groups` for several.
export const codelistProps = (name, codelists) =>
  typeof CODELISTS[name] === "string" ? { options: codelists[name] } : { groups: codelists[name] };

// Every entry of a codelist, flattening option groups.
export const codelistOptions = (name, codelists) => {
  const list = codelists[name] || [];
  return typeof CODELISTS[name] === "string" ? list : list.flatMap((group) => group.options);
};
