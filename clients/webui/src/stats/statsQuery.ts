import type { StatsRangeQuery } from "../api";
import type { DateRangeValue } from "../components/ui";

export type SectionFilterState = {
  difficulty: string;
  liveType: string;
  includeMeta: boolean;
};

export function dateRangeToQuery(range: DateRangeValue) {
  if (range.preset === "custom") {
    return { from_date: range.from || undefined, to_date: range.to || undefined };
  }
  return { preset: range.preset };
}

export function resolveAbsoluteDateRange(range: DateRangeValue): StatsRangeQuery | null {
  if (range.preset === "custom") {
    if (!range.from || !range.to) return null;
    return { from_date: range.from, to_date: range.to };
  }
  const end = new Date();
  const daysByPreset: Record<string, number> = { "7d": 7, "30d": 30, "90d": 90, "1y": 365 };
  const days = daysByPreset[range.preset];
  if (!days) return null;
  const start = new Date(end);
  start.setDate(end.getDate() - (days - 1));
  return {
    from_date: start.toISOString().slice(0, 10),
    to_date: end.toISOString().slice(0, 10),
  };
}

export function sectionFiltersToQuery(filters: SectionFilterState) {
  return {
    difficulty: filters.difficulty || undefined,
    live_type: filters.liveType || undefined,
    include_meta: filters.includeMeta,
  };
}
