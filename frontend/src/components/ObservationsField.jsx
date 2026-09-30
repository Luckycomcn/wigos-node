import { useEffect, useState } from "react";
import ObjectArrayField, { ObjectArrayItemRow } from "./ObjectArrayField";
import Dialog from "./Dialog";
import { getAtPath, setAtPath, isFieldsetComplete } from "../formPath";
import { getCodelist } from "../api";
import { TIME_FIELDS, GEOMETRY_FIELDS } from "../fieldDefs";

const OBSERVED_PROPERTY_CODELISTS = [
  { scheme: "ObservedVariableAtmosphere", label: "Atmosphere" },
  { scheme: "ObservedVariableOcean", label: "Ocean" },
  { scheme: "ObservedVariableTerrestrial", label: "Terrestrial" },
  { scheme: "ObservedVariableOuterSpace", label: "Outer space" },
];

// Field names/shapes follow definitions/Observations, Configurations and
// Instrument in wmo-im/wmdr2 schemas/wmdr2-bundled.json. Concept fields
// without `groups` take the codelist notation as free text, since those
// codelists aren't cached by the backend yet.

const INSTRUMENT_FIELDS = [
  { name: "id", label: "Instrument ID", type: "text" },
  { name: "manufacturer", label: "Manufacturer", type: "text" },
  { name: "model", label: "Model", type: "text" },
];

const VERTICAL_DISTANCE_FIELDS = [
  { name: "distances", label: "Distances", type: "array-string", placeholder: "Signed distance from reference surface" },
  { name: "unit", label: "Unit", type: "concept", placeholder: "e.g. m" },
  { name: "referenceSurface", label: "Reference surface", type: "concept", placeholder: "e.g. localGroundLevel" },
];

const CONFIGURATION_FIELDS = [
  { name: "id", label: "Configuration ID", type: "text", required: true },
  { name: "time", label: "Time", type: "object", fields: TIME_FIELDS },
  { name: "observingMethod", label: "Observing method", type: "concept", placeholder: "ObservingMethod notation" },
  { name: "operatingStatus", label: "Operating status", type: "concept", placeholder: "e.g. operational" },
  { name: "sourceOfObservation", label: "Source of observation", type: "concept", placeholder: "e.g. automaticReading" },
  { name: "geometry", label: "Location", type: "object", fields: GEOMETRY_FIELDS },
  { name: "instrument", label: "Instrument", type: "object", fields: INSTRUMENT_FIELDS },
  { name: "instrumentSerialNumber", label: "Instrument serial number", type: "text" },
  { name: "verticalDistance", label: "Vertical distance", type: "object", fields: VERTICAL_DISTANCE_FIELDS },
];

const PROGRAM_AFFILIATION_FIELDS = [
  { name: "programAffiliation", label: "Programme/network", type: "concept", required: true, placeholder: "e.g. GOS" },
  { name: "reportingStatus", label: "Reporting status", type: "concept", placeholder: "e.g. operational" },
  { name: "dateStart", label: "From", type: "date" },
  { name: "dateEnd", label: "To (empty if ongoing)", type: "date" },
];

function observationFields(observedPropertyGroups) {
  return [
    {
      name: "observedProperty",
      label: "Observed property",
      type: "concept",
      required: true,
      groups: observedPropertyGroups,
    },
    { name: "observedGeometry", label: "Observed geometry", type: "concept", placeholder: "e.g. point" },
    {
      name: "programAffiliations",
      label: "Program affiliation",
      type: "array-object",
      fields: PROGRAM_AFFILIATION_FIELDS,
      required: true,
      summary: (p) => p.programAffiliation?.title || p.programAffiliation?.id,
    },
    {
      name: "configurations",
      label: "Configuration",
      type: "array-object",
      fields: CONFIGURATION_FIELDS,
      required: true,
      summary: (c) => [c.id, [c.instrument?.manufacturer, c.instrument?.model].filter(Boolean).join(" ")].filter(Boolean).join(" – "),
    },
  ];
}

export default function ObservationsField({ value, onChange }) {
  const [trail, setTrail] = useState([]);
  const [observedPropertyGroups, setObservedPropertyGroups] = useState([]);

  useEffect(() => {
    let cancelled = false;
    Promise.all(
      OBSERVED_PROPERTY_CODELISTS.map(({ scheme, label }) =>
        getCodelist(scheme)
          .then((options) => ({ label, options: [...options].sort((a, b) => a.label.localeCompare(b.label)) }))
          .catch(() => ({ label, options: [] }))
      )
    ).then((groups) => {
      if (!cancelled) setObservedPropertyGroups(groups);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const fields = observationFields(observedPropertyGroups);

  const push = (path, label, fields) => setTrail((prev) => [...prev, { path, label, fields }]);
  const back = () => setTrail((prev) => prev.slice(0, -1));
  const close = () => setTrail([]);

  const current = trail[trail.length - 1];

  return (
    <>
      <ObjectArrayField
        label="Observations"
        itemLabel="Observation"
        values={value}
        onChange={onChange}
        fields={fields}
        itemSummary={(o) => o.observedProperty?.title || o.observedProperty?.id}
        mode="full"
        path={[]}
        onDrillInto={push}
        required
      />

      <Dialog open={!!current} title={current?.label} onClose={close}>
        {current && (
          <>
            {trail.length > 1 && (
              <button type="button" className="btn btn-ghost dialog-back" onClick={back}>
                &lt; Back to {trail[trail.length - 2].label}
              </button>
            )}
            <ObjectArrayItemRow
              item={getAtPath(value, current.path) || {}}
              fields={current.fields}
              onChange={(next) => onChange(setAtPath(value, current.path, next))}
              path={current.path}
              onDrillInto={push}
            />
            {trail.length <= 1 && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={close}
                disabled={!isFieldsetComplete(getAtPath(value, current.path) || {}, current.fields)}
              >
                Done
              </button>
            )}
          </>
        )}
      </Dialog>
    </>
  );
}
