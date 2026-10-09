import WigosIdInput, { WigosIdFeedback } from "./WigosIdInput";

// A list of WIGOS IDs, each entered part by part like the primary identifier.
// Starts empty: rows only appear once "+ Add" is pressed, and every row can be removed.
export default function WigosIdListField({ label, values, onChange, issuerCountries, statusOf, duplicates }) {
  const update = (index, value) => {
    onChange(values.map((v, i) => (i === index ? value : v)));
  };

  const add = () => onChange([...values, ""]);

  const remove = (index) => onChange(values.filter((_, i) => i !== index));

  return (
    <div className="list-field">
      {values.length > 0 && <div className="list-field-label">{label}</div>}
      {values.map((v, i) => (
        <div key={i} className="wigos-id-list-item">
          <div className="list-row">
            <WigosIdInput
              value={v}
              onChange={(value) => update(i, value)}
              issuerCountries={issuerCountries}
              labelPrefix={`${label} ${i + 1}: `}
            />
            <button type="button" className="btn btn-ghost" onClick={() => remove(i)}>
              Remove
            </button>
          </div>
          <WigosIdFeedback id={v} status={statusOf(v)} duplicate={duplicates.has(v)} />
        </div>
      ))}
      <button type="button" className="btn btn-secondary" onClick={add}>
        + Add additional WIGOS identifier
      </button>
    </div>
  );
}
