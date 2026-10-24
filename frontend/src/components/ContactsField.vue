<script>
import { CONTACT_LINK_FIELDS, LOGO_FIELDS } from "../fieldDefs";

// Labels and placeholders are i18n message keys (see i18n/keys.js).
const PHONE_FIELDS = [
  { name: "value", label: "field.phoneNumber", type: "text", placeholder: "+41791234567" },
  { name: "roles", label: "field.roles", type: "array-string" },
];

const EMAIL_FIELDS = [
  { name: "value", label: "field.emailAddress", type: "text", placeholder: "name@example.org" },
  { name: "roles", label: "field.roles", type: "array-string" },
];

const ADDRESS_FIELDS = [
  { name: "city", label: "field.city", type: "text" },
  { name: "administrativeArea", label: "field.administrativeArea", type: "text" },
  { name: "postalCode", label: "field.postalCode", type: "text" },
  { name: "country", label: "field.country", type: "text" },
  { name: "deliveryPoint", label: "field.deliveryPoint", type: "array-string" },
  { name: "roles", label: "field.roles", type: "array-string" },
];

const CONTACT_FIELDS = [
  { name: "organization", label: "field.organization", type: "text", required: true },
  { name: "name", label: "field.name", type: "text" },
  { name: "position", label: "field.position", type: "text" },
  { name: "identifier", label: "field.identifier", type: "text", placeholder: "ph.contactIdentifier" },
  { name: "phones", label: "field.phone", type: "array-object", fields: PHONE_FIELDS, summary: (p) => p.value },
  { name: "emails", label: "field.email", type: "array-object", fields: EMAIL_FIELDS, summary: (e) => e.value },
  {
    name: "addresses",
    label: "field.address",
    type: "array-object",
    fields: ADDRESS_FIELDS,
    summary: (a) => [a.city, a.country].filter(Boolean).join(", "),
  },
  { name: "links", label: "field.link", type: "array-object", fields: CONTACT_LINK_FIELDS, summary: (l) => l.title || l.href },
  { name: "hoursOfService", label: "field.hoursOfService", type: "text" },
  { name: "contactInstructions", label: "field.contactInstructions", type: "text" },
  { name: "roles", label: "field.roles", type: "array-string" },
  { name: "logo", label: "field.logo", type: "object", fields: LOGO_FIELDS },
];

const contactSummary = (c) => [c.organization, c.name].filter(Boolean).join(" - ");
</script>

<script setup>
import DrillInArrayField from "./DrillInArrayField.vue";

const contacts = defineModel({ type: Array, required: true });
</script>

<template>
  <DrillInArrayField
    v-model="contacts"
    label="field.contacts"
    item-label="field.contact"
    :fields="CONTACT_FIELDS"
    :item-summary="contactSummary"
    required
  />
</template>
