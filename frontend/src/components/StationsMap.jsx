import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, Marker, Popup, AttributionControl, useMap } from "react-leaflet";
import "../leafletIcons";
import { MAPBOX_TILE_URL, MAPBOX_ATTRIBUTION, MAPBOX_TILE_SIZE, MAPBOX_ZOOM_OFFSET } from "../mapConfig";

const DEFAULT_CENTER = [20, 0];
const DEFAULT_ZOOM = 2;
const SINGLE_STATION_ZOOM = 9;

function FitToMarkers({ positions }) {
  const map = useMap();
  useEffect(() => {
    if (positions.length === 0) return;
    if (positions.length === 1) {
      map.setView(positions[0], SINGLE_STATION_ZOOM);
    } else {
      map.fitBounds(positions, { padding: [30, 30] });
    }
  }, [positions, map]);
  return null;
}

export default function StationsMap({ stations }) {
  const positioned = useMemo(
    () =>
      stations
        .map((station) => ({
          ...station,
          lat: Number(station.latitude),
          lon: Number(station.longitude),
        }))
        .filter((station) => !Number.isNaN(station.lat) && !Number.isNaN(station.lon)),
    [stations]
  );
  const positions = useMemo(() => positioned.map((station) => [station.lat, station.lon]), [positioned]);

  if (positioned.length === 0) return null;

  return (
    <div className="map-container stations-map-container">
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
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
        {positioned.map((station) => (
          <Marker key={station.wsi} position={[station.lat, station.lon]}>
            <Popup>
              <strong>{station.name}</strong>
              <br />
              {station.wsi}
            </Popup>
          </Marker>
        ))}
        <FitToMarkers positions={positions} />
      </MapContainer>
    </div>
  );
}
