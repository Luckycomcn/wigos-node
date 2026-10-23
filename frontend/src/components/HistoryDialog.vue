<script setup>
import { ref, watch } from "vue";
import { getStationHistory, getStationVersion, getStationHistoryDiff } from "../api";

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  stationId: { type: Number, default: null },
});
const emit = defineEmits(["update:modelValue"]);

const history = ref([]);
const state = ref({ status: "idle" });
const selected = ref(null);
const diff = ref(null);
const diffError = ref("");

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
  diff.value = null;
  try {
    selected.value = await getStationVersion(props.stationId, version);
  } catch (err) {
    state.value = { status: "error", error: err.message };
  }
}

/**
 * F-8 变更对比。点某一行的 Diff 时对比「上一版 → 这一版」；
 * 第一版没有可比的旧版，就退到「第一版 → 第二版」。
 */
async function showDiff(row) {
  selected.value = null;
  diffError.value = "";
  const index = history.value.findIndex((item) => item.version === row.version);
  const older = history.value[index + 1]; // history 按 version 倒序，下标 +1 就是更早一版
  const from = older ? older.version : history.value[history.value.length - 1]?.version;
  try {
    diff.value = await getStationHistoryDiff(props.stationId, from, row.version);
  } catch (err) {
    diff.value = null;
    diffError.value = err.message;
  }
}

function preview(value) {
  if (typeof value === "string") return JSON.stringify(value);
  return JSON.stringify(value, null, 2);
}

watch(() => props.modelValue, (open) => {
  if (open) {
    selected.value = null;
    diff.value = null;
    diffError.value = "";
    load();
  }
});
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="860" @update:model-value="emit('update:modelValue', $event)">
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
              <v-btn size="small" variant="tonal" class="mr-1" @click="showVersion(row.version)">View</v-btn>
              <v-btn size="small" variant="tonal" :disabled="history.length < 2" @click="showDiff(row)">Diff</v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>

      <template v-if="selected">
        <h4 class="text-subtitle-1 mt-4">v{{ selected.version }} snapshot</h4>
        <pre class="snapshot">{{ JSON.stringify(selected.wmdrv2, null, 2) }}</pre>
      </template>

      <template v-if="diff">
        <div class="d-flex align-center justify-space-between mt-4">
          <h4 class="text-subtitle-1">
            Changes v{{ diff.from }} → v{{ diff.to }}
          </h4>
          <span class="text-caption text-medium-emphasis">
            +{{ diff.summary.added }} added · {{ diff.summary.changed }} changed · −{{ diff.summary.removed }} removed
            · {{ diff.summary.unchanged }} unchanged
          </span>
        </div>

        <v-alert v-if="!diff.summary.added && !diff.summary.changed && !diff.summary.removed" type="info" variant="tonal" class="mt-2">
          No field-level differences between these two versions.
        </v-alert>

        <div v-else class="diff-list mt-2">
          <div v-for="item in diff.added" :key="`a-${item.path}`" class="diff-row diff-added">
            <code class="diff-path">+ {{ item.path }}</code>
            <pre class="diff-value">{{ preview(item.value) }}</pre>
          </div>
          <div v-for="item in diff.changed" :key="`c-${item.path}`" class="diff-row diff-changed">
            <code class="diff-path">~ {{ item.path }}</code>
            <pre class="diff-value">{{ preview(item.from) }} → {{ preview(item.to) }}</pre>
          </div>
          <div v-for="item in diff.removed" :key="`r-${item.path}`" class="diff-row diff-removed">
            <code class="diff-path">− {{ item.path }}</code>
            <pre class="diff-value">{{ preview(item.value) }}</pre>
          </div>
        </div>
      </template>
      <v-alert v-if="diffError" type="error" variant="tonal" class="mt-4">{{ diffError }}</v-alert>
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

.diff-list {
  max-height: 420px;
  overflow: auto;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
}

.diff-row {
  padding: 0.35rem 0.75rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.diff-row:last-child {
  border-bottom: none;
}

.diff-path {
  font-size: 0.8rem;
  font-weight: 600;
}

.diff-value {
  margin: 0.15rem 0 0;
  font-size: 0.78rem;
  white-space: pre-wrap;
  word-break: break-all;
}

.diff-added { background: rgba(76, 175, 80, 0.10); }
.diff-added .diff-path { color: #2e7d32; }

.diff-removed { background: rgba(244, 67, 54, 0.10); }
.diff-removed .diff-path { color: #c62828; }

.diff-changed { background: rgba(255, 152, 0, 0.10); }
.diff-changed .diff-path { color: #ef6c00; }
</style>
