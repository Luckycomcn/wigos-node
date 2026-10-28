# Feature Branch — Detailed Change Log

**Branch**: `feature` (fork of `upstream` = `alhelguera/wigos-node` @ `vuetify-migration` / `c468012`)
**Scope**: 131 files changed, ~14,000 insertions, ~660 deletions vs upstream.
**Baseline audit**: this branch was built against a formal defect assessment that catalogued 26 defects (6 P0 / 11 P1 / 9 P2) in the English original. All 26 are addressed: 25 fixed, 1 consciously downgraded to an accepted residual risk (noted below).

The three MVP pillars defined in the node architecture brief — *sign in, create WMDR2 station records, publish them to the Global Catalogue* — were previously two of three (publishing had **no implementation at all**). This branch completes the third pillar and hardens the other two.

---

## 1. Defect fixes (26 catalogued items)

### P0 — blocking / security-critical (6)

| ID | Defect in upstream | Fix in feature |
|---|---|---|
| BUG-01 | Reverse migration `remove_stations` ran `Station.objects.all().delete()` — rolling back once would wipe **every** station in the database, not just demo rows. Reproduced in an isolated test database. | Migration rewired to delete only the WSI set seeded by that migration (resolved from `test_data/`); a no-op return when the demo data was never loaded. |
| BUG-02 | Migration `0004` reads `/app/api/codelists/ISO3166.csv` at module-import time — a container-only path. Outside Docker every `manage.py` command died on ImportError. | Path resolved via `__file__`; works under any prefix. |
| BUG-03 | Django admin user creation stored the password **in plaintext** (no `UserAdmin` configured) — accounts created in the admin could never log in. | `admin.py` rewritten around `UserAdmin` + `UserCreationForm` (two password fields, proper hashing). Verified: newly created users authenticate. |
| BUG-04 | Anonymous GET on `/api/my_issuer_of_identifiers/` returned HTTP 500 (attribute access on `AnonymousUser`). | Explicit `is_authenticated` guard → 401. Verified live. |
| BUG-05 | Following the official Quick-Start produced an exploitable instance by default: `DEBUG=True`, a committed placeholder `SECRET_KEY` accepted silently. | `DEBUG` defaults to false; empty or placeholder `SECRET_KEY` raises `ImproperlyConfigured` at startup. |
| BUG-23 | `.env.example` has **no** `CSRF_TRUSTED_ORIGINS`; the default allows only `:5173`. Any other port/host silently breaks every write operation with `403 CSRF Failed` — the UI stays clickable but nothing can be saved. Reproduced on a from-the-docs upstream instance. | Trusted origins are now derived (from `ALLOWED_HOSTS` × the node's web ports) with a loopback fallback when hosts is `*`; template now ships CORS/CSRF entries with comments. Verified by A/B: same write request → upstream 403, feature passes CSRF and hits business validation (400). |

### P1 — incorrect behaviour (11)

| ID | Defect | Fix |
|---|---|---|
| BUG-06 | Records could **never be deleted**: no `DELETE` method, no UI entry, `Station` not registered in admin. | `DELETE /api/wmdrv2/<id>` (owner or superuser only), delete button in the list, soft delete via archive; `Station` registered in admin. |
| BUG-07 | `/api/geojson/` accepted POST only (GET → 405) and was a hollow echo of the request body. | GET and POST both implemented against the database; returns a real `FeatureCollection`. |
| BUG-08 | Unknown `/api/…` paths returned an **HTML** 404 page — unparseable by the SPA. | JSON catch-all view with `path` and `hint`. |
| BUG-09 | Anonymous read of **all** data: `/api/my_stations/` returned every station without authentication; any record's full JSON was fetchable anonymously. | `my_stations` requires authentication (401 otherwise). Single-record anonymous read is retained deliberately for catalogue harvesting, with draft filtering added. |
| BUG-10 | List endpoint had no pagination or filtering; the front end pulled the full table (`items-per-page="-1"`). | `q` / `status` / `limit` / `offset` supported, `X-Total-Count` returned; out-of-range parameters clamped instead of 500. |
| BUG-11 | `populate_codelists` with no arguments crashes (`SystemExit 2`) on Python ≤ 3.11 (`nargs="*"` + `choices` argparse bug interaction). The official image survives only by pinning Python 3.12. | Combination removed; validation moved into `handle()`. `--if-missing` supported for offline runs. |
| BUG-12 | `requirements.txt` never mentions GDAL/GEOS — required native libraries for `django.contrib.gis`. Any non-Docker install fails at import. | Documented per-platform install paths plus `GDAL_LIBRARY_PATH` / `GEOS_LIBRARY_PATH` guidance appended to the requirements file. |
| BUG-13 | "Production" was dev servers: compose ran `manage.py runserver`, the front end ran a Vite dev server (source + HMR exposed). | Backend: gunicorn. Front end: two-stage build (node build → nginx serves `dist`). `db` port bound to 127.0.0.1. Verified on a real air-gapped host. |
| BUG-14 | API prose typo: "WMDv2 data … updated successfully." | Corrected to WMDR2 throughout; no residue. |
| BUG-24 | compose published PostgreSQL 5432 on 0.0.0.0 with the template's guessable password `app_password` — whole-segment database access. | Bind `127.0.0.1:5432:5432`; password placeholders now mandatory (`${POSTGRES_PASSWORD:?…}`) with warning comments. |
| BUG-26 | Migration `0011` hardcoded `create_superuser(username='admin', password='admin', …)` — every deployment from the docs ships a known-credential superuser. | Demo seeding is opt-in (`WIGOS_SEED_DEMO=true`); when seeded, the admin password comes from `WIGOS_SEED_ADMIN_PASSWORD` or a freshly generated `secrets.token_urlsafe(18)` printed once. |

### P2 — quality / maintainability (9)

| ID | Defect | Fix |
|---|---|---|
| BUG-15 | Debug `print()`s leaked to logs — including entire station records (contact details) during migrations. | Removed; migrations keep only content-free progress notes. |
| BUG-16 | `additional_wigos_identifiers` was `CharField(255)` with no uniqueness: 16+ identifiers → `DataError` surfaced as 500; check-then-write race allowed two stations to claim one identifier. | Column rebuilt as unbounded text (migration 0017; note: PostgreSQL cannot `ALTER TYPE` on a generated column, hence drop-and-recreate). **The concurrency race is retained as an accepted residual risk** — see §5. |
| BUG-17 | `editable_station_ids()` ran one object-permission query **per station**. | Batched into a single `values_list` over three columns. |
| BUG-18 | Station list: 2 columns, no search, no filters, no paging. | Debounced search (250 ms), status filter, server-side pagination; export counters use the true total. |
| BUG-19 | Mapbox token committed to the repo (shared WMO quota; hard dependency on `api.mapbox.com`, grey map offline). | Token via `VITE_MAPBOX_TOKEN` (upstream's public demo token remains the fallback so default behaviour matches upstream); plus a **multi-basemap registry** with a fully offline vector basemap — see §3.3. |
| BUG-20 | Font stylesheet linked to `fonts.googleapis.com` — degraded offline. | Links removed; system font stack (`PingFang SC`, `Microsoft YaHei`, `Noto Sans`). |
| BUG-21 | No login throttling whatsoever — unlimited password guessing. | Two gates: DRF anonymous rate throttle (30/min, flood protection) and a 15-minute-window failure lockout at 10 failures (`api/auth.py`, slow-guessing protection). **Discovered during this iteration and fixed on the spot:** with per-process caches the lockout weakened to "30 attempts allowed across 3 workers"; counters now live in `DatabaseCache` (shared across workers; `createcachetable` wired into startup). Measured: 40 guesses → 8 slips before, exactly 10 then blocked after. |
| BUG-22 | django-guardian's `AnonymousUser` row polluted the user table (empty username, `email='AnonymousUser'`) and occupied the unique email slot. | `ANONYMOUS_USER_NAME = None`, migration 0016 deletes the historical row, three query sites filter it; direct-by-id access returns 404. |
| BUG-25 | `.python-version` pinned 3.12 while `entrypoint.sh` called `populate_codelists` without arguments — a guaranteed crash (BUG-11) on system Python ≤ 3.11, with an argparse usage message that points nowhere near the real cause. | Version pin removed; entrypoint calls `--if-missing` and no longer aborts startup when codelists cannot refresh (offline-safe). |

---

## 2. New capabilities

### 2.1 Publishing (completes MVP pillar 3)
- **WNM (WIGOS Notification Message) generation** for create/update/deletion of WMDR2 records, following the WIS2 payload shape.
- Two transports, selectable via `WNM_PUBLISH_STRATEGY`: **HTTP** (`WNM_STORAGE_URL`, plus a node-side `/webstorage/` serving view for verification) and **MQTT** to a local WIS2 proxy (`paho-mqtt`; optional — absence reported as "channel unavailable", never a crash).
- **WSI allocation registry**: each `centre-id` is granted explicit WSI number ranges; every publish is checked against the registry and **refused locally (and logged) when out of range** — the "publishing authorisation" control. `WNM_REQUIRE_ALLOCATION=false` can relax this for bootstrapping legacy data.
- Publishes, refused publishes, and registry changes are all recorded in an **audit log** (API-level; admin browsing UI still open, see §5).
- `POST /api/wmdrv2/<id>/publish`, `GET /api/wmdrv2/<id>/publications/`, `GET /api/wsi/next/`.

### 2.2 Record lifecycle & data tools
- **Drafts**: `…/submit` transitions; drafts excluded from public harvesting.
- **Archive / restore** (soft delete) + **version history** with field-level **diff** between versions (`…/history/`, `…/history/diff`).
- **Batch**: `batch-create` (CSV ingest mapped to WMDR2), batch update, and **export in CSV / JSON / XML / GeoJSON** — all format-parameterised with permission rules preserved.
- **WMDR1 → WMDR2 migration import** (JSON).
- **Three-layer validation endpoint** (`/api/validate/`): JSON-schema, WMDR2 codelist membership, and cross-field consistency.
- **OGC API Records** endpoints: `/api/records/collections`, items with bbox/temporal filters, conformance class listing — the node can serve catalogue-style harvesting.
- Groups (`/api/groups/`), record templates (`/api/templates/`), data-quality grades (`/api/grades/`, per-station evaluation).
- **User administration** (`api/useradmin.py` + `UserAdminPanel.vue`): create/deactivate/reset-password/delete accounts, role display, self-lockout protection (an admin cannot delete or demote their own account), every change audited.
- `/api/health/` liveness endpoint.

### 2.3 UI / i18n (bilingual + Chinese-friendly)
- Full zh-CN translation with a language switcher persisted per browser (`wigos.locale`); covers API error prose, Leaflet control titles, codelist concept labels (stored in WMO English, displayed translated), spreadsheet-import column headings resolved at render time (files exported in one language import in the other), and a build-time guard that fails the build when a new schema keyword lacks translations.
- Navigation restructured: top bar keeps **My stations / Import–export**; all administrative actions (change password, user management, WSI registry, **map settings**) live in a single "Manage" menu — no duplicated entries; fixed a white-on-white tab bar regression caused by the app bar's inherited text colour.
- **Map settings panel** (`MapManagerPanel.vue`): switch the basemap live across all maps in the app — Mapbox (default, same as upstream, token overridable), Tianditu imagery/vector (China-licensed tiles; enabled by build-time `VITE_TIANDITU_TOKEN`, greyed out with the reason shown when not configured), an internal tile service via `VITE_TILE_URL`, or a fully **offline vector basemap** (Natural Earth 110m country polygons, 173 KB bundled into the app, zero external requests). Selection persists per browser; maps rebuild in place without losing the current view. A compliance note documents the 1:110M indicative boundary accuracy and recommends a licensed source for public-facing deployments in China.

---

## 3. Test & verification footprint

- Backend: **37 → 231 tests** (Django, run against real PostGIS). New suites for publishing, registry, user admin, drafts, history/diff, export, batch, OGC endpoints, CSRF derivation, throttle behaviour.
- Frontend: **179 vitest cases** (i18n catalogue consistency, codelist resolution, batch, intervals, WMDR mapping).
- End-to-end on a real headless browser against the production-shaped stack: three-version inspection suite (24 checks), navigation suite (22), user-admin suite (23), nav+map suite (13) — all green on the air-gapped deployment host.

## 4. Deployment

`docker-compose.yml` rewritten to production shape (gunicorn, built front end behind nginx, mandatory password, loopback-only db). Non-Docker layout (conda-run PostGIS + gunicorn + nginx, systemd-free control script) is what was actually validated on an offline intranet server; see the operator runbook that accompanies this branch.

## 5. Known limitations (honest list)

1. Publishing has only been exercised against the node-side HTTP view and local fakes — **no live WIS2 global-proxy co-tenancy test yet**.
2. `.env.example` (upstream template) still trails the ~17 variables this branch adds; comments here and the runbook compensate, but the file itself should be regenerated.
3. BUG-16's **concurrency race** on additional identifiers remains: two simultaneous writes can still claim the same identifier (field-size bug fixed; unique-constraint-with-retry deferred by design decision).
4. Contacts remain embedded per record — no standalone reusable Contact entity.
5. Audit log has an API but no dedicated browsing UI yet.
6. No OpenAPI/schema documentation for the API surface.
7. README still thin (this change log is the first addition).
8. Only English + Chinese shipped; fr/ru/ar/es are placeholders in the switcher.
