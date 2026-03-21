import type { User } from "../api";
import { webLocale } from "../utils/format";

export type RecapScope = "weekly" | "monthly" | "seasonal" | "yearly" | "event";

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
  // seasonal: step by calendar quarter (~season)
  next.setMonth(next.getMonth() + direction * 3);
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
  if (scope === "seasonal") {
    const m = anchor.getMonth();
    const year = anchor.getFullYear();
    let name: string;
    let startM: number;
    let endM: number;
    if (m >= 2 && m <= 4) {
      name = "Spring";
      startM = 2;
      endM = 4;
    } else if (m >= 5 && m <= 7) {
      name = "Summer";
      startM = 5;
      endM = 7;
    } else if (m >= 8 && m <= 10) {
      name = "Fall";
      startM = 8;
      endM = 10;
    } else {
      name = "Winter";
      return `${name} ${year} (Dec–Feb)`;
    }
    const start = new Date(year, startM, 1);
    const end = new Date(year, endM, 1);
    return `${name} ${year} (${start.toLocaleDateString(loc, { month: "short" })}–${end.toLocaleDateString(loc, { month: "short" })})`;
  }
  if (scope === "yearly") {
    return String(anchor.getFullYear());
  }
  return anchor.toLocaleDateString(loc, { month: "long", year: "numeric" });
}
