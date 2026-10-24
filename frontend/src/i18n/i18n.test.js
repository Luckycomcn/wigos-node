import { describe, expect, it } from "vitest";
import en from "./locales/en";
import zhCN from "./locales/zh-CN";
import { LOCALES, DEFAULT_LOCALE, isImplemented } from "./index";

// Flattens { a: { b: "x" } } to ["a.b"].
const keysOf = (messages, prefix = "") =>
  Object.entries(messages).flatMap(([key, value]) =>
    value && typeof value === "object" ? keysOf(value, `${prefix}${key}.`) : [`${prefix}${key}`]
  );

describe("message catalogs", () => {
  const enKeys = keysOf(en).sort();

  it("has no duplicate-free surprises: every key is a non-empty string", () => {
    expect(enKeys.length).toBeGreaterThan(0);
    expect(new Set(enKeys).size).toBe(enKeys.length);
  });

  it("translates exactly the keys English defines", () => {
    // A key added to en.js and forgotten in zh-CN would silently fall back to
    // English; a key only in zh-CN would never render. Both are caught here.
    expect(keysOf(zhCN).sort()).toEqual(enKeys);
  });

  it("keeps every placeholder of the English message", () => {
    const placeholders = (text) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    const flat = (messages, prefix = "") =>
      Object.fromEntries(
        Object.entries(messages).flatMap(([key, value]) =>
          value && typeof value === "object"
            ? Object.entries(flat(value, `${prefix}${key}.`))
            : [[`${prefix}${key}`, value]]
        )
      );
    const enFlat = flat(en);
    const zhFlat = flat(zhCN);
    for (const key of Object.keys(enFlat)) {
      expect(placeholders(zhFlat[key]), key).toEqual(placeholders(enFlat[key]));
    }
  });
});

describe("locale list", () => {
  it("ships English by default and offers Chinese as the other translation", () => {
    expect(DEFAULT_LOCALE).toBe("en");
    expect(isImplemented("en")).toBe(true);
    expect(isImplemented("zh-CN")).toBe(true);
  });

  it("lists the other UN official languages as not yet implemented", () => {
    const pending = LOCALES.filter((locale) => !locale.implemented).map((locale) => locale.code);
    expect(pending).toEqual(["fr", "ru", "ar", "es"]);
  });

  it("falls back to English for anything unimplemented", () => {
    expect(isImplemented("fr")).toBe(false);
    expect(isImplemented("xx")).toBe(false);
  });
});
