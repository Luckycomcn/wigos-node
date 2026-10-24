import L from "leaflet";
import { MAPBOX_TILE_URL, MAPBOX_ATTRIBUTION, MAPBOX_TILE_SIZE, MAPBOX_ZOOM_OFFSET } from "./mapConfig";
import { translate } from "./i18n/plain";

export const DEFAULT_CENTER = [20, 0];
export const DEFAULT_ZOOM = 2;
export const MARKER_STYLE = { color: "#1d4ed8", weight: 1, fillColor: "#3b82f6", fillOpacity: 0.9 };

// A Leaflet map on `element` with the Mapbox base layer.
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
  L.tileLayer(MAPBOX_TILE_URL, {
    attribution: MAPBOX_ATTRIBUTION,
    tileSize: MAPBOX_TILE_SIZE,
    zoomOffset: MAPBOX_ZOOM_OFFSET,
  }).addTo(map);
  L.control.attribution({ prefix: "Leaflet" }).addTo(map);

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
