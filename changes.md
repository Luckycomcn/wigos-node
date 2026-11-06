# Changes

## Changes made

Line numbers refer to the current versions of these files and may shift as
further changes are made.

### Frontend: navigation and app bar

| File | Lines | Amendment |
|---|---:|---|
| `frontend/src/App.vue` | 51–63 | Replaced hard-coded sidebar titles with translation keys and renders them through `t()`, so the labels follow the language switch without rebuilding the list. |
| `frontend/src/App.vue` | 126–173, 287–303 | Grouped email, the Manage menu and logout, separated that group from the locale control, and added the divider and spacing. |
| `frontend/src/App.vue` | 180–196 | The main navigation moved from the top bar to a left drawer, matching the layout of the English original: My stations, Publishing, Import / export. |
| `frontend/src/App.vue` | 180–196 | Sidebar is shown only for those three pages; the station form, the batch wizard and the panels reached from the Manage menu carry their own way back. |
| `frontend/src/App.vue` | 51–56 | The Import / export item uses `mdi-swap-horizontal`. `mdi-database-arrow-up-down` is not part of `@mdi/font` 7.4.47, so the item rendered with a blank gap where its icon should be. |
| `frontend/src/App.vue` | 51–56 | User management, WSI registry, map settings and change password are collected into a Manage menu instead of competing with the main pages for room in the bar. |
| `frontend/src/components/LocaleSwitcher.vue` | 17–26 | Uses a globe icon and hides the locale text at narrow viewport sizes; the accessible label remains. |
| `frontend/src/components/LocaleSwitcher.vue` | 47–51 | The locale button joins the shared `app-bar-user` class so it is drawn like the buttons beside it. |
| `frontend/src/app.css` | 123–142 | Colour, background, border and hover for the whole group of app bar buttons are defined once, globally. |

The last two entries address the same defect from opposite ends. The locale
button is rendered by `LocaleSwitcher`, and the scoped styles in `App.vue` could
only reach its root element, so the button kept the tonal fill while the two
buttons next to it were dark — three buttons in a row, one of them a shade too
light. Moving the appearance into `app.css` gives all of them one definition.

### Localisation

| File | Lines | Amendment |
|---|---:|---|
| `frontend/src/i18n/locales/en.js` | 10–13 | Added English sidebar labels. |
| `frontend/src/i18n/locales/zh-CN.js` | 9–12 | Added Chinese sidebar labels (`台站`, `发布`, `导入导出`). |

### Backend

| File | Lines | Amendment |
|---|---:|---|
| `backend/config/urls.py` | 10–27 | The JSON 404 catch-all for `^api/.*$` is appended after every other `api/` route. It used to sit in the literal list, ahead of the `outbox` routes, which swallowed the whole of `/api/publications/` into a 404 — the publishing list, the per-station status chip and the retry button were all unreachable. |

### Docker

| File | Lines | Amendment |
|---|---:|---|
| `docker-compose.yml` | 25 | PostgreSQL is published on the standard port 5432, bound to the loopback interface only. The original `"5432:5432"` listened on every interface. |

### Tests

| File | Lines | Amendment |
|---|---:|---|
| `frontend/src/App.test.js` | 79–106 | Added coverage for the Import / export item, the Chinese sidebar labels, header grouping, and selector visibility before login. |
| `frontend/src/App.test.js` | 48–52 | Resets the locale to English before each test. |
| `frontend/src/icons.test.js` | 1–73 | Collects every `mdi-*` name from the source and checks it against the glyphs the icon font actually provides, ignoring names that only appear in comments. A missing name is invisible at build time, type-check time and to every other test — the item simply renders with an empty gap. |

## Validation status

The frontend test suite passes: 12 files, 181 tests, plus a pre-existing
`undici` load failure that affects 8 component tests and is unrelated to these
changes (the same 8 fail on the untouched baseline). The icon test was checked
against its own subject: injecting a missing name makes it fail, restoring the
name makes it pass again.

The production build was run with `--base=/feature/` and the output inspected:
the Import / export icon is present, no unknown `mdi-*` name remains, and the
shared app bar button rule is emitted as
`.app-bar-user.v-btn{background:#ffffff29;border:1px solid #ffffff42}`.

The publishing endpoints were checked live: `GET /api/publications/` returns
200 with a page of results, and the retry endpoint is routed.

Browser and device verification across viewport widths is still pending.