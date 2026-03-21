import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { CalendarResponse, CalendarYearResponse, ScreenshotItem, User } from "../../api";
import type { ScreenshotListResponse } from "../../api";
import type { Loadable } from "../../hooks/useLoadable";
import { formatDateTime, formatDifficulty, formatLiveType, formatShortDate, webLocale } from "../../utils/format";
import { CalendarHeatmap } from "../charts/CalendarHeatmap";
import { EmptyState } from "../ui/EmptyState";
import { LoadingInline } from "../ui/LoadingCard";
import { SecureImage } from "../ui/SecureImage";
import { ResultStatGrid } from "../screenshots/ResultStatGrid";

export type CalendarExplorerMode = "year" | "month" | "week" | "day";

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

export function calendarRangeForMode(mode: CalendarExplorerMode, anchor: Date) {
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

function calendarLabel(mode: CalendarExplorerMode, anchor: Date, server: User["server"]) {
  const loc = webLocale(server);
  if (mode === "year") return String(anchor.getFullYear());
  if (mode === "week") {
    const range = calendarRangeForMode("week", anchor);
    return `Week of ${formatShortDate(range.from_date, server)} – ${formatShortDate(range.to_date, server)}`;
  }
  if (mode === "day") return formatShortDate(dateKey(anchor), server);
  return anchor.toLocaleDateString(loc, { month: "long", year: "numeric" });
}

function groupShotsByDate(items: ScreenshotItem[]) {
  const groups = new Map<string, ScreenshotItem[]>();
  for (const item of items) {
    const key = item.timestamp ? item.timestamp.slice(0, 10) : "unknown";
    const existing = groups.get(key);
    if (existing) existing.push(item);
    else groups.set(key, [item]);
  }
  return [...groups.entries()]
    .map(([date, shots]) => ({
      date,
      shots: shots.slice().sort((a, b) => String(b.timestamp || "").localeCompare(String(a.timestamp || ""))),
    }))
    .sort((a, b) => b.date.localeCompare(a.date));
}

function monthName(year: number, monthZeroBased: number, server: User["server"]) {
  return new Date(year, monthZeroBased, 1).toLocaleDateString(webLocale(server), { month: "short" });
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
}) {
  const [selectedShotId, setSelectedShotId] = useState<number | null>(null);
  useEffect(() => {
    if (!open) setSelectedShotId(null);
  }, [open]);

  const orderedShots = useMemo(
    () =>
      mode === "year" || shotsState.loading || shotsState.error
        ? []
        : (shotsState.data?.items || [])
            .slice()
            .sort((a, b) => String(b.timestamp || "").localeCompare(String(a.timestamp || ""))),
    [mode, shotsState.data, shotsState.loading, shotsState.error],
  );
  const groupedShots = useMemo(() => groupShotsByDate(orderedShots), [orderedShots]);
  const activeShot = orderedShots.find((shot) => shot.id === selectedShotId) || orderedShots[0] || null;
  const rangeLabel = calendarLabel(mode, anchorDate, server);
  const yearData = yearState.data;
  const yearBase = yearData ? Math.max(...yearData.months.map((item) => item.plays), 1) : 1;

  useEffect(() => {
    if (!orderedShots.length) {
      setSelectedShotId(null);
      return;
    }
    if (selectedShotId == null || !orderedShots.some((shot) => shot.id === selectedShotId)) {
      setSelectedShotId(orderedShots[0]!.id);
    }
  }, [orderedShots, selectedShotId]);

  if (!open) return null;

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal modal-wide calendar-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header calendar-modal__header">
          <div>
            <h3>{title}</h3>
            <div className="inline-meta">
              {subtitle || rangeLabel}
              {orderedShots.length ? ` · ${orderedShots.length} screenshots` : ""}
            </div>
          </div>
          <div className="button-row tight calendar-modal__toolbar">
            <label className="field inline-field calendar-modal__mode">
              <span>Mode</span>
              <select value={mode} onChange={(event) => onModeChange(event.target.value as CalendarExplorerMode)}>
                <option value="year">Year</option>
                <option value="month">Month</option>
                <option value="week">Week</option>
                <option value="day">Day</option>
              </select>
            </label>
            <button className="button ghost" type="button" onClick={() => onAnchorDateChange(stepCalendarAnchor(mode, anchorDate, -1))}>
              Prev
            </button>
            <div className="toolbar-chip">{rangeLabel}</div>
            <button className="button ghost" type="button" onClick={() => onAnchorDateChange(stepCalendarAnchor(mode, anchorDate, 1))}>
              Next
            </button>
            <button className="button ghost" type="button" onClick={onClose}>
              Close
            </button>
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

            {(mode === "week" || mode === "day") && shotsState.loading ? (
              <LoadingInline />
            ) : (mode === "week" || mode === "day") && shotsState.error ? (
              <div className="stack">
                <EmptyState text={`Could not load screenshots: ${shotsState.error}`} />
                <button className="button ghost" type="button" onClick={() => void shotsState.reload()}>
                  Retry
                </button>
              </div>
            ) : (mode === "week" || mode === "day") && groupedShots.length > 0 ? (
              <div className="calendar-modal__groups">
                {groupedShots.map((group) => (
                  <div className="calendar-modal__group" key={group.date}>
                    <div className="calendar-modal__group-head">
                      <button
                        type="button"
                        className="calendar-modal__group-button"
                        onClick={() => {
                          onAnchorDateChange(parseDateKey(group.date));
                          onModeChange("day");
                        }}
                      >
                        {formatShortDate(group.date, server)}
                      </button>
                      <span>{group.shots.length} screenshots</span>
                    </div>
                    <div className="calendar-modal__shot-list">
                      {group.shots.map((shot) => (
                        <button
                          key={shot.id}
                          type="button"
                          className={selectedShotId === shot.id ? "calendar-modal__shot active" : "calendar-modal__shot"}
                          onClick={() => setSelectedShotId(shot.id)}
                        >
                          <div className="calendar-modal__shot-thumb">
                            {shot.image_available && shot.image_url ? (
                              <SecureImage path={shot.image_url} alt={shot.filename || shot.song_name || `screenshot-${shot.id}`} className="calendar-modal__shot-image" />
                            ) : (
                              <div className="gallery-placeholder calendar-modal__shot-placeholder">No image</div>
                            )}
                          </div>
                          <div className="calendar-modal__shot-body">
                            <strong>{shot.song_name || `Song ${shot.song_id}`}</strong>
                            <span>
                              {formatDifficulty(shot.difficulty)} · {formatLiveType(shot.live_type)}
                            </span>
                            <small>{formatDateTime(shot.timestamp, server)}</small>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}

            {!orderedShots.length && mode !== "year" && !shotsState.loading ? <EmptyState text="No screenshots found for this range." /> : null}
          </div>

          <div className="calendar-modal__detail">
            {activeShot ? (
              <div className="stack">
                <div className="calendar-modal__detail-head">
                  <div>
                    <div className="brand-kicker">{formatDifficulty(activeShot.difficulty)}</div>
                    <h4>{activeShot.song_name || `Song ${activeShot.song_id}`}</h4>
                  </div>
                  <div className="badge-row">
                    {activeShot.full_combo ? <span className="badge fc">FC</span> : null}
                    {activeShot.all_perfect ? <span className="badge ap">AP</span> : null}
                    {activeShot.anomaly ? <span className="badge warn">!</span> : null}
                  </div>
                </div>
                <div className="calendar-modal__detail-meta inline-meta">
                  {formatLiveType(activeShot.live_type)}
                  {activeShot.level != null ? ` · Lv. ${activeShot.level}` : ""}
                  {activeShot.timestamp ? ` · ${formatDateTime(activeShot.timestamp, server)}` : ""}
                </div>
                {activeShot.image_url && activeShot.image_available !== false ? (
                  <SecureImage path={activeShot.image_url} alt={activeShot.filename || activeShot.song_name || "screenshot"} className="viewer-image" priority />
                ) : (
                  <EmptyState text="Image not available for this screenshot." />
                )}
                <ResultStatGrid item={activeShot} server={server} showMetaFooter />
              </div>
            ) : shotsState.loading ? (
              <LoadingInline />
            ) : (
              <EmptyState text="Pick a screenshot to inspect its full stats." />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
