import { WIGOS_ID_PATTERN, splitWigosId, joinWigosId } from "../wmdr";

// A WIGOS station identifier entered as its four parts: a fixed scheme (0),
// the issuer country from ISO3166, the issue number and the local identifier.
export default function WigosIdInput({ value, onChange, issuerCountries, disabled, labelPrefix = "" }) {
  const parts = splitWigosId(value);
  const setPart = (part) => (e) => onChange(joinWigosId({ ...parts, [part]: e.target.value }));

  return (
    <div className="row wigos-id-row">
      <input
        className="field-input"
        value={parts.scheme}
        disabled
        aria-label={`${labelPrefix}Identifier scheme`}
        title="Identifier scheme (always 0 for a WIGOS station identifier)"
      />
      <select
        className="field-input"
        value={parts.issuer}
        onChange={setPart("issuer")}
        disabled={disabled}
        aria-label={`${labelPrefix}Issuer ID`}
      >
        <option value="">Select a country</option>
        {issuerCountries.map((country) => (
          <option key={country.code} value={String(Number(country.code))}>
            {country.code} — {country.label}
          </option>
        ))}
      </select>
      <input
        className="field-input"
        value={parts.issue}
        onChange={setPart("issue")}
        placeholder="Issue number"
        disabled={disabled}
        aria-label={`${labelPrefix}Issue number`}
      />
      <input
        className="field-input"
        value={parts.local}
        onChange={setPart("local")}
        placeholder="Local identifier"
        disabled={disabled}
        aria-label={`${labelPrefix}Local identifier`}
      />
    </div>
  );
}

// Format, duplicate and availability feedback shown under a WigosIdInput.
// `status` comes from useWigosIdAvailability.
export function WigosIdFeedback({ id, status, duplicate }) {
  if (id && !WIGOS_ID_PATTERN.test(id)) {
    return (
      <div className="field-error">
        Select a country, and enter a numeric issue number and a local identifier
        (letters, numbers, &quot;.&quot;, &quot;_&quot; or &quot;-&quot;).
      </div>
    );
  }
  if (duplicate) {
    return <div className="field-error">This identifier is entered more than once in this form.</div>;
  }
  switch (status) {
    case "checking":
      return <div className="field-hint">Checking availability...</div>;
    case "available":
      return <div className="field-success">Identifier is available.</div>;
    case "taken":
      return <div className="field-error">This WIGOS identifier is already registered to another station.</div>;
    case "error":
      return <div className="field-hint">Couldn&apos;t check availability. It will be checked again on save.</div>;
    default:
      return null;
  }
}
