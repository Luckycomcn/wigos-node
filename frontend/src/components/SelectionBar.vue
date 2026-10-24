<script>
// Same limit as MAX_BATCH_UPDATES in backend/api/views.py.
export const MAX_BATCH_STATIONS = 500;
</script>

<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";

// Shown at the top of the station list while stations are selected.
const props = defineProps({
  count: { type: Number, required: true },
  editableCount: { type: Number, required: true },
});
const emit = defineEmits(["select-all", "clear", "batch"]);

const { t } = useI18n();
const tooMany = computed(() => props.count > MAX_BATCH_STATIONS);
// English is not the only language with a plural form: pick the message by
// count instead of gluing a suffix onto a noun.
const countLabel = computed(() =>
  props.count === 1 ? t("selection.countOne", { count: props.count }) : t("selection.countMany", { count: props.count })
);
</script>

<template>
  <v-sheet class="selection-bar" role="region" :aria-label="t('selection.region')">
    <span class="selection-count">{{ countLabel }}</span>
    <v-btn variant="text" color="secondary" :disabled="count === editableCount" @click="emit('select-all')">
      {{ t("selection.selectAll", { count: editableCount }) }}
    </v-btn>
    <v-btn variant="text" color="secondary" @click="emit('clear')">{{ t("selection.clear") }}</v-btn>
    <v-spacer />
    <span v-if="tooMany" class="text-error text-body-2">{{ t("selection.tooMany", { max: MAX_BATCH_STATIONS }) }}</span>
    <v-btn color="primary" :disabled="tooMany" @click="emit('batch')">{{ t("selection.batch") }}</v-btn>
  </v-sheet>
</template>

<style scoped>
@keyframes selection-bar-in {
  from {
    opacity: 0;
    transform: translateY(-0.5rem);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

.selection-bar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
  margin-bottom: 0.75rem;
  padding: 0.6rem 1rem;
  background: #dbeafe;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  animation: selection-bar-in 0.18s ease-out;
}

.selection-count {
  font-weight: 600;
  color: #1e3a8a;
}
</style>
