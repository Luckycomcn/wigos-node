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
