import { useI18n } from "vue-i18n";

// Field definitions (fieldDefs.js, ContactsField, ObservationsField, …) are
// plain data built outside a component, so they can't call t() themselves.
// Their translatable strings are written as message keys instead ("field.title",
// "ph.url") and are translated where they are rendered. Anything else —
// "e.g. text/html", "+41791234567" — is passed through unchanged.
const KEY = /^(field|ph|opt|op|step|col)\.[A-Za-z0-9]+$/;

export const isMessageKey = (value) => typeof value === "string" && KEY.test(value);

export function useFieldText() {
  const { t } = useI18n();
  return (value) => (isMessageKey(value) ? t(value) : value);
}
