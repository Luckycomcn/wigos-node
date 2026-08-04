export const GEOMETRY_TYPES = ["Point", "LineString", "Polygon", "MultiPoint"];

export const MIN_POINTS = {
  Point: 1,
  LineString: 2,
  Polygon: 3,
  MultiPoint: 1,
};

function toLngLat(point) {
  return [Number(point.lng), Number(point.lat)];
}

export function buildGeoJsonFeature(geometryType, points, properties) {
  const coords = points.map(toLngLat);

  let coordinates;
  if (geometryType === "Point") {
    coordinates = coords[0];
  } else if (geometryType === "LineString" || geometryType === "MultiPoint") {
    coordinates = coords;
  } else if (geometryType === "Polygon") {
    const ring = [...coords];
    const [firstLng, firstLat] = ring[0];
    const [lastLng, lastLat] = ring[ring.length - 1];
    if (firstLng !== lastLng || firstLat !== lastLat) {
      ring.push([firstLng, firstLat]);
    }
    coordinates = [ring];
  } else {
    throw new Error(`Unsupported geometry type: ${geometryType}`);
  }

  return {
    type: "Feature",
    geometry: {
      type: geometryType,
      coordinates,
    },
    properties: properties || {},
  };
}
