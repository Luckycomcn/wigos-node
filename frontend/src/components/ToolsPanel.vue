<script setup>
import { computed, ref, watch } from "vue";
import {
  createGroup,
  createTemplate,
  importRecords,
  importWmdr1,
  listGrades,
  listGroups,
  listTemplates,
} from "../api";

const open = defineModel({ type: Boolean, default: false });
const props = defineProps({
  stationIds: { type: Array, default: () => [] },
  initialTab: { type: String, default: "import" },
});
const emit = defineEmits(["imported"]);

const tab = ref("import");
const busy = ref(false);
const message = ref(null);

// ---------------- import ----------------
const file = ref(null);
const dryRun = ref(true);
const wmdr1Mode = ref(false);
const importResult = ref(null);

function notify(type, text) {
  message.value = { type, text };
}

async function onImport() {
  message.value = null;
  importResult.value = null;
  if (!file.value) {
    notify("error", "请先选择一个 .csv / .json / .xml 文件");
    return;
  }
  busy.value = true;
  try {
    const selected = Array.isArray(file.value) ? file.value[0] : file.value;
    if (wmdr1Mode.value) {
      const text = await selected.text();
      let parsed;
      try {
        parsed = JSON.parse(text);
      } catch (err) {
        throw new Error(`WMDR1 文件需为 JSON：${err.message}`);
      }
      const records = Array.isArray(parsed) ? parsed : parsed.records || [parsed];
      importResult.value = await importWmdr1(records, { dryRun: dryRun.value });
    } else {
      importResult.value = await importRecords({ file: selected, dryRun: dryRun.value });
    }
    const summary = importResult.value.summary || {};
    notify(summary.error ? "warning" : "success",
      `导入完成：成功 ${summary.ok ?? 0} 条，失败 ${summary.error ?? 0} 条${dryRun.value ? "（试运行，未写入）" : ""}`);
    if (!dryRun.value) emit("imported");
  } catch (err) {
    notify("error", err.message);
  } finally {
    busy.value = false;
  }
}

// ---------------- templates ----------------
const templates = ref([]);
const templateForm = ref({ name: "", description: "", shared: false, payload: '{\n  "properties": {}\n}' });
const templateError = ref(null);

async function loadTemplates() {
  try {
    templates.value = await listTemplates();
  } catch (err) {
    notify("error", err.message);
  }
}

async function saveTemplate() {
  templateError.value = null;
  let payload;
  try {
    payload = JSON.parse(templateForm.value.payload);
  } catch (err) {
    templateError.value = `payload 不是合法 JSON：${err.message}`;
    return;
  }
  if (!templateForm.value.name) {
    templateError.value = "请填写模板名称";
    return;
  }
  busy.value = true;
  try {
    await createTemplate(templateForm.value.name, payload, {
      description: templateForm.value.description,
      shared: templateForm.value.shared,
    });
    templateForm.value = { name: "", description: "", shared: false, payload: '{\n  "properties": {}\n}' };
    await loadTemplates();
    notify("success", "模板已保存");
  } catch (err) {
    templateError.value = err.message;
  } finally {
    busy.value = false;
  }
}

// ---------------- groups ----------------
const groups = ref([]);
const groupForm = ref({ name: "", description: "" });
const groupError = ref(null);

async function loadGroups() {
  try {
    groups.value = await listGroups();
  } catch (err) {
    notify("error", err.message);
  }
}

async function saveGroup() {
  groupError.value = null;
  if (!groupForm.value.name) {
    groupError.value = "请填写分组名称";
    return;
  }
  busy.value = true;
  try {
    await createGroup(groupForm.value.name, groupForm.value.description);
    groupForm.value = { name: "", description: "" };
    await loadGroups();
    notify("success", "分组已创建");
  } catch (err) {
    groupError.value = err.message;
  } finally {
    busy.value = false;
  }
}

// ---------------- grades ----------------
const grades = ref([]);

async function loadGrades() {
  try {
    grades.value = await listGrades();
  } catch (err) {
    notify("error", err.message);
  }
}

const gradeHeaders = [
  { title: "Code", key: "code" },
  { title: "Label", key: "label" },
  { title: "Criteria", key: "criteria", sortable: false },
];

const selectedCount = computed(() => props.stationIds.length);

watch(open, (value) => {
  if (!value) return;
  message.value = null;
  tab.value = props.initialTab || "import";
  if (tab.value === "templates") loadTemplates();
  if (tab.value === "groups") loadGroups();
  if (tab.value === "grades") loadGrades();
});

watch(tab, (value) => {
  if (value === "templates") loadTemplates();
  if (value === "groups") loadGroups();
  if (value === "grades") loadGrades();
});
</script>

<template>
  <v-dialog v-model="open" max-width="960" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <span>导入 / 导出与工具</span>
        <v-btn icon="mdi-close" variant="text" @click="open = false" />
      </v-card-title>
      <v-tabs v-model="tab" density="compact">
        <v-tab value="import">批量摄取</v-tab>
        <v-tab value="templates">模板</v-tab>
        <v-tab value="groups">分组</v-tab>
        <v-tab value="grades">分级</v-tab>
      </v-tabs>
      <v-divider />

      <v-card-text style="max-height: 60vh">
        <v-alert v-if="message" :type="message.type" variant="tonal" closable class="mb-3" @click:close="message = null">
          {{ message.text }}
        </v-alert>

        <!-- 批量摄取：CSV / JSON / XML（F-15），WMDR1（F-21） -->
        <template v-if="tab === 'import'">
          <p class="text-body-2 mb-2">
            支持 CSV、JSON、XML 三种格式；每条记录都按 WMDR2 表校验并沿用按 issuer 的权限规则。
            归档/只读账号无法写入。
          </p>
          <p v-if="selectedCount" class="text-body-2 mb-2">
            已选中 {{ selectedCount }} 条记录（导出时只导出选中的）。
          </p>
          <v-file-input v-model="file" label="选择文件（.csv / .json / .xml）" accept=".csv,.json,.xml"
                        density="compact" variant="outlined" prepend-icon="mdi-paperclip" />
          <div class="d-flex align-center ga-6 mb-3">
            <v-switch v-model="dryRun" label="试运行（不写入数据库）" density="compact" hide-details />
            <v-switch v-model="wmdr1Mode" label="按 WMDR V1 迁移（仅 JSON）" density="compact" hide-details />
            <v-btn color="primary" :loading="busy" prepend-icon="mdi-upload" @click="onImport">开始摄取</v-btn>
          </div>

          <template v-if="importResult">
            <v-alert type="info" variant="tonal" density="compact" class="mb-2">
              格式 {{ importResult.format || "wmdr1" }} ·
              成功 {{ importResult.summary?.ok ?? 0 }} ·
              失败 {{ importResult.summary?.error ?? 0 }} ·
              合计 {{ importResult.summary?.total ?? 0 }}
            </v-alert>
            <v-table density="compact">
              <thead>
                <tr><th>#</th><th>WSI</th><th>状态</th><th>说明</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in importResult.results" :key="row.index">
                  <td>{{ row.index }}</td>
                  <td>{{ row.wsi || "—" }}</td>
                  <td>
                    <v-chip size="x-small" :color="row.status === 'ok' ? 'success' : 'error'" variant="tonal">
                      {{ row.status }}
                    </v-chip>
                  </td>
                  <td class="text-caption">
                    {{ row.message || (row.errors ? row.errors.slice(0, 2).join("; ") : "") }}
                    <span v-if="row.placeholders && row.placeholders.length">
                      · 占位字段：{{ row.placeholders.join(", ") }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </template>
        </template>

        <!-- 模板（F-22） -->
        <template v-else-if="tab === 'templates'">
          <v-row dense>
            <v-col cols="12" md="5">
              <v-text-field v-model="templateForm.name" label="名称" density="compact" variant="outlined" />
              <v-textarea v-model="templateForm.description" label="说明" rows="2" density="compact" variant="outlined" />
              <v-switch v-model="templateForm.shared" label="共享给其他用户" density="compact" hide-details />
              <v-textarea v-model="templateForm.payload" label="预填 payload（JSON）" rows="8"
                          density="compact" variant="outlined" class="font-monospace" />
              <v-alert v-if="templateError" type="error" variant="tonal" density="compact" class="mb-2">
                {{ templateError }}
              </v-alert>
              <v-btn color="primary" :loading="busy" @click="saveTemplate">保存模板</v-btn>
            </v-col>
            <v-col cols="12" md="7">
              <v-list density="compact">
                <v-list-item v-for="tpl in templates" :key="tpl.id">
                  <v-list-item-title>{{ tpl.name }}
                    <v-chip v-if="tpl.shared" size="x-small" class="ml-2" variant="tonal">shared</v-chip>
                  </v-list-item-title>
                  <v-list-item-subtitle>{{ tpl.description || "（无说明）" }} · {{ tpl.owner }}</v-list-item-subtitle>
                </v-list-item>
                <v-list-item v-if="templates.length === 0">
                  <v-list-item-subtitle>还没有模板</v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-col>
          </v-row>
        </template>

        <!-- 分组（F-6） -->
        <template v-else-if="tab === 'groups'">
          <v-row dense>
            <v-col cols="12" md="5">
              <v-text-field v-model="groupForm.name" label="分组名称" density="compact" variant="outlined" />
              <v-textarea v-model="groupForm.description" label="说明" rows="2" density="compact" variant="outlined" />
              <v-alert v-if="groupError" type="error" variant="tonal" density="compact" class="mb-2">{{ groupError }}</v-alert>
              <v-btn color="primary" :loading="busy" @click="saveGroup">创建分组</v-btn>
              <p class="text-caption mt-2">成员增删：在记录列表里勾选后调用分组接口，或直接 POST /api/groups/&lt;id&gt;/。</p>
            </v-col>
            <v-col cols="12" md="7">
              <v-list density="compact">
                <v-list-item v-for="group in groups" :key="group.id">
                  <v-list-item-title>{{ group.name }}</v-list-item-title>
                  <v-list-item-subtitle>
                    {{ group.description || "（无说明）" }} · 成员 {{ group.station_ids.length }} · {{ group.owner }}
                  </v-list-item-subtitle>
                </v-list-item>
                <v-list-item v-if="groups.length === 0">
                  <v-list-item-subtitle>还没有分组</v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-col>
          </v-row>
        </template>

        <!-- 分级（F-24） -->
        <template v-else>
          <p class="text-body-2 mb-2">
            分级规则由后端 <code>/api/grades/</code> 定义（超级用户可写）；单条记录的分级评估见
            <code>/api/stations/&lt;id&gt;/grades/</code>。
          </p>
          <v-data-table :headers="gradeHeaders" :items="grades" density="compact" :items-per-page="-1" hide-default-footer>
            <template #[`item.criteria`]="{ item }">
              <code class="text-caption">{{ JSON.stringify(item.criteria) }}</code>
            </template>
          </v-data-table>
          <p v-if="grades.length === 0" class="text-caption">还没有分级定义。</p>
        </template>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
