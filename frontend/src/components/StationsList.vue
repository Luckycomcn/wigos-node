<script setup>
import { computed, ref, watch } from "vue";
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
const total = ref(0);
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

// BUG-18：原来只有两列、没有搜索、一次拉全量（items-per-page="-1"）。
// 台站上百条时运维只能靠浏览器 Ctrl+F。这里改成服务端搜索 + 服务端分页。
const search = ref("");
const statusFilter = ref("all");
const page = ref(1);
const pageSize = ref(25);

const PAGE_SIZES = [25, 50, 100];

const statusOptions = computed(() => [
  { title: t("list.filterAll"), value: "all" },
  { title: t("list.statusActive"), value: "submitted" },
  { title: t("list.statusDraft"), value: "draft" },
]);

async function load() {
  loadState.value = { status: "loading" };
  try {
    const rows = await listMyStations(showArchived.value, {
      q: search.value.trim() || undefined,
      status: statusFilter.value === "all" ? undefined : statusFilter.value,
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    });
    stations.value = rows;
    total.value = rows.total ?? rows.length;
    loadState.value = { status: "success" };
  } catch (err) {
    loadState.value = { status: "error", error: err.message };
  }
}

// 搜索与筛选改了要回到第一页，否则会停在一个空页面上。
function reload(resetPage = true) {
  if (resetPage) page.value = 1;
  load();
}

let searchTimer = null;
watch(search, () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => reload(), 250);
});
watch([statusFilter, pageSize, showArchived], () => reload());
watch(page, () => load());

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
// 注意：导出是服务端的全量导出（后端按 include_archived 取，不受分页限制），
// 所以这里的 count 不能再用 stations.value.length —— 那只是当前页。
function onExport(format) {
  const ids = selectedIds.value.length ? selectedIds.value : [];
  return run(
    () => exportStations(format, { stationIds: ids, includeArchived: showArchived.value }),
    (result) => t("list.msgExported", { count: ids.length || total.value, filename: result.filename }),
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
        <v-text-field
          v-model="search"
          :label="t('list.searchPlaceholder')"
          prepend-inner-icon="mdi-magnify"
          density="compact"
          hide-details
          clearable
          single-line
          class="list-search"
        />
        <v-select
          v-model="statusFilter"
          :items="statusOptions"
          density="compact"
          hide-details
          class="list-status-filter"
        />
        <v-switch
          v-model="showArchived"
          :label="t('list.showArchived')"
          density="compact"
          hide-details
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
    <p v-if="loadState.status === 'success' && stations.length === 0">
      {{ search.trim() || statusFilter !== 'all' ? t("list.emptyFiltered") : t("list.empty") }}
    </p>

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

      <!-- 服务端分页：数据是按页取回来的，所以用后端返回的 total，
           不能用 Vuetify 自己的客户端分页（它只认得当前这 25 行）。 -->
      <div class="list-pager d-flex align-center ga-4 mt-3">
        <span class="text-body-2">
          {{ t("list.pageSummary", { from: total === 0 ? 0 : (page - 1) * pageSize + 1,
                                     to: Math.min(page * pageSize, total), total }) }}
        </span>
        <v-select
          v-model="pageSize"
          :items="PAGE_SIZES"
          density="compact"
          hide-details
          class="list-page-size"
          :label="t('list.pageSize')"
        />
        <v-spacer />
        <v-btn
          variant="text"
          icon="mdi-chevron-left"
          :disabled="page <= 1 || loadState.status === 'loading'"
          :aria-label="t('list.prevPage')"
          @click="page -= 1"
        />
        <v-btn
          variant="text"
          icon="mdi-chevron-right"
          :disabled="page * pageSize >= total || loadState.status === 'loading'"
          :aria-label="t('list.nextPage')"
          @click="page += 1"
        />
      </div>
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
  gap: 1rem;
  flex-wrap: wrap;
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

/* 工具栏在窄屏上会挤成一团：搜索框给一个下限宽度，其余控件按内容收缩。 */
.list-search {
  min-width: 14rem;
  max-width: 22rem;
}

.list-status-filter {
  max-width: 11rem;
}

.list-page-size {
  max-width: 7rem;
}

:deep(.row-selected) td {
  background: #eff6ff;
}
</style>
