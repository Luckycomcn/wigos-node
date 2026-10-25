<script setup>
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  archiveStation,
  deleteStation,
  exportStation,
  exportStations,
  listMyStations,
  publishStation,
  restoreStation,
  submitStation,
} from "../api";
import StationsMap from "./StationsMap.vue";
import SelectionBar from "./SelectionBar.vue";
import HistoryDialog from "./HistoryDialog.vue";
import ToolsPanel from "./ToolsPanel.vue";
import WsiRegistryPanel from "./WsiRegistryPanel.vue";
import UserAdminPanel from "./UserAdminPanel.vue";

// `selected` (a Set of station IDs) is kept by the parent so it survives a
// trip to the batch wizard and back.
const selected = defineModel("selected", { type: Set, required: true });
const emit = defineEmits(["new", "edit", "batch"]);

// Whether the signed-in user administers the node; the backend refuses these
// calls anyway, so this only decides whether the entry point is shown.
const props = defineProps({ isStaff: { type: Boolean, default: false } });

const { t } = useI18n();

const headers = computed(() => [
  { title: t("list.columnWsi"), key: "wsi" },
  { title: t("list.columnName"), key: "name" },
  { title: t("list.columnState"), key: "state", sortable: false },
  { title: "", key: "actions", sortable: false, align: "end" },
]);

const stations = ref([]);
const loadState = ref({ status: "loading" });
const busy = ref(false);
const message = ref(null);
const showArchived = ref(false);
const historyOpen = ref(false);
const historyStationId = ref(null);
const toolsOpen = ref(false);
const toolsTab = ref("import");
const registryOpen = ref(false);
const usersOpen = ref(false);

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

const onArchive = (station) =>
  run(() => archiveStation(station.station_id), () => t("list.msgArchived", { wsi: station.wsi }));
const onRestore = (station) =>
  run(() => restoreStation(station.station_id), () => t("list.msgRestored", { wsi: station.wsi }));
const onPublish = (station) =>
  run(() => publishStation(station.station_id), (r) => t("list.msgPublished", { wsi: station.wsi, url: r.url }));

// 方案 5.6：草稿必须先提交。服务端会在提交时跑 schema 与业务规则，
// 不通过就退回草稿态并把原因带回来。
const onSubmit = (station) =>
  run(() => submitStation(station.station_id), () => t("list.msgSubmitted", { wsi: station.wsi }));

async function onDelete(station) {
  if (!window.confirm(t("list.confirmDelete", { wsi: station.wsi }))) return;
  await run(() => deleteStation(station.station_id), () => t("list.msgDeleted", { wsi: station.wsi }));
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
    (result) =>
      t("list.msgExported", { count: ids.length || stations.value.length, filename: result.filename }),
  );
}

const onExportOne = (station, format) =>
  run(() => exportStation(station.station_id, format), (r) => t("list.msgExportedOne", { wsi: station.wsi, filename: r.filename }));

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
      <h3>{{ t("list.title") }}</h3>
      <div class="d-flex align-center ga-3">
        <v-switch
          v-model="showArchived"
          :label="t('list.showArchived')"
          density="compact"
          hide-details
          @update:model-value="load"
        />
        <v-menu>
          <template #activator="{ props: menuProps }">
            <v-btn v-bind="menuProps" variant="tonal" prepend-icon="mdi-download" :disabled="busy || stations.length === 0">
              {{ selectedIds.length ? t("list.exportSelected", { count: selectedIds.length }) : t("list.export") }}
            </v-btn>
          </template>
          <v-list density="compact">
            <v-list-item title="CSV" @click="onExport('csv')" />
            <v-list-item title="JSON" @click="onExport('json')" />
            <v-list-item title="XML" @click="onExport('xml')" />
          </v-list>
        </v-menu>
        <v-btn variant="tonal" prepend-icon="mdi-upload" @click="openTools('import')">{{ t("list.import") }}</v-btn>
        <v-btn variant="tonal" prepend-icon="mdi-tools" @click="openTools('templates')">{{ t("list.tools") }}</v-btn>
        <v-btn variant="tonal" prepend-icon="mdi-shield-key" @click="registryOpen = true">{{ t("list.wsiRegistry") }}</v-btn>
        <v-btn v-if="props.isStaff" variant="tonal" prepend-icon="mdi-account-cog" @click="usersOpen = true">{{ t("list.users") }}</v-btn>
        <v-btn color="primary" prepend-icon="mdi-plus" @click="emit('new')">{{ t("list.newStation") }}</v-btn>
      </div>
    </div>

    <v-alert v-if="message" :type="message.type" variant="tonal" closable class="mb-3" @click:close="message = null">
      {{ message.text }}
    </v-alert>

    <p v-if="loadState.status === 'loading'">{{ t("list.loading") }}</p>
    <v-alert v-if="loadState.status === 'error'" type="error" variant="tonal">{{ t("common.error", { message: loadState.error }) }}</v-alert>
    <p v-if="loadState.status === 'success' && stations.length === 0">{{ t("list.empty") }}</p>

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
        :headers="headers"
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
            :aria-label="t('list.selectAria', { name: item.name || item.wsi })"
            :title="item.can_edit ? undefined : t('list.noPermission')"
            @update:model-value="toggleSelect(internalItem)"
          />
        </template>
        <template #[`item.state`]="{ item }">
          <!-- 方案 5.6：三个独立状态，草稿优先 —— 它就是还需要用户动手的信号。 -->
          <v-chip v-if="item.status === 'draft'" size="small" color="warning" variant="flat">{{ t("list.statusDraft") }}</v-chip>
          <v-chip v-else-if="item.archived" size="small" color="warning" variant="tonal">{{ t("list.statusArchived") }}</v-chip>
          <v-chip v-else size="small" color="success" variant="tonal">{{ t("list.statusActive") }}</v-chip>
        </template>
        <template #[`item.actions`]="{ item }">
          <div class="d-flex ga-1 justify-end flex-wrap">
            <v-btn v-if="!item.archived" variant="tonal" color="secondary" size="small" @click="emit('edit', item.station_id)">{{ t("list.edit") }}</v-btn>
            <v-btn variant="text" size="small" @click="onHistory(item)">{{ t("list.history") }}</v-btn>
            <v-menu>
              <template #activator="{ props: menuProps }">
                <v-btn v-bind="menuProps" variant="text" size="small">{{ t("list.export") }}</v-btn>
              </template>
              <v-list density="compact">
                <v-list-item title="CSV" @click="onExportOne(item, 'csv')" />
                <v-list-item title="JSON" @click="onExportOne(item, 'json')" />
                <v-list-item title="XML" @click="onExportOne(item, 'xml')" />
              </v-list>
            </v-menu>
            <!-- 草稿只能先提交；让它看起来可点、点了才报错，是很难用的设计。 -->
            <v-btn
              v-if="item.status === 'draft' && !item.archived && item.can_edit"
              variant="tonal" color="warning" size="small" :disabled="busy"
              @click="onSubmit(item)"
            >{{ t("list.submit") }}</v-btn>
            <v-btn
              v-else-if="!item.archived && item.can_edit"
              variant="tonal" color="primary" size="small" :disabled="busy"
              @click="onPublish(item)"
            >{{ t("list.publish") }}</v-btn>
            <v-btn v-if="!item.archived && item.can_edit" variant="tonal" size="small" :disabled="busy" @click="onArchive(item)">{{ t("list.archive") }}</v-btn>
            <v-btn v-if="item.archived && item.can_edit" variant="tonal" size="small" :disabled="busy" @click="onRestore(item)">{{ t("list.restore") }}</v-btn>
            <v-btn v-if="item.can_edit" variant="text" color="error" size="small" :disabled="busy" @click="onDelete(item)">{{ t("list.delete") }}</v-btn>
          </div>
        </template>
      </v-data-table>
    </template>

    <HistoryDialog v-model="historyOpen" :station-id="historyStationId" />
    <ToolsPanel v-model="toolsOpen" :station-ids="selectedIds" :initial-tab="toolsTab" @imported="load" />
    <!-- 方案 5.3：WSI 授权范围 + NF-6 审计。面板内部自行降级，非 staff 只看得到分配表。 -->
    <WsiRegistryPanel v-model="registryOpen" />
    <UserAdminPanel v-model="usersOpen" />
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
