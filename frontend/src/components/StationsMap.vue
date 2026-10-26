<script setup>
import { computed, onBeforeUnmount, shallowRef, watch } from "vue";
import L from "leaflet";
import { MARKER_STYLE, createBaseMap, activeBasemapId } from "../leafletMap";
import i18n from "../i18n";

const props = defineProps({ stations: { type: Array, required: true } });

const SINGLE_STATION_ZOOM = 9;
const TARGET_PIXEL_RADIUS = 6;
const MIN_MARKER_RADIUS_METERS = 2000;

// Web Mercator ground resolution: at zoom 0 the whole 40,075,016.686m
// equator is drawn across 256px, halving each zoom level; scaled by
// latitude to account for projection distortion away from the equator.
function metersPerPixel(latitude, zoom) {
  return (156543.03392 * Math.cos((latitude * Math.PI) / 180)) / Math.pow(2, zoom);
}

const positioned = computed(() =>
  props.stations
    .map((station) => ({ ...station, lat: Number(station.latitude), lon: Number(station.longitude) }))
    .filter((station) => !Number.isNaN(station.lat) && !Number.isNaN(station.lon))
);

const container = shallowRef(null);
let map = null;
let markers = null;

// Built with DOM nodes, not an HTML string, so station names are never parsed as markup.
function popupContent(station) {
  const content = document.createElement("div");
  const name = document.createElement("strong");
  name.textContent = station.name ?? "";
  content.append(name, document.createElement("br"), station.wsi ?? "");
  return content;
}

// Markers are sized for the zoom the map settles on after fitting, so they
// show as roughly TARGET_PIXEL_RADIUS px dots at that view.
function drawMarkers(zoom) {
  markers.clearLayers();
  positioned.value.forEach((station) => {
    const radius = Math.max(MIN_MARKER_RADIUS_METERS, TARGET_PIXEL_RADIUS * metersPerPixel(station.lat, zoom));
    L.circle([station.lat, station.lon], { radius, ...MARKER_STYLE })
      .bindPopup(popupContent(station))
      .addTo(markers);
  });
}

// fitBounds/setView animate the transition, so the zoom only reaches its
// final value once "moveend" fires.
function fitToMarkers() {
  const positions = positioned.value.map((station) => [station.lat, station.lon]);
  if (!positions.length) return;
  map.once("moveend", () => drawMarkers(map.getZoom()));
  if (positions.length === 1) map.setView(positions[0], SINGLE_STATION_ZOOM);
  else map.fitBounds(positions, { padding: [30, 30] });
}

function destroyMap() {
  map?.remove();
  map = null;
  markers = null;
}

function buildMap({ preserveView = false } = {}) {
  // preserveView：切底图时保住用户当前视野，不重新 fitBounds——用户可能
  // 已经放大到本国台站群，甩回全球视图会很突兀。初次构建仍自动适配台站。
  const preserved =
    preserveView && map ? { center: map.getCenter(), zoom: map.getZoom() } : {};
  destroyMap();
  const element = container.value;
  if (!element) return;
  map = createBaseMap(element, preserved);
  markers = L.layerGroup().addTo(map);
  if (preserveView) {
    drawMarkers(map.getZoom());
  } else {
    drawMarkers(map.getZoom());
    fitToMarkers();
  }
}

// The container only exists while there's something to show.
watch(container, () => buildMap(), { flush: "post" });

watch(positioned, () => {
  if (!map) return;
  drawMarkers(map.getZoom());
  fitToMarkers();
});

// Leaflet reads its control strings once, when the control is built, so a
// language change has to rebuild the map for the zoom buttons to follow.
watch(i18n.global.locale, () => buildMap());

// 「地图管理」切换底图 → 用新底图重建，保住当前视野。
watch(activeBasemapId, () => buildMap({ preserveView: true }));

onBeforeUnmount(destroyMap);
</script>

<template>
  <div v-if="positioned.length" ref="container" class="stations-map" />
</template>

<style scoped>
.stations-map {
  height: 320px;
  width: 100%;
  margin-bottom: 1rem;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
}
</style>
