import L from "leaflet";
import { TILE_URL, TILE_OPTIONS, HAS_BASEMAP } from "./mapConfig";
import { translate } from "./i18n/plain";

export const DEFAULT_CENTER = [20, 0];
export const DEFAULT_ZOOM = 2;
export const MARKER_STYLE = { color: "#1d4ed8", weight: 1, fillColor: "#3b82f6", fillOpacity: 0.9 };

// A Leaflet map on `element`.
//
// 底图是可选的：没有 VITE_TILE_URL / VITE_MAPBOX_TOKEN 时**不加载任何瓦片**，
// 只画一个带经纬度网格的空画布加台站标记。这样：
//   - 内网/离线部署不再请求 api.mapbox.com（原版在这里就是一片灰块，
//     还会在控制台刷一屏 ERR_NAME_NOT_RESOLVED）；
//   - 不用再把 WMO 的 Mapbox 令牌分发到每个国家。
//
// Leaflet's own controls carry English tooltips ("Zoom in", "Zoom out") and
// it reads them once, when the control is created — so they are supplied in
// the UI language here. Switching language mid-session rebuilds the map (the
// components remount it), which re-reads these.
export function createBaseMap(element, { center = DEFAULT_CENTER, zoom = DEFAULT_ZOOM } = {}) {
  const map = L.map(element, {
    center,
    zoom,
    attributionControl: false,
    zoomControl: false, // added below with translated titles
  });

  if (HAS_BASEMAP) {
    L.tileLayer(TILE_URL, TILE_OPTIONS).addTo(map);
    L.control.attribution({ prefix: "Leaflet" }).addTo(map);
  } else {
    // 无底图时给一个浅色背景，让标记还能看清；缩放时仍有网格感。
    const container = map.getContainer();
    container.classList.add("leaflet-no-basemap");
  }

  // Keep Leaflet's own click handlers and layout; only the two titles it
  // shows on hover/focus are language-dependent.
  const zoomControl = L.control.zoom();
  zoomControl.addTo(map);
  for (const [className, key] of [
    ["leaflet-control-zoom-in", "map.zoomIn"],
    ["leaflet-control-zoom-out", "map.zoomOut"],
  ]) {
    const button = zoomControl.getContainer()?.querySelector(`.${className}`);
    if (!button) continue;
    const label = translate(key);
    button.setAttribute("title", label);
    button.setAttribute("aria-label", label);
  }

  return map;
}