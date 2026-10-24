<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useLocale } from "../composables/useLocale";

// Language menu in the app bar. Languages without a translation yet are still
// selectable, but are marked and leave the UI in English.
const { t } = useI18n();
const { locales, selected, setLocale } = useLocale();

const current = computed(() => locales.find((locale) => locale.code === selected.value));
</script>

<template>
  <v-menu location="bottom end" offset="8">
    <template #activator="{ props: activator }">
      <v-btn
        v-bind="activator"
        class="locale-button"
        variant="tonal"
        prepend-icon="mdi-translate"
        :aria-label="t('locale.switch')"
        :title="t('locale.switch')"
      >
        {{ current?.label }}
      </v-btn>
    </template>

    <v-list density="compact" min-width="220">
      <v-list-item
        v-for="locale in locales"
        :key="locale.code"
        :active="locale.code === selected"
        :data-locale="locale.code"
        @click="setLocale(locale.code)"
      >
        <v-list-item-title>
          {{ locale.label }}
          <span v-if="!locale.implemented" class="pending-tag">{{ t("locale.pending") }}</span>
        </v-list-item-title>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<style scoped>
.locale-button {
  text-transform: none;
}

.pending-tag {
  margin-left: 0.35rem;
  font-size: 0.75rem;
  opacity: 0.75;
}
</style>
