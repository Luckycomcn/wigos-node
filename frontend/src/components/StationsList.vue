<script setup>
import { computed, ref } from "vue";
import {
  archiveStation,
  deleteStation,
  exportStation,
  exportStations,
  listMyStations,
  publishStation,
  restoreStation,
} from "../api";
import StationsMap from "./StationsMap.vue";
import SelectionBar from "./SelectionBar.vue";
import HistoryDialog from "./HistoryDialog.vue";
import ToolsPanel from "./ToolsPanel.vue";

// `selected` (a Set of station IDs) is kept by the parent so it survives a
// trip to the batch wizard and back.
const selected = defineModel("selected", { type: Set, required: true });
const emit = defineEmits(["new", "edit", "batch"]);

const HEADERS = [
  { title: "WIGOS identifier", key: "wsi" },
  { title: "Name", key: "name" },
  { title: "State", key: "state", sortable: false },
  { title: "", key: "actions", sortable: false, align: "end" },
];

const stations = ref([]);
const loadState = ref({ status: "loading" });
const busy = ref(false);
const message = ref(null);
const showArchived = ref(false);
const historyOpen = ref(false);
const historyStationId = ref(null);
const toolsOpen = ref(false);
const toolsTab = ref("import");

async function load() {
  loadState.value = { status: "loading" };
  try {
    stations.value = await listMyStations(showArchived.value);
    loadState.value = { status: "success" };
  } catch (err) {
    loadState.value = { status: "error", error: err.message };
  }
}

async function run(action, successMessage) {
  busy.value = true;
  message.value = null;
  try {
    const result = await action();
    message.value = { type: "success", text: successMessage(result) };
    await load();
    return result;
  } catch (err) {
    message.value = { type: "error", text: err.message };
    return null;
  } finally {
    busy.value = false;
  }
}

const onArchive = (station) => run(() => archiveStation(station.station_id), () => `Archived ${station.wsi}.`);
const onRestore = (station) => run(() => restoreStation(station.station_id), () => `Restored ${station.wsi}.`);
const onPublish = (station) =>
  run(() => publishStation(station.station_id), (r) => `Published ${station.wsi} → ${r.url}`);

async function onDelete(station) {
  if (!window.confirm(`Permanently delete ${station.wsi}? This cannot be undone. Prefer Archive.`)) return;
  await run(() => deleteStation(station.station_id), () => `Deleted ${station.wsi}.`);
}

function onHistory(station) {
  historyStationId.value = station.station_id;
  historyOpen.value = true;
}

// F-16: export the ticked records, or everything currently listed.
function onExport(format) {
  const ids = selectedIds.value.length ? selectedIds.value : [];
  return run(
    () => exportStations(format, { stationIds: ids, includeArchived: showArchived.value }),
    (result) => `Exported ${ids.length || stations.value.length} record(s) → ${result.filename}`,
  );
}

const onExportOne = (station, format) =>
  run(() => exportStation(station.station_id, format), (r) => `Exported ${station.wsi} → ${r.filename}`);

function openTools(tabName) {
  toolsTab.value = tabName;
  toolsOpen.value = true;
}

load();

const editableIds = computed(() => stations.value.filter((s) => s.can_edit && !s.archived).map((s) => s.station_id));
const selectedIds = computed(() => editableIds.value.filter((id) => selected.value.has(id)));

const setSelected = (ids) => {
  selected.value = new Set(ids);
};
const rowProps = ({ item }) => ({ class: selectedIds.value.includes(item.station_id) ? "row-selected" : "" });
</script>

<template>
  <v-card class="pa-6">
    <div class="list-header">
      <h3>My stations</h3>
      <div class="d-flex align-center ga-3">
        <v-switch v-model="showArchived" label="Show archived" density="compact" hide-details @update:model-value="load" />
        <v-menu>
          <template #activator="{ props: menuProps }">
            <v-btn v-bind="menuProps" variant="tonal" prepend-icon="mdi-download" :disabled="busy || stations.length === 0">
              Export{{ selectedIds.length ? ` (${selectedIds.length})` : "" }}
            </v-btn>
          </template>
          <v-list density="compact">
            <v-list-item title="CSV" @click="onExport('csv')" />
            <v-list-item title="JSON" @click="onExport('json')" />
            <v-list-item title="XML" @click="onExport('xml')" />
          </v-list>
        </v-menu>
        <v-btn variant="tonal" prepend-icon="mdi-upload" @click="openTools('import')">Import</v-btn>
        <v-btn variant="tonal" prepend-icon="mdi-tools" @click="openTools('templates')">Tools</v-btn>
        <v-btn color="primary" prepend-icon="mdi-plus" @click="emit('new')">New station</v-btn>
      </div>
    </div>

    <v-alert v-if="message" :type="message.type" variant="tonal" closable class="mb-3" @click:close="message = null">
      {{ message.text }}
    </v-alert>

    <p v-if="loadState.status === 'loading'">Loading stations...</p>
    <v-alert v-if="loadState.status === 'error'" type="error" variant="tonal">Error: {{ loadState.error }}</v-alert>
    <p v-if="loadState.status === 'success' && stations.length === 0">No stations saved yet.</p>

    <template v-if="stations.length > 0">
      <StationsMap :stations="stations.filter((s) => !s.archived)" />
      <SelectionBar
        v-if="selectedIds.length > 0"
        :count="selectedIds.length"
        :editable-count="editableIds.length"
        @select-all="setSelected(editableIds)"
        @clear="setSelected([])"
        @batch="emit('batch', selectedIds)"
      />
      <v-data-table
        :headers="HEADERS"
        :items="stations"
        item-value="station_id"
        item-selectable="can_edit"
        show-select
        select-strategy="all"
        :model-value="selectedIds"
        :items-per-page="-1"
        hide-default-footer
        :row-props="rowProps"
        @update:model-value="setSelected"
      >
        <template #[`item.data-table-select`]="{ item, internalItem, isSelected, toggleSelect }">
          <v-checkbox-btn
            :model-value="isSelected(internalItem)"
            :disabled="!item.can_edit || item.archived"
            :aria-label="`Select ${item.name || item.wsi}`"
            :title="item.can_edit ? undefined : `You don't have permission to edit this station`"
            @update:model-value="toggleSelect(internalItem)"
          />
        </template>
        <template #[`item.state`]="{ item }">
          <v-chip v-if="item.archived" size="small" color="warning" variant="tonal">Archived</v-chip>
          <v-chip v-else size="small" color="success" variant="tonal">Active</v-chip>
        </template>
        <template #[`item.actions`]="{ item }">
          <div class="d-flex ga-1 justify-end flex-wrap">
            <v-btn v-if="!item.archived" variant="tonal" color="secondary" size="small" @click="emit('edit', item.station_id)">Edit</v-btn>
            <v-btn variant="text" size="small" @click="onHistory(item)">History</v-btn>
            <v-menu>
              <template #activator="{ props: menuProps }">
                <v-btn v-bind="menuProps" variant="text" size="small">Export</v-btn>
              </template>
              <v-list density="compact">
                <v-list-item title="CSV" @click="onExportOne(item, 'csv')" />
                <v-list-item title="JSON" @click="onExportOne(item, 'json')" />
                <v-list-item title="XML" @click="onExportOne(item, 'xml')" />
              </v-list>
            </v-menu>
            <v-btn v-if="!item.archived && item.can_edit" variant="tonal" color="primary" size="small" :disabled="busy" @click="onPublish(item)">Publish</v-btn>
            <v-btn v-if="!item.archived && item.can_edit" variant="tonal" size="small" :disabled="busy" @click="onArchive(item)">Archive</v-btn>
            <v-btn v-if="item.archived && item.can_edit" variant="tonal" size="small" :disabled="busy" @click="onRestore(item)">Restore</v-btn>
            <v-btn v-if="item.can_edit" variant="text" color="error" size="small" :disabled="busy" @click="onDelete(item)">Delete</v-btn>
          </div>
        </template>
      </v-data-table>
    </template>

    <HistoryDialog v-model="historyOpen" :station-id="historyStationId" />
    <ToolsPanel v-model="toolsOpen" :station-ids="selectedIds" :initial-tab="toolsTab" @imported="load" />
  </v-card>
</template>

<style scoped>
.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
  border-bottom: 1px solid #dbeafe;
  padding-bottom: 0.5rem;
}

.list-header h3 {
  margin: 0;
  font-size: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #2563eb;
}

:deep(.row-selected) td {
  background: #eff6ff;
}
</style>
