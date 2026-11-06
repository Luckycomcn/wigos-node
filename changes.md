# Changes

## Changes made

Line numbers refer to the current versions of these files and may shift as
further changes are made.

| File | Lines | Amendment |
|---|---:|---|
| `frontend/src/App.vue` | 37–39, 112–114 | Replaced hard-coded sidebar titles with translation keys and renders them through `t()`. |
| `frontend/src/App.vue` | 93–100, 210–224 | Grouped email and logout, separated that group from the locale control, and added the divider and spacing. |
| `frontend/src/components/LocaleSwitcher.vue` | 17–25 | Uses a globe icon and hides the locale text at narrow viewport sizes; the accessible label remains. |
| `frontend/src/components/LocaleSwitcher.vue` | 47–50 | Sets the locale button text color to white (`#fff`) to address the reported contrast issue. |
| `frontend/src/i18n/locales/en.js` | 10–13 | Added English sidebar labels. |
| `frontend/src/i18n/locales/zh-CN.js` | 9–12 | Added Chinese sidebar labels (`台站`, `发布`). |
| `frontend/src/App.test.js` | 75–91, 111–116 | Added coverage for Chinese sidebar labels, header grouping, and selector visibility before login. |
| `frontend/src/App.test.js` | 42–45 | Resets the locale to English before each test. |

## Validation status

The focused frontend test command could not run because the sandbox denied
access to Docker's socket. The whitespace check was also blocked by a sandbox
restriction while Git attempted to access Xcode system files. Browser/device
verification is still pending.

Add browser/device details, screenshots, and further verification results here
after testing.
