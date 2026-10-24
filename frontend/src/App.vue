<script setup>
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import LoginPage from "./components/LoginPage.vue";
import StationsList from "./components/StationsList.vue";
import WmdrForm from "./components/WmdrForm.vue";
import BatchWizard from "./components/batch/BatchWizard.vue";
import LocaleSwitcher from "./components/LocaleSwitcher.vue";
import { useAuth } from "./composables/useAuth";
import { useLocale } from "./composables/useLocale";

const { t } = useI18n();
const { pending, active } = useLocale();

// The tab title follows the language too; index.html carries the English one
// for the moment before the app mounts. `lang` matters beyond the title: screen
// readers pick their pronunciation from it, and so do :lang() CSS rules.
watch(
  active,
  () => {
    document.title = t("app.title");
    document.documentElement.lang = active.value;
  },
  { immediate: true }
);

const { status, user, setUser, logout } = useAuth();

// { mode: "list" | "new" | "edit" | "batch", stationId?, stationIds? }
const view = ref({ mode: "list" });
// Station IDs ticked in the list; kept here so they survive the batch wizard.
const selected = ref(new Set());

async function handleLogout() {
  await logout();
  view.value = { mode: "list" };
  selected.value = new Set();
}
</script>

<template>
  <v-app>
    <v-app-bar class="app-bar" height="88" flat>
      <div class="app-bar-title">
        <h1>{{ t("app.title") }}</h1>
        <p>{{ t("app.subtitle") }}</p>
      </div>
      <template #append>
        <LocaleSwitcher />
        <template v-if="status === 'authenticated'">
          <span class="mr-3 ml-4">{{ user.email || user.username }}</span>
          <v-btn variant="tonal" @click="handleLogout">{{ t("app.logout") }}</v-btn>
        </template>
      </template>
    </v-app-bar>

    <v-main>
      <v-container :class="['app-main', { 'app-main-wide': view.mode === 'batch' }]">
        <v-alert v-if="pending" class="mb-4" type="info" variant="tonal" density="compact" data-testid="locale-pending">
          {{ t("locale.pendingNotice", { language: pending }) }}
        </v-alert>

        <p v-if="status === 'loading'">{{ t("app.loading") }}</p>

        <LoginPage v-else-if="status === 'anonymous'" @success="setUser" />

        <template v-else>
          <StationsList
            v-if="view.mode === 'list'"
            v-model:selected="selected"
            @new="view = { mode: 'new' }"
            @edit="(stationId) => (view = { mode: 'edit', stationId })"
            @batch="(stationIds) => (view = { mode: 'batch', stationIds })"
          />
          <WmdrForm
            v-else-if="view.mode === 'new' || view.mode === 'edit'"
            :key="view.mode === 'edit' ? view.stationId : 'new'"
            :station-id="view.mode === 'edit' ? view.stationId : null"
            @saved="view = { mode: 'list' }"
            @cancel="view = { mode: 'list' }"
          />
          <!-- Only the stations that failed stay selected after applying. -->
          <BatchWizard
            v-else-if="view.mode === 'batch'"
            :station-ids="view.stationIds"
            @applied="(failedIds) => (selected = new Set(failedIds))"
            @close="view = { mode: 'list' }"
          />
        </template>
      </v-container>
    </v-main>
  </v-app>
</template>

<style scoped>
.app-bar {
  background: linear-gradient(135deg, #1d4ed8, #3b82f6) !important;
  color: #fff !important;
  padding: 0 1rem;
}

.app-bar-title h1 {
  color: #fff;
  font-size: 1.4rem;
  font-weight: 700;
  margin: 0;
}

.app-bar-title p {
  margin: 0.25rem 0 0;
  color: #dbeafe;
  font-size: 0.9rem;
}

.app-main {
  max-width: 1200px;
  padding: 2rem;
}

/* The batch wizard needs the width for wide grids. */
.app-main-wide {
  max-width: none;
}
</style>
