<script setup>
import { useI18n } from "vue-i18n";
import { useFieldText } from "../i18n/keys";

// A list of strings that always keeps at least one (possibly empty) entry.
defineProps({
  label: { type: String, required: true },
  placeholder: String,
  required: Boolean,
});
const values = defineModel({ type: Array, required: true });

const { t } = useI18n();
const text = useFieldText();

const update = (index, value) => {
  values.value = values.value.map((v, i) => (i === index ? value : v));
};
const add = () => {
  values.value = [...values.value, ""];
};
const remove = (index) => {
  const next = values.value.filter((_, i) => i !== index);
  values.value = next.length ? next : [""];
};
</script>

<template>
  <div class="mb-4">
    <div class="group-label">
      {{ text(label) }}<span v-if="required" class="required-mark">*</span>
    </div>
    <div v-for="(value, i) in values" :key="i" class="input-row mb-2">
      <v-text-field
        :model-value="value"
        :placeholder="text(placeholder)"
        :aria-label="`${text(label)} ${i + 1}`"
        @update:model-value="(next) => update(i, next)"
      />
      <v-btn variant="outlined" :disabled="values.length <= 1" @click="remove(i)">{{ t("common.remove") }}</v-btn>
    </div>
    <v-btn variant="tonal" color="secondary" size="small" prepend-icon="mdi-plus" @click="add">{{ t("common.add") }}</v-btn>
  </div>
</template>
