<script>
// Edits a codelist concept ({ id, title?, description?, url? }). With
// `options` or `groups` (entries from getCodelist) it renders a select that
// fills every property from the codelist (a type-to-filter autocomplete for
// long lists); otherwise a text input for the codelist notation, with the
// other properties behind a "Details" toggle, for codelists that aren't
// cached locally yet.

const optionValue = (opt) => opt.id || opt.code;

function conceptFromOption(opt) {
  const concept = { id: opt.code, title: opt.label };
  if (opt.description) concept.description = opt.description;
  if (opt.id) concept.url = opt.id;
  return concept;
}

// Match on the concept URI first: notations can collide across codelists
// (e.g. "12244" is both an atmosphere and an ocean variable).
function findOption(allOptions, concept) {
  if (!concept) return null;
  return (
    (concept.url && allOptions.find((opt) => opt.id === concept.url)) ||
    allOptions.find((opt) => opt.code === concept.id) ||
    null
  );
}

// Every whitespace-separated term has to appear in the label or notation.
// `haystack` may hold both the shown name and the English one, so a search
// works in either language.
function matchesQuery(haystack, query) {
  const lower = haystack.toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((term) => lower.includes(term));
}

const DETAIL_FIELDS = [
  { name: "title", label: "field.title" },
  { name: "url", label: "field.url", placeholder: "ph.conceptUri" },
  { name: "description", label: "field.description" },
];

// Codelists longer than this get a type-to-filter box instead of a select.
const SEARCHABLE_MIN_OPTIONS = 15;
// Stands for a value that isn't in the codelist (or while it's still loading).
const CURRENT = "__current__";
</script>

<script setup>
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useFieldText } from "../i18n/keys";
import { activeLocale } from "../i18n/plain";
import { codelistText } from "../i18n/codelistNames";

const props = defineProps({
  label: { type: String, required: true },
  options: Array,
  groups: Array,
  required: Boolean,
  placeholder: String,
  // The codelist the options came from, so their names can be shown in the UI
  // language. Only the display is translated; `opt.label` — the wording
  // conceptFromOption stores in the record — stays the WMO English.
  scheme: String,
});
const concept = defineModel({ type: Object, default: null });

const { t } = useI18n();
const text = useFieldText();
const labelText = computed(() => text(props.label));
const fieldLabel = computed(() => (props.required ? `${labelText.value} *` : labelText.value));

// --- Codelist (select / autocomplete)

const allOptions = computed(() => (props.groups ? props.groups.flatMap((group) => group.options) : props.options || []));
const selected = computed(() => findOption(allOptions.value, concept.value));
const searchable = computed(() => allOptions.value.length > SEARCHABLE_MIN_OPTIONS);

// `scheme` on the props covers a field backed by one list; a grouped field
// carries a scheme per group instead (observedProperty draws on five lists).
const toItem = (opt, scheme) => ({ title: codelistText(scheme, opt, activeLocale()), value: optionValue(opt), opt, scheme });
const items = computed(() => {
  const list = [];
  // Keep a value that isn't in the codelist (or while it's still loading) visible.
  if (!selected.value && concept.value?.id) {
    const label = concept.value.title || concept.value.id;
    list.push({ title: label, value: CURRENT, opt: { label, code: concept.value.id } });
  }
  if (props.groups) {
    props.groups.forEach((group) => {
      if (!group.options.length) return;
      // The scheme groups arrive as message keys ("opt.atmosphere").
      list.push({ type: "subheader", title: text(group.label) });
      list.push(...group.options.map((opt) => toItem(opt, group.scheme)));
    });
  } else {
    list.push(...(props.options || []).map((opt) => toItem(opt, props.scheme)));
  }
  return list;
});
const selectedValue = computed(() => (selected.value ? optionValue(selected.value) : concept.value?.id ? CURRENT : null));

function choose(value) {
  if (value == null) {
    concept.value = null;
    return;
  }
  const opt = allOptions.value.find((o) => optionValue(o) === value);
  if (opt) concept.value = conceptFromOption(opt);
}

// Typing in either language finds the entry: the shown name first, then the
// English label the record will store. The scheme rides on the item because a
// grouped field reads its options from several lists.
const filter = (_value, query, item) => {
  const { opt, scheme } = item.raw;
  if (!opt) return true;
  return matchesQuery(`${codelistText(scheme, opt, activeLocale())} ${opt.label} ${opt.code}`, query);
};

// --- Free text (no codelist)

const showDetails = ref(DETAIL_FIELDS.some((field) => concept.value?.[field.name]));

function updateFreeText(key, text) {
  const next = { ...(concept.value || { id: "" }), [key]: text ?? "" };
  Object.keys(next).forEach((k) => {
    if (k !== "id" && !next[k]) delete next[k];
  });
  concept.value = Object.values(next).some(Boolean) ? next : null;
}
</script>

<template>
  <div v-if="!options && !groups">
    <div class="input-row">
      <v-text-field
        :label="fieldLabel"
        :model-value="concept?.id || ''"
        :placeholder="text(placeholder)"
        :persistent-placeholder="!!placeholder"
        @update:model-value="(text2) => updateFreeText('id', text2)"
      />
      <v-btn variant="outlined" :aria-expanded="showDetails" @click="showDetails = !showDetails">
        {{ showDetails ? t("concept.hideDetails") : t("concept.details") }}
      </v-btn>
    </div>
    <template v-if="showDetails">
      <v-text-field
        v-for="field in DETAIL_FIELDS"
        :key="field.name"
        class="mt-2"
        :label="text(field.label)"
        :model-value="concept?.[field.name] || ''"
        :placeholder="text(field.placeholder)"
        @update:model-value="(value) => updateFreeText(field.name, value)"
      />
    </template>
  </div>

  <v-autocomplete
    v-else-if="searchable"
    :label="fieldLabel"
    :placeholder="t('concept.typeToFilter')"
    :items="items"
    :model-value="selectedValue"
    :custom-filter="filter"
    auto-select-first
    clearable
    @update:model-value="choose"
  >
    <template #item="{ item, props: itemProps }">
      <v-list-item v-bind="itemProps">
        <template v-if="item.opt.code !== item.opt.label" #append>
          <span class="concept-code">{{ item.opt.code }}</span>
        </template>
      </v-list-item>
    </template>
  </v-autocomplete>

  <v-select
    v-else
    :label="fieldLabel"
    :placeholder="t('concept.noneSelected')"
    :items="items"
    :model-value="selectedValue"
    clearable
    @update:model-value="choose"
  />
</template>

<style scoped>
.concept-code {
  margin-left: 0.75rem;
  font-size: 0.8rem;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
