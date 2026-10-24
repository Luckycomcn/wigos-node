<script setup>
import { translate } from "../../i18n/plain";
import { backendMessage } from "../../i18n/backendMessages";
import { computed } from "vue";

// Lists the changes per station with the frontend schema check and the
// backend dry run. `changes`: [{ stationId, name, wsi, diff, schemaErrors }];
// `dryRun`: { status: "running" | "done" | "error", byStation, error }.
const props = defineProps({
  changes: { type: Array, required: true },
  unchangedCount: { type: Number, required: true },
  dryRun: { type: Object, required: true },
});
const emit = defineEmits(["confirm", "back"]);

// The dry run reports its rejections in English prose from the API (D9).
const failureText = (stationId) => {
  const message = props.dryRun.byStation?.[stationId]?.message;
  return backendMessage(message) ?? message;
};

const show = (value) => (value === undefined ? "—" : JSON.stringify(value));
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

const schemaFailures = computed(() => props.changes.filter((change) => change.schemaErrors.length).length);
const dryRunFailures = computed(() =>
  props.dryRun.status === "done"
    ? props.changes.filter((change) => props.dryRun.byStation[change.stationId]?.status !== "ok").length
    : 0
);
const canConfirm = computed(
  () => props.changes.length > 0 && !schemaFailures.value && props.dryRun.status === "done" && !dryRunFailures.value
);
const failureSummary = computed(() =>
  [
    schemaFailures.value && translate("preview.failingSchema", { count: schemaFailures.value }),
    dryRunFailures.value && translate("preview.rejectedByServer", { count: dryRunFailures.value }),
  ]
    .filter(Boolean)
    .join(translate("common.listSeparator"))
);
</script>

<template>
  <v-dialog :model-value="true" max-width="960" scrollable @update:model-value="(open) => !open && emit('back')">
    <v-card>
      <v-card-title class="d-flex align-center">
        <span>{{ translate("preview.title") }}</span>
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" :aria-label="translate('common.close')" @click="emit('back')" />
      </v-card-title>
      <v-divider />
      <v-card-text>
        <p class="batch-intro">
          {{ translate(changes.length === 1 ? "preview.willChangeOne" : "preview.willChangeMany", { count: changes.length }) }}<template v-if="unchangedCount > 0"
            >{{ translate(unchangedCount === 1 ? "preview.unchangedOne" : "preview.unchangedMany", { count: unchangedCount }) }}</template
          >
        </p>

        <v-alert v-if="dryRun.status === 'running'" class="mb-3" type="info" variant="tonal" density="compact">
          {{ translate("preview.checking") }}
        </v-alert>
        <v-alert v-if="dryRun.status === 'error'" class="mb-3" type="error" variant="tonal" density="compact">
          {{ translate("preview.checkFailed", { message: dryRun.error }) }}
        </v-alert>
        <v-alert v-if="failureSummary" class="mb-3" type="error" variant="tonal" density="compact">
          {{ translate("preview.fixMarked", { summary: failureSummary }) }}
        </v-alert>

        <div class="preview-list">
          <div v-for="change in changes" :key="change.stationId" class="preview-station">
            <div class="preview-station-header">
              <span>
                <strong>{{ change.name || translate("batch.stationNumber", { id: change.stationId }) }}</strong>
                <span class="preview-wsi">{{ change.wsi }}</span>
              </span>
              <span class="preview-badges">
                <v-chip
                  size="small"
                  variant="tonal"
                  :color="change.schemaErrors.length ? 'error' : 'success'"
                  :prepend-icon="change.schemaErrors.length ? 'mdi-close' : 'mdi-check'"
                >
                  {{ translate("preview.badgeSchema") }}
                </v-chip>
                <v-chip v-if="dryRun.status === 'running'" size="small" variant="tonal">{{ translate("preview.badgeServerPending") }}</v-chip>
                <v-chip
                  v-if="dryRun.byStation?.[change.stationId]"
                  size="small"
                  variant="tonal"
                  :color="dryRun.byStation[change.stationId].status === 'ok' ? 'success' : 'error'"
                  :prepend-icon="dryRun.byStation[change.stationId].status === 'ok' ? 'mdi-check' : 'mdi-close'"
                >
                  {{ translate("preview.badgeServer") }}
                </v-chip>
              </span>
            </div>
            <table class="preview-diff">
              <tbody>
                <tr v-for="entry in change.diff" :key="entry.path">
                  <td class="preview-path">{{ entry.path }}</td>
                  <td class="preview-before">{{ show(entry.before) }}</td>
                  <td class="preview-arrow">→</td>
                  <td class="preview-after">{{ show(entry.after) }}</td>
                </tr>
              </tbody>
            </table>
            <ul v-if="change.schemaErrors.length > 0" class="error-list text-error">
              <li v-for="error in change.schemaErrors" :key="error">{{ error }}</li>
            </ul>
            <div
              v-if="dryRun.byStation?.[change.stationId] && dryRun.byStation[change.stationId].status !== 'ok'"
              class="text-error mt-2"
            >
              {{ failureText(change.stationId) }}
              <ul v-if="dryRun.byStation[change.stationId].errors?.length > 0" class="error-list">
                <li v-for="error in dryRun.byStation[change.stationId].errors" :key="error">{{ error }}</li>
              </ul>
            </div>
          </div>
        </div>
      </v-card-text>
      <v-divider />
      <v-card-actions class="justify-end">
        <v-btn variant="outlined" @click="emit('back')">{{ translate("preview.backToEditing") }}</v-btn>
        <v-btn color="primary" variant="flat" :disabled="!canConfirm" @click="emit('confirm')">
          {{ translate(changes.length === 1 ? "preview.confirmOne" : "preview.confirmMany", { count: changes.length }) }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.batch-intro {
  margin: 0 0 1rem;
  color: #475569;
  font-size: 0.9rem;
}

.preview-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.preview-station {
  padding: 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.preview-station-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
}

.preview-wsi {
  margin-left: 0.4rem;
  color: #64748b;
  font-size: 0.85rem;
}

.preview-badges {
  display: flex;
  gap: 0.35rem;
  flex-shrink: 0;
}

.preview-diff {
  width: 100%;
  border-collapse: collapse;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 0.75rem;
}

.preview-diff td {
  padding: 0.2rem 0.4rem;
  vertical-align: top;
  word-break: break-word;
  border-top: 1px solid #e2e8f0;
}

.preview-path {
  width: 35%;
  color: #475569;
}

.preview-before {
  color: #dc2626;
  text-decoration: line-through;
}

.preview-arrow {
  width: 1rem;
  color: #64748b;
}

.preview-after {
  color: #059669;
}

.error-list {
  margin: 0.4rem 0 0;
  padding-left: 1.2rem;
  font-size: 0.85rem;
}
</style>
