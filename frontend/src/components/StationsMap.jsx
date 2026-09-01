import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Circle, Popup, AttributionControl, useMap } from "react-leaflet";
import { MAPBOX_TILE_URL, MAPBOX_ATTRIBUTION, MAPBOX_TILE_SIZE, MAPBOX_ZOOM_OFFSET } from "../mapConfig";

const DEFAULT_CENTER = [20, 0];
const DEFAULT_ZOOM = 2;
const SINGLE_STATION_ZOOM = 9;
const TARGET_PIXEL_RADIUS = 6;
const MIN_MARKER_RADIUS_METERS = 2000;
const MARKER_STYLE = { color: "#1d4ed8", weight: 1, fillColor: "#3b82f6", fillOpacity: 0.9 };

// Web Mercator ground resolution: at zoom 0 the whole 40,075,016.686m
// equator is drawn across 256px, halving each zoom level; scaled by
// latitude to account for projection distortion away from the equator.
function metersPerPixel(latitude, zoom) {
  return (156543.03392 * Math.cos((latitude * Math.PI) / 180)) / Math.pow(2, zoom);
}

function FitToMarkers({ positions, onZoomChange }) {
  const map = useMap();
  useEffect(() => {
    if (positions.length === 0) return;

    const updateZoom = () => onZoomChange(map.getZoom());

    // fitBounds/setView animate the transition, so the zoom only reaches
    // its final value once "moveend" fires — reading it synchronously
    // here would still see the pre-transition zoom.
    map.once("moveend", updateZoom);
    if (positions.length === 1) {
      map.setView(positions[0], SINGLE_STATION_ZOOM);
    } else {
      map.fitBounds(positions, { padding: [30, 30] });
    }
    return () => map.off("moveend", updateZoom);
  }, [positions, map, onZoomChange]);
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
  const [zoom, setZoom] = useState(DEFAULT_ZOOM);

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
        {positioned.map((station) => {
          const radius = Math.max(MIN_MARKER_RADIUS_METERS, TARGET_PIXEL_RADIUS * metersPerPixel(station.lat, zoom));
          return (
            <Circle key={station.id} center={[station.lat, station.lon]} radius={radius} {...MARKER_STYLE}>
              <Popup>
                <strong>{station.name}</strong>
                <br />
                {station.wsi}
              </Popup>
            </Circle>
          );
        })}
        <FitToMarkers positions={positions} onZoomChange={setZoom} />
      </MapContainer>
    </div>
  );
}
