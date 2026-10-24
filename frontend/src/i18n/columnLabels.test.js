// Column headings in both languages. The catalog tests prove a key exists in
// each locale; these prove the heading a user actually reads changes when the
// language does.
//
// A `columns` array is built once, at module load. Translating a label there
// would compute it in whatever language the app started in and freeze it —
// which is exactly the bug the "Additional ID 1" headings had: three columns
// followed the switch and three did not. So `columns` carries keys, and the
// heading is resolved at render time by columnLabel().
import { afterEach, describe, expect, it } from "vitest";
import i18n, { DEFAULT_LOCALE } from "./index";
import { canonical, columnLabel } from "./plain";
import * as affiliations from "../batch/affiliations";
import * as configurations from "../batch/configurations";
import * as wigosIds from "../batch/wigosIds";

const use = (locale) => {
  i18n.global.locale.value = locale;
};

afterEach(() => use(DEFAULT_LOCALE));

const modules = { affiliations, configurations, wigosIds };
// Keys are what a module-level label must be. A literal string here means
// someone resolved the translation too early.
const allColumns = () => Object.values(modules).flatMap((mod) => mod.columns);

describe("batch grid headings", () => {
  it("keeps every column label as a message key, never a resolved string", () => {
    const literals = allColumns()
      .filter((column) => !/^[a-z]+\.[A-Za-z0-9]+$/.test(column.label))
      .map((column) => `${column.key}: ${JSON.stringify(column.label)}`);
    expect(literals).toEqual([]);
  });

  it("resolves a heading to Chinese and back without reloading", () => {
    const numbered = allColumns().filter((column) => column.labelParams);
    // The additional-WIGOS-ID columns are the only ones that number themselves;
    // they are also the ones that used to freeze.
    expect(numbered.length).toBeGreaterThan(0);

    use("en");
    const english = numbered.map((column) => columnLabel(column));
    use("zh-CN");
    const chinese = numbered.map((column) => columnLabel(column));
    use("en");
    const back = numbered.map((column) => columnLabel(column));

    expect(chinese).not.toEqual(english);
    expect(back).toEqual(english);
    // The parameter survives the switch — otherwise the headings collapse into
    // three identical "附加标识 {index}" strings.
    expect(new Set(chinese).size).toBe(chinese.length);
    expect(chinese[0]).not.toMatch(/\{index\}/);
  });

  it("translates every heading in both locales", () => {
    const untranslated = allColumns()
      .filter((column) => {
        use("en");
        const en = columnLabel(column);
        use("zh-CN");
        const zh = columnLabel(column);
        // A heading that cannot be looked up comes back as its own key, which is
        // what a missing catalog entry looks like.
        return en === zh || /^[a-z]+\.[A-Za-z0-9]+$/.test(zh);
      })
      .map((column) => column.key);
    expect(untranslated).toEqual([]);
  });

  it("still accepts the English heading in a spreadsheet, whatever the UI language", () => {
    // Import matches on the key, the English wording and the active wording.
    // canonical() must therefore ignore the active locale.
    use("zh-CN");
    const column = allColumns().find((col) => col.label === "col.currentWigosId");
    expect(column).toBeTruthy();
    expect(canonical(column.label)).toBe("Current WIGOS ID");
    expect(columnLabel(column)).not.toBe("Current WIGOS ID");
  });
});