<script setup>
import { ref, watch } from "vue";
import {
  createWsiAllocation,
  deleteWsiAllocation,
  exportWsiAllocations,
  importWsiAllocations,
  listAuditLog,
  listWsiAllocations,
  updateWsiAllocation,
} from "../api";

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
      isStaff.value = false; // 非 staff 读审计表会 403
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
    notify("error", "centre-id（issuer）必须是非负整数");
    return;
  }
  if (!Number.isInteger(payload.numberFrom) || !Number.isInteger(payload.numberTo)) {
    notify("error", "起止序号必须是整数");
    return;
  }
  busy.value = true;
  try {
    if (editingId.value == null) {
      await createWsiAllocation(payload);
      notify("success", "已新增授权区间");
    } else {
      await updateWsiAllocation(editingId.value, payload);
      notify("success", "已更新授权区间");
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
  if (!window.confirm(`删除 centre-id ${row.issuer} 的 ${row.numberFrom}–${row.numberTo} 区间？`)) return;
  busy.value = true;
  try {
    await deleteWsiAllocation(row.id);
    notify("success", "已删除");
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
    notify("success", `已导出 wsi-allocations.${format}`);
  } catch (err) {
    notify("error", err.message);
  } finally {
    busy.value = false;
  }
}

async function runImport() {
  if (!importText.value.trim()) {
    notify("error", "请粘贴要导入的 JSON 或 CSV 内容");
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
      `导入${importDryRun.value ? "试运行" : ""}完成：接受 ${accepted} 条，拒绝 ${rejected} 条`);
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
          <h3 class="text-h6">WSI 注册表与发布授权</h3>
          <div class="text-caption text-medium-emphasis">
            登记每个 centre-id 被授予的 WSI 序号区间；发布时逐条比对，超范围在本地拒绝并留痕。
          </div>
        </div>
        <v-btn variant="text" @click="open = false">关闭</v-btn>
      </div>

      <v-alert v-if="message" :type="message.type" variant="tonal" class="mb-3" closable
        @click:close="message = null">{{ message.text }}</v-alert>

      <v-tabs v-model="tab" density="compact">
        <v-tab value="allocations">授权区间</v-tab>
        <v-tab value="transfer">导入 / 导出</v-tab>
        <v-tab v-if="isStaff" value="audit">操作审计</v-tab>
      </v-tabs>

      <v-window v-model="tab" class="mt-3">
        <!-- ---------------- 授权区间 ---------------- -->
        <v-window-item value="allocations">
          <div class="d-flex ga-2 mb-3">
            <v-btn size="small" color="primary" variant="tonal" @click="startCreate">新增区间</v-btn>
            <v-btn size="small" variant="tonal" :disabled="busy" @click="load">刷新</v-btn>
          </div>

          <p v-if="busy && !displayRows.length">加载中…</p>
          <v-alert v-else-if="!displayRows.length" type="info" variant="tonal">
            还没有登记任何授权区间。未登记的 centre-id 无法发布任何站点。
          </v-alert>

          <v-table v-else density="compact">
            <thead>
              <tr>
                <th>centre-id</th><th>series</th><th>起始序号</th><th>结束序号</th>
                <th>备注</th><th></th>
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
                  <v-btn size="small" variant="text" @click="startEdit(row)">编辑</v-btn>
                  <v-btn size="small" variant="text" color="error" @click="remove(row)">删除</v-btn>
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-window-item>

        <!-- ---------------- 导入 / 导出 ---------------- -->
        <v-window-item value="transfer">
          <div class="d-flex ga-2 mb-3">
            <v-btn size="small" variant="tonal" @click="download('json')">导出 JSON</v-btn>
            <v-btn size="small" variant="tonal" @click="download('csv')">导出 CSV</v-btn>
          </div>
          <div class="text-caption text-medium-emphasis mb-2">
            导出的文件可直接交给目录侧做同步校验；也可在此粘贴回来完成批量导入。
          </div>

          <v-radio-group v-model="importFormat" inline density="compact" class="mb-2">
            <v-radio label="JSON" value="json" />
            <v-radio label="CSV" value="csv" />
          </v-radio-group>
          <v-textarea v-model="importText" rows="8" variant="outlined" density="compact"
            placeholder='JSON: [{"issuer":20000,"series":0,"numberFrom":0,"numberTo":999999,"note":"..."}]
CSV: issuer,series,numberFrom,numberTo,note' />
          <div class="d-flex align-center ga-3 mt-2">
            <v-checkbox v-model="importDryRun" label="试运行（只校验不写入）" density="compact" hide-details />
            <v-btn size="small" color="primary" variant="tonal" :disabled="busy" @click="runImport">导入</v-btn>
          </div>

          <div v-if="importResult" class="mt-3">
            <v-alert :type="importResult.rejected ? 'warning' : 'success'" variant="tonal" class="mb-2">
              接受 {{ importResult.accepted }} 条，拒绝 {{ importResult.rejected }} 条
            </v-alert>
            <pre class="result-box">{{ JSON.stringify(importResult.results, null, 2) }}</pre>
          </div>
        </v-window-item>

        <!-- ---------------- 审计 ---------------- -->
        <v-window-item value="audit">
          <div class="text-caption text-medium-emphasis mb-2">
            发布、发布被拒、注册表变更都会留痕（NF-6）。仅节点管理员可见。
          </div>
          <v-table v-if="auditRows.length" density="compact">
            <thead>
              <tr><th>时间</th><th>操作</th><th>操作者</th><th>站点</th><th>详情</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in auditRows" :key="row.id">
                <td class="text-no-wrap">{{ new Date(row.created).toLocaleString() }}</td>
                <td><code>{{ row.action }}</code></td>
                <td>{{ row.actor || "匿名" }}</td>
                <td>{{ row.wsi || "—" }}</td>
                <td class="text-medium-emphasis result-cell">{{ JSON.stringify(row.detail) }}</td>
              </tr>
            </tbody>
          </v-table>
          <v-alert v-else type="info" variant="tonal">暂无审计记录。</v-alert>
        </v-window-item>
      </v-window>

      <v-dialog v-model="dialog" max-width="520">
        <v-card class="pa-4">
          <h4 class="text-subtitle-1 mb-3">{{ editingId == null ? "新增授权区间" : "编辑授权区间" }}</h4>
          <v-text-field v-model="form.issuer" label="centre-id（issuer 段，如 20000）" density="compact" />
          <v-text-field v-model="form.series" label="series（默认 0）" density="compact" type="number" />
          <v-text-field v-model="form.numberFrom" label="起始序号" density="compact" type="number" />
          <v-text-field v-model="form.numberTo" label="结束序号（含）" density="compact" type="number" />
          <v-text-field v-model="form.note" label="备注（授权来源、日期等）" density="compact" />
          <div class="d-flex justify-end ga-2 mt-3">
            <v-btn variant="text" @click="dialog = false">取消</v-btn>
            <v-btn color="primary" variant="tonal" :disabled="busy" @click="save">保存</v-btn>
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
