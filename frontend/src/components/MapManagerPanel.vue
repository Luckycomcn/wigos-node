<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { activeBasemapId, setBasemap, currentBasemap } from "../leafletMap";
import { BASEMAPS, DEFAULT_BASEMAP_ID } from "../mapConfig";
import MapPreview from "./MapPreview.vue";

const { t } = useI18n();
const emit = defineEmits(["close"]);

// 注册表本身来自 mapConfig.js（构建期环境变量决定 custom/tianditu 是否可用）。
// 这里只负责"看得见地列出来 + 切换 + 立即预览"。
const options = computed(() =>
  BASEMAPS.map((b) => ({
    ...b,
    label: t(b.labelKey),
    hint: b.needsToken
      ? t("mapManager.needsToken")
      : b.online
        ? t("mapManager.onlineHint")
        : t("mapManager.offlineHint"),
  }))
);

const selected = computed({
  get: () => activeBasemapId.value,
  set: (id) => setBasemap(id),
});

const isDefault = computed(() => selected.value === DEFAULT_BASEMAP_ID);
const currentLabel = computed(() => t(currentBasemap().labelKey));
</script>

<template>
  <div>
    <div class="d-flex align-center mb-2">
      <h2 class="panel-title">{{ t("mapManager.title") }}</h2>
      <v-spacer />
      <v-btn variant="text" prepend-icon="mdi-arrow-left" @click="emit('close')">
        {{ t("nav.backToList") }}
      </v-btn>
    </div>
    <p class="text-medium-emphasis mb-4">{{ t("mapManager.intro") }}</p>

    <v-row>
      <v-col cols="12" md="5">
        <v-card variant="outlined">
          <v-card-title class="text-body-1 font-weight-bold">{{ t("mapManager.pick") }}</v-card-title>
          <v-card-text>
            <v-radio-group v-model="selected" density="compact" hide-details="auto">
              <v-radio
                v-for="opt in options"
                :key="opt.id"
                :value="opt.id"
                :label="opt.label"
                :disabled="Boolean(opt.needsToken)"
              >
                <template #details>
                  <span :class="opt.needsToken ? 'text-warning' : 'text-medium-emphasis'">
                    {{ opt.hint }}
                  </span>
                </template>
              </v-radio>
            </v-radio-group>

            <v-alert
              v-if="!isDefault"
              class="mt-3"
              type="info"
              variant="tonal"
              density="compact"
            >
              {{ t("mapManager.nonDefaultNotice", { basemap: currentLabel }) }}
              <v-btn
                class="ml-2"
                variant="text"
                size="small"
                color="primary"
                @click="setBasemap(DEFAULT_BASEMAP_ID)"
              >
                {{ t("mapManager.restoreDefault") }}
              </v-btn>
            </v-alert>

            <p class="source-note mt-3">{{ t("mapManager.complianceNote") }}</p>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="7">
        <v-card variant="outlined">
          <v-card-title class="text-body-1 font-weight-bold">
            {{ t("mapManager.preview") }}
            <span class="text-medium-emphasis font-weight-regular">— {{ currentLabel }}</span>
          </v-card-title>
          <v-card-text>
            <!-- 复用编辑页的坐标预览图：它 watch activeBasemapId，切换即刻重绘。
                 不传坐标 = 空画布看底图本身。 -->
            <MapPreview />
            <p class="text-caption text-medium-emphasis mt-2">{{ t("mapManager.previewNote") }}</p>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<style scoped>
.panel-title {
  font-size: 1.25rem;
  font-weight: 700;
}

.source-note {
  font-size: 0.78rem;
  color: #64748b;
  line-height: 1.5;
}
</style>
