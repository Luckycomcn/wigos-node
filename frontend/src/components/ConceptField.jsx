import { useState } from "react";

// Edits a codelist concept ({ id, title?, description?, url? }). With
// `options` or `groups` (entries from getCodelist) it renders a select that
// fills every property from the codelist; otherwise a text input for the
// codelist notation, with the other properties behind a "Details" toggle,
// for codelists that aren't cached locally yet.

const optionValue = (opt) => opt.id || opt.code;

function conceptFromOption(opt) {
  const concept = { id: opt.code, title: opt.label };
  if (opt.description) concept.description = opt.description;
  if (opt.id) concept.url = opt.id;
  return concept;
}

// Match on the concept URI first: notations can collide across codelists
// (e.g. "12244" is both an atmosphere and an ocean variable).
function findOption(allOptions, concept) {
  if (!concept) return null;
  return (
    (concept.url && allOptions.find((opt) => opt.id === concept.url)) ||
    allOptions.find((opt) => opt.code === concept.id) ||
    null
  );
}

const DETAIL_FIELDS = [
  { name: "title", label: "Title" },
  { name: "url", label: "URL", placeholder: "Concept URI" },
  { name: "description", label: "Description" },
];

function FreeTextConcept({ labelNode, value, onChange, placeholder }) {
  const [showDetails, setShowDetails] = useState(() => DETAIL_FIELDS.some((f) => value?.[f.name]));

  const update = (key, text) => {
    const next = { ...(value || { id: "" }), [key]: text };
    Object.keys(next).forEach((k) => {
      if (k !== "id" && !next[k]) delete next[k];
    });
    onChange(Object.values(next).some(Boolean) ? next : null);
  };

  return (
    <div className="field">
      {labelNode}
      <div className="list-row">
        <input
          className="field-input"
          value={value?.id || ""}
          placeholder={placeholder}
          onChange={(e) => update("id", e.target.value)}
        />
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => setShowDetails((open) => !open)}
          aria-expanded={showDetails}
        >
          {showDetails ? "Hide details" : "Details"}
        </button>
      </div>
      {showDetails &&
        DETAIL_FIELDS.map((field) => (
          <input
            key={field.name}
            className="field-input concept-detail"
            value={value?.[field.name] || ""}
            placeholder={field.placeholder || field.label}
            aria-label={field.label}
            onChange={(e) => update(field.name, e.target.value)}
          />
        ))}
    </div>
  );
}

export default function ConceptField({ label, value, onChange, options, groups, required, placeholder }) {
  const labelNode = (
    <label>
      {label} {required && <span className="required">*</span>}
    </label>
  );

  if (!options && !groups) {
    return <FreeTextConcept labelNode={labelNode} value={value} onChange={onChange} placeholder={placeholder} />;
  }

  const allOptions = groups ? groups.flatMap((group) => group.options) : options;
  const selected = findOption(allOptions, value);
  const renderOption = (opt) => (
    <option key={optionValue(opt)} value={optionValue(opt)}>
      {opt.label}
    </option>
  );

  return (
    <div className="field">
      {labelNode}
      <select
        className="field-input"
        value={selected ? optionValue(selected) : value?.id ? "__current__" : ""}
        onChange={(e) => {
          const opt = allOptions.find((o) => optionValue(o) === e.target.value);
          if (opt) onChange(conceptFromOption(opt));
          else if (e.target.value === "") onChange(null);
        }}
      >
        <option value="">None selected</option>
        {/* Keep a value that isn't in the codelist (or while it's still loading) visible. */}
        {!selected && value?.id && <option value="__current__">{value.title || value.id}</option>}
        {groups
          ? groups.map((group) => (
              <optgroup label={group.label} key={group.label}>
                {group.options.map(renderOption)}
              </optgroup>
            ))
          : options.map(renderOption)}
      </select>
    </div>
  );
}
