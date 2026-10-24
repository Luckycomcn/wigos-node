// The API answers with English prose — `{"detail": "Station 3 not found"}` —
// and that string is what the user ends up reading in the error alert, so it
// stayed English in the Chinese UI. This maps the known wording to message
// keys.
//
// Matching on prose is brittle by nature: any rewording upstream and the line
// falls back to the English. The fix belongs in the backend (structured
// `{code, params}` instead of a sentence), which the i18n branch does not
// touch — it is reported upstream as D9. Until then this keeps the common
// failures readable, and an unrecognised message still shows as it arrived
// rather than being swallowed by a generic "request failed".

import { activeLocale, translate } from "./plain";

// Ordered: the first match wins, so the more specific wording comes first.
const RULES = [
  {
    re: /^The record must be a JSON object\.$/,
    key: "api.backend.recordNotObject",
  },
  {
    re: /^The record is not valid against the WMDR2 schema\.$/,
    key: "api.backend.invalidRecord",
  },
  {
    re: /^WIGOS identifier '([^']*)' is already in use in additional identifiers in another station$/,
    key: "api.backend.wsiInUseAdditional",
    params: (m) => ({ wsi: m[1] }),
  },
  {
    re: /^WIGOS identifier '([^']*)' is already in use in another station$/,
    key: "api.backend.wsiInUse",
    params: (m) => ({ wsi: m[1] }),
  },
  {
    re: /^No station with WIGOS identifier (\S+)$/,
    key: "api.backend.stationNotFoundByWsi",
    params: (m) => ({ wsi: m[1] }),
  },
  {
    re: /^Station (\S+) not found\.?$/,
    key: "api.backend.stationNotFound",
    params: (m) => ({ station: m[1] }),
  },
  {
    // "create"/"update" are the only actions the backend passes.
    re: /^You do not have permission to (create|update) a station for the issuer of identifier (\S+)\.$/,
    key: "api.backend.noPermissionForIssuer",
    params: (m) => ({ action: translate(`api.backend.action.${m[1]}`), issuer: m[2] }),
  },
  {
    re: /^You do not have permission to change this station\.$/,
    key: "api.backend.noPermissionToChange",
  },
  {
    re: /^Provide one or more numeric station_id parameters\.$/,
    key: "api.backend.batchNoStationIds",
  },
  {
    re: /^At most (\d+) stations can be read at once\.$/,
    key: "api.backend.batchReadLimit",
    params: (m) => ({ limit: m[1] }),
  },
  {
    re: /^At most (\d+) updates are allowed per request\.$/,
    key: "api.backend.batchUpdateLimit",
    params: (m) => ({ limit: m[1] }),
  },
  {
    re: /^Expected \{ "dry_run": bool, "updates": \[\.\.\.\] \}\.$/,
    key: "api.backend.batchPayloadShape",
  },
  {
    re: /^A numeric station_id is required\. Batch operations never create stations\.$/,
    key: "api.backend.batchNeedsStationId",
  },
  {
    re: /^The station could not be saved: ([\s\S]+)$/,
    key: "api.backend.saveFailed",
    params: (m) => ({ reason: m[1] }),
  },
  {
    re: /^Invalid username or password\.$/,
    key: "api.backend.badCredentials",
  },
  {
    re: /^Not authenticated\.$/,
    key: "api.backend.notAuthenticated",
  },
  {
    re: /^No WIGOS identifiers provided$/,
    key: "api.backend.noWigosIds",
  },
  {
    re: /^Payload must be a GeoJSON Feature$/,
    key: "api.backend.geojsonNotFeature",
  },
  {
    re: /^No cached codelist for '([^']*)'$/,
    key: "api.backend.noCachedCodelist",
    params: (m) => ({ scheme: m[1] }),
  },
  // Success messages, in case a caller ever surfaces them.
  {
    re: /^Station (\S+) created successfully\.$/,
    key: "api.backend.stationCreated",
    params: (m) => ({ station: m[1] }),
  },
  {
    re: /^WMD[vV]2 data for station (\S+) updated successfully\.$/,
    key: "api.backend.stationUpdated",
    params: (m) => ({ station: m[1] }),
  },
];

/**
 * The message to show for an API `detail`, in the UI language.
 *
 * Null when there is nothing to show, so the caller can fall back to its own
 * message. An English locale gets the server's own wording back untouched.
 */
export function backendMessage(detail) {
  if (!detail || typeof detail !== "string") return null;
  if (activeLocale() === "en") return detail;
  const rule = RULES.find((candidate) => candidate.re.test(detail));
  if (!rule) return detail;
  const match = detail.match(rule.re);
  return translate(rule.key, rule.params ? rule.params(match) : undefined);
}

/** True when `detail` has a translation (used by the tests). */
export const hasBackendMessage = (detail) => !!detail && RULES.some((rule) => rule.re.test(detail));