// Interval bounds as wmdr2-bundled.json allows them: a year, month or day, a
// UTC date and time, a UTC time of day, or ".." for an open bound. Affiliation
// and territory dates allow only days (`daysOnly`).
//
// Everything here is plain JavaScript with no Vue dependency, so the wording
// has an English default and is translated only when the caller passes a
// translator (`options.t`) — see the `FALLBACK` table at the bottom.

export const OPEN = "..";

const DAY_MS = 24 * 60 * 60 * 1000;
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const pad = (n) => String(n).padStart(2, "0");

// Month names and day orders differ per language, so a non-English locale
// formats its labels with Intl rather than the English table above.
const isEnglish = (locale) => !locale || locale.startsWith("en");

function monthLabel(year, month, locale) {
  if (isEnglish(locale)) return `${MONTHS[month - 1]} ${year}`;
  return new Intl.DateTimeFormat(locale, { year: "numeric", month: "long" }).format(new Date(Date.UTC(year, month - 1, 1)));
}

function dayLabel(year, month, day, locale) {
  if (isEnglish(locale)) return `${day} ${MONTHS[month - 1]} ${year}`;
  return new Intl.DateTimeFormat(locale, { year: "numeric", month: "long", day: "numeric" }).format(
    new Date(Date.UTC(year, month - 1, day))
  );
}

// A calendar date that exists (no 2020-02-30), as the UTC start of that day.
function utcDay(year, month, day) {
  const ms = Date.UTC(year, month - 1, day);
  const d = new Date(ms);
  return d.getUTCFullYear() === year && d.getUTCMonth() === month - 1 && d.getUTCDate() === day ? ms : null;
}

const validTime = (h, m, s) => h < 24 && m < 60 && s < 60;

// Each reader returns { label, from, to, scale } for a valid value: the period
// it covers ([from, to) in ms) on the "date" or "time of day" scale.
const READERS = [
  {
    kind: "year",
    pattern: /^(\d{4})$/,
    read: ([y]) => ({ label: String(y), from: Date.UTC(y, 0, 1), to: Date.UTC(y + 1, 0, 1) }),
  },
  {
    kind: "month",
    pattern: /^(\d{4})-(\d{2})$/,
    read: ([y, m], locale) =>
      m >= 1 && m <= 12 ? { label: monthLabel(y, m, locale), from: Date.UTC(y, m - 1, 1), to: Date.UTC(y, m, 1) } : null,
  },
  {
    kind: "day",
    pattern: /^(\d{4})-(\d{2})-(\d{2})$/,
    read: ([y, m, d], locale) => {
      const from = utcDay(y, m, d);
      return from == null ? null : { label: dayLabel(y, m, d, locale), from, to: from + DAY_MS };
    },
  },
  {
    kind: "datetime",
    pattern: /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?Z$/,
    read: ([y, mo, d, h, mi, s], locale) => {
      const day = utcDay(y, mo, d);
      if (day == null || !validTime(h, mi, s)) return null;
      const from = day + ((h * 60 + mi) * 60 + s) * 1000;
      return { label: `${dayLabel(y, mo, d, locale)}, ${pad(h)}:${pad(mi)}:${pad(s)} UTC`, from, to: from + 1000 };
    },
  },
  {
    kind: "time",
    pattern: /^T(\d{2})(?::(\d{2}))?(?::(\d{2}))?(?:\.\d+)?Z$/,
    scale: "time",
    read: ([h, m = 0, s = 0], locale, t) => {
      if (!validTime(h, m, s)) return null;
      const from = ((h * 60 + m) * 60 + s) * 1000;
      const clock = `${pad(h)}:${pad(m)}${s ? `:${pad(s)}` : ""}`;
      return { label: tr(t, "interval.timeOfDay", { clock }), from, to: from + 1000 };
    },
  },
];

// What a bound reads as: { kind: "empty" | "open" | "invalid" | <reader kind>, ... }.
export function readBound(value, { daysOnly = false, locale, t } = {}) {
  const text = (value ?? "").toString().trim();
  if (!text) return { kind: "empty" };
  if (text === OPEN) return { kind: "open" };
  for (const reader of READERS) {
    const match = reader.pattern.exec(text);
    if (!match) continue;
    if (daysOnly && reader.kind !== "day") return { kind: "invalid", message: tr(t, "interval.dayHelp") };
    const parts = match.slice(1).map((part) => (part === undefined ? undefined : Number(part)));
    const period = reader.read(parts, locale, t);
    if (!period) return { kind: "invalid", message: tr(t, "interval.invalid") };
    return { kind: reader.kind, scale: reader.scale || "date", ...period };
  }
  return { kind: "invalid", message: tr(t, daysOnly ? "interval.dayHelp" : "interval.formatHelp") };
}

// Why the interval is wrong as a whole, or null. Bounds are compared only on
// the same scale: 2020 to 2020 is fine (the end covers the whole year).
export function intervalError(start, end, options) {
  const from = readBound(start, options);
  const to = readBound(end, options);
  if (from.from == null || to.from == null || from.scale !== to.scale) return null;
  return to.to <= from.from ? tr(options?.t, "interval.endBeforeStart") : null;
}

const isOpen = (bound) => bound.kind === "open" || bound.kind === "empty";

// One line for a collapsed item, e.g. "Since January 2020, ongoing". Empty
// when neither bound is set; invalid bounds are shown as typed. A year or month
// end covers that whole period, so it reads "end of 2026", not "2026".
export function describeInterval(start, end, options) {
  const from = readBound(start, options);
  const to = readBound(end, options);
  const label = (bound, value) => bound.label || (value ?? "").toString().trim();
  const endLabel = ["year", "month"].includes(to.kind)
    ? tr(options?.t, "interval.endOf", { label: to.label })
    : label(to, end);
  if (isOpen(from) && isOpen(to)) return "";
  if (isOpen(from)) return tr(options?.t, "interval.until", { label: endLabel });
  if (isOpen(to)) return tr(options?.t, "interval.since", { label: label(from, start) });
  return tr(options?.t, "interval.range", { from: label(from, start), to: endLabel });
}

// The date picker's value as a day bound, and a day bound as the picker's value.
export function dayFromPicker(value) {
  if (!value) return "";
  if (typeof value === "string") return value.slice(0, 10);
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

export function pickerFromDay(value) {
  const bound = readBound(value);
  if (bound.kind !== "day") return null;
  const [y, m, d] = value.trim().split("-").map(Number);
  return new Date(y, m - 1, d);
}

// English defaults, used when no translator is passed (tests, plain JS callers).
const FALLBACK = {
  "interval.formatHelp": () =>
    "Use a year, month or day (2020, 2020-01, 2020-01-31), a UTC time (2020-01-31T06:00:00Z) or a time of day (T06:00Z)",
  "interval.dayHelp": () => "Use a date as YYYY-MM-DD",
  "interval.invalid": () => "Not a valid date or time",
  "interval.endBeforeStart": () => "The end is before the start",
  "interval.endOf": ({ label }) => `end of ${label}`,
  "interval.until": ({ label }) => `Until ${label}`,
  "interval.since": ({ label }) => `Since ${label}, ongoing`,
  "interval.range": ({ from, to }) => `${from} – ${to}`,
  "interval.timeOfDay": ({ clock }) => `${clock} UTC, time of day`,
};

function tr(t, key, params) {
  return t ? t(key, params) : FALLBACK[key](params);
}
