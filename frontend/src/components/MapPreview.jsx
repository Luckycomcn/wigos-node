import { useEffect } from "react";
import { MapContainer, TileLayer, Circle, AttributionControl, useMap } from "react-leaflet";
import { MAPBOX_TILE_URL, MAPBOX_ATTRIBUTION, MAPBOX_TILE_SIZE, MAPBOX_ZOOM_OFFSET } from "../mapConfig";

const DEFAULT_CENTER = [20, 0];
const DEFAULT_ZOOM = 2;
const POINT_ZOOM = 9;
const MARKER_RADIUS_METERS = 5000;
const MARKER_STYLE = { radius: MARKER_RADIUS_METERS, color: "#1d4ed8", weight: 1, fillColor: "#3b82f6", fillOpacity: 0.9 };

function Recenter({ position }) {
  const map = useMap();
  useEffect(() => {
    if (position) {
      map.setView(position, POINT_ZOOM);
    }
  }, [position, map]);
  return null;
}

export default function MapPreview({ latitude, longitude }) {
  const lat = Number(latitude);
  const lon = Number(longitude);
  const hasPosition = latitude !== "" && longitude !== "" && !Number.isNaN(lat) && !Number.isNaN(lon);
  const position = hasPosition ? [lat, lon] : null;

  return (
    <div>
      <div className="map-container">
        <MapContainer
          center={position || DEFAULT_CENTER}
          zoom={position ? POINT_ZOOM : DEFAULT_ZOOM}
          style={{ height: "100%", width: "100%" }}
          attributionControl={false}
        >
          <TileLayer
            attribution={MAPBOX_ATTRIBUTION}
            url={MAPBOX_TILE_URL}
            tileSize={MAPBOX_TILE_SIZE}
            zoomOffset={MAPBOX_ZOOM_OFFSET}
          />
          <AttributionControl prefix="Leaflet" />
          {position && <Circle center={position} {...MARKER_STYLE} />}
          <Recenter position={position} />
        </MapContainer>
      </div>
      {!hasPosition && <p className="map-hint">Enter latitude/longitude to preview the point.</p>}
    </div>
  );
}
