<script setup>
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import LoginPage from "./components/LoginPage.vue";
import StationsList from "./components/StationsList.vue";
import WmdrForm from "./components/WmdrForm.vue";
import BatchWizard from "./components/batch/BatchWizard.vue";
import LocaleSwitcher from "./components/LocaleSwitcher.vue";
import ChangePasswordDialog from "./components/ChangePasswordDialog.vue";
import UserAdminPanel from "./components/UserAdminPanel.vue";
import WsiRegistryPanel from "./components/WsiRegistryPanel.vue";
import MapManagerPanel from "./components/MapManagerPanel.vue";
import ToolsPanel from "./components/ToolsPanel.vue";
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

// 页面级视图。原来只有 list / new / edit / batch 四种，工具、用户管理、
// WSI 注册表都挤在列表页的按钮里、以对话框打开 —— 那几块是独立的完整
// 功能，各自有表格、筛选、分页，塞进 980px 的弹窗里既看不清也不像"一个
// 地方可以长期停留"的页面。现在它们各占一个顶级导航项。
const view = ref({ mode: "list" });
const passwordOpen = ref(false);
// Station IDs ticked in the list; kept here so they survive the batch wizard.
const selected = ref(new Set());

const isStaff = computed(() => Boolean(user.value?.is_staff));

// 顶部导航项。这里只放"日常操作"两页：我的台站、导入导出。
// 用户管理 / WSI 注册表 / 地图管理都是"配置性质、偶尔进一次"的管理动作，
// 统一收进右上角的「管理」菜单——它们若同时出现在导航条和菜单里就是重复入口
// （上一版正是如此，导航条第二行既有它们、菜单里也有，用户看不到白底白字的
// 那一行、又以为功能丢了）。导航条保持精简。
const navItems = computed(() => [
  { value: "list", title: t("nav.stations"), icon: "mdi-format-list-bulleted" },
  { value: "tools", title: t("nav.tools"), icon: "mdi-database-arrow-up-down" },
]);

// 当前高亮的导航项：新建/编辑/批量都属于"我的台站"这个区。
const activeNav = computed(() =>
  ["new", "edit", "batch"].includes(view.value.mode) ? "list" : view.value.mode
);

function go(mode) {
  view.value = { mode };
}

async function handleLogout() {
  await logout();
  view.value = { mode: "list" };
  selected.value = new Set();
}
</script>

<template>
  <v-app>
    <v-app-bar class="app-bar" height="88" flat extended extension-height="48">
      <div class="app-bar-title">
        <h1>{{ t("app.title") }}</h1>
        <p>{{ t("app.subtitle") }}</p>
      </div>
      <template #append>
        <LocaleSwitcher />
        <template v-if="status === 'authenticated'">
          <span class="mr-3 ml-4">{{ user.email || user.username }}</span>
          <!--
            "修改密码"原来是一个独立按钮，但它跟用户管理、WSI 注册表是同类的
            "管理自己的账号 / 数据"动作，散在顶栏里很难被发现。收进一个「管理」
            菜单，语义清楚，也不会随功能增加把顶栏挤爆。
          -->
          <v-menu>
            <template #activator="{ props: menuProps }">
              <v-btn v-bind="menuProps" variant="tonal" prepend-icon="mdi-cog-outline" append-icon="mdi-menu-down">
                {{ t("nav.manage") }}
              </v-btn>
            </template>
            <v-list density="compact">
              <v-list-item prepend-icon="mdi-lock-reset" @click="passwordOpen = true">
                <v-list-item-title>{{ t("nav.changePassword") }}</v-list-item-title>
              </v-list-item>
              <v-list-item
                v-if="isStaff"
                prepend-icon="mdi-account-group-outline"
                @click="go('users')"
              >
                <v-list-item-title>{{ t("nav.users") }}</v-list-item-title>
              </v-list-item>
              <v-list-item prepend-icon="mdi-shield-key-outline" @click="go('registry')">
                <v-list-item-title>{{ t("nav.wsiRegistry") }}</v-list-item-title>
              </v-list-item>
              <v-list-item prepend-icon="mdi-map-outline" @click="go('map')">
                <v-list-item-title>{{ t("nav.mapSettings") }}</v-list-item-title>
              </v-list-item>
            </v-list>
          </v-menu>
          <v-btn variant="tonal" @click="handleLogout">{{ t("app.logout") }}</v-btn>
        </template>
      </template>

      <!--
        功能页之间的切换靠这条 tab 栏，而不是列表页里的一排按钮。
        必须放进 v-app-bar 的 #extension 槽里，不能直接摆在 <v-app-bar> 和
        <v-main> 之间：v-app-bar 是 position:fixed，脱离文档流，紧跟其后的
        兄弟元素会从 y=0 开始排布并被顶栏**盖住** —— 视觉上看着「有一行、但
        点不动」，而且 v-main 的顶部偏移只算了顶栏，还会再和它重叠一次。
        extension 槽由 Vuetify 自己算高度并同步给 v-main。
      -->
      <template #extension>
        <v-tabs
          v-if="status === 'authenticated'"
          :model-value="activeNav"
          class="nav-tabs"
          density="compact"
          @update:model-value="go"
        >
          <v-tab v-for="item in navItems" :key="item.value" :value="item.value" :prepend-icon="item.icon">
            {{ item.title }}
          </v-tab>
        </v-tabs>
      </template>
    </v-app-bar>

    <v-main>
      <v-container :class="['app-main', { 'app-main-wide': view.mode === 'batch' || view.mode === 'tools' || view.mode === 'registry' || view.mode === 'users' }]">
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
          <ToolsPanel v-else-if="view.mode === 'tools'" @close="view = { mode: 'list' }" />
          <WsiRegistryPanel v-else-if="view.mode === 'registry'" @close="view = { mode: 'list' }" />
          <UserAdminPanel v-else-if="view.mode === 'users'" @close="view = { mode: 'list' }" />
          <MapManagerPanel v-else-if="view.mode === 'map'" @close="view = { mode: 'list' }" />
        </template>
      </v-container>
    </v-main>

    <!-- 任何登录用户都能改自己的密码，与管理员面板无关。 -->
    <ChangePasswordDialog v-model="passwordOpen" />
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

/* 导航条在顶栏的 extension 区里。背景是浅色，但 `.app-bar` 上的
   `color:#fff !important` 会一路继承进 extension —— 上一版正是这样变成
   "白底白字、整行看不见"。这里必须显式把文字颜色改回深色，不能指望继承。
   v-tab 自身的颜色由 Vuetify 的 color/oncolor 控制，这里只兜住容器文字。 */
.nav-tabs {
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  padding: 0 1rem;
  flex: 1 1 auto;
  height: 48px;
  color: #334155 !important;
}

.nav-tabs :deep(.v-tab) {
  color: #475569;
  opacity: 1;
}

.nav-tabs :deep(.v-tab--selected) {
  color: #1d4ed8;
}

.app-main {
  max-width: 1200px;
  padding: 2rem;
}

/* The batch wizard needs the width for wide grids. */
.app-main-wide {
  max-width: 1500px;
}
</style>