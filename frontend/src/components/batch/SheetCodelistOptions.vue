<script setup>
import { computed } from "vue";
import { activeLocale, translate } from "../../i18n/plain";
import { codelistText } from "../../i18n/codelistNames";
import { findCodelistOption } from "../../batch/common";
import { CODELISTS, codelistOptions, codelistScheme } from "../../codelists";

// The <option>s of a codelist column, grouped like the station form. A value
// that isn't in the codelist is kept as an extra option so it stays visible.
const props = defineProps({
  column: { type: Object, required: true },
  codelists: { type: Object, required: true },
  value: { type: String, default: "" },
});

const list = computed(() => props.codelists[props.column.codelist] || []);
const grouped = computed(() => typeof CODELISTS[props.column.codelist] !== "string");
const scheme = computed(() => codelistScheme(props.column.codelist));
const unknown = computed(
  () => !!props.value && !findCodelistOption(codelistOptions(props.column.codelist, props.codelists), props.value)
);
// Shown in the UI language; the <option> value is the notation, which is what
// the cell stores.
const optionText = (opt, group) => {
  const name = codelistText(group?.scheme || scheme.value, opt, activeLocale());
  return name === opt.code ? name : `${name} (${opt.code})`;
};
</script>

<template>
  <option v-if="unknown" :value="value">{{ value }} {{ translate("sheet.notInCodelist") }}</option>
  <template v-if="grouped">
    <optgroup v-for="group in list" :key="group.label" :label="translate(group.label)">
      <option v-for="opt in group.options" :key="`${opt.id}|${opt.code}`" :value="opt.code">{{ optionText(opt, group) }}</option>
    </optgroup>
  </template>
  <template v-else>
    <option v-for="opt in list" :key="`${opt.id}|${opt.code}`" :value="opt.code">{{ optionText(opt) }}</option>
  </template>
</template>
