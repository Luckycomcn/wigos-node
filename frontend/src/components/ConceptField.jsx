import { useEffect, useId, useRef, useState } from "react";

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

// Codelists longer than this get a type-to-filter box instead of a select.
const SEARCHABLE_MIN_OPTIONS = 15;

// Every whitespace-separated term has to appear in the label or notation.
function matchesQuery(opt, query) {
  const haystack = `${opt.label} ${opt.code}`.toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((term) => haystack.includes(term));
}

function SearchableConcept({ labelNode, value, onChange, groups, options, selected }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listRef = useRef(null);
  const listId = useId();

  const sections = groups || [{ label: null, options }];
  const matches = sections.flatMap((section) =>
    section.options.filter((opt) => matchesQuery(opt, query)).map((opt) => ({ group: section.label, opt }))
  );

  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  const choose = (opt) => {
    onChange(conceptFromOption(opt));
    setOpen(false);
    setQuery("");
  };

  const openList = () => {
    setOpen(true);
    const index = selected ? matches.findIndex((m) => m.opt === selected) : -1;
    setActive(Math.max(index, 0));
  };

  const handleKeyDown = (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) return openList();
      const step = e.key === "ArrowDown" ? 1 : -1;
      setActive((i) => Math.min(Math.max(i + step, 0), matches.length - 1));
    } else if (e.key === "Enter") {
      // Never submit the form from here.
      e.preventDefault();
      if (open && matches[active]) choose(matches[active].opt);
    } else if (e.key === "Escape" && open) {
      e.stopPropagation(); // keep an enclosing dialog open
      setOpen(false);
      setQuery("");
    }
  };

  const shownValue = open ? query : selected?.label || value?.title || value?.id || "";

  return (
    <div className="field">
      {labelNode}
      <div className="list-row">
        <div className="combo">
          <input
            className="field-input"
            role="combobox"
            aria-expanded={open}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={open && matches[active] ? `${listId}-${active}` : undefined}
            value={shownValue}
            placeholder={open ? selected?.label || "Type to filter" : "Type to filter"}
            onFocus={openList}
            onClick={() => !open && openList()}
            onBlur={() => {
              setOpen(false);
              setQuery("");
            }}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
              setOpen(true);
            }}
            onKeyDown={handleKeyDown}
          />
          {open && (
            <ul className="combo-list" role="listbox" id={listId} ref={listRef}>
              {matches.length === 0 && <li className="combo-empty">No matches</li>}
              {matches.map(({ group, opt }, i) => (
                <li key={`${group}|${optionValue(opt)}`} role="presentation">
                  {group && (i === 0 || matches[i - 1].group !== group) && (
                    <div className="combo-group">{group}</div>
                  )}
                  <div
                    id={`${listId}-${i}`}
                    data-index={i}
                    role="option"
                    aria-selected={opt === selected}
                    className={`combo-option${i === active ? " active" : ""}`}
                    // mousedown, not click: the input's blur would close the list first.
                    onMouseDown={(e) => {
                      e.preventDefault();
                      choose(opt);
                    }}
                    onMouseEnter={() => setActive(i)}
                  >
                    <span>{opt.label}</span>
                    {opt.code !== opt.label && <span className="combo-code">{opt.code}</span>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
        {value && (
          <button type="button" className="btn btn-ghost" onClick={() => onChange(null)}>
            Clear
          </button>
        )}
      </div>
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

  if (allOptions.length > SEARCHABLE_MIN_OPTIONS) {
    return (
      <SearchableConcept
        labelNode={labelNode}
        value={value}
        onChange={onChange}
        groups={groups}
        options={options}
        selected={selected}
      />
    );
  }
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
