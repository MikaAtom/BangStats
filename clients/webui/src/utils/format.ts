import type { User } from "../api";

const SERVER_LOCALE: Record<User["server"], string> = {
  en: "en-GB",
  jp: "ja-JP",
  tw: "zh-TW",
  cn: "zh-CN",
  kr: "ko-KR",
};

/** Use for all `Intl` formatting so UI matches the user's game server choice. */
export function webLocale(server: User["server"]) {
  return SERVER_LOCALE[server] || "en-GB";
}

function titleCase(value: string) {
  return value
    .replace(/_/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function coerceTimestampMs(value: unknown, server?: User["server"]) {
  let raw = value;
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const map = raw as Record<string, unknown>;
    raw = (server && map[server]) || map.en || Object.values(map)[0] || null;
  }
  if (typeof raw !== "string" && typeof raw !== "number") return null;
  const timestamp = Number(raw);
  return Number.isFinite(timestamp) && timestamp > 0 ? timestamp : null;
}

export function formatLiveType(type: string | null | undefined) {
  if (!type) return "Unknown";
  const mapping: Record<string, string> = {
    normal_live: "Normal Live",
    event_live: "Event Live",
    challenge_live: "Challenge Live",
    multi_live: "Multi Live",
    vs_live: "VS Live",
    free_live: "Free Live",
  };
  return mapping[type] || titleCase(type);
}

export function formatDifficulty(value: string | null | undefined) {
  if (!value) return "Unknown";
  return titleCase(value);
}

export function formatShortDate(value: string | null | undefined, server: User["server"] = "en") {
  if (!value) return "Not found in repo";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(webLocale(server), { year: "numeric", month: "short", day: "numeric" });
}

export function formatDateTime(value: string | null | undefined, server: User["server"] = "en") {
  if (!value) return "Not found in repo";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(webLocale(server), { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function formatDateRange(
  fromDate: string | null | undefined,
  toDate: string | null | undefined,
  server: User["server"] = "en",
) {
  return `${formatShortDate(fromDate, server)} -> ${formatShortDate(toDate, server)}`;
}

export function formatEventLabel(event: Record<string, unknown>, server: User["server"]) {
  const rawName = event.event_name;
  let name = `Event #${String(event.id || event.event_id || "")}`;
  if (rawName && typeof rawName === "object") {
    const map = rawName as Record<string, string>;
    name = map[server] || map.en || Object.values(map)[0] || name;
  } else if (typeof rawName === "string" && rawName.trim()) {
    name = rawName;
  }

  const start = formatEventBoundary(event.event_start_at, server);
  const end = formatEventBoundary(event.event_end_at, server);
  if (start !== "Not found in repo" && end !== "Not found in repo") {
    return `${name} · ${start} -> ${end}`;
  }
  return name;
}

/** Date-only boundaries for recap/event picker (no time-of-day). */
export function formatEventDateOnlyBoundary(value: unknown, server: User["server"]) {
  const timestampMs = coerceTimestampMs(value, server);
  if (timestampMs == null) return "Not found in repo";
  return new Date(timestampMs).toLocaleDateString(webLocale(server), {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatEventLabelDateOnly(event: Record<string, unknown>, server: User["server"]) {
  const rawName = event.event_name;
  let name = `Event #${String(event.id || event.event_id || "")}`;
  if (rawName && typeof rawName === "object") {
    const map = rawName as Record<string, string>;
    name = map[server] || map.en || Object.values(map)[0] || name;
  } else if (typeof rawName === "string" && rawName.trim()) {
    name = rawName;
  }
  const start = formatEventDateOnlyBoundary(event.event_start_at, server);
  const end = formatEventDateOnlyBoundary(event.event_end_at, server);
  if (start !== "Not found in repo" && end !== "Not found in repo") {
    return `${name} · ${start} – ${end}`;
  }
  return name;
}

export function resolveEventName(event: Record<string, unknown> | null | undefined, server: User["server"]) {
  if (!event) return "No current event";
  return formatEventLabel(event, server).split(" · ")[0];
}

export function formatEventBoundary(value: unknown, server: User["server"]) {
  const timestampMs = coerceTimestampMs(value, server);
  if (timestampMs == null) return "Not found in repo";
  return new Date(timestampMs).toLocaleString(webLocale(server), {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function groupActiveHours(activeHours: Record<string, number>) {
  const ranges = [
    { label: "Night (12am-6am)", hours: [0, 1, 2, 3, 4, 5] },
    { label: "Morning (6am-12pm)", hours: [6, 7, 8, 9, 10, 11] },
    { label: "Afternoon (12pm-6pm)", hours: [12, 13, 14, 15, 16, 17] },
    { label: "Evening (6pm-12am)", hours: [18, 19, 20, 21, 22, 23] },
  ];

  return ranges.map((range) => ({
    label: range.label,
    value: range.hours.reduce((total, hour) => total + (activeHours[String(hour)] || 0), 0),
  }));
}

export function isoDateForMonth(year: number, month: number) {
  const date = new Date(Date.UTC(year, month - 1, 1));
  return date.toISOString().slice(0, 10);
}
