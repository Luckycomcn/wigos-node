// The API answers in English prose; these prove the common failures reach a
// Chinese user in Chinese, and that English is untouched.
import { afterEach, describe, expect, it } from "vitest";
import i18n, { DEFAULT_LOCALE } from "./index";
import { backendMessage, hasBackendMessage } from "./backendMessages";

const use = (locale) => {
  i18n.global.locale.value = locale;
};

afterEach(() => use(DEFAULT_LOCALE));

describe("backendMessage", () => {
  it("translates the messages the API actually sends", () => {
    use("zh-CN");
    expect(backendMessage("Station 3 not found")).toBe("未找到台站 3。");
    expect(backendMessage("Station 3 not found.")).toBe("未找到台站 3。");
    expect(backendMessage("Invalid username or password.")).toBe("用户名或密码不正确。");
    expect(backendMessage("The record is not valid against the WMDR2 schema.")).toBe("记录不符合 WMDR2 schema。");
    expect(backendMessage("Provide one or more numeric station_id parameters.")).toBe(
      "请至少提供一个数字型 station_id 参数。"
    );
  });

  it("keeps the value a message carries", () => {
    use("zh-CN");
    expect(backendMessage("WIGOS identifier '0-756-0-AUTOTEST01' is already in use in another station")).toBe(
      "WIGOS 标识符「0-756-0-AUTOTEST01」已被其他台站使用。"
    );
    expect(backendMessage("At most 200 stations can be read at once.")).toBe("一次最多只能读取 200 个台站。");
  });

  it("translates the permission message's action as well", () => {
    use("zh-CN");
    expect(
      backendMessage("You do not have permission to update a station for the issuer of identifier 756.")
    ).toBe("您无权为签发机构 756 更新台站。");
    expect(
      backendMessage("You do not have permission to create a station for the issuer of identifier 20000.")
    ).toBe("您无权为签发机构 20000 创建台站。");
  });

  it("passes English through untouched", () => {
    use("en");
    expect(backendMessage("Station 3 not found")).toBe("Station 3 not found");
  });

  it("shows an unrecognised message as it arrived rather than hiding it", () => {
    use("zh-CN");
    // A rewording upstream must still be readable: a generic "request failed"
    // would be worse than English prose.
    expect(backendMessage("Some new backend wording.")).toBe("Some new backend wording.");
    expect(hasBackendMessage("Some new backend wording.")).toBe(false);
  });

  it("returns null when there is nothing to show", () => {
    use("zh-CN");
    expect(backendMessage(undefined)).toBeNull();
    expect(backendMessage("")).toBeNull();
    expect(backendMessage(null)).toBeNull();
  });
});