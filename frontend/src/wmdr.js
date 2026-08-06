export const WIGOS_ID_PATTERN = /^(0|1|2|3)-([1-9]\d*)-([0-9]+)-([A-Za-z0-9._-]+)$/;
export const CONFORMANCE_CLASS = "http://wigos.wmo.int/spec/wmdr/2/conf/core";

const nonEmpty = (arr) => arr.map((v) => v.trim()).filter(Boolean);

export function isValidWmdrRecord(form) {
  return (
    WIGOS_ID_PATTERN.test(form.id) &&
    form.latitude !== "" &&
    form.longitude !== "" &&
    !Number.isNaN(Number(form.latitude)) &&
    !Number.isNaN(Number(form.longitude)) &&
    form.title.trim() !== "" &&
    form.created !== "" &&
    nonEmpty(form.contacts).length > 0 &&
    nonEmpty(form.observingCapabilities).length > 0 &&
    nonEmpty(form.links).length > 0
  );
}

export function buildWmdrRecord(form) {
  const properties = {
    title: form.title.trim(),
    contacts: nonEmpty(form.contacts).map((organization) => ({ organization })),
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
