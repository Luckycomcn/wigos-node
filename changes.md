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
| `frontend/src/components/StationsList.vue` | 90–120 | A Publishing column shows each station's latest publication status, so "the station record was saved" and "the change reached WIS2" are no longer the same thing on screen. Refreshed every 5 s while a record is pending or processing, and it stops when the status settles or the page is left. |
| `frontend/src/components/StationsList.vue` | 214–221 | A station with no status the user may see gets no chip rather than a placeholder; if the statuses cannot be loaded at all, the list still renders. |

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
| `frontend/src/i18n/locales/en.js` | 121 | Added the Publishing column heading. |
| `frontend/src/i18n/locales/zh-CN.js` | 117 | Added the Publishing column heading (`发布`). |

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
| `frontend/src/components/StationsList.test.js` | 44–102 | Publishing status: the chip per station, the absent chip, the list surviving a failed status load, the refresh stopping once a status settles, and the watcher being cleared when the page is left. |
| `frontend/src/icons.test.js` | 1–73 | Collects every `mdi-*` name from the source and checks it against the glyphs the icon font actually provides, ignoring names that only appear in comments. A missing name is invisible at build time, type-check time and to every other test — the item simply renders with an empty gap. |

## Validation status

The frontend suite passes in full: 20 files, 247 tests. Running it needed Node
22 — `undici` 8.12.1, pulled in by `jsdom` 30.1.2, needs it, and on Node 20 those
eight files fail to load at all. They were reporting as "8 errors" alongside a
green test count, which hid 19 real failures behind them; the count is now the
whole suite.

The icon test was checked against its own subject: injecting a missing name
makes it fail, restoring the name makes it pass again.

The production build was run with `--base=/feature/` and the output inspected:
the Import / export icon is present, no unknown `mdi-*` name remains, the
Publishing column and its chip text are in the bundle, and the shared app bar
button rule is emitted as
`.app-bar-user.v-btn{background:#ffffff29;border:1px solid rgba(255,255,255,.42)}`.

The API was checked live: `GET /api/publications/` returns 200 with a page of
results, `GET /api/publications/latest/` returns 200 with the per-station map the
column reads, and the retry endpoint is routed.

Browser and device verification across viewport widths is still pending.