import { ref } from "vue";
import L from "leaflet";
import { BASEMAPS, getBasemap, setBasemapId, storedBasemapId } from "./mapConfig";
import { translate } from "./i18n/plain";

export const DEFAULT_CENTER = [20, 0];
export const DEFAULT_ZOOM = 2;
export const MARKER_STYLE = { color: "#1d4ed8", weight: 1, fillColor: "#3b82f6", fillOpacity: 0.9 };

// 当前选择的底图 id（响应式）。「地图管理」面板调 setBasemap 切换它；各地图
// 组件 watch 这个 ref 重建底图——切换立即生效，不用刷新页面。初值从
// localStorage 恢复（持久化，与 wigos.locale 同一套做法）。
export const activeBasemapId = ref(storedBasemapId());

export function setBasemap(id) {
  if (!BASEMAPS.some((b) => b.id === id)) return;
  activeBasemapId.value = id;
  setBasemapId(id);
}

export function currentBasemap() {
  return getBasemap(activeBasemapId.value);
}

// 离线矢量底图的样式：海面浅蓝（容器背景提供）、陆地灰白、国界细线——与
// oscar_portal_demo 的"国际底图"同一思路（Natural Earth 110m 公有领域几何，
// 自绘渲染，不依赖任何瓦片服务）。110m 是简化精度、仅作示意；页面注明
// 数据来源，境内合规部署切天地图源。
const GEOJSON_STYLE = {
  color: "#94a3b8",
  weight: 0.8,
  fillColor: "#eef2f7",
  fillOpacity: 0.85,
};

// 在 `map` 上加载当前选择的底图。返回是否加载成功。
// map.on("baserebuild") 之类的机制不需要——切换底图时组件直接重建整个 map
// （与语言切换同一处理方式），图层跟着新 map 走，不会泄漏。
function addBasemapLayer(map) {
  const basemap = currentBasemap();
  const container = map.getContainer();

  if (basemap.kind === "geojson") {
    // 容器给一层海面蓝，陆块由 geojson 填充；整张图零外网请求。
    container.classList.add("leaflet-offline-basemap");
    L.geoJSON(basemap.geojson, { style: GEOJSON_STYLE, interactive: false }).addTo(map);
    return;
  }

  if (!basemap.url) {
    // 选了需要令牌但部署方没配（如天地图无 VITE_TIANDITU_TOKEN）：与其发
    // 匿名请求刷一屏 4xx，不如浅色画布 + 台站标记照常可用。
    container.classList.add("leaflet-no-basemap");
    return;
  }

  L.tileLayer(basemap.url, basemap.options).addTo(map);
  L.control.attribution({ prefix: "Leaflet" }).addTo(map);
}

// A Leaflet map on `element`.
//
// 底图由 activeBasemapId 决定（默认 mapbox —— 与 upstream 一致）。离线/内网
// 环境在「管理 → 地图管理」切到 offline（Natural Earth 矢量，零外网请求）
// 或天地图。tile 源在断网浏览器里加载失败是 Leaflet 的既有行为，与上游相同。
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

  addBasemapLayer(map);

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
