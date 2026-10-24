import { computed, ref } from "vue";
import { DEFAULT_LOCALE, LOCALES, isImplemented, localeLabel, storedLocale } from "../i18n";
import i18n from "../i18n";

// The chosen language and the language the UI is actually drawn in. They differ
// while the chosen one has no translation yet, which is what the notice reports.
const selected = ref(storedLocale());
const active = computed(() => (isImplemented(selected.value) ? selected.value : DEFAULT_LOCALE));
const pending = computed(() => (isImplemented(selected.value) ? null : localeLabel(selected.value)));

i18n.global.locale.value = active.value;

export function useLocale() {
  function setLocale(code) {
    if (!LOCALES.some((locale) => locale.code === code)) return;
    selected.value = code;
    i18n.global.locale.value = isImplemented(code) ? code : DEFAULT_LOCALE;
    try {
      window.localStorage.setItem("wigos.locale", code);
    } catch {
      // Private mode: the choice just isn't remembered.
    }
  }

  return {
    locales: LOCALES,
    selected,
    active,
    pending,
    setLocale,
    isImplemented,
    label: localeLabel,
  };
}
