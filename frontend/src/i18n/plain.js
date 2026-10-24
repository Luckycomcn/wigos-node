import i18n from "./index";
import { isMessageKey } from "./keys";
import en from "./locales/en";

// For modules that build strings outside a component (field definitions,
// summary helpers in a plain <script> block, batch column labels).
//
// Reading `locale` first is deliberate: it makes a render that calls translate()
// depend on the active language, so the UI re-renders when it changes — the same
// reactivity useI18n()'s `t` gets inside a component.
export const translate = (key, params) => {
  void i18n.global.locale.value;
  return i18n.global.t(key, params);
};

export const activeLocale = () => i18n.global.locale.value;

const lookup = (messages, key) => key.split(".").reduce((node, part) => (node && typeof node === "object" ? node[part] : undefined), messages);

// The English wording of a message key, whatever the UI language is. Used for
// things that must not change with the language — notably the column headers
// accepted when importing a spreadsheet, so a file exported in one language
// still imports in another.
export const canonical = (value) => (isMessageKey(value) ? lookup(en, value) ?? value : value);
