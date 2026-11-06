<script setup>
import { computed, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { listPublications } from "./api";
import LoginPage from "./components/LoginPage.vue";
import PublicationsPage from "./components/PublicationsPage.vue";
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
// 地方可以长期停留"的页面。现在它们各占一个页面。
const view = ref({ mode: "list" });
const passwordOpen = ref(false);
// Station IDs ticked in the list; kept here so they survive the batch wizard.
const selected = ref(new Set());

const isStaff = computed(() => Boolean(user.value?.is_staff));

// 左侧导航项：与英文版一致，只放三块"日常操作"——我的台站、发布、导入导出。
// 用户管理 / WSI 注册表 / 地图管理是"配置性质、偶尔进一次"的管理动作，
// 统一收进右上角的「管理」菜单，避免导航栏和菜单出现重复入口。
// 标题走 t() 而不是存成裸键名，切换语言时不用重新计算列表。
const NAV_ITEMS = computed(() => [
  { mode: "list", title: t("nav.stations"), icon: "mdi-map-marker-multiple" },
  { mode: "publications", title: t("nav.publications"), icon: "mdi-history" },
  // `mdi-database-arrow-up-down` 不在 @mdi/font 7.4.47 里，写了也是空白
  // 字形，页面上看起来就是"这一项没有图标"。换成确实存在的双向箭头。
  { mode: "tools", title: t("nav.tools"), icon: "mdi-swap-horizontal" },
]);

// 侧栏只服务于上面这三页；表单、批量向导、以及从「管理」菜单进入的面板页
// 都自带返回入口，和英文版对表单/向导的处理保持一致。
const showNav = computed(
  () => status.value === "authenticated" && NAV_ITEMS.value.some((item) => item.mode === view.value.mode)
);
// null: open on large screens, closed on small ones (Vuetify's default)
const navOpen = ref(null);

// 当前高亮的导航项：新建/编辑/批量都属于"我的台站"这个区。
const activeNav = computed(() =>
  ["new", "edit", "batch"].includes(view.value.mode) ? "list" : view.value.mode
);

function go(mode) {
  view.value = { mode };
}

// Failures someone can still act on, on the Publishing item. It only shows with
// the sidebar, so it is only kept up to date then.
const FAILURES_REFRESH_MS = 30000;
const failures = ref(0);
let failuresTimer = null;
let failuresRequests = 0;

async function refreshFailures() {
  const request = ++failuresRequests;
  try {
    const { count } = await listPublications({ attention: 1, limit: 1 });
    // A slower, older answer must not replace a newer one.
    if (request === failuresRequests) failures.value = count;
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
    <v-app-bar class="app-bar" height="100" flat>
      <template v-if="showNav" #prepend>
        <v-app-bar-nav-icon :aria-label="t('nav.toggleMenu')" @click="navOpen = !navOpen" />
      </template>
      <img class="app-bar-logo" src="./assets/img/logo.png" alt="WMO logo" />
      <div class="app-bar-title">
        <h1>{{ t("app.title") }}</h1>
        <!-- On narrower screens it would run into the dark part of the banner. -->
        <p class="d-none d-lg-block">{{ t("app.subtitle") }}</p>
      </div>
      <template #append>
        <!--
          分成两组：账号相关（邮箱 / 「管理」 / 「退出」）在左，语言切换在右，
          中间由 .app-bar-locale 的左边框隔开。语言切换是全局设置、与登录状态
          无关，未登录时也照常显示，所以它不能放进 v-if 里。
        -->
        <div class="app-bar-actions">
          <div v-if="status === 'authenticated'" class="app-bar-account">
            <span class="app-bar-user">{{ user.email || user.username }}</span>
            <v-divider vertical class="app-bar-account-divider" aria-hidden="true" />
            <!--
              用户管理 / WSI 注册表 / 地图管理 / 修改密码都是"配置性质、偶尔进一次"
              的动作，统一收进「管理」菜单，语义清楚，也不会随功能增加把顶栏挤爆。
            -->
            <v-menu>
              <template #activator="{ props: menuProps }">
                <v-btn
                  v-bind="menuProps"
                  class="app-bar-user"
                  variant="tonal"
                  prepend-icon="mdi-cog-outline"
                  append-icon="mdi-menu-down"
                >
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
            <v-btn class="app-bar-user" variant="tonal" @click="handleLogout">{{ t("app.logout") }}</v-btn>
          </div>
          <div class="app-bar-locale">
            <LocaleSwitcher />
          </div>
        </div>
      </template>
    </v-app-bar>

    <!-- Before the drawer, so that it spans the whole width below it. -->
    <v-footer class="app-footer" height="12" app />

    <v-navigation-drawer v-if="showNav" v-model="navOpen">
      <v-list nav>
        <v-list-item
          v-for="item in NAV_ITEMS"
          :key="item.mode"
          :title="item.title"
          :prepend-icon="item.icon"
          :active="activeNav === item.mode"
          color="primary"
          @click="go(item.mode)"
        >
          <template v-if="item.mode === 'publications' && failures > 0" #append>
            <v-chip size="x-small" color="error" variant="flat" :aria-label="t('nav.failedCount', { count: failures })">{{ failures }}</v-chip>
          </template>
        </v-list-item>
      </v-list>
    </v-navigation-drawer>

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
            @changed="refreshFailures"
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
          <PublicationsPage v-else-if="view.mode === 'publications'" @changed="refreshFailures" />
        </template>
      </v-container>
    </v-main>

    <!-- 任何登录用户都能改自己的密码，与管理员面板无关。 -->
    <ChangePasswordDialog v-model="passwordOpen" />
  </v-app>
</template>

<style scoped>
/* The clouds, with the coloured stripe below them. The banner is white on the
   left and blue on the right, so the title is dark and the user's details light. */
.app-bar {
  background:
    url("./assets/img/wmo-foot.png") bottom / 100% 12px no-repeat,
    url("./assets/img/wmo-banner.png") top / 100% calc(100% - 12px) no-repeat,
    #fff !important;
  color: #003a78 !important;
  padding: 0 1rem;
}

.app-bar :deep(.v-toolbar__content) {
  padding-bottom: 12px;
}

.app-bar-logo {
  height: 72px;
  margin-right: 1rem;
}

.app-bar-title {
  text-shadow: 0 0 6px rgba(255, 255, 255, 0.9);
}

.app-bar-title h1 {
  color: #003a78;
  font-size: 1.4rem;
  font-weight: 700;
  margin: 0;
}

.app-bar-title p {
  margin: 0.25rem 0 0;
  color: #1f2f46;
  font-size: 0.9rem;
}

/* 顶栏右上角那几个元素（邮箱、语言切换、「管理」、「退出」）共用 .app-bar-user，
   具体配色在 app.css 里统一定义 —— 语言切换在子组件里，scoped 样式到不了，
   写在那边只能命中它的根元素，会出现"一颗白字、两颗深字"的错位。 */

.app-bar-actions,
.app-bar-account {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.app-bar-account-divider {
  border-color: rgba(255, 255, 255, 0.6);
  opacity: 1;
  height: 28px;
}

.app-bar-locale {
  border-left: 1px solid rgba(255, 255, 255, 0.6);
  padding-left: 1rem;
}

.app-footer {
  background: url("./assets/img/wmo-foot.png") center / 100% 100% no-repeat;
  padding: 0;
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