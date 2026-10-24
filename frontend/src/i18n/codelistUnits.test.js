import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { parseCsvRows } from "../csv";
import { codelistText } from "./codelistNames";

// How much of the unit codelist this layer actually reaches, measured against
// the real CSV the backend serves rather than a sample. A composition gap is a
// word missing from UNIT_WORDS/PLURALS, not a sentence missing from a list.
const rows = parseCsvRows(readFileSync(new URL("../../../backend/api/codelists/unit.csv", import.meta.url), "utf8"));
const units = rows.slice(1).map((row) => ({ code: row[4], label: row[3] }));

// Names that are already the same word in Chinese, so composing them is noise.
const translated = units.filter((unit) => codelistText("unit", unit, "zh-CN") !== unit.label);

describe("unit codelist coverage", () => {
  it("composes nearly every label", () => {
    // Measured: 284 of 286. The two left are "metre(s) to the two thirds
    // power per second", whose notations m(2_3)_s-1 / m(2.3-1).s-1 suggest
    // the label pushes the Wiktionary reading of "two thirds power" past
    // what a unit table should express; they stay English rather than become
    // a guess.
    expect(translated.length).toBeGreaterThanOrEqual(284);
  });

  it("leaves no label half-translated", () => {
    // A half-translated label ("米 per second") would be worse than English.
    const mixed = translated.filter((unit) => / per |\bper\b/.test(codelistText("unit", unit, "zh-CN")));
    expect(mixed).toEqual([]);
  });

  it("never leaves a stray English word in a translated label", () => {
    // Every composed label is Chinese characters, digits, punctuation and the
    // odd Latin symbol (°C, pH), never an English word.
    const LEFTOVER = /\b(?:per|square|cubic|metre|metres|second|seconds|hour|hours|degree|degrees|kilogram|kilogram)\b/i;
    const left = translated.filter((unit) => LEFTOVER.test(codelistText("unit", unit, "zh-CN")));
    expect(left).toEqual([]);
  });
});