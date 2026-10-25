<script setup>
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
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
const { t } = useI18n();

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
    notify("error", t("tools.noFile"));
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
        throw new Error(t("tools.wmdr1NotJson", { message: err.message }));
      }
      const records = Array.isArray(parsed) ? parsed : parsed.records || [parsed];
      importResult.value = await importWmdr1(records, { dryRun: dryRun.value });
    } else {
      importResult.value = await importRecords({ file: selected, dryRun: dryRun.value });
    }
    const summary = importResult.value.summary || {};
    notify(summary.error ? "warning" : "success",
      t("tools.importDone", { ok: summary.ok ?? 0, failed: summary.error ?? 0, dry: dryRun.value ? t("tools.dryRunSuffix") : "" }));
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
    templateError.value = t("tools.payloadNotJson", { message: err.message });
    return;
  }
  if (!templateForm.value.name) {
    templateError.value = t("tools.errorTemplateName");
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
    notify("success", t("tools.templateSaved"));
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
    groupError.value = t("tools.errorGroupName");
    return;
  }
  busy.value = true;
  try {
    await createGroup(groupForm.value.name, groupForm.value.description);
    groupForm.value = { name: "", description: "" };
    await loadGroups();
    notify("success", t("tools.groupCreated"));
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

const gradeHeaders = computed(() => [
  { title: t("tools.gradeCode"), key: "code" },
  { title: t("tools.gradeLabel"), key: "label" },
  { title: t("tools.gradeCriteria"), key: "criteria", sortable: false },
]);

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
        <span>{{ t("tools.title") }}</span>
        <v-btn icon="mdi-close" variant="text" @click="open = false" />
      </v-card-title>
      <v-tabs v-model="tab" density="compact">
        <v-tab value="import">{{ t("tools.tabImport") }}</v-tab>
        <v-tab value="templates">{{ t("tools.tabTemplates") }}</v-tab>
        <v-tab value="groups">{{ t("tools.tabGroups") }}</v-tab>
        <v-tab value="grades">{{ t("tools.tabGrades") }}</v-tab>
      </v-tabs>
      <v-divider />

      <v-card-text style="max-height: 60vh">
        <v-alert v-if="message" :type="message.type" variant="tonal" closable class="mb-3" @click:close="message = null">
          {{ message.text }}
        </v-alert>

        <!-- 批量摄取：CSV / JSON / XML（F-15），WMDR1（F-21） -->
        <template v-if="tab === 'import'">
          <p class="text-body-2 mb-2">
            {{ t("tools.intro") }} {{ t("tools.readOnlyNote") }}
          </p>
          <p v-if="selectedCount" class="text-body-2 mb-2">
            {{ t("tools.selectedCount", { count: selectedCount }) }}
          </p>
          <v-file-input v-model="file" :label="t('tools.chooseFile')" accept=".csv,.json,.xml"
                        density="compact" variant="outlined" prepend-icon="mdi-paperclip" />
          <div class="d-flex align-center ga-6 mb-3">
            <v-switch v-model="dryRun" :label="t('tools.dryRun')" density="compact" hide-details />
            <v-switch v-model="wmdr1Mode" :label="t('tools.wmdr1Mode')" density="compact" hide-details />
            <v-btn color="primary" :loading="busy" prepend-icon="mdi-upload" @click="onImport">{{ t("tools.startImport") }}</v-btn>
          </div>

          <template v-if="importResult">
            <v-alert type="info" variant="tonal" density="compact" class="mb-2">
              {{ t("tools.resultFormat", { format: importResult.format || "wmdr1" }) }} ·
              {{ t("tools.resultOk", { count: importResult.summary?.ok ?? 0 }) }} ·
              {{ t("tools.resultFailed", { count: importResult.summary?.error ?? 0 }) }} ·
              {{ t("tools.resultTotal", { count: importResult.summary?.total ?? 0 }) }}
            </v-alert>
            <v-table density="compact">
              <thead>
                <tr><th>#</th><th>{{ t("tools.colWsi") }}</th><th>{{ t("tools.colStatus") }}</th><th>{{ t("tools.colDetail") }}</th></tr>
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
                      {{ t("tools.placeholders", { fields: row.placeholders.join(", ") }) }}
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
              <v-text-field v-model="templateForm.name" :label="t('tools.name')" density="compact" variant="outlined" />
              <v-textarea v-model="templateForm.description" :label="t('tools.description')" rows="2" density="compact" variant="outlined" />
              <v-switch v-model="templateForm.shared" :label="t('tools.templateShared')" density="compact" hide-details />
              <v-textarea v-model="templateForm.payload" :label="t('tools.templatePayload')" rows="8"
                          density="compact" variant="outlined" class="font-monospace" />
              <v-alert v-if="templateError" type="error" variant="tonal" density="compact" class="mb-2">
                {{ templateError }}
              </v-alert>
              <v-btn color="primary" :loading="busy" @click="saveTemplate">{{ t("tools.saveTemplate") }}</v-btn>
            </v-col>
            <v-col cols="12" md="7">
              <v-list density="compact">
                <v-list-item v-for="tpl in templates" :key="tpl.id">
                  <v-list-item-title>{{ tpl.name }}
                    <v-chip v-if="tpl.shared" size="x-small" class="ml-2" variant="tonal">shared</v-chip>
                  </v-list-item-title>
                  <v-list-item-subtitle>{{ tpl.description || t("tools.noDescription") }} · {{ tpl.owner }}</v-list-item-subtitle>
                </v-list-item>
                <v-list-item v-if="templates.length === 0">
                  <v-list-item-subtitle>{{ t("tools.noTemplates") }}</v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-col>
          </v-row>
        </template>

        <!-- 分组（F-6） -->
        <template v-else-if="tab === 'groups'">
          <v-row dense>
            <v-col cols="12" md="5">
              <v-text-field v-model="groupForm.name" :label="t('tools.groupName')" density="compact" variant="outlined" />
              <v-textarea v-model="groupForm.description" :label="t('tools.description')" rows="2" density="compact" variant="outlined" />
              <v-alert v-if="groupError" type="error" variant="tonal" density="compact" class="mb-2">{{ groupError }}</v-alert>
              <v-btn color="primary" :loading="busy" @click="saveGroup">{{ t("tools.createGroup") }}</v-btn>
              <p class="text-caption mt-2">{{ t("tools.groupMembersHint") }}</p>
            </v-col>
            <v-col cols="12" md="7">
              <v-list density="compact">
                <v-list-item v-for="group in groups" :key="group.id">
                  <v-list-item-title>{{ group.name }}</v-list-item-title>
                  <v-list-item-subtitle>
                    {{ group.description || t("tools.noDescription") }} · {{ t("tools.groupMembers", { count: group.station_ids.length }) }} · {{ group.owner }}
                  </v-list-item-subtitle>
                </v-list-item>
                <v-list-item v-if="groups.length === 0">
                  <v-list-item-subtitle>{{ t("tools.noGroups") }}</v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-col>
          </v-row>
        </template>

        <!-- 分级（F-24） -->
        <template v-else>
          <p class="text-body-2 mb-2">
            {{ t("tools.gradesHint") }}
            <code>/api/stations/&lt;id&gt;/grades/</code>。
          </p>
          <v-data-table :headers="gradeHeaders" :items="grades" density="compact" :items-per-page="-1" hide-default-footer>
            <template #[`item.criteria`]="{ item }">
              <code class="text-caption">{{ JSON.stringify(item.criteria) }}</code>
            </template>
          </v-data-table>
          <p v-if="grades.length === 0" class="text-caption">{{ t("tools.noGrades") }}</p>
        </template>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">{{ t("common.close") }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
