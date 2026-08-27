import { useEffect } from "react";
import { MapContainer, TileLayer, Marker, AttributionControl, useMap } from "react-leaflet";
import L from "leaflet";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

const DEFAULT_CENTER = [20, 0];
const DEFAULT_ZOOM = 2;
const POINT_ZOOM = 9;

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
            attribution='&copy; <a href="https://www.mapbox.com/about/maps/">Mapbox</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://api.mapbox.com/styles/v1/wmowis/cmmdlz8nb004m01scaoyh6boo/tiles/{z}/{x}/{y}?access_token=pk.eyJ1Ijoid21vd2lzIiwiYSI6ImNtbWRrdTZwbDA0NXMyc3F1ZnN1enVkOG4ifQ.bArk5X6_yvpknSC_Mplpew"
            tileSize={512}
            zoomOffset={-1}
          />
          <AttributionControl prefix="Leaflet" />
          {position && <Marker position={position} />}
          <Recenter position={position} />
        </MapContainer>
      </div>
      {!hasPosition && <p className="map-hint">Enter latitude/longitude to preview the point.</p>}
    </div>
  );
}
