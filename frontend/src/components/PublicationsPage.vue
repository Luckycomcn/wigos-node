<script setup>
import { computed, onUnmounted, ref, watch } from "vue";
import { listPublications, retryPublication } from "../api";
import PublicationStatusChip, { PUBLICATION_STATUSES } from "./PublicationStatusChip.vue";

const emit = defineEmits(["changed"]);

const PAGE_SIZE = 50;
const REFRESH_MS = 5000; // while an event is on its way

const OPERATIONS = { create: "Created", update: "Updated", delete: "Deleted" };
const FILTERS = [
  { title: "All", value: null },
  { title: "Needs attention", value: "attention" },
  ...Object.entries(PUBLICATION_STATUSES).map(([value, { label }]) => ({ title: label, value })),
];

const events = ref([]);
const total = ref(0);
const filter = ref(null);
const loadState = ref({ status: "loading" });
const retrying = ref(new Set());
const retryError = ref(null);

let timer = null;
let requests = 0;

const hasMore = computed(() => events.value.length < total.value);
const isActive = (event) => event.status === "pending" || event.status === "processing";

// Fetches the first `limit` events. A slower, older answer is dropped, and a
// failing refresh keeps what is shown.
async function load(limit) {
  const request = ++requests;
  clearTimeout(timer);
  try {
    const filters = filter.value === "attention" ? { attention: 1 } : { status: filter.value };
    const data = await listPublications({ ...filters, limit, offset: 0 });
    if (request !== requests) return;
    events.value = data.results;
    total.value = data.count;
    loadState.value = { status: "success" };
    emit("changed");
  } catch (err) {
    if (request !== requests) return;
    loadState.value = { status: "error", error: err.message };
  }
  if (events.value.some(isActive)) {
    timer = setTimeout(() => load(Math.max(events.value.length, PAGE_SIZE)), REFRESH_MS);
  }
}

const refresh = () => load(Math.max(events.value.length, PAGE_SIZE));
const loadMore = () => load(events.value.length + PAGE_SIZE);

async function retry(event) {
  retryError.value = null;
  retrying.value = new Set(retrying.value).add(event.id);
  try {
    await retryPublication(event.id);
  } catch (err) {
    retryError.value = `${event.wigos_identifier}: ${err.message}`;
  }
  const remaining = new Set(retrying.value);
  remaining.delete(event.id);
  retrying.value = remaining;
  await refresh();
}

watch(filter, () => {
  loadState.value = { status: "loading" };
  events.value = [];
  load(PAGE_SIZE);
}, { immediate: true });

onUnmounted(() => {
  requests += 1; // drops an answer still on its way, which would start the timer again
  clearTimeout(timer);
});

const formatTime = (value) => (value ? new Date(value).toLocaleString() : "");
</script>

<template>
  <v-card class="pa-6">
    <div class="list-header">
      <h3>Publishing</h3>
      <div class="list-actions">
        <v-select
          v-model="filter"
          :items="FILTERS"
          label="Show"
          density="compact"
          hide-details
          class="status-filter"
        />
        <v-btn variant="tonal" prepend-icon="mdi-refresh" @click="refresh">Refresh</v-btn>
      </div>
    </div>

    <p v-if="loadState.status === 'loading'">Loading…</p>
    <v-alert v-if="loadState.status === 'error'" type="error" variant="tonal" class="mb-3">
      Error: {{ loadState.error }}
    </v-alert>
    <v-alert
      v-if="retryError"
      type="error"
      variant="tonal"
      class="mb-3"
      closable
      @click:close="retryError = null"
    >
      {{ retryError }}
    </v-alert>
    <p v-if="loadState.status === 'success' && events.length === 0" class="empty">
      {{ filter ? "No changes with this status." : "No changes published for your stations yet." }}
    </p>

    <template v-if="events.length > 0">
      <v-table class="publications">
        <thead>
          <tr>
            <th>When</th>
            <th>Change</th>
            <th>WIGOS identifier</th>
            <th>By</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="event in events" :key="event.id">
            <td class="when">{{ formatTime(event.created_at) }}</td>
            <td>{{ OPERATIONS[event.operation] }}</td>
            <td>{{ event.wigos_identifier }}</td>
            <td>{{ event.changed_by || event.source_label }}</td>
            <td>
              <PublicationStatusChip :status="event.status" />
              <!-- Only failed events: a later success keeps the earlier error on the event. -->
              <template v-if="event.status === 'failed'">
                <p class="event-error text-error">{{ event.last_error }}</p>
                <p v-if="event.needs_cleanup" class="event-note">
                  Its file couldn't be removed, which holds back this station's later changes. An administrator needs to
                  clean it up.
                </p>
                <p v-else-if="!event.can_retry" class="event-note">
                  A later change replaced this one, so it can't be retried. To publish again, save the station.
                </p>
              </template>
            </td>
            <td class="event-actions">
              <v-btn
                v-if="event.can_retry"
                color="primary"
                size="small"
                :loading="retrying.has(event.id)"
                @click="retry(event)"
              >
                Retry
              </v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>
      <div v-if="hasMore" class="more">
        <v-btn variant="tonal" @click="loadMore">Show more</v-btn>
      </div>
    </template>
  </v-card>
</template>

<style scoped>
.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
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

.list-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.status-filter {
  width: 13rem;
  flex: none;
}

.publications td {
  padding-top: 0.5rem !important;
  padding-bottom: 0.5rem !important;
  vertical-align: top;
}

.when {
  white-space: nowrap;
}

.event-error,
.event-note {
  margin: 0.4rem 0 0;
  font-size: 0.85rem;
  overflow-wrap: anywhere;
}

.event-actions {
  text-align: end;
}

.more {
  display: flex;
  justify-content: center;
  margin-top: 1rem;
}
</style>
