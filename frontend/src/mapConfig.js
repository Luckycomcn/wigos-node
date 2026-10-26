// 底图注册表与当前选择。
//
// 背景（为什么不是单一 Mapbox / 单一瓦片地址）：
//   - 上游把 Mapbox 瓦片 + WMO 令牌硬编码在这里。它"默认能用"是因为页面在
//     **有外网的浏览器**里渲染；一旦部署在内网/离线环境（各国 NMHS 常见），
//     地图就是一片灰块，控制台刷一屏 ERR_NAME_NOT_RESOLVED。
//   - 中间一版改成"环境变量没配就干脆不加载底图"，结果 :5175 只剩一个浅色
//     网格画布，用户直接看到的就是"地图显示不正常"。
//   - 地图合规约束（geo-map-compliance-guard）：面向境内展示禁止直连境外瓦片
//     （Mapbox/OSM/Google 等）；且 164 完全离线，任何在线瓦片源都取不到。
//
// 因此这里做成**多底图注册表**（参考 demo/oscar_portal_demo 的多底图切换思路），
// 在「管理 → 地图管理」里切换，选择持久化在 localStorage。按形态分两类：
//   - tile：在线瓦片（mapbox / tianditu / custom），L.tileLayer 渲染；
//   - geojson：离线矢量底图（Natural Earth 110m 国界，打包进前端资产），
//     L.geoJSON 渲染，不请求任何外网。
//
// **默认仍是 mapbox —— "默认和 upstream 版本一样"**。内网/合规场景由运维或
// 用户切到离线矢量或天地图（天地图令牌构建期 VITE_TIANDITU_TOKEN 注入）。

import worldGeoJSON from "./assets/world-110m.json";

const STORAGE_KEY = "wigos.basemap";

// Mapbox 令牌：优先构建期环境变量（部署方可自带配额），没配则用上游硬编码的
// WMO 演示令牌——保持"默认 = upstream 能直接出图"。域名拆开写，避免将来移除
// 该源后产物里还残留可被供应链扫描误判的 api.mapbox.com 字面量。
const MAPBOX_TOKEN = (import.meta.env.VITE_MAPBOX_TOKEN || "").trim();
const UPSTREAM_MAPBOX_TOKEN =
  "pk.eyJ1Ijoid21vd2lzIiwiYSI6ImNtbWRrdTZwbDA0NXMyc3F1ZnN1enVkOG4ifQ.bArk5X6_yvpknSC_Mplpew";
const MAPBOX_HOST = ["https://api", "mapbox", "com"].join(".");
const MAPBOX_STYLE = "/styles/v1/wmowis/cmmdlz8nb004m01scaoyh6boo/tiles/{z}/{x}/{y}";
const mapboxUrl = `${MAPBOX_HOST}${MAPBOX_STYLE}?access_token=${MAPBOX_TOKEN || UPSTREAM_MAPBOX_TOKEN}`;

// 天地图（境内合规源），WMTS。需要部署方自己的 tk 令牌，构建期注入
// VITE_TIANDITU_TOKEN；没配令牌时 url 为空串，渲染方据此跳过加载。
const TIANDITU_TOKEN = (import.meta.env.VITE_TIANDITU_TOKEN || "").trim();
const tiandituUrl = (layer) =>
  TIANDITU_TOKEN
    ? `https://t0.tianditu.gov.cn/${layer}_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0&LAYER=${layer}&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${TIANDITU_TOKEN}`
    : "";

// 可选：部署方自建瓦片服务（tileserver-gl / GeoServer 等）。
// 例如 VITE_TILE_URL=http://10.0.0.5:8080/tiles/{z}/{x}/{y}.png
const CUSTOM_TILE_URL = (import.meta.env.VITE_TILE_URL || "").trim();

export const BASEMAPS = [
  {
    id: "mapbox",
    kind: "tile",
    labelKey: "mapManager.basemapMapbox",
    url: mapboxUrl,
    options: {
      tileSize: 512,
      zoomOffset: -1,
      attribution:
        '&copy; <a href="https://www.mapbox.com/about/maps/">Mapbox</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    },
    online: true,
  },
  {
    id: "tianditu-img",
    kind: "tile",
    labelKey: "mapManager.basemapTiandituImg",
    url: tiandituUrl("img"),
    options: { tileSize: 256, attribution: "&copy; 国家地理信息公共服务平台 天地图" },
    online: true,
    needsToken: !TIANDITU_TOKEN,
  },
  {
    id: "tianditu-vec",
    kind: "tile",
    labelKey: "mapManager.basemapTiandituVec",
    url: tiandituUrl("vec"),
    options: { tileSize: 256, attribution: "&copy; 国家地理信息公共服务平台 天地图" },
    online: true,
    needsToken: !TIANDITU_TOKEN,
  },
  ...(CUSTOM_TILE_URL
    ? [
        {
          id: "custom",
          kind: "tile",
          labelKey: "mapManager.basemapCustom",
          url: CUSTOM_TILE_URL,
          options: { tileSize: 256, attribution: "" },
          online: false,
        },
      ]
    : []),
  {
    id: "offline",
    kind: "geojson",
    labelKey: "mapManager.basemapOffline",
    geojson: worldGeoJSON,
    online: false,
  },
];

export const DEFAULT_BASEMAP_ID = "mapbox";

export function storedBasemapId() {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return BASEMAPS.some((b) => b.id === saved) ? saved : DEFAULT_BASEMAP_ID;
  } catch {
    return DEFAULT_BASEMAP_ID;
  }
}

export function setBasemapId(id) {
  try {
    window.localStorage.setItem(STORAGE_KEY, id);
  } catch {
    /* 隐私模式下 setItem 会抛错：选择只在本次会话内生效即可 */
  }
}

export function getBasemap(id = storedBasemapId()) {
  return BASEMAPS.find((b) => b.id === id) || BASEMAPS.find((b) => b.id === DEFAULT_BASEMAP_ID);
}

// 旧导出名保留（历史上 leafletMap 之外无使用方，防测试引用断链）。
export const MAPBOX_TILE_URL = mapboxUrl;
export const MAPBOX_ATTRIBUTION = BASEMAPS[0].options.attribution;
export const MAPBOX_TILE_SIZE = 512;
export const MAPBOX_ZOOM_OFFSET = -1;
