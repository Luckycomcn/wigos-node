# Changes

This branch is the upstream code plus the Chinese UI. Backend and functional
changes live on the `feature` branch; the full change log, including those, is
`changes.md` there.

## Changes made

Line numbers refer to the current versions of these files and may shift as
further changes are made.

| File | Lines | Amendment |
|---|---:|---|
| `frontend/src/App.vue` | 37–41 | Sidebar titles became translation keys rendered through `t()`, so they follow the language switch without rebuilding the list. |
| `frontend/src/App.vue` | 110–130, 205–220 | Email and logout are grouped, the locale control is separated from them, and a divider was added between the two. |
| `frontend/src/components/LocaleSwitcher.vue` | 17–25 | Uses a globe icon and hides the locale text at narrow viewport sizes; the accessible label remains. |
| `frontend/src/components/LocaleSwitcher.vue` | 47–50 | The locale button text is white, for contrast against the dark right half of the banner. |
| `frontend/src/i18n/locales/en.js` | 10–13 | English sidebar labels. |
| `frontend/src/i18n/locales/zh-CN.js` | 9–12 | Chinese sidebar labels (`台站`, `发布`). |
| `frontend/src/App.test.js` | 75–91, 111–116 | Coverage for the Chinese sidebar labels, the header grouping, and the selector being visible before login. |
| `frontend/src/App.test.js` | 42–45 | Resets the locale to English before each test. |

## Validation status

The frontend suite passes: 19 files, 243 tests.

Browser and device verification across viewport widths is still pending.