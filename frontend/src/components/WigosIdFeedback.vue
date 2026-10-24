<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { WIGOS_ID_PATTERN } from "../wmdr";

// Format, duplicate and availability feedback shown under a WigosIdInput.
// `status` comes from useWigosIdAvailability.
const props = defineProps({
  id: { type: String, default: "" },
  status: { type: String, default: null },
  duplicate: Boolean,
});

const { t } = useI18n();

const MESSAGES = {
  checking: { key: "wigos.checking", color: "text-medium-emphasis" },
  available: { key: "wigos.available", color: "text-success" },
  taken: { key: "wigos.taken", color: "text-error" },
  error: { key: "wigos.checkFailed", color: "text-medium-emphasis" },
};

const message = computed(() => {
  if (props.id && !WIGOS_ID_PATTERN.test(props.id)) {
    return { text: t("wigos.invalidFormat"), color: "text-error" };
  }
  if (props.duplicate) return { text: t("wigos.duplicate"), color: "text-error" };
  const known = MESSAGES[props.status];
  return known ? { text: t(known.key), color: known.color } : null;
});
</script>

<template>
  <div v-if="message" :class="['field-message', message.color]">{{ message.text }}</div>
</template>
