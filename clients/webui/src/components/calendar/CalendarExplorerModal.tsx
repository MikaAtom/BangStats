import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { CalendarResponse, CalendarYearResponse, ScreenshotItem, User } from "../../api";
import type { ScreenshotListResponse } from "../../api";
import type { Loadable } from "../../hooks/useLoadable";
import { formatShortDate, webLocale } from "../../utils/format";
import { CalendarHeatmap } from "../charts/CalendarHeatmap";
import { EmptyState } from "../ui/EmptyState";
import { LoadingInline } from "../ui/LoadingCard";
import { ScreenshotModal, type ScreenshotModalItem } from "../screenshots/ScreenshotModal";
import { CalendarHourGrid } from "./CalendarHourGrid";

export type CalendarExplorerMode = "year" | "month" | "week" | "day" | "event";

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
    const day = start.getDay();
    const diff = (day + 6) % 7;
    start.setDate(start.getDate() - diff);
    end.setTime(start.getTime());
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
    return formatShortDate(dateKey(anchor), server);
  }
  if (mode === "year") return String(anchor.getFullYear());
  if (mode === "week") {
    const range = calendarRangeForMode("week", anchor);
    return `Week of ${formatShortDate(range.from_date, server)} – ${formatShortDate(range.to_date, server)}`;
  }
  if (mode === "day") return formatShortDate(dateKey(anchor), server);
  return anchor.toLocaleDateString(loc, { month: "long", year: "numeric" });
}

function monthName(year: number, monthZeroBased: number, server: User["server"]) {
  return new Date(year, monthZeroBased, 1).toLocaleDateString(webLocale(server), { month: "short" });
}

function toModalItem(item: ScreenshotItem): ScreenshotModalItem {
  return {
    ...item,
    image_available: item.image_available,
  };
}

export function CalendarExplorerModal({
  open,
  title,
  subtitle,
  server,
  mode,
  anchorDate,
  onModeChange,
  onAnchorDateChange,
  onClose,
  yearState,
  monthState,
  shotsState,
  showEventMode = false,
  eventRange = null,
  variant = "modal",
}: {
  open: boolean;
  title: string;
  subtitle?: ReactNode;
  server: User["server"];
  mode: CalendarExplorerMode;
  anchorDate: Date;
  onModeChange: (mode: CalendarExplorerMode) => void;
  onAnchorDateChange: (next: Date) => void;
  onClose: () => void;
  yearState: Loadable<CalendarYearResponse> & { reload: () => Promise<void> };
  monthState: Loadable<CalendarResponse> & { reload: () => Promise<void> };
  shotsState: Loadable<ScreenshotListResponse> & { reload: () => Promise<void> };
  showEventMode?: boolean;
  eventRange?: { from_date: string; to_date: string } | null;
  /** Inline: embedded in a page (no backdrop, no Close). */
  variant?: "modal" | "inline";
}) {
  const [shotModalIndex, setShotModalIndex] = useState<number | null>(null);
  useEffect(() => {
    if (!open) setShotModalIndex(null);
  }, [open]);

  const explorerRange = useMemo(() => calendarRangeForMode(mode, anchorDate, eventRange), [mode, anchorDate, eventRange]);

  const orderedShots = useMemo(() => {
    if (mode === "year" || mode === "month") return [];
    if (shotsState.error) return [];
    const { from_date, to_date } = explorerRange;
    const filtered = (shotsState.data?.items || []).filter((s) => {
      const dk = s.timestamp?.slice(0, 10);
      if (!dk) return false;
      return dk >= from_date && dk <= to_date;
    });
    return filtered.sort((a, b) => String(b.timestamp || "").localeCompare(String(a.timestamp || "")));
  }, [mode, shotsState.data, shotsState.error, explorerRange.from_date, explorerRange.to_date]);

  const modalItems = useMemo(() => orderedShots.map(toModalItem), [orderedShots]);

  const rangeLabel = calendarLabel(mode, anchorDate, server, eventRange);
  const yearData = yearState.data;
  const yearBase = yearData ? Math.max(...yearData.months.map((item) => item.plays), 1) : 1;

  const shotsIdle = mode === "year" || mode === "month";
  const showShotListLoading = !shotsIdle && shotsState.loading && orderedShots.length === 0;
  const showShotError = !shotsIdle && Boolean(shotsState.error);
  const showHourGrid = !shotsIdle && !shotsState.error && orderedShots.length > 0;
  const showShotEmpty = !shotsIdle && !shotsState.loading && !shotsState.error && orderedShots.length === 0;

  const eventRangeReady = Boolean(eventRange?.from_date && eventRange?.to_date);
  const isInline = variant === "inline";

  if (!open) return null;

  const shell = (
    <div
      className={`modal modal-wide calendar-modal${isInline ? " calendar-modal--inline" : ""}`}
      role={isInline ? undefined : "dialog"}
      aria-modal={isInline ? undefined : true}
      onClick={isInline ? undefined : (event) => event.stopPropagation()}
    >
      <div className="modal-header calendar-modal__header">
        <div>
          <h3>{title}</h3>
          <div className="inline-meta">
            {subtitle || rangeLabel}
            {!shotsIdle && orderedShots.length ? ` · ${orderedShots.length} screenshots` : ""}
          </div>
        </div>
        <div className="button-row tight calendar-modal__toolbar">
          <div className="calendar-modal__mode">
            <span className="calendar-modal__mode-label">Mode</span>
            <select value={mode} onChange={(event) => onModeChange(event.target.value as CalendarExplorerMode)}>
              <option value="year">Year</option>
              <option value="month">Month</option>
              <option value="week">Week</option>
              <option value="day">Day</option>
              {showEventMode ? (
                <option value="event" disabled={!eventRangeReady}>
                  Event{!eventRangeReady ? " (loading…)" : ""}
                </option>
              ) : null}
            </select>
          </div>
          <button
            className="button ghost"
            type="button"
            disabled={mode === "event"}
            onClick={() => onAnchorDateChange(stepCalendarAnchor(mode, anchorDate, -1))}
          >
            Prev
          </button>
          <div className="toolbar-chip">{rangeLabel}</div>
          <button
            className="button ghost"
            type="button"
            disabled={mode === "event"}
            onClick={() => onAnchorDateChange(stepCalendarAnchor(mode, anchorDate, 1))}
          >
            Next
          </button>
          {isInline ? null : (
            <button className="button ghost" type="button" onClick={onClose}>
              Close
            </button>
          )}
        </div>
      </div>

      <div className="calendar-modal__layout">
        <div className="calendar-modal__browser">
            {mode === "year" && yearState.loading ? (
              <LoadingInline />
            ) : mode === "year" && yearState.error ? (
              <div className="stack">
                <EmptyState text={`Could not load yearly calendar: ${yearState.error}`} />
                <button className="button ghost" type="button" onClick={() => void yearState.reload()}>
                  Retry
                </button>
              </div>
            ) : mode === "year" && yearData ? (
              <div className="calendar-modal__year-grid">
                {yearData.months.map((month) => {
                  const intensity = Math.max(month.plays, month.fc, month.ap, month.active_days, 1);
                  const alpha = 0.16 + (intensity / yearBase) * 0.84;
                  return (
                    <button
                      key={month.month}
                      type="button"
                      className="calendar-modal__month-card"
                      style={{ background: `rgba(124, 92, 255, ${alpha})` }}
                      onClick={() => {
                        onAnchorDateChange(new Date(yearData.year, month.month - 1, 1));
                        onModeChange("month");
                      }}
                    >
                      <strong>{monthName(yearData.year, month.month - 1, server)}</strong>
                      <span>{month.plays} plays</span>
                      <small>
                        {month.fc} FC · {month.ap} AP · {month.active_days} active days
                      </small>
                    </button>
                  );
                })}
              </div>
            ) : null}

            {mode === "month" && monthState.loading ? (
              <LoadingInline />
            ) : mode === "month" && monthState.error ? (
              <div className="stack">
                <EmptyState text={`Could not load monthly calendar: ${monthState.error}`} />
                <button className="button ghost" type="button" onClick={() => void monthState.reload()}>
                  Retry
                </button>
              </div>
            ) : mode === "month" && monthState.data ? (
              <div className="stack">
                <CalendarHeatmap
                  data={monthState.data}
                  onDayClick={(isoDate) => {
                    onAnchorDateChange(parseDateKey(isoDate));
                    onModeChange("day");
                  }}
                />
                <div className="inline-meta">Select a day to zoom into its screenshots.</div>
              </div>
            ) : null}

            {showShotListLoading ? <LoadingInline /> : null}
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
