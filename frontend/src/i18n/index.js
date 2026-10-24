import { createI18n } from "vue-i18n";
import en from "./locales/en";
import zhCN from "./locales/zh-CN";

// Languages offered in the switcher. `implemented: false` entries are listed
// but their UI is not translated yet: the app falls back to English and says so.
export const LOCALES = [
  { code: "en", label: "English", implemented: true },
  { code: "zh-CN", label: "中文", implemented: true },
  { code: "fr", label: "Français", implemented: false },
  { code: "ru", label: "Русский", implemented: false },
  { code: "ar", label: "العربية", implemented: false },
  { code: "es", label: "Español", implemented: false },
];

const STORAGE_KEY = "wigos.locale";
export const DEFAULT_LOCALE = "en";

export const isImplemented = (code) => LOCALES.some((locale) => locale.code === code && locale.implemented);
export const localeLabel = (code) => LOCALES.find((locale) => locale.code === code)?.label || code;

// A stored locale that the browser no longer offers (or that we dropped) falls
// back to English rather than leaving the app in an unknown language.
export function storedLocale() {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return LOCALES.some((locale) => locale.code === saved) ? saved : DEFAULT_LOCALE;
  } catch {
    return DEFAULT_LOCALE;
  }
}

const i18n = createI18n({
  legacy: false,
  locale: storedLocale(),
  fallbackLocale: DEFAULT_LOCALE,
  messages: { en, "zh-CN": zhCN },
  // A missing key is a bug in the catalog, not a runtime error: it renders as
  // the key itself and logs once in development.
  missingWarn: import.meta.env?.DEV ?? false,
  fallbackWarn: false,
});

export default i18n;
