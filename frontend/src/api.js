import { parseCsv } from "./csv";
import { csrfHeader } from "./auth";
import { translate } from "./i18n/plain";
import { backendMessage } from "./i18n/backendMessages";

const API_URL = import.meta.env.VITE_API_URL || "";

// Notify the app when the session is gone so it can drop back to the login page.
function handle401(res) {
  if (res.status === 401) {
    window.dispatchEvent(new Event("auth:unauthenticated"));
  }
  return res;
}

export async function getHello() {
  const res = handle401(await fetch(`${API_URL}/api/hello/`, { credentials: "include" }));
  if (!res.ok) {
    throw new Error(translate("api.requestFailed", { status: res.status }));
  }
  return res.json();
}

export async function saveStation(stationId, record) {
  const url = stationId == null ? `${API_URL}/api/wmdrv2/` : `${API_URL}/api/wmdrv2/${encodeURIComponent(stationId)}`;
  const res = handle401(await fetch(url, {
    method: stationId == null ? "POST" : "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...csrfHeader() },
    body: JSON.stringify(record),
  }));
  const data = await res.json();
  if (!res.ok) {
    throw new Error(backendMessage(data.detail) || translate("api.requestFailed", { status: res.status }));
  }
  return data;
}

export async function getStation(stationId) {
  const res = handle401(await fetch(`${API_URL}/api/wmdrv2/${encodeURIComponent(stationId)}`, {
    credentials: "include",
  }));
  const data = await res.json();
  if (!res.ok) {
    throw new Error(backendMessage(data.detail) || translate("api.requestFailed", { status: res.status }));
  }
  return data;
}

// Returns { [stationId]: record } for the given stations; unknown IDs are left out.
export async function getStations(stationIds) {
  const params = new URLSearchParams(stationIds.map((id) => ["station_id", id]));
  const res = handle401(await fetch(`${API_URL}/api/wmdrv2/batch/?${params}`, { credentials: "include" }));
  const data = await res.json();
  if (!res.ok) {
    throw new Error(backendMessage(data.detail) || translate("api.requestFailed", { status: res.status }));
  }
  return data;
}

// updates: [{ station_id, wmdrv2 }]. Returns { dry_run, summary, results }
// with a result per update; one station failing doesn't stop the others.
export async function saveStationsBatch(updates, { dryRun = false } = {}) {
  const res = handle401(await fetch(`${API_URL}/api/wmdrv2/batch/`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...csrfHeader() },
    body: JSON.stringify({ dry_run: dryRun, updates }),
  }));
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(backendMessage(data.detail || data.error) || translate("api.requestFailed", { status: res.status }));
  }
  return data;
}

export async function listMyStations(includeArchived = false, options = {}) {
  const params = new URLSearchParams();
  if (includeArchived) params.set("include_archived", "1");
  const { q, status, limit, offset } = options || {};
  if (q) params.set("q", q);
  if (status) params.set("status", status);
  // limit=0 表示"要全部"，导出与地图用；默认由后端给 50。
  if (limit !== undefined && limit !== null) params.set("limit", String(limit));
  if (offset) params.set("offset", String(offset));
  const suffix = params.toString() ? `?${params}` : "";
  const res = handle401(await fetch(`${API_URL}/api/my_stations/${suffix}`, { credentials: "include" }));
  if (!res.ok) {
    throw new Error(translate("api.requestFailed", { status: res.status }));
  }
  const rows = await res.json();
  // 总数放在响应头里，响应体仍是数组 —— 既有调用方不用改。
  const total = Number(res.headers.get("X-Total-Count"));
  Object.defineProperty(rows, "total", {
    value: Number.isFinite(total) ? total : rows.length,
    enumerable: false,
  });
  return rows;
}

export async function listMyIssuers() {
  const res = handle401(await fetch(`${API_URL}/api/my_issuer_of_identifiers/`, {
    credentials: "include",
  }));
  if (!res.ok) {
    throw new Error(translate("api.requestFailed", { status: res.status }));
  }
  return res.json();
}

// Returns { [wigosId]: boolean }, true when a station already uses the ID
// as its primary or one of its additional identifiers.
export async function checkWigosIdentifiers(ids) {
  const params = new URLSearchParams(ids.map((id) => ["wigos_identifier", id]));
  const res = handle401(await fetch(`${API_URL}/api/check_wigosidentifiers/?${params}`, {
    credentials: "include",
  }));
  if (!res.ok) {
    throw new Error(translate("api.requestFailed", { status: res.status }));
  }
  return res.json();
}

export async function getCodelist(scheme) {
  const res = await fetch(`${API_URL}/api/codelists/${scheme}.csv`, { credentials: "include" });
  if (!res.ok) {
    throw new Error(translate("api.codelistFailed", { scheme, status: res.status }));
  }
  const text = await res.text();
  return parseCsv(text)
    .map((row) => ({
      code: row["skos:notation"],
      label: row["rdfs:label"] || row["skos:notation"],
      id: (row["@id"] || "").replace(/^<|>$/g, ""),
      // Stored as a quoted RDF literal with a language tag, e.g. 'Africa'@en.
      description: (row["dct:description"] || "").replace(/@[A-Za-z-]+$/, "").replace(/^'([\s\S]*)'$/, "$1").trim(),
    }))
    .filter((entry) => entry.code);
}

// --------------------------------------------------------------------------
// MVP completion: archive / history / publish / groups / templates / grades
// --------------------------------------------------------------------------
async function jsonOrThrow(res, fallback) {
  const data = res.status === 204 ? {} : await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || data.error || fallback || `API request failed: ${res.status}`);
  }
  return data;
}

const jsonHeaders = () => ({ "Content-Type": "application/json", ...csrfHeader() });

export async function archiveStation(stationId) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wmdrv2/${stationId}/archive`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
  })), "Failed to archive station");
}

export async function restoreStation(stationId) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wmdrv2/${stationId}/restore`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
  })), "Failed to restore station");
}

export async function deleteStation(stationId) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wmdrv2/${stationId}`, {
    method: "DELETE", credentials: "include", headers: jsonHeaders(),
  })), "Failed to delete station");
}

export async function getStationHistory(stationId) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wmdrv2/${stationId}/history/`, {
    credentials: "include",
  })), "Failed to load history");
}

export async function getStationVersion(stationId, version) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wmdrv2/${stationId}/history/${version}`, {
    credentials: "include",
  })), "Failed to load version");
}

/**
 * F-8 变更对比。from/to 都可省略：都不给时后端对比「上一版 → 最新版」。
 */
export async function getStationHistoryDiff(stationId, from, to) {
  const params = new URLSearchParams();
  if (from != null) params.set("from", String(from));
  if (to != null) params.set("to", String(to));
  const qs = params.toString();
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wmdrv2/${stationId}/history/diff${qs ? `?${qs}` : ""}`, {
    credentials: "include",
  })), "Failed to load diff");
}

export async function publishStation(stationId, operation = "canonical") {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wmdrv2/${stationId}/publish`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
    body: JSON.stringify({ operation }),
  })), "Failed to publish station");
}

/**
 * 方案 5.6：草稿 → 提交 → 校验 → 发布。草稿不可发布，提交后才行。
 * 服务端会把把关结果一并回来：schema 问题或业务规则不通过都是 400。
 */
export async function submitStation(stationId) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wmdrv2/${stationId}/submit`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
  })), "Failed to submit station");
}

export async function listGroups() {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/groups/`, { credentials: "include" })), "Failed to load groups");
}

export async function createGroup(name, description = "") {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/groups/`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
    body: JSON.stringify({ name, description }),
  })), "Failed to create group");
}

export async function updateGroupMembers(groupId, add = [], remove = []) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/groups/${groupId}/`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
    body: JSON.stringify({ add, remove }),
  })), "Failed to update group members");
}

export async function listTemplates() {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/templates/`, { credentials: "include" })), "Failed to load templates");
}

export async function createTemplate(name, payload, { description = "", shared = false } = {}) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/templates/`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
    body: JSON.stringify({ name, description, shared, payload }),
  })), "Failed to create template");
}

export async function listGrades() {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/grades/`, { credentials: "include" })), "Failed to load grades");
}

export async function getStationGrades(stationId) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/stations/${stationId}/grades/`, {
    credentials: "include",
  })), "Failed to evaluate grades");
}

export async function getNextWsi({ issuer, station = "0", series = "0" }) {
  const params = new URLSearchParams({ issuer, station, series });
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wsi/next/?${params}`, {
    credentials: "include",
  })), "Failed to allocate a WIGOS identifier");
}

export async function createStationsBatch(records, { dryRun = false } = {}) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wmdrv2/batch-create/`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
    body: JSON.stringify({ dry_run: dryRun, records }),
  })), "Failed to create records in batch");
}

// --------------------------------------------------------------------------- //
// F-16 export / F-15 ingest / F-21 WMDR1 import / F-13 providers
// --------------------------------------------------------------------------- //
function filenameFrom(response, fallback) {
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/);
  return match ? match[1] : fallback;
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

// Bulk export in csv / json / xml; `stationIds` empty means every visible record.
export async function exportStations(format, { stationIds = [], includeArchived = false } = {}) {
  const params = new URLSearchParams({ format });
  stationIds.forEach((id) => params.append("station_id", id));
  if (includeArchived) params.set("include_archived", "1");
  const res = handle401(await fetch(`${API_URL}/api/export/?${params}`, { credentials: "include" }));
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Export failed: ${res.status}`);
  }
  const blob = await res.blob();
  triggerDownload(blob, filenameFrom(res, `wigos-wmdr2.${format}`));
  return { size: blob.size, filename: filenameFrom(res, `wigos-wmdr2.${format}`) };
}

export async function exportStation(stationId, format) {
  const res = handle401(await fetch(`${API_URL}/api/wmdrv2/${stationId}/export?format=${format}`, {
    credentials: "include",
  }));
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Export failed: ${res.status}`);
  }
  const blob = await res.blob();
  const filename = filenameFrom(res, `wmdr2-${stationId}.${format}`);
  triggerDownload(blob, filename);
  return { size: blob.size, filename };
}

// Upload a CSV / JSON / XML payload (FormData with `file`) or inline text.
export async function importRecords({ file = null, format = null, data = null, dryRun = false } = {}) {
  let body;
  const headers = { ...csrfHeader() };
  if (file) {
    body = new FormData();
    body.append("file", file);
    if (format) body.append("format", format);
    if (dryRun) body.append("dry_run", "true");
    delete headers["Content-Type"];
  } else {
    body = JSON.stringify({ format, data, dry_run: dryRun });
    headers["Content-Type"] = "application/json";
  }
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/import/`, {
    method: "POST", credentials: "include", headers, body,
  })), "Import failed");
}

export async function importWmdr1(records, { dryRun = false } = {}) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/import/wmdr1/`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
    body: JSON.stringify({ records, dry_run: dryRun }),
  })), "WMDR1 import failed");
}

export async function listProviders(stationId) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wmdrv2/${stationId}/providers/`, {
    credentials: "include",
  })), "Failed to load providers");
}

export async function addProvider(stationId, { organization, role = "dataProvider", contact = {} }) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wmdrv2/${stationId}/providers/`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
    body: JSON.stringify({ organization, role, contact }),
  })), "Failed to add provider");
}

export async function removeProvider(providerId) {
  const res = handle401(await fetch(`${API_URL}/api/providers/${providerId}/`, {
    method: "DELETE", credentials: "include", headers: { ...csrfHeader() },
  }));
  if (!res.ok && res.status !== 204) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Failed to remove provider: ${res.status}`);
  }
  return true;
}

// ---------------------------------------------------------------------------
// 方案 5.3：WSI 注册表（centre-id ↔ WSI 授权范围）+ NF-6 审计
// ---------------------------------------------------------------------------

export async function listWsiAllocations({ issuer = "" } = {}) {
  const qs = issuer ? `?issuer=${encodeURIComponent(issuer)}` : "";
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wsi-allocations/${qs}`, {
    credentials: "include",
  })), "Failed to load WSI allocations");
}

export async function createWsiAllocation({ issuer, series = 0, numberFrom, numberTo, note = "" }) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wsi-allocations/`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
    body: JSON.stringify({ issuer, series, numberFrom, numberTo, note }),
  })), "Failed to create allocation");
}

export async function updateWsiAllocation(id, patch) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wsi-allocations/${id}/`, {
    method: "PATCH", credentials: "include", headers: jsonHeaders(),
    body: JSON.stringify(patch),
  })), "Failed to update allocation");
}

export async function deleteWsiAllocation(id) {
  const res = handle401(await fetch(`${API_URL}/api/wsi-allocations/${id}/`, {
    method: "DELETE", credentials: "include", headers: { ...csrfHeader() },
  }));
  if (!res.ok && res.status !== 204) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Failed to delete allocation: ${res.status}`);
  }
  return true;
}

export async function exportWsiAllocations(format = "json") {
  const res = handle401(await fetch(`${API_URL}/api/wsi-allocations/export?format=${format}`, {
    credentials: "include",
  }));
  if (!res.ok) throw new Error(`Failed to export allocations: ${res.status}`);
  return res.blob();
}

export async function importWsiAllocations(payload) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/wsi-allocations/import`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
    body: JSON.stringify(payload),
  })), "Failed to import allocations");
}

export async function listAuditLog({ action = "", station = "", limit = 200 } = {}) {
  const params = new URLSearchParams();
  if (action) params.set("action", action);
  if (station) params.set("station", String(station));
  params.set("limit", String(limit));
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/audit/?${params.toString()}`, {
    credentials: "include",
  })), "Failed to load audit log");
}

/**
 * F-9 发布前自检。records 传数组；ets=true 时附带 pywmdr ETS（未安装会自动降级）。
 */
export async function validateRecords(records, { ets = false } = {}) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/validate/`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
    body: JSON.stringify({ records, ets }),
  })), "Validation failed");
}

// --------------------------------------------------------------------------- //
// 用户管理（节点管理员）：账号增删、重置他人密码；任何登录者可改自己密码。
// --------------------------------------------------------------------------- //
export async function listUsers() {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/users/`, {
    credentials: "include",
  })), "Failed to load users");
}

export async function listUserGroups() {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/users/groups/`, {
    credentials: "include",
  })), "Failed to load groups");
}

export async function createUser({ username, email, password, isStaff = false, groups = [] }) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/users/`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
    body: JSON.stringify({ username, email, password, is_staff: isStaff, groups }),
  })), "Failed to create the account");
}

export async function updateUser(userId, patch) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/users/${encodeURIComponent(userId)}/`, {
    method: "PATCH", credentials: "include", headers: jsonHeaders(),
    body: JSON.stringify(patch),
  })), "Failed to update the account");
}

export async function deleteUser(userId) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/users/${encodeURIComponent(userId)}/`, {
    method: "DELETE", credentials: "include", headers: jsonHeaders(),
  })), "Failed to delete the account");
}

export async function setUserPassword(userId, password) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/users/${encodeURIComponent(userId)}/password`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
    body: JSON.stringify({ password }),
  })), "Failed to set the password");
}

export async function changeOwnPassword(oldPassword, newPassword) {
  return jsonOrThrow(handle401(await fetch(`${API_URL}/api/password/change`, {
    method: "POST", credentials: "include", headers: jsonHeaders(),
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  })), "Failed to change the password");
}
