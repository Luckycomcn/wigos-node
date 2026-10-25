<script setup>
// Node user administration: who may log in, and what they may do.
//
// Accounts are created here by the node administrator — there is no public
// sign-up — and passwords are reset here too. Every change goes through the
// backend's audit log, so the panel deliberately keeps no local state beyond
// the form being edited.
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import {
  createUser,
  deleteUser,
  listUserGroups,
  listUsers,
  setUserPassword,
  updateUser,
} from "../api";
import { backendMessage } from "../i18n/backendMessages";

const open = defineModel({ type: Boolean, default: false });
const { t } = useI18n();

const rows = ref([]);
const groupOptions = ref([]);
const busy = ref(false);
const message = ref(null);

const dialog = ref(false);
const editingId = ref(null);
const form = ref(blank());

const passwordDialog = ref(false);
const passwordTarget = ref(null);
const newPassword = ref("");

function blank() {
  return { username: "", email: "", password: "", isStaff: false, isActive: true, groups: [] };
}

function notify(type, text) {
  message.value = { type, text };
}

async function load() {
  busy.value = true;
  message.value = null;
  try {
    rows.value = await listUsers();
  } catch (err) {
    notify("error", backendMessage(err.message));
    return;
  } finally {
    busy.value = false;
  }
  try {
    groupOptions.value = await listUserGroups();
  } catch {
    groupOptions.value = []; // 组列表只是下拉选项，拿不到不影响主流程
  }
}

function startCreate() {
  form.value = blank();
  editingId.value = null;
  dialog.value = true;
}

function startEdit(row) {
  form.value = {
    username: row.username,
    email: row.email,
    password: "",
    isStaff: row.is_staff,
    isActive: row.is_active,
    groups: [...(row.groups || [])],
  };
  editingId.value = row.id;
  dialog.value = true;
}

function fieldError() {
  if (!form.value.username.trim()) return t("admin.errorUsername");
  if (!form.value.email.trim()) return t("admin.errorEmail");
  if (editingId.value === null && !form.value.password) return t("admin.errorPassword");
  return null;
}

async function save() {
  const problem = fieldError();
  if (problem) {
    notify("error", problem);
    return;
  }
  busy.value = true;
  try {
    if (editingId.value === null) {
      await createUser({
        username: form.value.username.trim(),
        email: form.value.email.trim(),
        password: form.value.password,
        isStaff: form.value.isStaff,
        groups: form.value.groups,
      });
      notify("success", t("admin.created"));
    } else {
      await updateUser(editingId.value, {
        username: form.value.username.trim(),
        email: form.value.email.trim(),
        is_staff: form.value.isStaff,
        is_active: form.value.isActive,
        groups: form.value.groups,
      });
      notify("success", t("admin.updated"));
    }
    dialog.value = false;
    await load();
  } catch (err) {
    notify("error", backendMessage(err.message));
  } finally {
    busy.value = false;
  }
}

async function remove(row) {
  if (!window.confirm(t("admin.confirmDelete", { name: row.email || row.username }))) return;
  busy.value = true;
  try {
    await deleteUser(row.id);
    notify("success", t("admin.deleted"));
    await load();
  } catch (err) {
    notify("error", backendMessage(err.message));
  } finally {
    busy.value = false;
  }
}

function startPassword(row) {
  passwordTarget.value = row;
  newPassword.value = "";
  passwordDialog.value = true;
}

async function submitPassword() {
  if (!newPassword.value) {
    notify("error", t("admin.errorPassword"));
    return;
  }
  busy.value = true;
  try {
    await setUserPassword(passwordTarget.value.id, newPassword.value);
    notify("success", t("admin.passwordUpdated"));
    passwordDialog.value = false;
  } catch (err) {
    notify("error", backendMessage(err.message));
  } finally {
    busy.value = false;
  }
}

watch(open, (value) => {
  if (value) load();
});
</script>

<template>
  <v-dialog v-model="open" max-width="980">
    <v-card class="pa-6">
      <div class="d-flex align-center justify-space-between mb-2">
        <div>
          <h3 class="text-h6">{{ t("admin.title") }}</h3>
          <p class="text-caption text-medium-emphasis mb-0">{{ t("admin.subtitle") }}</p>
        </div>
        <div class="d-flex ga-2">
          <v-btn variant="tonal" prepend-icon="mdi-refresh" :disabled="busy" @click="load">{{ t("admin.refresh") }}</v-btn>
          <v-btn color="primary" prepend-icon="mdi-account-plus" :disabled="busy" @click="startCreate">{{ t("admin.newUser") }}</v-btn>
        </div>
      </div>

      <v-alert v-if="message" :type="message.type" variant="tonal" closable class="mb-3" @click:close="message = null">
        {{ message.text }}
      </v-alert>

      <p v-if="busy && rows.length === 0">{{ t("admin.loading") }}</p>

      <v-table v-if="rows.length" density="compact" class="user-table">
        <thead>
          <tr>
            <th>{{ t("admin.columnUser") }}</th>
            <th>{{ t("admin.columnEmail") }}</th>
            <th>{{ t("admin.columnRole") }}</th>
            <th>{{ t("admin.columnState") }}</th>
            <th>{{ t("admin.columnGroups") }}</th>
            <th class="text-right">{{ t("admin.columnActions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td>{{ row.username }}</td>
            <td>{{ row.email }}</td>
            <td>
              <v-chip v-if="row.is_superuser" size="small" color="error" variant="flat">{{ t("admin.roleSuperuser") }}</v-chip>
              <v-chip v-else-if="row.is_staff" size="small" color="primary" variant="tonal">{{ t("admin.roleAdmin") }}</v-chip>
              <v-chip v-else size="small" variant="tonal">{{ t("admin.roleUser") }}</v-chip>
            </td>
            <td>
              <v-chip :color="row.is_active ? 'success' : 'default'" size="small" variant="tonal">
                {{ row.is_active ? t("admin.active") : t("admin.inactive") }}
              </v-chip>
            </td>
            <td class="text-medium-emphasis">
              {{ (row.groups || []).join(", ") || "—" }}
            </td>
            <td class="text-right text-no-wrap">
              <v-btn variant="text" size="small" :disabled="busy" @click="startEdit(row)">{{ t("admin.edit") }}</v-btn>
              <v-btn variant="text" size="small" :disabled="busy" @click="startPassword(row)">{{ t("admin.password") }}</v-btn>
              <v-btn
                v-if="row.can_delete"
                variant="text" color="error" size="small" :disabled="busy"
                @click="remove(row)"
              >{{ t("admin.delete") }}</v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>

      <v-alert v-else-if="!busy" type="info" variant="tonal">{{ t("admin.empty") }}</v-alert>

      <!-- ---------------- 新建 / 编辑 ---------------- -->
      <v-dialog v-model="dialog" max-width="560">
        <v-card class="pa-4">
          <h4 class="text-subtitle-1 mb-3">
            {{ editingId === null ? t("admin.formTitleNew") : t("admin.formTitleEdit") }}
          </h4>
          <v-text-field v-model="form.username" :label="t('admin.username')" density="compact" />
          <v-text-field v-model="form.email" :label="t('admin.email')" density="compact" type="email" />
          <v-text-field
            v-if="editingId === null"
            v-model="form.password"
            :label="t('admin.password')"
            density="compact" type="password"
            :hint="t('admin.passwordHint')" persistent-hint
          />
          <v-switch v-model="form.isStaff" :label="t('admin.isStaff')" density="compact" hide-details class="mt-2" />
          <v-switch
            v-if="editingId !== null"
            v-model="form.isActive"
            :label="t('admin.isActive')"
            density="compact" hide-details
          />
          <v-select
            v-model="form.groups"
            :items="groupOptions"
            item-title="name"
            item-value="name"
            :label="t('admin.groups')"
            density="compact" multiple chips closable-chips class="mt-3"
          />
          <div class="d-flex justify-end ga-2 mt-4">
            <v-btn variant="text" @click="dialog = false">{{ t("admin.cancel") }}</v-btn>
            <v-btn color="primary" variant="tonal" :disabled="busy" @click="save">{{ t("admin.save") }}</v-btn>
          </div>
        </v-card>
      </v-dialog>

      <!-- ---------------- 重置他人密码 ---------------- -->
      <v-dialog v-model="passwordDialog" max-width="460">
        <v-card class="pa-4">
          <h4 class="text-subtitle-1 mb-1">{{ t("admin.passwordTitle") }}</h4>
          <p class="text-caption text-medium-emphasis mb-3">
            {{ t("admin.passwordFor", { name: passwordTarget?.email || passwordTarget?.username || "" }) }}
          </p>
          <v-text-field v-model="newPassword" :label="t('admin.newPassword')" density="compact" type="password" />
          <div class="d-flex justify-end ga-2 mt-3">
            <v-btn variant="text" @click="passwordDialog = false">{{ t("admin.cancel") }}</v-btn>
            <v-btn color="primary" variant="tonal" :disabled="busy" @click="submitPassword">{{ t("admin.save") }}</v-btn>
          </div>
        </v-card>
      </v-dialog>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.user-table td {
  font-size: 0.85rem;
}
</style>
