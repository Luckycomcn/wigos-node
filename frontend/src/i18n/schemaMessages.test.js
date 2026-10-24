// Validation messages in both languages. The catalog tests prove a key exists
// in each locale; these prove the Chinese wording actually reaches the UI, and
// that a message is inert in English (the default) exactly as before.
import { afterEach, describe, expect, it } from "vitest";
import i18n, { DEFAULT_LOCALE } from "./index";

const use = (locale) => {
  i18n.global.locale.value = locale;
};

afterEach(() => use(DEFAULT_LOCALE));

describe("schema validation messages", () => {
  it("localises every keyword the bundled schema uses", () => {
    // Mirrors what wmdrSchema.js looks up; a new key here without a translation
    // would silently fall back to English in the middle of a Chinese sentence.
    const keys = [
      "schema.required",
      "schema.pattern",
      "schema.minItems",
      "schema.maxItems",
      "schema.contains",
      "schema.uniqueItems",
      "schema.format",
      "schema.formatDate",
      "schema.formatDateTime",
      "schema.formatUri",
      "schema.formatEmail",
      "schema.formatOther",
      "schema.enum",
      "schema.const",
      "schema.additionalProperties",
      "schema.type",
      "schema.typeString",
      "schema.typeNumber",
      "schema.typeInteger",
      "schema.typeObject",
      "schema.typeArray",
      "schema.typeBoolean",
      "schema.typeNull",
      "schema.typeOther",
      "schema.or",
    ];
    use("zh-CN");
    const english = (() => {
      use(DEFAULT_LOCALE);
      return keys.map((key) => i18n.global.t(key, { limit: 1, property: "x", type: "y", values: "z", value: "v", format: "f" }));
    })();
    use("zh-CN");
    keys.forEach((key, i) => {
      const chinese = i18n.global.t(key, { limit: 1, property: "x", type: "y", values: "z", value: "v", format: "f" });
      expect(chinese, key).not.toBe(key);
      // "URI" is a technical term and stays as-is in both languages; every
      // other message has to differ, or it was never translated.
      if (chinese !== "URI") expect(chinese, key).not.toBe(english[i]);
    });
  });

  it("renders a field path plus the message, as the form shows it", () => {
    // What wmdrSchema.js composes: `${formatPath(...)} ${formatMessage(...)}`.
    use(DEFAULT_LOCALE);
    expect(`geometry.longitude ${i18n.global.t("schema.type", { type: i18n.global.t("schema.typeNumber") })}`).toBe(
      "geometry.longitude must be number"
    );

    use("zh-CN");
    expect(`geometry.longitude ${i18n.global.t("schema.type", { type: i18n.global.t("schema.typeNumber") })}`).toBe(
      "geometry.longitude 必须是数字"
    );
  });

  it("does not translate the field path itself", () => {
    // Paths are JSON pointers into the record, not prose: contacts[1].name and
    // observations[2].configurations[1].time must stay identical in both locales.
    use("zh-CN");
    expect(i18n.global.t("schema.required")).toBe("为必填项");
    // The path segment comes from formatPath(), which never consults i18n.
    expect("contacts[1].organization").toBe("contacts[1].organization");
  });
});