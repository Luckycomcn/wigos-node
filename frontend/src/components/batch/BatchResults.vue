<script setup>
import { translate } from "../../i18n/plain";
import { computed } from "vue";
import { resultsToCsv } from "../../batch/common";
import { csvBlob, downloadBlob } from "../../batch/sheetIO";

// `state`: { status: "running", count } | { status: "done", response } | { status: "error", error }.
const props = defineProps({ state: { type: Object, required: true } });
const emit = defineEmits(["retry", "retry-failed", "back"]);

const failed = computed(() =>
  props.state.status === "done" ? props.state.response.results.filter((result) => result.status !== "ok") : []
);

const download = () => downloadBlob(csvBlob(resultsToCsv(props.state.response.results)), "batch-results.csv");
</script>

<template>
  <v-alert v-if="state.status === 'running'" type="info" variant="tonal">
    {{ translate(state.count === 1 ? "batch.applyingOne" : "batch.applyingMany", { count: state.count }) }}
  </v-alert>

  <div v-else-if="state.status === 'error'">
    <v-alert type="error" variant="tonal">{{ translate("batch.sendFailed", { message: state.error }) }}</v-alert>
    <div class="batch-actions">
      <v-btn variant="outlined" @click="emit('back')">{{ translate("batch.backToStations") }}</v-btn>
      <v-btn color="primary" @click="emit('retry')">{{ translate("common.retry") }}</v-btn>
    </div>
  </div>

  <div v-else>
    <v-alert :type="failed.length ? 'error' : 'success'" variant="tonal" class="mb-3">
      {{ translate("batch.summary", { ok: state.response.summary.ok, failed: state.response.summary.error }) }}
    </v-alert>
    <v-table class="batch-results">
      <thead>
        <tr>
          <th>{{ translate("col.station") }}</th>
          <th>{{ translate("col.wigosId") }}</th>
          <th>{{ translate("batch.columnResult") }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="result in state.response.results" :key="result.index">
          <td>{{ result.station_name || translate("batch.stationNumber", { id: result.station_id }) }}</td>
          <td>{{ result.wsi }}</td>
          <td>
            <v-chip v-if="result.status === 'ok'" size="small" variant="tonal" color="success" prepend-icon="mdi-check">
              {{ translate("batch.resultSaved") }}
            </v-chip>
            <template v-else>
              <v-chip size="small" variant="tonal" color="error" prepend-icon="mdi-close">{{ translate("batch.resultFailed") }}</v-chip>
              {{ result.message }}
              <ul v-if="result.errors?.length > 0" class="error-list text-error">
                <li v-for="error in result.errors" :key="error">{{ error }}</li>
              </ul>
            </template>
          </td>
        </tr>
      </tbody>
    </v-table>
    <div class="batch-actions">
      <v-btn variant="outlined" @click="emit('back')">{{ translate("batch.backToStations") }}</v-btn>
      <v-btn variant="tonal" color="secondary" prepend-icon="mdi-download" @click="download">{{ translate("batch.downloadResults") }}</v-btn>
      <v-btn v-if="failed.length > 0" color="primary" @click="emit('retry-failed', failed.map((result) => result.station_id))">
        {{ translate("batch.retryFailed", { count: failed.length }) }}
      </v-btn>
    </div>
  </div>
</template>

<style scoped>
.batch-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1rem;
}

.batch-results td {
  padding-top: 0.4rem !important;
  padding-bottom: 0.4rem !important;
  vertical-align: top;
}

.error-list {
  margin: 0.4rem 0 0;
  padding-left: 1.2rem;
  font-size: 0.85rem;
}
</style>
