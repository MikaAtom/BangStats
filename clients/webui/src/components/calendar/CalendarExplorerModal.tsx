import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { CalendarResponse, ScreenshotItem, User } from "../../api";
import type { ScreenshotListResponse } from "../../api";
import type { Loadable } from "../../hooks/useLoadable";
import { formatShortDate, webLocale } from "../../utils/format";
import { EmptyState } from "../ui/EmptyState";
import { LoadingSpinner } from "../ui/LoadingCard";
import { ScreenshotModal, type ScreenshotModalItem } from "../screenshots/ScreenshotModal";
import { CalendarHourGrid } from "./CalendarHourGrid";

export type CalendarExplorerMode = "year" | "month" | "week" | "day" | "event";
export type CalendarYearSurface = {
  year: number;
  months: CalendarResponse[];
};

type CalendarDay = CalendarResponse["days"][number];
type CalendarMatrixCell = {
  date: string;
  year: number;
  month: number;
  day: number;
  inMonth: boolean;
  isToday: boolean;
  data: CalendarDay | null;
};

function dateKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseDateKey(value: string) {
  const [year, month, day] = value.split("-").map((part) => Number(part));
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return new Date();
  }
  return new Date(year, month - 1, day);
}

function startOfWeekMonday(date: Date) {
  const next = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const day = next.getDay();
  const diff = (day + 6) % 7;
  next.setDate(next.getDate() - diff);
  return next;
}

function buildCalendarMatrix(data: CalendarResponse) {
  const first = new Date(data.year, data.month - 1, 1);
  const gridStart = startOfWeekMonday(first);
  const today = dateKey(new Date());
  const map = new Map(data.days.map((item) => [item.date, item]));
  const cells: CalendarMatrixCell[] = [];

  for (let index = 0; index < 42; index += 1) {
    const current = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + index);
    const key = dateKey(current);
    cells.push({
      date: key,
      year: current.getFullYear(),
      month: current.getMonth() + 1,
      day: current.getDate(),
      inMonth: current.getMonth() === data.month - 1,
      isToday: key === today,
      data: map.get(key) || null,
    });
  }

  return Array.from({ length: 6 }, (_, rowIndex) => cells.slice(rowIndex * 7, rowIndex * 7 + 7));
}

function monthName(year: number, monthZeroBased: number, server: User["server"], format: "short" | "long" = "short") {
  return new Date(year, monthZeroBased, 1).toLocaleDateString(webLocale(server), { month: format });
}

function formatMonthHeading(data: CalendarResponse, server: User["server"]) {
  return new Date(data.year, data.month - 1, 1).toLocaleDateString(webLocale(server), {
    month: "long",
    year: "numeric",
  });
}

export function stepCalendarAnchor(mode: CalendarExplorerMode, anchor: Date, direction: -1 | 1) {
  if (mode === "event") return new Date(anchor.getTime());
  const next = new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate());
  if (mode === "year") {
    next.setFullYear(next.getFullYear() + direction);
    return next;
  }
  if (mode === "month") {
    next.setMonth(next.getMonth() + direction);
    return next;
  }
  if (mode === "week") {
    next.setDate(next.getDate() + direction * 7);
    return next;
  }
  next.setDate(next.getDate() + direction);
  return next;
}

export function calendarRangeForMode(
  mode: CalendarExplorerMode,
  anchor: Date,
  eventRange?: { from_date: string; to_date: string } | null,
) {
  if (mode === "event") {
    if (eventRange?.from_date && eventRange?.to_date) {
      return { from_date: eventRange.from_date, to_date: eventRange.to_date };
    }
    const k = dateKey(anchor);
    return { from_date: k, to_date: k };
  }

  const start = new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate());
  const end = new Date(start);

  if (mode === "year") {
    start.setMonth(0, 1);
    end.setMonth(11, 31);
  } else if (mode === "month") {
    start.setDate(1);
    end.setMonth(end.getMonth() + 1, 0);
  } else if (mode === "week") {
    const aligned = startOfWeekMonday(start);
    start.setTime(aligned.getTime());
    end.setTime(aligned.getTime());
    end.setDate(start.getDate() + 6);
  }

  return {
    from_date: dateKey(start),
    to_date: dateKey(end),
  };
}

function calendarLabel(
  mode: CalendarExplorerMode,
  anchor: Date,
  server: User["server"],
  eventRange?: { from_date: string; to_date: string } | null,
) {
  const loc = webLocale(server);
  if (mode === "event") {
    if (eventRange?.from_date && eventRange?.to_date) {
      return `${formatShortDate(eventRange.from_date, server)} – ${formatShortDate(eventRange.to_date, server)}`;
    }
    return "Pick an event to load its range";
  }
  if (mode === "year") return String(anchor.getFullYear());
  if (mode === "week") {
    const range = calendarRangeForMode("week", anchor);
    return `Week of ${formatShortDate(range.from_date, server)} – ${formatShortDate(range.to_date, server)}`;
  }
  if (mode === "day") return formatShortDate(dateKey(anchor), server);
  return anchor.toLocaleDateString(loc, { month: "long", year: "numeric" });
}

function weekdayLabels(server: User["server"], format: "short" | "narrow" = "short") {
  const base = startOfWeekMonday(new Date(2024, 0, 1));
  return Array.from({ length: 7 }, (_, index) =>
    new Date(base.getFullYear(), base.getMonth(), base.getDate() + index).toLocaleDateString(webLocale(server), {
      weekday: format,
    }),
  );
}

function toModalItem(item: ScreenshotItem): ScreenshotModalItem {
  return {
    ...item,
    image_available: item.image_available,
  };
}

function intensityClass(plays: number, maxPlays: number) {
  if (!plays || maxPlays <= 0) return "is-idle";
  const ratio = plays / maxPlays;
  if (ratio >= 0.8) return "is-hot";
  if (ratio >= 0.45) return "is-warm";
  return "is-cool";
}

function MiniMonthCard({
  data,
  maxPlays,
  server,
  onSelect,
}: {
  data: CalendarResponse;
  maxPlays: number;
  server: User["server"];
  onSelect: () => void;
}) {
  const weeks = useMemo(() => buildCalendarMatrix(data), [data]);
  return (
    <button type="button" className="calendar-mini-month" onClick={onSelect}>
      <div className="calendar-mini-month__header">
        <strong>{monthName(data.year, data.month - 1, server, "long")}</strong>
        <span>{data.days.reduce((total, item) => total + item.plays, 0)} plays</span>
      </div>
      <div className="calendar-mini-month__weekday-row">
        {weekdayLabels(server, "narrow").map((label) => (
          <span key={label}>{label}</span>
        ))}
      </div>
      <div className="calendar-mini-month__grid">
        {weeks.flat().map((cell) => (
          <span
            key={cell.date}
            className={`calendar-mini-month__day ${cell.inMonth ? "" : "is-outside"} ${cell.isToday ? "is-today" : ""} ${intensityClass(cell.data?.plays || 0, maxPlays)}`.trim()}
          >
            {cell.day}
          </span>
        ))}
      </div>
    </button>
  );
}

function MonthWallCalendar({
  data,
  server,
  onDayClick,
}: {
  data: CalendarResponse;
  server: User["server"];
  onDayClick: (isoDate: string) => void;
}) {
  const weeks = useMemo(() => buildCalendarMatrix(data), [data]);
  const maxPlays = Math.max(...data.days.map((item) => item.plays), 1);

  return (
    <div className="calendar-wall">
      <div className="calendar-wall__hero">
        <div>
          <h4>{formatMonthHeading(data, server)}</h4>
          <div className="inline-meta">
            {data.total_days_with_plays} active days · {data.days.reduce((total, item) => total + item.plays, 0)} plays
          </div>
        </div>
      </div>
      <div className="calendar-wall__weekday-row">
        {weekdayLabels(server).map((label, index) => (
          <div key={`${label}-${index}`} className="calendar-wall__weekday">
            {label}
          </div>
        ))}
      </div>
      <div className="calendar-wall__grid">
        {weeks.flat().map((cell) => {
          const plays = cell.data?.plays || 0;
          return (
            <button
              key={cell.date}
              type="button"
              className={`calendar-wall__cell ${cell.inMonth ? "" : "is-outside"} ${cell.isToday ? "is-today" : ""} ${intensityClass(plays, maxPlays)}`.trim()}
              onClick={() => cell.inMonth && onDayClick(cell.date)}
              disabled={!cell.inMonth}
            >
              <div className="calendar-wall__cell-day">{cell.day}</div>
              <div className="calendar-wall__cell-body">
                {cell.inMonth && plays > 0 ? (
                  <>
                    <strong>{plays}</strong>
                    <span>
                      {cell.data?.fc || 0} FC · {cell.data?.ap || 0} AP
                    </span>
                  </>
                ) : cell.inMonth ? (
                  <span className="calendar-wall__cell-empty">No plays</span>
                ) : null}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function CalendarExplorerModal({
  open,
  title,
  server,
  mode,
  anchorDate,
  onModeChange,
  onAnchorDateChange,
  onClose,
  yearState,
  monthState,
  shotsState,
  eventRange = null,
  secondaryControls = null,
  secondaryControlsCount = 0,
  onStepEvent,
  canStepEventBackward = false,
  canStepEventForward = false,
  variant = "modal",
}: {
  open: boolean;
  title: string;
  server: User["server"];
  mode: CalendarExplorerMode;
  anchorDate: Date;
  onModeChange: (mode: CalendarExplorerMode) => void;
  onAnchorDateChange: (next: Date) => void;
  onClose: () => void;
  yearState: Loadable<CalendarYearSurface> & { reload: () => Promise<void> };
  monthState: Loadable<CalendarResponse> & { reload: () => Promise<void> };
  shotsState: Loadable<ScreenshotListResponse> & { reload: () => Promise<void> };
  eventRange?: { from_date: string; to_date: string } | null;
  secondaryControls?: ReactNode;
  secondaryControlsCount?: number;
  onStepEvent?: (direction: -1 | 1) => void;
  canStepEventBackward?: boolean;
  canStepEventForward?: boolean;
  variant?: "modal" | "inline";
}) {
  const [shotModalIndex, setShotModalIndex] = useState<number | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    if (!open) setShotModalIndex(null);
  }, [open]);

  const explorerRange = useMemo(() => calendarRangeForMode(mode, anchorDate, eventRange), [mode, anchorDate, eventRange]);
  const eventRangeReady = Boolean(eventRange?.from_date && eventRange?.to_date);
  const orderedShots = useMemo(() => {
    if (mode === "year" || mode === "month") return [];
    if (mode === "event" && !eventRangeReady) return [];
    if (shotsState.error) return [];
    const { from_date, to_date } = explorerRange;
    const filtered = (shotsState.data?.items || []).filter((s) => {
      const dk = s.timestamp?.slice(0, 10);
      if (!dk) return false;
      return dk >= from_date && dk <= to_date;
    });
    return filtered.sort((a, b) => String(b.timestamp || "").localeCompare(String(a.timestamp || "")));
  }, [mode, shotsState.data, shotsState.error, explorerRange, eventRangeReady]);

  const modalItems = useMemo(() => orderedShots.map(toModalItem), [orderedShots]);
  const rangeLabel = calendarLabel(mode, anchorDate, server, eventRange);
  const isInline = variant === "inline";
  const shotsIdle = mode === "year" || mode === "month" || (mode === "event" && !eventRangeReady);
  const showShotListLoading = !shotsIdle && shotsState.loading && orderedShots.length === 0;
  const showShotError = !shotsIdle && Boolean(shotsState.error);
  const showHourGrid = !shotsIdle && !shotsState.error && orderedShots.length > 0;
  const showShotEmpty = !shotsIdle && !shotsState.loading && !shotsState.error && orderedShots.length === 0;
  const screenshotCountLabel = !shotsIdle && shotsState.data ? `${shotsState.data.total || orderedShots.length} screenshots` : "";

  if (!open) return null;

  const shell = (
    <div
      className={`modal modal-wide calendar-modal${isInline ? " calendar-modal--inline" : ""}`}
      role={isInline ? undefined : "dialog"}
      aria-modal={isInline ? undefined : true}
      onClick={isInline ? undefined : (event) => event.stopPropagation()}
    >
      <div className="modal-header calendar-modal__header">
        <div className="calendar-modal__toprow">
          <div className="calendar-modal__heading">
            <h3>{title}</h3>
            <div className="calendar-modal__meta">
              <span className="inline-meta calendar-modal__meta-range">{rangeLabel}</span>
              <span className="inline-meta calendar-modal__meta-count">{screenshotCountLabel}</span>
            </div>
          </div>
          <div className="calendar-modal__toolbar">
            <div className="calendar-modal__mode">
              <span className="calendar-modal__mode-label">Mode</span>
              <select value={mode} onChange={(event) => onModeChange(event.target.value as CalendarExplorerMode)}>
                <option value="year">Year</option>
                <option value="month">Month</option>
                <option value="week">Week</option>
                <option value="day">Day</option>
                <option value="event">Event</option>
              </select>
            </div>
            <div className="calendar-modal__nav">
              <button
                className="button ghost"
                type="button"
                disabled={mode === "event" ? !canStepEventBackward : false}
                onClick={() => {
                  if (mode === "event") {
                    onStepEvent?.(-1);
                    return;
                  }
                  onAnchorDateChange(stepCalendarAnchor(mode, anchorDate, -1));
                }}
              >
                Prev
              </button>
              <button
                className="button ghost"
                type="button"
                disabled={mode === "event" ? !canStepEventForward : false}
                onClick={() => {
                  if (mode === "event") {
                    onStepEvent?.(1);
                    return;
                  }
                  onAnchorDateChange(stepCalendarAnchor(mode, anchorDate, 1));
                }}
              >
                Next
              </button>
            </div>
            {secondaryControls ? (
              <button className="button ghost calendar-modal__filter-toggle" type="button" onClick={() => setFiltersOpen((current) => !current)}>
                Filters{secondaryControlsCount > 0 ? ` (${secondaryControlsCount})` : ""}
              </button>
            ) : null}
            {isInline ? null : (
              <button className="button ghost" type="button" onClick={onClose}>
                Close
              </button>
            )}
          </div>
        </div>
        {secondaryControls && filtersOpen ? (
          <div className="calendar-modal__filters">
            <div className="analytics-filter-row">{secondaryControls}</div>
          </div>
        ) : null}
      </div>

      <div className="calendar-modal__layout">
        <div className="calendar-modal__browser">
          {mode === "year" && yearState.loading ? <LoadingSpinner centered /> : null}
          {mode === "year" && yearState.error ? (
            <div className="stack">
              <EmptyState text={`Could not load yearly calendar: ${yearState.error}`} />
              <button className="button ghost" type="button" onClick={() => void yearState.reload()}>
                Retry
              </button>
            </div>
          ) : null}
          {mode === "year" && yearState.data
            ? (() => {
                const yearData = yearState.data;
                const maxYearPlays = Math.max(...yearData.months.flatMap((item) => item.days.map((day) => day.plays)), 1);
                return (
                  <div className="calendar-year">
                    <div className="calendar-year__headline">
                      <h4>{yearData.year}</h4>
                      <span>{rangeLabel}</span>
                    </div>
                    <div className="calendar-year__grid">
                      {yearData.months.map((month) => (
                        <MiniMonthCard
                          key={`${month.year}-${month.month}`}
                          data={month}
                          server={server}
                          maxPlays={maxYearPlays}
                          onSelect={() => {
                            onAnchorDateChange(new Date(month.year, month.month - 1, 1));
                            onModeChange("month");
                          }}
                        />
                      ))}
                    </div>
                  </div>
                );
              })()
            : null}

          {mode === "month" && monthState.loading ? <LoadingSpinner centered /> : null}
          {mode === "month" && monthState.error ? (
            <div className="stack">
              <EmptyState text={`Could not load monthly calendar: ${monthState.error}`} />
              <button className="button ghost" type="button" onClick={() => void monthState.reload()}>
                Retry
              </button>
            </div>
          ) : null}
          {mode === "month" && monthState.data ? (
            <MonthWallCalendar
              data={monthState.data}
              server={server}
              onDayClick={(isoDate) => {
                onAnchorDateChange(parseDateKey(isoDate));
                onModeChange("day");
              }}
            />
          ) : null}

          {mode === "event" && !eventRangeReady ? <EmptyState text="Pick an event in the center field to load Event mode." /> : null}
          {showShotListLoading ? <LoadingSpinner centered /> : null}
          {showShotError ? (
            <div className="stack">
              <EmptyState text={`Could not load screenshots: ${shotsState.error}`} />
              <button className="button ghost" type="button" onClick={() => void shotsState.reload()}>
                Retry
              </button>
            </div>
          ) : null}
          {showHourGrid ? (
            <CalendarHourGrid
              from_date={explorerRange.from_date}
              to_date={explorerRange.to_date}
              shots={orderedShots}
              server={server}
              onShotClick={(shot) => {
                const idx = orderedShots.findIndex((s) => s.id === shot.id);
                if (idx >= 0) setShotModalIndex(idx);
              }}
            />
          ) : null}
          {showShotEmpty ? <EmptyState text="No screenshots found for this range." /> : null}
        </div>
      </div>
    </div>
  );

  return (
    <>
      {isInline ? (
        <div className="calendar-explorer-inline">{shell}</div>
      ) : (
        <div className="modal-backdrop" role="presentation" onClick={onClose}>
          {shell}
        </div>
      )}
      {shotModalIndex != null && modalItems.length ? (
        <ScreenshotModal
          elevated
          items={modalItems}
          index={shotModalIndex}
          server={server}
          onClose={() => setShotModalIndex(null)}
          onIndexChange={setShotModalIndex}
        />
      ) : null}
    </>
  );
}
