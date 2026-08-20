import { useState } from "react";
import ObjectArrayField, { ObjectArrayItemRow } from "./ObjectArrayField";
import Dialog from "./Dialog";
import { getAtPath, setAtPath } from "../formPath";

// Field names/shapes verified against schemas/observingCapability.yaml,
// deployment.yaml and instrument.yaml in wmo-im/wmdr2 (wigosbox-catalogue1.99-dev),
// plus the shared "time" definition in wcmp2's wcmpRecordGeoJSON.yaml.

const TIME_FIELDS = [
  { name: "date", label: "Date", type: "date" },
  { name: "timestamp", label: "Timestamp", type: "datetime-local" },
  { name: "intervalStart", label: "Interval start", type: "date" },
  { name: "intervalEnd", label: "Interval end", type: "date" },
  { name: "resolution", label: "Resolution", type: "text", placeholder: "ISO 8601 duration, e.g. P1D" },
];

const REFERENCE_SURFACE_FIELDS = [
  { name: "referenceSurface", label: "Reference surface type", type: "text", required: true },
  { name: "verticalDistance", label: "Vertical distance", type: "text", required: true, placeholder: "Height above reference surface" },
];

const GEOMETRY_FIELDS = [
  { name: "latitude", label: "Latitude", type: "text" },
  { name: "longitude", label: "Longitude", type: "text" },
];

const INSTRUMENT_FIELDS = [
  { name: "id", label: "Instrument ID", type: "text", required: true },
  { name: "manufacturer", label: "Manufacturer", type: "text" },
  { name: "model", label: "Model", type: "text" },
  { name: "serialNumber", label: "Serial number", type: "text" },
];

const DEPLOYMENT_FIELDS = [
  { name: "id", label: "Deployment ID", type: "text", required: true },
  { name: "geometry", label: "Location", type: "object", fields: GEOMETRY_FIELDS },
  { name: "time", label: "Time", type: "object", fields: TIME_FIELDS },
  { name: "keywords", label: "Keywords", type: "array-string" },
  {
    name: "referenceSurfaces",
    label: "Reference surface",
    type: "array-object",
    fields: REFERENCE_SURFACE_FIELDS,
    summary: (r) => [r.referenceSurface, r.verticalDistance].filter(Boolean).join(" – "),
  },
  { name: "instrument", label: "Instrument", type: "object", fields: INSTRUMENT_FIELDS },
];

const OBSERVING_CAPABILITY_FIELDS = [
  { name: "observedProperty", label: "Observed property", type: "text", required: true },
  { name: "observingMethod", label: "Observing method", type: "text" },
  { name: "operatingStatus", label: "Operating status", type: "text" },
  { name: "sourceOfObservation", label: "Source of observation", type: "text" },
  { name: "time", label: "Time", type: "object", fields: TIME_FIELDS },
  {
    name: "deployments",
    label: "Deployment",
    type: "array-object",
    fields: DEPLOYMENT_FIELDS,
    maxItems: 1,
    summary: (d) => [d.instrument?.manufacturer, d.instrument?.model].filter(Boolean).join(" ") || d.id,
  },
];

export default function ObservingCapabilitiesField({ value, onChange }) {
  const [trail, setTrail] = useState([]);

  const push = (path, label, fields) => setTrail((prev) => [...prev, { path, label, fields }]);
  const back = () => setTrail((prev) => prev.slice(0, -1));
  const close = () => setTrail([]);

  const current = trail[trail.length - 1];

  return (
    <>
      <ObjectArrayField
        label="Observing capabilities"
        itemLabel="Observing capability"
        values={value}
        onChange={onChange}
        fields={OBSERVING_CAPABILITY_FIELDS}
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
              <button type="button" className="btn btn-secondary" onClick={close}>
                Done
              </button>
            )}
          </>
        )}
      </Dialog>
    </>
  );
}
