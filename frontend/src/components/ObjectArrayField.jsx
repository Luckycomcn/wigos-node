import { useEffect, useRef, useState } from "react";
import StringListField from "./StringListField";
import ConceptField from "./ConceptField";

const INPUT_TYPES = ["text", "date", "datetime-local"];

function emptyValueForField(field) {
  if (field.default !== undefined) return field.default;
  if (INPUT_TYPES.includes(field.type)) return "";
  if (field.type === "concept") return null;
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
        if (field.type === "concept") {
          return (
            <ConceptField
              key={field.name}
              label={field.label}
              value={item[field.name]}
              onChange={(next) => onChange({ ...item, [field.name]: next })}
              options={field.options}
              groups={field.groups}
              required={field.required}
              placeholder={field.placeholder}
            />
          );
        }
        if (field.type === "array-string") {
          return (
            <StringListField
              key={field.name}
              label={field.label}
              values={item[field.name] || []}
              onChange={(next) => onChange({ ...item, [field.name]: next })}
              placeholder={field.placeholder}
              required={field.required}
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
            required={field.required}
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
  // All items start collapsed when the form first loads. Items added later
  // via "+ Add" are not in this set, so they start expanded for editing.
  const [collapsed, setCollapsed] = useState(() => new Set(values.map((_, i) => i)));

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
    // The card elements that `target` is outside of - decided at focus time,
    // so a card added by the click that moved focus isn't included.
    const cardsOutside = (target) => {
      // A drill-in Dialog is rendered outside the card's DOM subtree, but
      // it's still editing that card's data, so don't treat it as leaving.
      if (target?.closest?.(".dialog-backdrop")) return [];
      return Object.values(cardRefs.current).filter((node) => node && !node.contains(target));
    };
    const collapseCards = (nodes) => {
      if (!nodes.length) return;
      setCollapsed((prev) => {
        let next = prev;
        Object.entries(cardRefs.current).forEach(([key, node]) => {
          const idx = Number(key);
          if (prev.has(idx) || !nodes.includes(node)) return;
          if (next === prev) next = new Set(prev);
          next.add(idx);
        });
        return next;
      });
    };
    // Focus moves on pointerdown, before the click. Collapsing a card then
    // shifts the layout, so the pointerup lands on a different element and
    // the click (e.g. on a "+ Add" button below the card) is lost. Wait until
    // the pointer is released and the click has been dispatched.
    let pointerDown = false;
    let pendingCards = null;
    const handlePointerDown = () => {
      pointerDown = true;
    };
    const handlePointerUp = () => {
      pointerDown = false;
      if (!pendingCards) return;
      const nodes = pendingCards;
      pendingCards = null;
      setTimeout(() => collapseCards(nodes), 0);
    };
    const handleFocusIn = (e) => {
      if (pointerDown) pendingCards = cardsOutside(e.target);
      else collapseCards(cardsOutside(e.target));
    };
    document.addEventListener("pointerdown", handlePointerDown, true);
    document.addEventListener("pointerup", handlePointerUp, true);
    document.addEventListener("pointercancel", handlePointerUp, true);
    document.addEventListener("focusin", handleFocusIn);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown, true);
      document.removeEventListener("pointerup", handlePointerUp, true);
      document.removeEventListener("pointercancel", handlePointerUp, true);
      document.removeEventListener("focusin", handleFocusIn);
    };
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
                  <span>{(itemSummary && itemSummary(item)) || `${itemLabel} ${i + 1}`}</span>
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
