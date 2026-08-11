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
    nonEmpty(form.observingCapabilities).length > 0 &&
    nonEmpty(form.links).length > 0
  );
}

export function buildWmdrRecord(form) {
  const properties = {
    title: form.title.trim(),
    contacts: cleanContacts(form.contacts),
    created: new Date(form.created).toISOString(),
    observingCapabilities: nonEmpty(form.observingCapabilities).map((name) => ({ name })),
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
