<script>
import { codelistProps } from "../codelists";
import { TIME_FIELDS, GEOMETRY_FIELDS, DATES_FIELD } from "../fieldDefs";
import { describeInterval } from "../interval";
import { activeLocale, translate } from "../i18n/plain";

// Field names/shapes follow definitions/Observations, Configurations and
// Instrument in wmo-im/wmdr2 schemas/wmdr2-bundled.json.
// Labels are i18n message keys (see i18n/keys.js).

const INSTRUMENT_FIELDS = [
  { name: "id", label: "field.instrumentId", type: "text" },
  { name: "manufacturer", label: "field.manufacturer", type: "text" },
  { name: "model", label: "field.model", type: "text" },
];

function observationFields(codelists) {
  const concept = (name, label, extra) => ({ name, label, type: "concept", ...codelistProps(name, codelists), ...extra });

  const verticalDistanceFields = [
    { name: "distances", label: "field.distances", type: "array-string", placeholder: "ph.signedDistance" },
    concept("unit", "field.unit"),
    concept("referenceSurface", "field.referenceSurface"),
  ];

  // No id field: buildWmdrRecord assigns one to a configuration without it.
  const configurationFields = [
    { name: "time", label: "field.time", type: "object", fields: TIME_FIELDS },
    concept("observingMethod", "field.observingMethod"),
    concept("operatingStatus", "field.operatingStatus"),
    concept("sourceOfObservation", "field.sourceOfObservation"),
    { name: "geometry", label: "field.location", type: "object", fields: GEOMETRY_FIELDS },
    { name: "instrument", label: "field.instrument", type: "object", fields: INSTRUMENT_FIELDS },
    { name: "instrumentSerialNumber", label: "field.instrumentSerialNumber", type: "text" },
    { name: "verticalDistance", label: "field.verticalDistance", type: "object", fields: verticalDistanceFields },
  ];

  const programAffiliationFields = [
    concept("programAffiliation", "field.programAffiliation", { required: true }),
    concept("reportingStatus", "field.reportingStatus"),
    DATES_FIELD,
  ];

  return [
    concept("observedProperty", "field.observedProperty", { required: true }),
    concept("observedGeometry", "field.observedGeometry"),
    {
      name: "programAffiliations",
      label: "field.programAffiliations",
      type: "array-object",
      fields: programAffiliationFields,
      required: true,
      summary: (p) => p.programAffiliation?.title || p.programAffiliation?.id,
    },
    {
      name: "configurations",
      label: "field.configurations",
      type: "array-object",
      fields: configurationFields,
      required: true,
      summary: configurationSummary,
    },
  ];
}

const observationSummary = (o) => o.observedProperty?.title || o.observedProperty?.id;

// e.g. "Vaisala HMP155 · Since 2020, ongoing · Operational". A configuration
// with none of these (a stored one may hold only its id) says so, rather than
// showing a blank card. The interval wording and the date labels follow the
// UI language, because this runs during render.
const configurationSummary = (c) =>
  [
    [c.instrument?.manufacturer, c.instrument?.model].filter(Boolean).join(" "),
    describeInterval(c.time?.intervalStart, c.time?.intervalEnd, { t: translate, locale: activeLocale() }),
    c.operatingStatus?.title || c.operatingStatus?.id,
  ]
    .filter(Boolean)
    .join(" · ") || translate("observations.noDetails");
</script>

<script setup>
import { computed } from "vue";
import DrillInArrayField from "./DrillInArrayField.vue";
import { useCodelists } from "../composables/useCodelists";

const observations = defineModel({ type: Array, required: true });
const { codelists } = useCodelists();
const fields = computed(() => observationFields(codelists.value));
</script>

<template>
  <DrillInArrayField
    v-model="observations"
    label="field.observations"
    item-label="field.observation"
    :fields="fields"
    :item-summary="observationSummary"
    required
  />
</template>
