<script setup>
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useFieldText } from "../i18n/keys";

// An ISO 8601 duration (e.g. PT10M) edited as a number and a unit, with a few
// one-click values. A stored value that isn't one number and one unit (e.g.
// P1DT6H) is kept until another is entered.
defineProps({ label: { type: String, required: true } });
const duration = defineModel({ type: String, default: "" });

const { t } = useI18n();
const text = useFieldText();

// `time` units go after the "T" (PT10M is 10 minutes, P1M is 1 month).
const UNITS = [
  { value: "S", time: true, title: "duration.unitSeconds" },
  { value: "M", time: true, title: "duration.unitMinutes" },
  { value: "H", time: true, title: "duration.unitHours" },
  { value: "D", time: false, title: "duration.unitDays" },
  { value: "W", time: false, title: "duration.unitWeeks" },
  { value: "MO", time: false, title: "duration.unitMonths" },
  { value: "Y", time: false, title: "duration.unitYears" },
];
const PRESETS = [
  { value: "PT30M", title: "30m", tooltip: "duration.preset30m" },
  { value: "PT1H", title: "1H", tooltip: "duration.preset1h" },
  { value: "PT3H", title: "3H", tooltip: "duration.preset3h" },
  { value: "PT6H", title: "6H", tooltip: "duration.preset6h" },
  { value: "PT12H", title: "12H", tooltip: "duration.preset12h" },
  { value: "P1D", title: "1D", tooltip: "duration.preset1d" },
  { value: "P1M", title: "1M", tooltip: "duration.preset1m" },
];

const toDuration = (amount, unit) =>
  unit.time ? `PT${amount}${unit.value}` : `P${amount}${unit.value === "MO" ? "M" : unit.value}`;

function fromDuration(value) {
  const match = /^P(T)?(\d+(?:\.\d+)?)([YMWDHS])$/.exec(value || "");
  if (!match) return null;
  const [, time, amount, letter] = match;
  const unit = UNITS.find((u) => u.time === Boolean(time) && (u.value === letter || (letter === "M" && !time && u.value === "MO")));
  return unit && (unit.value === "S" || !amount.includes(".")) ? { amount, unit: unit.value } : null;
}

const amount = ref("");
const unit = ref(null);
watch(
  duration,
  (value) => {
    const parsed = fromDuration(value);
    if (parsed) [amount.value, unit.value] = [parsed.amount, parsed.unit];
    else if (value) amount.value = "";
  },
  { immediate: true }
);

const amountError = computed(() => {
  const text = String(amount.value ?? "").trim();
  if (!text) return null;
  const pattern = unit.value === "S" ? /^\d+(\.\d+)?$/ : /^\d+$/;
  if (!pattern.test(text)) return unit.value === "S" ? t("duration.enterNumber") : t("duration.enterWholeNumber");
  return Number(text) > 0 ? null : t("duration.enterPositive");
});
const unitError = computed(() => (String(amount.value ?? "").trim() && !unit.value ? t("duration.chooseUnit") : null));
const isCustom = computed(() => !!duration.value && !fromDuration(duration.value));

// Writes the duration once both parts are valid; clearing the number clears it.
function update() {
  const text = String(amount.value ?? "").trim();
  if (!text) duration.value = "";
  else if (unit.value && !amountError.value) duration.value = toDuration(text, UNITS.find((u) => u.value === unit.value));
}
</script>

<template>
  <div class="mb-3">
    <div class="group-label">{{ text(label) }}</div>
    <div class="duration-inputs">
      <v-text-field
        class="duration-amount"
        :label="t('duration.every')"
        type="number"
        min="0"
        :model-value="amount"
        :error-messages="amountError || []"
        @update:model-value="(value) => ((amount = value ?? ''), update())"
      />
      <v-select
        class="duration-unit"
        :label="t('duration.unit')"
        :items="UNITS"
        :model-value="unit"
        :error-messages="unitError || []"
        @update:model-value="(value) => ((unit = value), update())"
      >
        <template #item="{ item, props: itemProps }">
          <v-list-item v-bind="itemProps" :title="t(item.raw.title)" />
        </template>
        <template #selection="{ item }">{{ t(item.raw.title) }}</template>
      </v-select>
      <div class="duration-presets">
        <v-chip
          v-for="preset in PRESETS"
          :key="preset.value"
          size="x-small"
          :color="duration === preset.value ? 'primary' : undefined"
          :variant="duration === preset.value ? 'flat' : 'outlined'"
          :title="t(preset.tooltip)"
          @click="duration = preset.value"
        >
          {{ preset.title }}
        </v-chip>
      </div>
    </div>
    <div v-if="isCustom" class="duration-note">{{ t("duration.stored", { duration }) }}</div>
  </div>
</template>

<style scoped>
.duration-inputs {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.duration-amount {
  flex: 0 0 110px;
}

.duration-unit {
  flex: 0 0 140px;
}

.duration-presets {
  display: flex;
  gap: 0.25rem;
  padding-top: 0.55rem;
}

.duration-note {
  font-size: 0.85rem;
  color: #475569;
}
</style>
