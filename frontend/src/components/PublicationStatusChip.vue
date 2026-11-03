<script>
export const PUBLICATION_STATUSES = {
  pending: { label: "Pending", color: "info", icon: "mdi-clock-outline" },
  processing: { label: "Publishing", color: "info", icon: "mdi-progress-upload" },
  processed: { label: "Processed", color: "success", icon: "mdi-check" },
  published: { label: "Published", color: "success", icon: "mdi-check-all" },
  failed: { label: "Publishing failed", color: "error", icon: "mdi-close" },
};
</script>

<script setup>
defineProps({ status: { type: String, required: true } });
</script>

<template>
  <v-chip
    size="small"
    variant="tonal"
    :color="PUBLICATION_STATUSES[status].color"
    :prepend-icon="PUBLICATION_STATUSES[status].icon"
  >
    {{ PUBLICATION_STATUSES[status].label }}
  </v-chip>
</template>
