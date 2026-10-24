// Form field definitions shared between the station, observation and contact
// editors. Shapes follow wmo-im/wmdr2 schemas/wmdr2-bundled.json.
//
// `label` and `placeholder` hold i18n message keys (see i18n/keys.js): these
// objects are built outside a component, so the strings are translated where
// they are rendered, not here.

// An interval field (IntervalField) edits two keys of its item, `start` and
// `end`. Time intervals accept years, months, days, UTC timestamps and times of
// day; an open bound is ".." (and an empty one is written as ".." too).
export const TIME_FIELDS = [
  { name: "date", label: "field.date", type: "date" },
  { name: "timestamp", label: "field.timestamp", type: "datetime-local" },
  { name: "interval", label: "field.interval", type: "interval", start: "intervalStart", end: "intervalEnd" },
  { name: "resolution", label: "field.resolution", type: "duration" },
];

// The station's own time has no resolution (wmo-im/wmdr2 PR #41 disallows it
// there); configurations keep it. A stored value is still written back.
export const STATION_TIME_FIELDS = TIME_FIELDS.filter((field) => field.name !== "resolution");

// Programme affiliation and territory `dates`: full days only, per the schema.
export const DATES_FIELD = { name: "dates", label: "field.dates", type: "interval", start: "dateStart", end: "dateEnd", daysOnly: true };

export const GEOMETRY_FIELDS = [
  { name: "latitude", label: "field.latitude", type: "text" },
  { name: "longitude", label: "field.longitude", type: "text" },
  { name: "height", label: "field.height", type: "text" },
];

// Record-level links: rel and href are required. `length` (the target's size
// in bytes) isn't offered on any link; a stored value is still written back.
export const LINK_FIELDS = [
  { name: "href", label: "field.url", type: "text", required: true, placeholder: "https://..." },
  { name: "rel", label: "field.relation", type: "text", required: true, default: "about", placeholder: "ph.relationExample" },
  { name: "type", label: "field.mediaType", type: "text", placeholder: "ph.mediaTypeExample" },
  { name: "hreflang", label: "field.language", type: "text", placeholder: "ph.languageExample" },
  { name: "title", label: "field.title", type: "text" },
];

// Contact links (the OGC Records link shape): href and type are required,
// and profile/created/updated are also allowed.
const CONTACT_LINK_BASE_FIELDS = [
  { name: "type", label: "field.mediaType", type: "text", placeholder: "ph.mediaTypeExample" },
  { name: "hreflang", label: "field.language", type: "text", placeholder: "ph.languageExample" },
  { name: "title", label: "field.title", type: "text" },
  { name: "profile", label: "field.profiles", type: "array-string" },
  { name: "created", label: "field.created", type: "datetime-local" },
  { name: "updated", label: "field.updated", type: "datetime-local" },
];

export const CONTACT_LINK_FIELDS = [
  { name: "href", label: "field.url", type: "text", required: true, placeholder: "https://..." },
  { name: "rel", label: "field.relation", type: "text", default: "about", placeholder: "ph.relationShortExample" },
  ...CONTACT_LINK_BASE_FIELDS.map((field) => (field.name === "type" ? { ...field, required: true } : field)),
];

// The logo is optional, so nothing is marked required here (it would block
// the contact's "Done" button); the schema check reports a half-filled logo.
// `rel` is always "icon" and is added when the record is built.
export const LOGO_FIELDS = [
  { name: "href", label: "field.imageUrl", type: "text", placeholder: "ph.logoUrl" },
  ...CONTACT_LINK_BASE_FIELDS.map((field) => (field.name === "type" ? { ...field, placeholder: "ph.logoType" } : field)),
];
