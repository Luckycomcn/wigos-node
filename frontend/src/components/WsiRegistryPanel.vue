<script setup>
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import {
  createWsiAllocation,
  deleteWsiAllocation,
  exportWsiAllocations,
  importWsiAllocations,
  listAuditLog,
  listWsiAllocations,
  updateWsiAllocation,
} from "../api";

const { t } = useI18n();

const open = defineModel({ type: Boolean, default: false });
const emit = defineEmits(["changed"]);

const tab = ref("allocations");
const busy = ref(false);
const message = ref(null);
const rows = ref([]);
const auditRows = ref([]);
const isStaff = ref(false);

const form = ref(blank());
const editingId = ref(null);
const dialog = ref(false);

const importText = ref("");
const importFormat = ref("json");
const importDryRun = ref(true);
const importResult = ref(null);

function blank() {
  return { issuer: "", series: 0, numberFrom: "", numberTo: "", note: "" };
}

function notify(type, text) {
  message.value = { type, text };
}

async function load() {
  busy.value = true;
  message.value = null;
  try {
    rows.value = await listWsiAllocations();
    try {
      auditRows.value = await listAuditLog({ limit: 100 });
      isStaff.value = true;
    } catch {
      // 非 staff 读审计表会 403：面板降级为「只有授权区间」。
      isStaff.value = false;
    }
  } catch (err) {
    notify("error", err.message);
  } finally {
    busy.value = false;
  }
}

function startCreate() {
  form.value = blank();
  editingId.value = null;
  dialog.value = true;
}

function startEdit(row) {
  form.value = { issuer: row.issuer, series: row.series, numberFrom: row.numberFrom, numberTo: row.numberTo, note: row.note };
  editingId.value = row.id;
  dialog.value = true;
}

async function save() {
  const payload = {
    issuer: Number(form.value.issuer),
    series: Number(form.value.series || 0),
    numberFrom: Number(form.value.numberFrom),
    numberTo: Number(form.value.numberTo),
    note: form.value.note || "",
  };
  if (!Number.isInteger(payload.issuer) || payload.issuer < 0) {
    notify("error", t("registry.errorIssuer"));
    return;
  }
  if (!Number.isInteger(payload.numberFrom) || !Number.isInteger(payload.numberTo)) {
    notify("error", t("registry.errorNumber"));
    return;
  }
  busy.value = true;
  try {
    if (editingId.value == null) {
      await createWsiAllocation(payload);
      notify("success", t("registry.created"));
    } else {
      await updateWsiAllocation(editingId.value, payload);
      notify("success", t("registry.updated"));
    }
    dialog.value = false;
    await load();
    emit("changed");
  } catch (err) {
    notify("error", err.message);
  } finally {
    busy.value = false;
  }
}

async function remove(row) {
  const question = t("registry.confirmDelete", {
    issuer: row.issuer,
    from: row.numberFrom,
    to: row.numberTo,
  });
  if (!window.confirm(question)) return;
  busy.value = true;
  try {
    await deleteWsiAllocation(row.id);
    notify("success", t("registry.deleted"));
    await load();
    emit("changed");
  } catch (err) {
    notify("error", err.message);
  } finally {
    busy.value = false;
  }
}

async function download(format) {
  busy.value = true;
  try {
    const blob = await exportWsiAllocations(format);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `wsi-allocations.${format}`;
    link.click();
    URL.revokeObjectURL(url);
    notify("success", t("registry.exported", { format }));
  } catch (err) {
    notify("error", err.message);
  } finally {
    busy.value = false;
  }
}

async function runImport() {
  if (!importText.value.trim()) {
    notify("error", t("registry.pasteRequired"));
    return;
  }
  busy.value = true;
  importResult.value = null;
  try {
    importResult.value = await importWsiAllocations({
      format: importFormat.value,
      data: importText.value,
      dry_run: importDryRun.value,
    });
    const accepted = importResult.value.accepted ?? 0;
    const rejected = importResult.value.rejected ?? 0;
    notify(rejected ? "warning" : "success",
      t(importDryRun.value ? "registry.importDoneDry" : "registry.importDone", { accepted, rejected }));
    if (!importDryRun.value) {
      await load();
      emit("changed");
    }
  } catch (err) {
    notify("error", err.message);
  } finally {
    busy.value = false;
  }
}

// 后端列表接口带主键 id（PATCH/DELETE 要用）；导出接口不带，两者刻意不同。
const displayRows = computed(() => rows.value);

watch(open, (value) => {
  if (value) {
    tab.value = "allocations";
    importResult.value = null;
    load();
  }
});
</script>

<template>
  <v-dialog :model-value="open" max-width="900" @update:model-value="open = $event">
    <v-card class="pa-4">
      <div class="d-flex align-center justify-space-between mb-3">
        <div>
          <h3 class="text-h6">{{ t("registry.title") }}</h3>
          <div class="text-caption text-medium-emphasis">{{ t("registry.intro") }}</div>
        </div>
        <v-btn variant="text" @click="open = false">{{ t("common.close") }}</v-btn>
      </div>

      <v-alert v-if="message" :type="message.type" variant="tonal" class="mb-3" closable
        @click:close="message = null">{{ message.text }}</v-alert>

      <v-tabs v-model="tab" density="compact">
        <v-tab value="allocations">{{ t("registry.tabAllocations") }}</v-tab>
        <v-tab value="transfer">{{ t("registry.tabTransfer") }}</v-tab>
        <v-tab v-if="isStaff" value="audit">{{ t("registry.tabAudit") }}</v-tab>
      </v-tabs>

      <v-window v-model="tab" class="mt-3">
        <!-- ---------------- 授权区间 ---------------- -->
        <v-window-item value="allocations">
          <div class="d-flex ga-2 mb-3">
            <v-btn size="small" color="primary" variant="tonal" @click="startCreate">{{ t("registry.newRange") }}</v-btn>
            <v-btn size="small" variant="tonal" :disabled="busy" @click="load">{{ t("registry.refresh") }}</v-btn>
          </div>

          <p v-if="busy && !displayRows.length">{{ t("registry.loading") }}</p>
          <v-alert v-else-if="!displayRows.length" type="info" variant="tonal">
            {{ t("registry.empty") }}
          </v-alert>

          <v-table v-else density="compact">
            <thead>
              <tr>
                <th>{{ t("registry.colCentre") }}</th>
                <th>{{ t("registry.colSeries") }}</th>
                <th>{{ t("registry.colFrom") }}</th>
                <th>{{ t("registry.colTo") }}</th>
                <th>{{ t("registry.colNote") }}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in displayRows" :key="row.id">
                <td>{{ row.issuer }}</td>
                <td>{{ row.series }}</td>
                <td>{{ row.numberFrom }}</td>
                <td>{{ row.numberTo }}</td>
                <td class="text-medium-emphasis">{{ row.note || "—" }}</td>
                <td class="text-right">
                  <v-btn size="small" variant="text" @click="startEdit(row)">{{ t("registry.edit") }}</v-btn>
                  <v-btn size="small" variant="text" color="error" @click="remove(row)">{{ t("registry.delete") }}</v-btn>
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-window-item>

        <!-- ---------------- 导入 / 导出 ---------------- -->
        <v-window-item value="transfer">
          <div class="d-flex ga-2 mb-3">
            <v-btn size="small" variant="tonal" @click="download('json')">{{ t("registry.exportJson") }}</v-btn>
            <v-btn size="small" variant="tonal" @click="download('csv')">{{ t("registry.exportCsv") }}</v-btn>
          </div>
          <div class="text-caption text-medium-emphasis mb-2">{{ t("registry.transferHint") }}</div>

          <v-radio-group v-model="importFormat" inline density="compact" class="mb-2">
            <v-radio label="JSON" value="json" />
            <v-radio label="CSV" value="csv" />
          </v-radio-group>
          <v-textarea v-model="importText" rows="8" variant="outlined" density="compact"
            :placeholder="t('registry.pastePlaceholder')" />
          <div class="d-flex align-center ga-3 mt-2">
            <v-checkbox v-model="importDryRun" :label="t('registry.dryRunOnly')" density="compact" hide-details />
            <v-btn size="small" color="primary" variant="tonal" :disabled="busy" @click="runImport">{{ t("registry.importBtn") }}</v-btn>
          </div>

          <div v-if="importResult" class="mt-3">
            <v-alert :type="importResult.rejected ? 'warning' : 'success'" variant="tonal" class="mb-2">
              {{ t("registry.acceptedRejected", { accepted: importResult.accepted, rejected: importResult.rejected }) }}
            </v-alert>
            <pre class="result-box">{{ JSON.stringify(importResult.results, null, 2) }}</pre>
          </div>
        </v-window-item>

        <!-- ---------------- 审计 ---------------- -->
        <v-window-item value="audit">
          <div class="text-caption text-medium-emphasis mb-2">{{ t("registry.auditIntro") }}</div>
          <v-table v-if="auditRows.length" density="compact">
            <thead>
              <tr>
                <th>{{ t("registry.colTime") }}</th>
                <th>{{ t("registry.colAction") }}</th>
                <th>{{ t("registry.colActor") }}</th>
                <th>{{ t("registry.colStation") }}</th>
                <th>{{ t("registry.colDetail") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in auditRows" :key="row.id">
                <td class="text-no-wrap">{{ new Date(row.created).toLocaleString() }}</td>
                <td><code>{{ row.action }}</code></td>
                <td>{{ row.actor || t("registry.anonymous") }}</td>
                <td>{{ row.wsi || "—" }}</td>
                <td class="text-medium-emphasis result-cell">{{ JSON.stringify(row.detail) }}</td>
              </tr>
            </tbody>
          </v-table>
          <v-alert v-else type="info" variant="tonal">{{ t("registry.noAudit") }}</v-alert>
        </v-window-item>
      </v-window>

      <v-dialog v-model="dialog" max-width="520">
        <v-card class="pa-4">
          <h4 class="text-subtitle-1 mb-3">
            {{ editingId == null ? t("registry.newRangeTitle") : t("registry.editRangeTitle") }}
          </h4>
          <v-text-field v-model="form.issuer" :label="t('registry.labelIssuer')" density="compact" />
          <v-text-field v-model="form.series" :label="t('registry.labelSeries')" density="compact" type="number" />
          <v-text-field v-model="form.numberFrom" :label="t('registry.labelFrom')" density="compact" type="number" />
          <v-text-field v-model="form.numberTo" :label="t('registry.labelTo')" density="compact" type="number" />
          <v-text-field v-model="form.note" :label="t('registry.labelNote')" density="compact" />
          <div class="d-flex justify-end ga-2 mt-3">
            <v-btn variant="text" @click="dialog = false">{{ t("common.cancel") }}</v-btn>
            <v-btn color="primary" variant="tonal" :disabled="busy" @click="save">{{ t("registry.save") }}</v-btn>
          </div>
        </v-card>
      </v-dialog>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.result-box {
  max-height: 220px;
  overflow: auto;
  background: #0f172a;
  color: #e2e8f0;
  padding: 0.75rem;
  border-radius: 8px;
  font-size: 0.75rem;
}

.result-cell {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.75rem;
}
</style>
