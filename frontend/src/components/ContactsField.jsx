import { useState } from "react";
import ObjectArrayField, { ObjectArrayItemRow } from "./ObjectArrayField";
import Dialog from "./Dialog";
import { getAtPath, setAtPath, isFieldsetComplete } from "../formPath";

const PHONE_FIELDS = [
  { name: "value", label: "Phone number", type: "text", placeholder: "+41791234567" },
  { name: "roles", label: "Roles", type: "array-string" },
];

const EMAIL_FIELDS = [
  { name: "value", label: "Email address", type: "text", placeholder: "name@example.org" },
  { name: "roles", label: "Roles", type: "array-string" },
];

const ADDRESS_FIELDS = [
  { name: "city", label: "City", type: "text" },
  { name: "administrativeArea", label: "State / province", type: "text" },
  { name: "postalCode", label: "Postal code", type: "text" },
  { name: "country", label: "Country", type: "text" },
  { name: "deliveryPoint", label: "Delivery point lines", type: "array-string" },
  { name: "roles", label: "Roles", type: "array-string" },
];

const CONTACT_FIELDS = [
  { name: "organization", label: "Organization", type: "text", required: true },
  { name: "name", label: "Name", type: "text" },
  { name: "position", label: "Position", type: "text" },
  { name: "phones", label: "Phone", type: "array-object", fields: PHONE_FIELDS, summary: (p) => p.value },
  { name: "emails", label: "Email", type: "array-object", fields: EMAIL_FIELDS, summary: (e) => e.value },
  {
    name: "addresses",
    label: "Address",
    type: "array-object",
    fields: ADDRESS_FIELDS,
    summary: (a) => [a.city, a.country].filter(Boolean).join(", "),
  },
  { name: "roles", label: "Roles", type: "array-string" },
];

export default function ContactsField({ value, onChange }) {
  const [trail, setTrail] = useState([]);

  const push = (path, label, fields) => setTrail((prev) => [...prev, { path, label, fields }]);
  const back = () => setTrail((prev) => prev.slice(0, -1));
  const close = () => setTrail([]);

  const current = trail[trail.length - 1];

  return (
    <>
      <ObjectArrayField
        label="Contacts"
        itemLabel="Contact"
        values={value}
        onChange={onChange}
        fields={CONTACT_FIELDS}
        itemSummary={(c) => [c.organization, c.name].filter(Boolean).join(" - ")}
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
