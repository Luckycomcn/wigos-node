import { describe, expect, it } from "vitest";
import { codelistText, countryCodes, hasCodelistText } from "./codelistNames";

const opt = (code, label) => ({ code, label, id: `http://codes.wmo.int/wmdr/X/${code}` });

describe("codelistText", () => {
  it("translates the closed lists", () => {
    expect(codelistText("FacilityType", opt("landFixed", "Land (fixed)"), "zh-CN")).toBe("陆地（固定）");
    expect(codelistText("WMORegion", opt("africa", "Africa"), "zh-CN")).toBe("非洲");
    expect(codelistText("ReportingStatus", opt("operational", "Operational"), "fr")).toBe("Opérationnelle");
  });

  it("translates country names from the ISO 3166 notation", () => {
    expect(codelistText("ISO3166", opt("156", "China"), "zh-CN")).toBe("中国");
    expect(codelistText("TerritoryName", opt("CHE", "Switzerland"), "zh-CN")).toBe("瑞士");
    expect(codelistText("ISO3166", opt("20000", "WWW land-station (SI=0)"), "zh-CN")).toContain("WWW");
  });

  it("composes unit labels from their words", () => {
    expect(codelistText("unit", opt("m", "metre"), "zh-CN")).toBe("米");
    expect(codelistText("unit", opt("m_s-1", "metres per second"), "zh-CN")).toBe("米/秒");
    expect(codelistText("unit", opt("hPa_h-1", "hectopascals per hour"), "zh-CN")).toBe("百帕/小时");
    expect(codelistText("unit", opt("W_m-2_sr-1", "watts per square metre per steradian"), "zh-CN")).toBe("瓦特/平方米/球面度");
    expect(codelistText("unit", opt("cm-3", "per cubic centimetre"), "zh-CN")).toBe("每立方厘米");
    expect(codelistText("unit", opt("ug_m-3_25C", "micrograms per cubic metre at 25 degrees"), "zh-CN")).toBe("微克/立方米（25 度下）");
    expect(codelistText("unit", opt("V2.m-2.Hz-1", "Volt squared per metre squared per Hertz"), "zh-CN")).toBe("伏特平方/米的平方/赫兹");
  });

  it("leaves the label alone when there is no translation", () => {
    // Latin taxa and chemical formulae: translating them would be wrong.
    expect(codelistText("ObservedVariableAtmosphere", opt("1", "Abies"), "zh-CN")).toBe("Abies");
    expect(codelistText("unit", opt("x", "furlongs per fortnight"), "zh-CN")).toBe("furlongs per fortnight");
    expect(hasCodelistText("unit", opt("x", "furlongs per fortnight"), "zh-CN")).toBe(false);
  });

  it("never translates the English UI", () => {
    expect(codelistText("FacilityType", opt("landFixed", "Land (fixed)"), "en")).toBe("Land (fixed)");
  });
});

describe("countryCodes", () => {
  it("gives a numeric issuer code its ISO alpha-3 as well", () => {
    expect(countryCodes("156")).toEqual(["156", "CHN"]);
    expect(countryCodes("756")).toEqual(["756", "CHE"]);
  });

  it("accepts an alpha-3 notation as it stands", () => {
    expect(countryCodes("CHE")).toEqual(["CHE"]);
  });

  it("leaves the WMO-local issuer codes alone", () => {
    // 20000+ are WWW land-station, GAW, GCW, ships, radar, space: no ISO code.
    expect(countryCodes("20000")).toEqual(["20000"]);
  });
});