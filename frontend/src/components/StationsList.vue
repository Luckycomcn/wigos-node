<script setup>
import { computed, onUnmounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { listLatestPublications, listMyStations } from "../api";
import PublicationStatusChip from "./PublicationStatusChip.vue";
import StationsMap from "./StationsMap.vue";
import SelectionBar from "./SelectionBar.vue";

// `selected` (a Set of station IDs) is kept by the parent so it survives a
// trip to the batch wizard and back.
const selected = defineModel("selected", { type: Set, required: true });
const emit = defineEmits(["new", "edit", "batch", "changed"]);

const { t } = useI18n();

const headers = computed(() => [
  { title: t("list.columnWsi"), key: "wsi" },
  { title: t("list.columnName"), key: "name" },
  { title: t("list.columnPublishing"), key: "publishing", sortable: false },
  { title: "", key: "actions", sortable: false, align: "end" },
]);

const stations = ref([]);
const loadState = ref({ status: "loading" });

listMyStations()
  .then((data) => {
    stations.value = data;
    loadState.value = { status: "success" };
  })
  .catch((err) => {
    loadState.value = { status: "error", error: err.message };
  });

// Each station's latest publishing status, refreshed while one is on its way.
// A station without one has no chip: no changes yet, or not one the user may see.
const REFRESH_MS = 5000;
const latest = ref({});
let timer = null;
let left = false;

async function loadLatest() {
  try {
    const data = await listLatestPublications();
    if (left) return;
    latest.value = data;
    emit("changed");
  } catch {
    return; // the list works without the chips
  }
  if (Object.values(latest.value).some(({ status }) => status === "pending" || status === "processing")) {
    timer = setTimeout(loadLatest, REFRESH_MS);
  }
}
loadLatest();

onUnmounted(() => {
  left = true;
  clearTimeout(timer);
});

const editableIds = computed(() => stations.value.filter((station) => station.can_edit).map((station) => station.station_id));
// Only stations still listed and editable count as selected.
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
      <v-btn color="primary" prepend-icon="mdi-plus" @click="emit('new')">{{ t("list.newStation") }}</v-btn>
    </div>

    <p v-if="loadState.status === 'loading'">{{ t("list.loading") }}</p>
    <v-alert v-if="loadState.status === 'error'" type="error" variant="tonal">{{ t("common.error", { message: loadState.error }) }}</v-alert>
    <p v-if="loadState.status === 'success' && stations.length === 0">{{ t("list.empty") }}</p>

    <template v-if="stations.length > 0">
      <StationsMap :stations="stations" />
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
            :disabled="!item.can_edit"
            :aria-label="t('list.selectAria', { name: item.name || item.wsi })"
            :title="item.can_edit ? undefined : t('list.noPermission')"
            @update:model-value="toggleSelect(internalItem)"
          />
        </template>
        <template #[`item.publishing`]="{ item }">
          <PublicationStatusChip v-if="latest[item.station_id]" :status="latest[item.station_id].status" />
        </template>
        <template #[`item.actions`]="{ item }">
          <v-btn variant="tonal" color="secondary" size="small" @click="emit('edit', item.station_id)">{{ t("list.edit") }}</v-btn>
        </template>
      </v-data-table>
    </template>
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
