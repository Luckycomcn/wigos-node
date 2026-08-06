export default function StringListField({ label, values, onChange, placeholder, required }) {
  const update = (index, value) => {
    onChange(values.map((v, i) => (i === index ? value : v)));
  };

  const add = () => onChange([...values, ""]);

  const remove = (index) => {
    const next = values.filter((_, i) => i !== index);
    onChange(next.length ? next : [""]);
  };

  return (
    <div className="list-field">
      <div className="list-field-label">
        {label} {required && <span className="required">*</span>}
      </div>
      {values.map((v, i) => (
        <div key={i} className="list-row">
          <input
            className="list-input"
            value={v}
            placeholder={placeholder}
            onChange={(e) => update(i, e.target.value)}
          />
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => remove(i)}
            disabled={values.length <= 1}
          >
            Remove
          </button>
        </div>
      ))}
      <button type="button" className="btn btn-secondary" onClick={add}>
        + Add
      </button>
    </div>
  );
}
