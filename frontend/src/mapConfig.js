// 底图配置。
//
// 原版把 Mapbox 的访问令牌写死在这个文件里提交进仓库（`pk.eyJ1Ijoid21vd2lz...`）。
// 后果有三层：
//   1. 那个令牌是 WMO 的账号配额，任何国家部署都共用，谁都能从公开仓库里抄走；
//   2. 地图强依赖 api.mapbox.com —— 内网/离线环境（各国 NMHS 常见）一片灰块；
//   3. 换令牌必须改代码重新构建，运维没法只改配置。
//
// 现在：令牌从构建期环境变量 VITE_MAPBOX_TOKEN 读，没配就不加载商业底图，
// 只画台站标记 + 坐标网格。演示与内网部署都不再依赖外网，也不再需要令牌。

const MAPBOX_TOKEN = (import.meta.env.VITE_MAPBOX_TOKEN || "").trim();

export const HAS_TILE_LAYER = MAPBOX_TOKEN.length > 0;

export const MAPBOX_TILE_URL = HAS_TILE_LAYER
  ? `https://api.mapbox.com/styles/v1/wmowis/cmmdlz8nb004m01scaoyh6boo/tiles/{z}/{x}/{y}?access_token=${MAPBOX_TOKEN}`
  : "";

export const MAPBOX_ATTRIBUTION =
  '&copy; <a href="https://www.mapbox.com/about/maps/">Mapbox</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

// Mapbox serves 512px tiles; Leaflet defaults to 256px, so zoomOffset keeps zoom levels aligned.
export const MAPBOX_TILE_SIZE = 512;
export const MAPBOX_ZOOM_OFFSET = -1;

// 可选：指向本地瓦片服务（如内网部署的 tileserver-gl / GeoServer）。
// 例如 VITE_TILE_URL=http://10.0.0.5:8080/tiles/{z}/{x}/{y}.png
// 设了它就用本地瓦片，不需要 Mapbox 令牌，也不访问外网。
export const LOCAL_TILE_URL = (import.meta.env.VITE_TILE_URL || "").trim();

export const TILE_URL = LOCAL_TILE_URL || MAPBOX_TILE_URL;

export const TILE_OPTIONS = LOCAL_TILE_URL
  ? { attribution: "&copy; OpenStreetMap contributors", tileSize: 256 }
  : {
      attribution: MAPBOX_ATTRIBUTION,
      tileSize: MAPBOX_TILE_SIZE,
      zoomOffset: MAPBOX_ZOOM_OFFSET,
    };

export const HAS_BASEMAP = Boolean(TILE_URL);