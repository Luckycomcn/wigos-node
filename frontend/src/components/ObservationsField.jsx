import { useState } from "react";
import ObjectArrayField, { ObjectArrayItemRow } from "./ObjectArrayField";
import Dialog from "./Dialog";
import { getAtPath, setAtPath, isFieldsetComplete } from "../formPath";
import { codelistProps } from "../codelists";
import { useCodelists } from "../useCodelists";
import { TIME_FIELDS, GEOMETRY_FIELDS } from "../fieldDefs";

// Field names/shapes follow definitions/Observations, Configurations and
// Instrument in wmo-im/wmdr2 schemas/wmdr2-bundled.json.

const INSTRUMENT_FIELDS = [
  { name: "id", label: "Instrument ID", type: "text" },
  { name: "manufacturer", label: "Manufacturer", type: "text" },
  { name: "model", label: "Model", type: "text" },
];

function observationFields(codelists) {
  const concept = (name, label, extra) => ({ name, label, type: "concept", ...codelistProps(name, codelists), ...extra });

  const verticalDistanceFields = [
    { name: "distances", label: "Distances", type: "array-string", placeholder: "Signed distance from reference surface" },
    concept("unit", "Unit"),
    concept("referenceSurface", "Reference surface"),
  ];

  const configurationFields = [
    { name: "id", label: "Configuration ID", type: "text", required: true },
    { name: "time", label: "Time", type: "object", fields: TIME_FIELDS },
    concept("observingMethod", "Observing method"),
    concept("operatingStatus", "Operating status"),
    concept("sourceOfObservation", "Source of observation"),
    { name: "geometry", label: "Location", type: "object", fields: GEOMETRY_FIELDS },
    { name: "instrument", label: "Instrument", type: "object", fields: INSTRUMENT_FIELDS },
    { name: "instrumentSerialNumber", label: "Instrument serial number", type: "text" },
    { name: "verticalDistance", label: "Vertical distance", type: "object", fields: verticalDistanceFields },
  ];

  const programAffiliationFields = [
    concept("programAffiliation", "Programme/network", { required: true }),
    concept("reportingStatus", "Reporting status"),
    { name: "dateStart", label: "From", type: "date" },
    { name: "dateEnd", label: "To (empty if ongoing)", type: "date" },
  ];

  return [
    concept("observedProperty", "Observed property", { required: true }),
    concept("observedGeometry", "Observed geometry"),
    {
      name: "programAffiliations",
      label: "Program affiliation",
      type: "array-object",
      fields: programAffiliationFields,
      required: true,
      summary: (p) => p.programAffiliation?.title || p.programAffiliation?.id,
    },
    {
      name: "configurations",
      label: "Configuration",
      type: "array-object",
      fields: configurationFields,
      required: true,
      summary: (c) => [c.id, [c.instrument?.manufacturer, c.instrument?.model].filter(Boolean).join(" ")].filter(Boolean).join(" – "),
    },
  ];
}

export default function ObservationsField({ value, onChange }) {
  const [trail, setTrail] = useState([]);
  const { codelists } = useCodelists();

  const fields = observationFields(codelists);

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
