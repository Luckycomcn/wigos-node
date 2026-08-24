export const WIGOS_ID_PATTERN = /^(0|1|2|3)-([1-9]\d*)-([0-9]+)-([A-Za-z0-9._-]+)$/;
export const CONFORMANCE_CLASS = "http://wigos.wmo.int/spec/wmdr/2/conf/core";

const nonEmpty = (arr) => arr.map((v) => v.trim()).filter(Boolean);

function cleanStringArray(arr) {
  return (arr || []).map((v) => v.trim()).filter(Boolean);
}

function cleanPhoneOrEmail(entry) {
  const value = (entry.value || "").trim();
  if (!value) return null;
  const cleaned = { value };
  const roles = cleanStringArray(entry.roles);
  if (roles.length) cleaned.roles = roles;
  return cleaned;
}

function cleanAddress(address) {
  const cleaned = {};
  ["city", "administrativeArea", "postalCode", "country"].forEach((key) => {
    const value = (address[key] || "").trim();
    if (value) cleaned[key] = value;
  });
  const deliveryPoint = cleanStringArray(address.deliveryPoint);
  if (deliveryPoint.length) cleaned.deliveryPoint = deliveryPoint;
  const roles = cleanStringArray(address.roles);
  if (roles.length) cleaned.roles = roles;
  return Object.keys(cleaned).length ? cleaned : null;
}

function cleanContact(contact) {
  const organization = (contact.organization || "").trim();
  if (!organization) return null;
  const cleaned = { organization };

  const name = (contact.name || "").trim();
  if (name) cleaned.name = name;
  const position = (contact.position || "").trim();
  if (position) cleaned.position = position;

  const phones = (contact.phones || []).map(cleanPhoneOrEmail).filter(Boolean);
  if (phones.length) cleaned.phones = phones;
  const emails = (contact.emails || []).map(cleanPhoneOrEmail).filter(Boolean);
  if (emails.length) cleaned.emails = emails;
  const addresses = (contact.addresses || []).map(cleanAddress).filter(Boolean);
  if (addresses.length) cleaned.addresses = addresses;
  const roles = cleanStringArray(contact.roles);
  if (roles.length) cleaned.roles = roles;

  return cleaned;
}

function cleanContacts(contacts) {
  return (contacts || []).map(cleanContact).filter(Boolean);
}

function cleanTime(time) {
  if (!time) return null;
  const cleaned = {};
  const date = (time.date || "").trim();
  if (date) cleaned.date = date;
  const timestamp = (time.timestamp || "").trim();
  if (timestamp) cleaned.timestamp = new Date(timestamp).toISOString();
  const intervalStart = (time.intervalStart || "").trim();
  const intervalEnd = (time.intervalEnd || "").trim();
  if (intervalStart && intervalEnd) cleaned.interval = [intervalStart, intervalEnd];
  const resolution = (time.resolution || "").trim();
  if (resolution) cleaned.resolution = resolution;
  return Object.keys(cleaned).length ? cleaned : null;
}

function cleanGeometry(geometry) {
  if (!geometry) return null;
  const latitude = (geometry.latitude ?? "").toString().trim();
  const longitude = (geometry.longitude ?? "").toString().trim();
  if (latitude === "" || longitude === "" || Number.isNaN(Number(latitude)) || Number.isNaN(Number(longitude))) {
    return null;
  }
  return { type: "Point", coordinates: [Number(longitude), Number(latitude)] };
}

function cleanReferenceSurface(referenceSurface) {
  const type = (referenceSurface.referenceSurface || "").trim();
  const verticalDistance = (referenceSurface.verticalDistance ?? "").toString().trim();
  if (!type || verticalDistance === "" || Number.isNaN(Number(verticalDistance))) return null;
  return { referenceSurface: type, verticalDistance: Number(verticalDistance) };
}

function cleanReferenceSurfaces(referenceSurfaces) {
  return (referenceSurfaces || []).map(cleanReferenceSurface).filter(Boolean);
}

function cleanInstrument(instrument) {
  const id = (instrument?.id || "").trim();
  if (!id) return null;
  const cleaned = { id };
  const manufacturer = (instrument.manufacturer || "").trim();
  if (manufacturer) cleaned.manufacturer = manufacturer;
  const model = (instrument.model || "").trim();
  if (model) cleaned.model = model;
  const serialNumber = (instrument.serialNumber || "").trim();
  if (serialNumber) cleaned.serialNumber = serialNumber;
  return cleaned;
}

function cleanDeployment(deployment) {
  const instrument = cleanInstrument(deployment.instrument);
  if (!instrument) return null;
  const id = (deployment.id || "").trim();
  if (!id) return null;
  const cleaned = { id, instrument };
  const geometry = cleanGeometry(deployment.geometry);
  if (geometry) cleaned.geometry = geometry;
  const time = cleanTime(deployment.time);
  if (time) cleaned.time = time;
  const keywords = cleanStringArray(deployment.keywords);
  if (keywords.length) cleaned.keywords = keywords;
  const referenceSurfaces = cleanReferenceSurfaces(deployment.referenceSurfaces);
  if (referenceSurfaces.length) cleaned.referenceSurfaces = referenceSurfaces;
  return cleaned;
}

function cleanObservingCapability(capability) {
  const observedProperty = (capability.observedProperty || "").trim();
  if (!observedProperty) return null;
  const cleaned = { observedProperty };
  const observingMethod = (capability.observingMethod || "").trim();
  if (observingMethod) cleaned.observingMethod = observingMethod;
  const operatingStatus = (capability.operatingStatus || "").trim();
  if (operatingStatus) cleaned.operatingStatus = operatingStatus;
  const sourceOfObservation = (capability.sourceOfObservation || "").trim();
  if (sourceOfObservation) cleaned.sourceOfObservation = sourceOfObservation;
  const time = cleanTime(capability.time);
  if (time) cleaned.time = time;
  const deployments = (capability.deployments || [])
    .slice(0, 1)
    .map(cleanDeployment)
    .filter(Boolean);
  if (deployments.length) cleaned.deployments = deployments;
  return cleaned;
}

function cleanObservingCapabilities(capabilities) {
  return (capabilities || []).map(cleanObservingCapability).filter(Boolean);
}

export function isValidWmdrRecord(form) {
  return (
    WIGOS_ID_PATTERN.test(form.id) &&
    form.latitude !== "" &&
    form.longitude !== "" &&
    !Number.isNaN(Number(form.latitude)) &&
    !Number.isNaN(Number(form.longitude)) &&
    form.title.trim() !== "" &&
    form.created !== "" &&
    cleanContacts(form.contacts).length > 0 &&
    cleanObservingCapabilities(form.observingCapabilities).length > 0 &&
    nonEmpty(form.links).length > 0
  );
}

function toDatetimeLocal(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function parseTime(time) {
  const [intervalStart, intervalEnd] = (time && time.interval) || ["", ""];
  return {
    date: (time && time.date) || "",
    timestamp: time && time.timestamp ? toDatetimeLocal(time.timestamp) : "",
    intervalStart: intervalStart || "",
    intervalEnd: intervalEnd || "",
    resolution: (time && time.resolution) || "",
  };
}

function parsePhoneOrEmail(entry) {
  return { value: entry.value || "", roles: entry.roles || [] };
}

function parseAddress(address) {
  return {
    city: address.city || "",
    administrativeArea: address.administrativeArea || "",
    postalCode: address.postalCode || "",
    country: address.country || "",
    deliveryPoint: address.deliveryPoint || [],
    roles: address.roles || [],
  };
}

function parseContact(contact) {
  return {
    organization: contact.organization || "",
    name: contact.name || "",
    position: contact.position || "",
    phones: (contact.phones || []).map(parsePhoneOrEmail),
    emails: (contact.emails || []).map(parsePhoneOrEmail),
    addresses: (contact.addresses || []).map(parseAddress),
    roles: contact.roles || [],
  };
}

function parseInstrument(instrument) {
  return {
    id: (instrument && instrument.id) || "",
    manufacturer: (instrument && instrument.manufacturer) || "",
    model: (instrument && instrument.model) || "",
    serialNumber: (instrument && instrument.serialNumber) || "",
  };
}

function parseDeploymentGeometry(geometry) {
  const coordinates = geometry && geometry.coordinates;
  if (!coordinates) return { latitude: "", longitude: "" };
  return { latitude: String(coordinates[1]), longitude: String(coordinates[0]) };
}

function parseReferenceSurface(referenceSurface) {
  return {
    referenceSurface: referenceSurface.referenceSurface || "",
    verticalDistance:
      referenceSurface.verticalDistance != null ? String(referenceSurface.verticalDistance) : "",
  };
}

function parseDeployment(deployment) {
  return {
    id: deployment.id || "",
    geometry: parseDeploymentGeometry(deployment.geometry),
    time: parseTime(deployment.time),
    keywords: deployment.keywords || [],
    referenceSurfaces: (deployment.referenceSurfaces || []).map(parseReferenceSurface),
    instrument: parseInstrument(deployment.instrument),
  };
}

function parseObservingCapability(capability) {
  return {
    observedProperty: capability.observedProperty || "",
    observingMethod: capability.observingMethod || "",
    operatingStatus: capability.operatingStatus || "",
    sourceOfObservation: capability.sourceOfObservation || "",
    time: parseTime(capability.time),
    deployments: (capability.deployments || []).map(parseDeployment),
  };
}

export function parseWmdrRecord(record) {
  const properties = record.properties || {};
  const coordinates = (record.geometry && record.geometry.coordinates) || ["", ""];
  return {
    id: record.id || "",
    latitude: coordinates[1] != null ? String(coordinates[1]) : "",
    longitude: coordinates[0] != null ? String(coordinates[0]) : "",
    title: properties.title || "",
    description: properties.description || "",
    additionalTitles: properties.additionalTitles?.length ? properties.additionalTitles : [""],
    additionalIds: properties.additionalIds?.length ? properties.additionalIds : [""],
    facilityType: properties.facilityType || "",
    wmoRegion: properties.wmoRegion || "",
    contacts: (properties.contacts || []).map(parseContact),
    created: toDatetimeLocal(properties.created),
    updated: toDatetimeLocal(properties.updated),
    keywords: properties.keywords?.length ? properties.keywords : [""],
    territories: properties.territories?.length
      ? properties.territories.map((t) => t.territory)
      : [""],
    programAffiliations: properties.programAffiliations?.length
      ? properties.programAffiliations.map((p) => p.programAffiliation)
      : [""],
    observingCapabilities: (properties.observingCapabilities || []).map(parseObservingCapability),
    links: record.links?.length ? record.links.map((l) => l.href) : [""],
  };
}

export function buildWmdrRecord(form) {
  const properties = {
    title: form.title.trim(),
    contacts: cleanContacts(form.contacts),
    created: new Date(form.created).toISOString(),
    observingCapabilities: cleanObservingCapabilities(form.observingCapabilities),
  };

  if (form.description.trim()) properties.description = form.description.trim();
  if (nonEmpty(form.additionalTitles).length) properties.additionalTitles = nonEmpty(form.additionalTitles);
  if (nonEmpty(form.additionalIds).length) properties.additionalIds = nonEmpty(form.additionalIds);
  if (form.facilityType.trim()) properties.facilityType = form.facilityType.trim();
  if (form.wmoRegion.trim()) properties.wmoRegion = form.wmoRegion.trim();
  if (form.updated) properties.updated = new Date(form.updated).toISOString();
  if (nonEmpty(form.keywords).length) properties.keywords = nonEmpty(form.keywords);
  if (nonEmpty(form.territories).length) {
    properties.territories = nonEmpty(form.territories).map((territory) => ({ territory }));
  }
  if (nonEmpty(form.programAffiliations).length) {
    properties.programAffiliations = nonEmpty(form.programAffiliations).map((programAffiliation) => ({
      programAffiliation,
    }));
  }

  return {
    id: form.id.trim(),
    conformsTo: [CONFORMANCE_CLASS],
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates: [Number(form.longitude), Number(form.latitude)],
    },
    properties,
    links: nonEmpty(form.links).map((href) => ({ href })),
  };
}
