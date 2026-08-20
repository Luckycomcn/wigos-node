import { useEffect, useState } from "react";
import { WIGOS_ID_PATTERN, isValidWmdrRecord, buildWmdrRecord } from "../wmdr";
import { submitGeoJson, getCodelist } from "../api";
import StringListField from "./StringListField";
import ContactsField from "./ContactsField";
import ObservingCapabilitiesField from "./ObservingCapabilitiesField";
import MapPreview from "./MapPreview";

const initialState = {
  id: "",
  latitude: "",
  longitude: "",
  title: "",
  description: "",
  additionalTitles: [""],
  additionalIds: [""],
  facilityType: "",
  wmoRegion: "",
  contacts: [],
  created: "",
  updated: "",
  keywords: [""],
  territories: [""],
  programAffiliations: [""],
  observingCapabilities: [],
  links: [""],
};

export default function WmdrForm() {
  const [form, setForm] = useState(initialState);
  const [submitState, setSubmitState] = useState({ status: "idle" });
  const [facilityTypes, setFacilityTypes] = useState([]);
  const [wmoRegions, setWmoRegions] = useState([]);

  useEffect(() => {
    getCodelist("FacilityType").then(setFacilityTypes).catch(() => setFacilityTypes([]));
    getCodelist("WMORegion").then(setWmoRegions).catch(() => setWmoRegions([]));
  }, []);

  const set = (field) => (value) => setForm((prev) => ({ ...prev, [field]: value }));
  const setInput = (field) => (e) => set(field)(e.target.value);

  const idValid = form.id === "" || WIGOS_ID_PATTERN.test(form.id);
  const valid = isValidWmdrRecord(form);
  const record = valid ? buildWmdrRecord(form) : null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!record) return;
    setSubmitState({ status: "loading" });
    try {
      const data = await submitGeoJson(record);
      setSubmitState({ status: "success", data });
    } catch (err) {
      setSubmitState({ status: "error", error: err.message });
    }
  };

  return (
    <>
      <form onSubmit={handleSubmit}>
        <div className="card">
          <h3>Identification</h3>
          <div className="field">
            <label>
              WIGOS station identifier <span className="required">*</span>
            </label>
            <input
              className="field-input"
              value={form.id}
              onChange={setInput("id")}
              placeholder="0-20000-0-12345"
            />
            {!idValid && (
              <div className="field-error">
                Must match 0|1|2|3-issuer-issue-local (e.g. 0-20000-0-12345)
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

          <div className="row">
            <div className="field">
              <label>Facility type</label>
              <select className="field-input" value={form.facilityType} onChange={setInput("facilityType")}>
                <option value="">None selected</option>
                {facilityTypes.map((opt) => (
                  <option key={opt.code} value={opt.code}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>WMO region</label>
              <select className="field-input" value={form.wmoRegion} onChange={setInput("wmoRegion")}>
                <option value="">None selected</option>
                {wmoRegions.map((opt) => (
                  <option key={opt.code} value={opt.code}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
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

          <StringListField label="Keywords" values={form.keywords} onChange={set("keywords")} />
          <StringListField label="Territories" values={form.territories} onChange={set("territories")} />
          <StringListField
            label="Program affiliations"
            values={form.programAffiliations}
            onChange={set("programAffiliations")}
          />
          <ObservingCapabilitiesField
            value={form.observingCapabilities}
            onChange={set("observingCapabilities")}
          />
        </div>

        <div className="card">
          <h3>Links</h3>
          <StringListField label="Links (href)" values={form.links} onChange={set("links")} required />
        </div>

        <button type="submit" className="btn btn-primary" disabled={!valid || submitState.status === "loading"}>
          {submitState.status === "loading" ? "Submitting..." : "Submit WMDR record"}
        </button>

        {submitState.status === "success" && (
          <div className="status-message status-success">Submitted successfully.</div>
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
          <pre className="geojson-preview">
            {record ? JSON.stringify(record, null, 2) : "Fill in all required (*) fields to preview"}
          </pre>
        </div>
      </div>
    </>
  );
}
