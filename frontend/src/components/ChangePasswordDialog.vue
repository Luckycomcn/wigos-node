<script setup>
// Changing your own password. The current one is asked for: a session left
// open on a shared machine must not be enough to lock the owner out.
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import { changeOwnPassword } from "../api";
import { backendMessage } from "../i18n/backendMessages";

const open = defineModel({ type: Boolean, default: false });
const { t } = useI18n();

const oldPassword = ref("");
const newPassword = ref("");
const confirmPassword = ref("");
const busy = ref(false);
const message = ref(null);

function reset() {
  oldPassword.value = "";
  newPassword.value = "";
  confirmPassword.value = "";
  message.value = null;
}

async function submit() {
  message.value = null;
  if (!oldPassword.value || !newPassword.value) {
    message.value = { type: "error", text: t("password.errorRequired") };
    return;
  }
  if (newPassword.value !== confirmPassword.value) {
    message.value = { type: "error", text: t("password.errorMismatch") };
    return;
  }
  busy.value = true;
  try {
    await changeOwnPassword(oldPassword.value, newPassword.value);
    message.value = { type: "success", text: t("password.updated") };
    reset();
    // 密码改完会话仍然有效（后端 update_session_auth_hash），不需要重新登录。
    setTimeout(() => (open.value = false), 1200);
  } catch (err) {
    message.value = { type: "error", text: backendMessage(err.message) };
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <v-dialog v-model="open" max-width="460" @after-leave="reset">
    <v-card class="pa-4">
      <h4 class="text-subtitle-1 mb-1">{{ t("password.title") }}</h4>
      <p class="text-caption text-medium-emphasis mb-3">{{ t("password.subtitle") }}</p>

      <v-alert v-if="message" :type="message.type" variant="tonal" class="mb-3">{{ message.text }}</v-alert>

      <v-text-field
        v-model="oldPassword" :label="t('password.current')"
        density="compact" type="password" autocomplete="current-password"
      />
      <v-text-field
        v-model="newPassword" :label="t('password.new')"
        density="compact" type="password" autocomplete="new-password"
      />
      <v-text-field
        v-model="confirmPassword" :label="t('password.confirm')"
        density="compact" type="password" autocomplete="new-password"
      />

      <div class="d-flex justify-end ga-2 mt-3">
        <v-btn variant="text" @click="open = false">{{ t("password.cancel") }}</v-btn>
        <v-btn color="primary" variant="tonal" :disabled="busy" @click="submit">{{ t("password.submit") }}</v-btn>
      </div>
    </v-card>
  </v-dialog>
</template>
