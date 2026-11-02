<script setup>
import { computed, onUnmounted, ref, watch } from "vue";
import { listPublications } from "./api";
import LoginPage from "./components/LoginPage.vue";
import PublicationsPage from "./components/PublicationsPage.vue";
import StationsList from "./components/StationsList.vue";
import WmdrForm from "./components/WmdrForm.vue";
import BatchWizard from "./components/batch/BatchWizard.vue";
import { useAuth } from "./composables/useAuth";

const { status, user, setUser, logout } = useAuth();

// { mode: "list" | "new" | "edit" | "batch" | "publications", stationId?, stationIds? }
const view = ref({ mode: "list" });
// Station IDs ticked in the list; kept here so they survive the batch wizard.
const selected = ref(new Set());

// The sidebar is for the main pages; the form and the wizard have their own way out.
const NAV_ITEMS = [
  { mode: "list", title: "Stations", icon: "mdi-map-marker-multiple" },
  { mode: "publications", title: "Publishing", icon: "mdi-history" },
];
const showNav = computed(() => status.value === "authenticated" && NAV_ITEMS.some((item) => item.mode === view.value.mode));
// null: open on large screens, closed on small ones (Vuetify's default)
const navOpen = ref(null);

// Failures someone can still act on, on the Publishing item. It only shows with
// the sidebar, so it is only kept up to date then.
const FAILURES_REFRESH_MS = 30000;
const failures = ref(0);
let failuresTimer = null;

async function refreshFailures() {
  try {
    failures.value = (await listPublications({ attention: 1, limit: 1 })).count;
  } catch {
    // keeps the last number: the rest of the app works without it
  }
}

watch(showNav, (shown) => {
  clearInterval(failuresTimer);
  if (shown) {
    refreshFailures();
    failuresTimer = setInterval(refreshFailures, FAILURES_REFRESH_MS);
  }
}, { immediate: true });
onUnmounted(() => clearInterval(failuresTimer));

async function handleLogout() {
  await logout();
  view.value = { mode: "list" };
  selected.value = new Set();
  failures.value = 0;
}
</script>

<template>
  <v-app>
    <v-app-bar class="app-bar" height="88" flat>
      <template v-if="showNav" #prepend>
        <v-app-bar-nav-icon aria-label="Toggle the menu" @click="navOpen = !navOpen" />
      </template>
      <div class="app-bar-title">
        <h1>WMDR Station Record Builder</h1>
        <p>Fill in station metadata and generate a WIGOS-conformant GeoJSON record.</p>
      </div>
      <template v-if="status === 'authenticated'" #append>
        <span class="mr-3">{{ user.email || user.username }}</span>
        <v-btn variant="tonal" @click="handleLogout">Log out</v-btn>
      </template>
    </v-app-bar>

    <v-navigation-drawer v-if="showNav" v-model="navOpen">
      <v-list nav>
        <v-list-item
          v-for="item in NAV_ITEMS"
          :key="item.mode"
          :title="item.title"
          :prepend-icon="item.icon"
          :active="view.mode === item.mode"
          color="primary"
          @click="view = { mode: item.mode }"
        >
          <template v-if="item.mode === 'publications' && failures > 0" #append>
            <v-chip size="x-small" color="error" variant="flat" :aria-label="`${failures} failed`">{{ failures }}</v-chip>
          </template>
        </v-list-item>
      </v-list>
    </v-navigation-drawer>

    <v-main>
      <v-container :class="['app-main', { 'app-main-wide': view.mode === 'batch' }]">
        <p v-if="status === 'loading'">Loading…</p>

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
          <PublicationsPage v-else-if="view.mode === 'publications'" @changed="refreshFailures" />
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
