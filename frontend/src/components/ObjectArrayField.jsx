import { useEffect, useRef, useState } from "react";
import StringListField from "./StringListField";

const INPUT_TYPES = ["text", "date", "datetime-local"];

function emptyValueForField(field) {
  if (INPUT_TYPES.includes(field.type)) return "";
  if (field.type === "object") return emptyItem(field.fields);
  if (field.type === "array-object" && field.required) return [emptyItem(field.fields)];
  return [];
}

function emptyItem(fields) {
  return Object.fromEntries(fields.map((field) => [field.name, emptyValueForField(field)]));
}

export function ObjectArrayItemRow({ item, fields, onChange, path, onDrillInto }) {
  return (
    <>
      {fields.map((field) => {
        if (INPUT_TYPES.includes(field.type)) {
          return (
            <div className="field" key={field.name}>
              <label>
                {field.label} {field.required && <span className="required">*</span>}
              </label>
              <input
                className="field-input"
                type={field.type}
                value={item[field.name] || ""}
                placeholder={field.placeholder}
                onChange={(e) => onChange({ ...item, [field.name]: e.target.value })}
              />
            </div>
          );
        }
        if (field.type === "array-string") {
          return (
            <StringListField
              key={field.name}
              label={field.label}
              values={item[field.name] || []}
              onChange={(next) => onChange({ ...item, [field.name]: next })}
            />
          );
        }
        if (field.type === "object") {
          return (
            <div className="nested-card" key={field.name}>
              <div className="nested-card-header">
                <span>{field.label}</span>
              </div>
              <ObjectArrayItemRow
                item={item[field.name] || {}}
                fields={field.fields}
                onChange={(next) => onChange({ ...item, [field.name]: next })}
                path={[...path, field.name]}
                onDrillInto={onDrillInto}
              />
            </div>
          );
        }
        return (
          <ObjectArrayField
            key={field.name}
            label={field.label}
            itemLabel={field.label}
            values={item[field.name] || []}
            onChange={(next) => onChange({ ...item, [field.name]: next })}
            fields={field.fields}
            itemSummary={field.summary}
            mode="summary"
            path={[...path, field.name]}
            onDrillInto={onDrillInto}
            maxItems={field.maxItems}
          />
        );
      })}
    </>
  );
}

export default function ObjectArrayField({
  label,
  itemLabel,
  values,
  onChange,
  fields,
  itemSummary,
  mode = "full",
  path,
  onDrillInto,
  required,
  maxItems,
}) {
  // Only the first item starts expanded; the rest start collapsed.
  const [collapsed, setCollapsed] = useState(() => new Set(values.map((_, i) => i).slice(1)));

  const update = (index, next) => onChange(values.map((v, i) => (i === index ? next : v)));
  const add = () => onChange([...values, emptyItem(fields)]);
  const remove = (index) => {
    onChange(values.filter((_, i) => i !== index));
    setCollapsed((prev) => {
      const next = new Set();
      prev.forEach((idx) => {
        if (idx < index) next.add(idx);
        else if (idx > index) next.add(idx - 1);
      });
      return next;
    });
  };
  const toggleCollapsed = (index) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  // Auto-collapse any expanded card once focus lands somewhere outside it -
  // listening globally (rather than for onBlur within each card) so a card
  // that was never focused in the first place (e.g. the one expanded by
  // default) still collapses when focus moves elsewhere on the page.
  const cardRefs = useRef({});
  useEffect(() => {
    if (mode !== "full") return undefined;
    const handleFocusIn = (e) => {
      // A drill-in Dialog is rendered outside the card's DOM subtree, but
      // it's still editing that card's data, so don't treat it as leaving.
      if (e.target?.closest?.(".dialog-backdrop")) return;
      setCollapsed((prev) => {
        let next = prev;
        Object.entries(cardRefs.current).forEach(([key, node]) => {
          const idx = Number(key);
          if (prev.has(idx) || !node || node.contains(e.target)) return;
          if (next === prev) next = new Set(prev);
          next.add(idx);
        });
        return next;
      });
    };
    document.addEventListener("focusin", handleFocusIn);
    return () => document.removeEventListener("focusin", handleFocusIn);
  }, [mode]);
  const atMax = maxItems != null && values.length >= maxItems;

  return (
    <div className="list-field">
      <div className="list-field-label">
        {label} {required && <span className="required">*</span>}
      </div>

      {mode === "summary"
        ? values.map((item, i) => (
            <div className="summary-row" key={i}>
              <span className="summary-row-label">
                {(itemSummary && itemSummary(item)) || `New ${itemLabel.toLowerCase()}`}
              </span>
              <div className="summary-row-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => onDrillInto([...path, i], `${itemLabel} ${i + 1}`, fields)}
                >
                  Edit details &gt;
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => remove(i)}>
                  Remove
                </button>
              </div>
            </div>
          ))
        : values.map((item, i) => {
            const isCollapsed = collapsed.has(i);
            return (
              <div
                className="nested-card"
                key={i}
                ref={(node) => {
                  cardRefs.current[i] = node;
                }}
              >
                <div className="nested-card-header">
                  <span>
                    {itemLabel} {i + 1}
                  </span>
                  <div className="nested-card-header-actions">
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={() => toggleCollapsed(i)}
                      aria-expanded={!isCollapsed}
                    >
                      {isCollapsed ? "Expand" : "Minimize"}
                    </button>
                    <button type="button" className="btn btn-ghost" onClick={() => remove(i)}>
                      Remove
                    </button>
                  </div>
                </div>
                {!isCollapsed && (
                  <ObjectArrayItemRow
                    item={item}
                    fields={fields}
                    onChange={(next) => update(i, next)}
                    path={[...path, i]}
                    onDrillInto={onDrillInto}
                  />
                )}
              </div>
            );
          })}

      {!atMax && (
        <button type="button" className="btn btn-secondary" onClick={add}>
          + Add {itemLabel}
        </button>
      )}
    </div>
  );
}
