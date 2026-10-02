import { useEffect, useState } from "react";
import {
  WIGOS_ID_PATTERN,
  buildWmdrRecord,
  parseWmdrRecord,
  splitWigosId,
  joinWigosId,
} from "../wmdr";
import { validateWmdrRecord } from "../wmdrSchema";
import { saveStation, getStation, getCodelist } from "../api";
import StringListField from "./StringListField";
import ContactsField from "./ContactsField";
import ConceptField from "./ConceptField";
import ObjectArrayField, { ObjectArrayItemRow } from "./ObjectArrayField";
import ObservationsField from "./ObservationsField";
import MapPreview from "./MapPreview";
import { TIME_FIELDS, LINK_FIELDS } from "../fieldDefs";

const initialState = {
  id: "",
  latitude: "",
  longitude: "",
  height: "",
  time: { date: "", timestamp: "", intervalStart: "", intervalEnd: "", resolution: "" },
  title: "",
  description: "",
  additionalTitles: [""],
  additionalIds: [""],
  facilityType: null,
  wmoRegion: null,
  contacts: [],
  created: "",
  updated: "",
  territories: [],
  externalIds: [],
  observations: [],
  links: [],
};

const EXTERNAL_ID_FIELDS = [
  { name: "value", label: "Identifier", type: "text", required: true },
  { name: "scheme", label: "Scheme", type: "text", placeholder: "Issuing authority, ideally a resolvable URI" },
];

const territoryFields = (territoryNames) => [
  { name: "territory", label: "Territory", type: "concept", required: true, options: territoryNames },
  { name: "dateStart", label: "From", type: "date" },
  { name: "dateEnd", label: "To (empty if ongoing)", type: "date" },
];


export default function WmdrForm({ stationId, onSaved, onCancel }) {
  const isEditing = stationId != null;
  const [form, setForm] = useState(initialState);
  const [submitState, setSubmitState] = useState({ status: "idle" });
  const [loadState, setLoadState] = useState({ status: isEditing ? "loading" : "idle" });
  const [facilityTypes, setFacilityTypes] = useState([]);
  const [wmoRegions, setWmoRegions] = useState([]);
  const [issuerCountries, setIssuerCountries] = useState([]);
  const [territoryNames, setTerritoryNames] = useState([]);

  useEffect(() => {
    getCodelist("FacilityType").then(setFacilityTypes).catch(() => setFacilityTypes([]));
    getCodelist("WMORegion").then(setWmoRegions).catch(() => setWmoRegions([]));
    getCodelist("ISO3166").then(setIssuerCountries).catch(() => setIssuerCountries([]));
    getCodelist("TerritoryName")
      .then((options) => setTerritoryNames([...options].sort((a, b) => a.label.localeCompare(b.label))))
      .catch(() => setTerritoryNames([]));
  }, []);

  useEffect(() => {
    if (!isEditing) return;
    setLoadState({ status: "loading" });
    getStation(stationId)
      .then((record) => {
        setForm(parseWmdrRecord(record));
        setLoadState({ status: "success" });
      })
      .catch((err) => setLoadState({ status: "error", error: err.message }));
  }, [isEditing, stationId]);

  const set = (field) => (value) => setForm((prev) => ({ ...prev, [field]: value }));
  const setInput = (field) => (e) => set(field)(e.target.value);

  const idParts = splitWigosId(form.id);
  const setIdPart = (part) => (e) => set("id")(joinWigosId({ ...idParts, [part]: e.target.value }));

  const idValid = form.id === "" || WIGOS_ID_PATTERN.test(form.id);
  const record = buildWmdrRecord(form);
  const schemaErrors = validateWmdrRecord(record);
  const valid = schemaErrors.length === 0;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!valid) return;
    setSubmitState({ status: "loading" });
    try {
      const data = await saveStation(stationId, record);
      setSubmitState({ status: "success", data });
      onSaved?.(data.station_id);
    } catch (err) {
      setSubmitState({ status: "error", error: err.message });
    }
  };

  const backLink = onCancel && (
    <button type="button" className="btn-link" onClick={onCancel}>
      &lt; Back to stations
    </button>
  );

  if (isEditing && loadState.status === "loading") {
    return (
      <div className="card">
        {backLink}
        <p>Loading station...</p>
      </div>
    );
  }

  if (isEditing && loadState.status === "error") {
    return (
      <div className="card">
        {backLink}
        <div className="status-message status-error">Error: {loadState.error}</div>
      </div>
    );
  }

  return (
    <>
      {backLink}
      <div className="form-layout">
        <form onSubmit={handleSubmit}>
          <div className="card">
            <h3>Identification</h3>
            <div className="field">
              <label>
                WIGOS station identifier <span className="required">*</span>
              </label>
              <div className="row wigos-id-row">
                <input
                  className="field-input"
                  value={idParts.scheme}
                  disabled
                  aria-label="Identifier scheme"
                  title="Identifier scheme (always 0 for a WIGOS station identifier)"
                />
                <select
                  className="field-input"
                  value={idParts.issuer}
                  onChange={setIdPart("issuer")}
                  disabled={isEditing}
                  aria-label="Issuer ID"
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
                  value={idParts.issue}
                  onChange={setIdPart("issue")}
                  placeholder="Issue number"
                  disabled={isEditing}
                  aria-label="Issue number"
                />
                <input
                  className="field-input"
                  value={idParts.local}
                  onChange={setIdPart("local")}
                  placeholder="Local identifier"
                  disabled={isEditing}
                  aria-label="Local identifier"
                />
              </div>
              {!idValid && (
                <div className="field-error">
                  Select a country, and enter a numeric issue number and a local identifier
                  (letters, numbers, &quot;.&quot;, &quot;_&quot; or &quot;-&quot;).
                </div>
              )}
            </div>

            <div className="row">
              <div className="field">
                <label>
                  Latitude <span className="required">*</span>
                </label>
                <input
                  className="field-input"
                  type="number"
                  step="any"
                  value={form.latitude}
                  onChange={setInput("latitude")}
                />
              </div>
              <div className="field">
                <label>
                  Longitude <span className="required">*</span>
                </label>
                <input
                  className="field-input"
                  type="number"
                  step="any"
                  value={form.longitude}
                  onChange={setInput("longitude")}
                />
              </div>
              <div className="field">
                <label>Height (m)</label>
                <input
                  className="field-input"
                  type="number"
                  step="any"
                  value={form.height}
                  onChange={setInput("height")}
                  placeholder="Above sea level"
                />
              </div>
            </div>

            <div className="nested-card">
              <div className="nested-card-header">
                <span>Time</span>
              </div>
              <ObjectArrayItemRow item={form.time} fields={TIME_FIELDS} onChange={set("time")} path={["time"]} />
            </div>
          </div>

          <div className="card">
            <h3>Properties</h3>
            <div className="field">
              <label>
                Title <span className="required">*</span>
              </label>
              <input className="field-input" value={form.title} onChange={setInput("title")} />
            </div>
            <div className="field">
              <label>Description</label>
              <textarea className="field-input" rows={3} value={form.description} onChange={setInput("description")} />
            </div>

            <StringListField label="Additional titles" values={form.additionalTitles} onChange={set("additionalTitles")} />
            <StringListField label="Additional IDs" values={form.additionalIds} onChange={set("additionalIds")} />
            <ObjectArrayField
              label="External IDs"
              itemLabel="External ID"
              values={form.externalIds}
              onChange={set("externalIds")}
              fields={EXTERNAL_ID_FIELDS}
              itemSummary={(e) => [e.scheme, e.value].filter(Boolean).join(": ")}
              path={[]}
            />

            <div className="row">
              <ConceptField
                label="Facility type"
                value={form.facilityType}
                onChange={set("facilityType")}
                options={facilityTypes}
              />
              <ConceptField label="WMO region" value={form.wmoRegion} onChange={set("wmoRegion")} options={wmoRegions} />
            </div>

            <ContactsField value={form.contacts} onChange={set("contacts")} />

            <div className="row">
              <div className="field">
                <label>
                  Created <span className="required">*</span>
                </label>
                <input className="field-input" type="datetime-local" value={form.created} onChange={setInput("created")} />
              </div>
              <div className="field">
                <label>Updated</label>
                <input className="field-input" type="datetime-local" value={form.updated} onChange={setInput("updated")} />
              </div>
            </div>

            <ObjectArrayField
              label="Territories"
              itemLabel="Territory"
              values={form.territories}
              onChange={set("territories")}
              fields={territoryFields(territoryNames)}
              itemSummary={(t) => t.territory?.id}
              path={[]}
            />
            <ObservationsField value={form.observations} onChange={set("observations")} />
          </div>

          <div className="card">
            <h3>Links</h3>
            <ObjectArrayField
              label="Links"
              itemLabel="Link"
              values={form.links}
              onChange={set("links")}
              fields={LINK_FIELDS}
              itemSummary={(l) => l.title || l.href}
              path={[]}
              required
            />
          </div>

          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={!valid || submitState.status === "loading"}>
              {submitState.status === "loading" ? "Saving..." : isEditing ? "Save changes" : "Save WMDR record"}
            </button>
            {onCancel && (
              <button type="button" className="btn btn-secondary" onClick={onCancel}>
                Cancel
              </button>
            )}
          </div>

          {submitState.status === "success" && (
            <div className="status-message status-success">Saved successfully.</div>
          )}
          {submitState.status === "error" && (
            <div className="status-message status-error">Error: {submitState.error}</div>
          )}
        </form>

        <div className="sticky-col">
          <div className="card">
            <h3>Map</h3>
            <MapPreview latitude={form.latitude} longitude={form.longitude} />
          </div>
          <div className="card">
            <h3>GeoJSON preview</h3>
            {valid ? (
              <div className="status-message status-success">Valid against the WMDR2 schema.</div>
            ) : (
              <div className="status-message status-error">
                Not yet valid against the WMDR2 schema:
                <ul className="schema-errors">
                  {schemaErrors.map((error) => (
                    <li key={error}>{error}</li>
                  ))}
                </ul>
              </div>
            )}
            <pre className="geojson-preview">{JSON.stringify(record, null, 2)}</pre>
          </div>
        </div>
      </div>
    </>
  );
}
