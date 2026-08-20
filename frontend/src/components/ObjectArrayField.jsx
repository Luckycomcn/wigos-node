import StringListField from "./StringListField";

const INPUT_TYPES = ["text", "date", "datetime-local"];

function emptyValueForField(field) {
  if (INPUT_TYPES.includes(field.type)) return "";
  if (field.type === "object") return emptyItem(field.fields);
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
  const update = (index, next) => onChange(values.map((v, i) => (i === index ? next : v)));
  const add = () => onChange([...values, emptyItem(fields)]);
  const remove = (index) => onChange(values.filter((_, i) => i !== index));
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
        : values.map((item, i) => (
            <div className="nested-card" key={i}>
              <div className="nested-card-header">
                <span>
                  {itemLabel} {i + 1}
                </span>
                <button type="button" className="btn btn-ghost" onClick={() => remove(i)}>
                  Remove
                </button>
              </div>
              <ObjectArrayItemRow
                item={item}
                fields={fields}
                onChange={(next) => update(i, next)}
                path={[...path, i]}
                onDrillInto={onDrillInto}
              />
            </div>
          ))}

      {!atMax && (
        <button type="button" className="btn btn-secondary" onClick={add}>
          + Add {itemLabel}
        </button>
      )}
    </div>
  );
}
