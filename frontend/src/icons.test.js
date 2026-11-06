// @vitest-environment node
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

// 图标名写错（或写了一个当前 @mdi/font 版本里根本没有的名字）不会报错，
// 也不会崩 —— 只是渲染成空白字形，页面上表现为"这一项没有图标"。这种缺陷
// 类型检查、单测、构建全都拦不住，只有肉眼看页面才发现，所以在这里断言：
// 源码里出现的每个 mdi-* 都必须在字体 CSS 里真的有定义。

const SRC = resolve(__dirname);
const FONT_CSS = resolve(
  __dirname,
  "../node_modules/@mdi/font/css/materialdesignicons.css"
);

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      walk(path, out);
    } else if (/\.(vue|js)$/.test(name) && !/\.test\.js$/.test(name)) {
      out.push(path);
    }
  }
  return out;
}

function stripComments(text) {
  // 注释里会提到图标名（例如解释"某个名字并不存在"），那不是引用，
  // 不能当成"这个图标被用了"来断言，否则解释性注释反而把测试弄红。
  return text
    .replace(/<!--[\s\S]*?-->/g, "")          // Vue template comments
    .replace(/\/\*[\s\S]*?\*\//g, "")         // block comments
    .replace(/(^|[^:])\/\/.*$/gm, "$1");      // line comments (leave urls alone)
}

function collectIconNames() {
  const used = new Map(); // name -> files that mention it
  for (const file of walk(SRC)) {
    const text = stripComments(readFileSync(file, "utf8"));
    for (const m of text.matchAll(/\bmdi-[a-z0-9-]+/g)) {
      const name = m[0];
      if (!used.has(name)) used.set(name, []);
      used.get(name).push(file.replace(SRC + "/", ""));
    }
  }
  return used;
}

describe("Material Design Icons", () => {
  it("only uses icon names the bundled font actually defines", () => {
    const css = readFileSync(FONT_CSS, "utf8");
    const missing = [];
    for (const [name, files] of collectIconNames()) {
      // The font declares each icon as `.mdi-foo::before { content: "\F...."; }`
      if (!css.includes(`.${name}::before`)) {
        missing.push(`${name} (used in ${[...new Set(files)].join(", ")})`);
      }
    }
    expect(missing).toEqual([]);
  });

  it("gives the import/export entry an icon that exists", () => {
    // 回归：这一项曾用 `mdi-database-arrow-up-down`，@mdi/font 7.4.47 里没有，
    // 于是左侧导航第三项一直没有图标。
    const app = readFileSync(join(SRC, "App.vue"), "utf8");
    const match = app.match(/mode:\s*"tools"[^}]*icon:\s*"([^"]+)"/);
    expect(match, 'the import/export nav item should declare an icon').toBeTruthy();

    const css = readFileSync(FONT_CSS, "utf8");
    expect(css.includes(`.${match[1]}::before`)).toBe(true);
  });
});