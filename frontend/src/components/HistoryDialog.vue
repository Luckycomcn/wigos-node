<script setup>
import { ref, watch } from "vue";
import { getStationHistory, getStationVersion } from "../api";

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  stationId: { type: Number, default: null },
});
const emit = defineEmits(["update:modelValue"]);

const history = ref([]);
const state = ref({ status: "idle" });
const selected = ref(null);

async function load() {
  if (!props.stationId) return;
  state.value = { status: "loading" };
  try {
    history.value = await getStationHistory(props.stationId);
    state.value = { status: "success" };
  } catch (err) {
    state.value = { status: "error", error: err.message };
  }
}

async function showVersion(version) {
  try {
    selected.value = await getStationVersion(props.stationId, version);
  } catch (err) {
    state.value = { status: "error", error: err.message };
  }
}

watch(() => props.modelValue, (open) => {
  if (open) {
    selected.value = null;
    load();
  }
});
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="820" @update:model-value="emit('update:modelValue', $event)">
    <v-card class="pa-4">
      <div class="d-flex align-center justify-space-between mb-3">
        <h3 class="text-h6">Version history</h3>
        <v-btn variant="text" @click="emit('update:modelValue', false)">Close</v-btn>
      </div>

      <p v-if="state.status === 'loading'">Loading…</p>
      <v-alert v-if="state.status === 'error'" type="error" variant="tonal">{{ state.error }}</v-alert>
      <p v-if="state.status === 'success' && history.length === 0">No versions recorded yet.</p>

      <v-table v-if="history.length" density="compact">
        <thead>
          <tr><th>Version</th><th>Operation</th><th>When</th><th>By</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="row in history" :key="row.version">
            <td>v{{ row.version }}</td>
            <td>{{ row.operation }}</td>
            <td>{{ new Date(row.created).toLocaleString() }}</td>
            <td>{{ row.created_by || "—" }}</td>
            <td class="text-right">
              <v-btn size="small" variant="tonal" @click="showVersion(row.version)">View</v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>

      <template v-if="selected">
        <h4 class="text-subtitle-1 mt-4">v{{ selected.version }} snapshot</h4>
        <pre class="snapshot">{{ JSON.stringify(selected.wmdrv2, null, 2) }}</pre>
      </template>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.snapshot {
  max-height: 360px;
  overflow: auto;
  background: #0f172a;
  color: #e2e8f0;
  padding: 1rem;
  border-radius: 8px;
  font-size: 0.78rem;
}
</style>
