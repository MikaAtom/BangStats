import type { User } from "../api";
import { webLocale } from "../utils/format";

export type RecapScope = "weekly" | "monthly" | "yearly" | "event";

/** Monday-start week containing `anchor` (local). */
export function weekRangeContaining(anchor: Date): { start: Date; end: Date } {
  const d = new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate());
  const day = d.getDay();
  const diff = (day + 6) % 7;
  const start = new Date(d);
  start.setDate(d.getDate() - diff);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  return { start, end };
}

export function stepRecapAnchor(scope: RecapScope, anchor: Date, direction: -1 | 1): Date {
  if (scope === "event") return anchor;
  const next = new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate());
  if (scope === "weekly") {
    next.setDate(next.getDate() + direction * 7);
    return next;
  }
  if (scope === "monthly") {
    next.setMonth(next.getMonth() + direction);
    return next;
  }
  if (scope === "yearly") {
    next.setFullYear(next.getFullYear() + direction);
    return next;
  }
  next.setMonth(next.getMonth() + direction);
  return next;
}

export function recapNavLabel(scope: RecapScope, anchor: Date, server: User["server"]): string {
  const loc = webLocale(server);
  if (scope === "weekly") {
    const { start, end } = weekRangeContaining(anchor);
    const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric", year: "numeric" };
    return `Week of ${start.toLocaleDateString(loc, opts)} – ${end.toLocaleDateString(loc, opts)}`;
  }
  if (scope === "monthly") {
    return anchor.toLocaleDateString(loc, { month: "long", year: "numeric" });
  }
  if (scope === "yearly") {
    return String(anchor.getFullYear());
  }
  return anchor.toLocaleDateString(loc, { month: "long", year: "numeric" });
}
