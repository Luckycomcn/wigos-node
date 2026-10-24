import { beforeEach, describe, expect, it } from "vitest";
import { createSSRApp, defineComponent, h, nextTick, watchEffect } from "vue";
import { renderToString } from "@vue/server-renderer";

// This file runs in the default node environment (no DOM). Only the parts of
// `window` that the locale modules touch are stubbed, and they are stubbed
// *before* the modules are imported, because `storedLocale()` reads
// localStorage the moment the i18n instance is created.
const store = new Map();
globalThis.window = {
  localStorage: {
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: (key) => store.delete(key),
    clear: () => store.clear(),
  },
};

const i18n = (await import("../i18n")).default;
const { DEFAULT_LOCALE, storedLocale } = await import("../i18n");
const { translate } = await import("../i18n/plain");
const { useFieldText } = await import("../i18n/keys");
const { useLocale } = await import("../composables/useLocale");

// The composable keeps module-level state on purpose (one choice per session),
// so every test starts from English.
const { selected, active, pending, setLocale } = useLocale();

beforeEach(() => {
  store.clear();
  setLocale(DEFAULT_LOCALE);
});

describe("useLocale", () => {
  it("starts in English with nothing pending", () => {
    expect(selected.value).toBe("en");
    expect(active.value).toBe("en");
    expect(pending.value).toBeNull();
    expect(translate("app.title")).toBe("WMDR Station Record Builder");
  });

  it("switches the whole UI to Chinese and remembers the choice", () => {
    setLocale("zh-CN");
    expect(selected.value).toBe("zh-CN");
    expect(active.value).toBe("zh-CN");
    expect(pending.value).toBeNull();
    // The vue-i18n instance is what components read through useI18n().
    expect(i18n.global.locale.value).toBe("zh-CN");
    expect(translate("app.title")).toBe("WMDR 台站记录构建器");
    expect(store.get("wigos.locale")).toBe("zh-CN");
  });

  it("keeps English but names the language while it is untranslated", () => {
    setLocale("fr");
    // The choice sticks, so the notice can explain it, but the UI stays English.
    expect(selected.value).toBe("fr");
    expect(active.value).toBe("en");
    expect(pending.value).toBe("Français");
    expect(i18n.global.locale.value).toBe("en");
    expect(translate("app.title")).toBe("WMDR Station Record Builder");
    // And both the tag and the notice are translatable themselves.
    expect(translate("locale.pending")).toBe("(to be developed)");
    expect(translate("locale.pendingNotice", { language: "Français" })).toContain("Français");
    setLocale("zh-CN");
    expect(translate("locale.pending")).toBe("（待开发）");
    expect(translate("locale.pendingNotice", { language: "Русский" })).toContain("Русский");
  });

  it("ignores a language code the app does not offer", () => {
    setLocale("xx");
    expect(selected.value).toBe("en");
  });

  it("returns to Chinese after a detour through an untranslated language", () => {
    setLocale("zh-CN");
    setLocale("ru");
    expect(active.value).toBe("en");
    setLocale("zh-CN");
    expect(active.value).toBe("zh-CN");
    expect(pending.value).toBeNull();
  });
});

describe("the remembered choice", () => {
  it("survives a reload and is read back by storedLocale()", () => {
    setLocale("zh-CN");
    expect(storedLocale()).toBe("zh-CN");
  });

  it("falls back to English for a language the build no longer ships", () => {
    store.set("wigos.locale", "de");
    expect(storedLocale()).toBe("en");
  });
});

describe("field labels carried as message keys", () => {
  // A component that labels a field the way fieldDefs.js does: the prop carries
  // a message key and the component resolves it in setup. Rendered through the
  // server renderer so no DOM is needed.
  const FieldLabel = defineComponent({
    props: { label: { type: String, required: true } },
    setup(props) {
      const text = useFieldText();
      return () => h("span", text(props.label));
    },
  });

  const render = async (label) => {
    const app = createSSRApp(FieldLabel, { label });
    app.use(i18n);
    return renderToString(app);
  };

  it("renders in the active language and re-renders after a switch", async () => {
    expect(await render("field.date")).toBe("<span>Date</span>");

    setLocale("zh-CN");
    expect(await render("field.date")).toBe("<span>日期</span>");

    setLocale("en");
    expect(await render("field.date")).toBe("<span>Date</span>");
  });

  it("passes through text that is not a message key", async () => {
    expect(await render("Station name")).toBe("<span>Station name</span>");
  });

  it("binds labels to the locale reactively, which is what repaints the form", async () => {
    // useFieldText() resolves through the global composer, so tracking that
    // composer is what makes every label in a rendered form follow the switch.
    const seen = [];
    const stop = watchEffect(() => seen.push(i18n.global.t("field.date")));
    expect(seen).toEqual(["Date"]);

    setLocale("zh-CN");
    await nextTick();
    expect(seen).toEqual(["Date", "日期"]);

    setLocale("en");
    await nextTick();
    expect(seen).toEqual(["Date", "日期", "Date"]);
    stop();
  });
});
