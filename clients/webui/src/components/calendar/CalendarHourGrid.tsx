import { Fragment, useMemo } from "react";
import type { ScreenshotItem, User } from "../../api";
import { formatDifficulty, webLocale } from "../../utils/format";

const HOURS = Array.from({ length: 24 }, (_, i) => i);

function dateKeyFromDate(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function parseIsoDate(value: string) {
  const [year, month, day] = value.split("-").map((part) => Number(part));
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return new Date();
  }
  return new Date(year, month - 1, day);
}

function eachDateKeyInRange(from_date: string, to_date: string): string[] {
  const start = parseIsoDate(from_date);
  const end = parseIsoDate(to_date);
  const keys: string[] = [];
  const cur = new Date(start.getFullYear(), start.getMonth(), start.getDate());
  const endNorm = new Date(end.getFullYear(), end.getMonth(), end.getDate());
  while (cur <= endNorm) {
    keys.push(dateKeyFromDate(cur));
    cur.setDate(cur.getDate() + 1);
  }
  return keys;
}

function classifyShot(shot: ScreenshotItem): { dayKey: string; hour: number | "allday" } {
  const ts = shot.timestamp;
  if (!ts) return { dayKey: "", hour: "allday" };
  const datePart = ts.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(datePart)) return { dayKey: "", hour: "allday" };
  const hasTime = ts.length > 10 && (ts.includes("T") || /^\d{4}-\d{2}-\d{2}\s/.test(ts));
  if (!hasTime) return { dayKey: datePart, hour: "allday" };
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return { dayKey: datePart, hour: "allday" };
  return { dayKey: dateKeyFromDate(d), hour: d.getHours() };
}

function formatHourLabel(hour: number) {
  return `${String(hour).padStart(2, "0")}:00`;
}

function formatDayHeader(dayKey: string, server: User["server"]) {
  const d = parseIsoDate(dayKey);
  return d.toLocaleDateString(webLocale(server), { weekday: "short", month: "numeric", day: "numeric" });
}

function formatAccuracyPct(accuracy: number) {
  const n = Number(accuracy);
  if (!Number.isFinite(n)) return "—";
  return `${n % 1 === 0 ? String(Math.round(n)) : n.toFixed(1)}%`;
}

function FcApRibbon({ shot }: { shot: ScreenshotItem }) {
  if (shot.all_perfect) return <span className="badge ap calendar-hour-grid__ribbon">AP</span>;
  if (shot.full_combo) return <span className="badge fc calendar-hour-grid__ribbon">FC</span>;
  return null;
}

export function CalendarHourGrid({
  from_date,
  to_date,
  shots,
  server,
  onShotClick,
}: {
  from_date: string;
  to_date: string;
  shots: ScreenshotItem[];
  server: User["server"];
  onShotClick: (shot: ScreenshotItem) => void;
}) {
  const dayKeys = useMemo(() => eachDateKeyInRange(from_date, to_date), [from_date, to_date]);
  const daySet = useMemo(() => new Set(dayKeys), [dayKeys]);

  const buckets = useMemo(() => {
    const map = new Map<string, ScreenshotItem[]>();
    for (const shot of shots) {
      const { dayKey, hour } = classifyShot(shot);
      if (!dayKey || !daySet.has(dayKey)) continue;
      const key = hour === "allday" ? `${dayKey}:allday` : `${dayKey}:${hour}`;
      const list = map.get(key);
      if (list) list.push(shot);
      else map.set(key, [shot]);
    }
    for (const list of map.values()) {
      list.sort((a, b) => String(b.timestamp || "").localeCompare(String(a.timestamp || "")));
    }
    return map;
  }, [shots, daySet]);

  const n = dayKeys.length;
  const gridStyle = {
    gridTemplateColumns: `3.35rem repeat(${n}, minmax(88px, 1fr))`,
    gridTemplateRows: `auto auto repeat(24, minmax(36px, auto))`,
  };

  function renderEntries(bucketKey: string) {
    const list = buckets.get(bucketKey) || [];
    if (!list.length) return <div className="calendar-hour-grid__cell-inner" />;
    return (
      <div className="calendar-hour-grid__cell-inner">
        {list.map((shot) => {
          const title = shot.song_name || `Song ${shot.song_id}`;
          return (
            <button
              key={shot.id}
              type="button"
              className="calendar-hour-grid__entry"
              title={title}
              onClick={() => onShotClick(shot)}
            >
              <div className="calendar-hour-grid__entry-top">
                <span className="calendar-hour-grid__entry-meta">
                  {formatDifficulty(shot.difficulty)} · {formatAccuracyPct(shot.accuracy)}
                </span>
                <FcApRibbon shot={shot} />
              </div>
              <span className="calendar-hour-grid__entry-song">{title}</span>
            </button>
          );
        })}
      </div>
    );
  }

  if (n === 0) return null;

  return (
    <div className="calendar-hour-grid-wrap">
      <div className="calendar-hour-grid" style={gridStyle}>
        <div className="calendar-hour-grid__corner" style={{ gridColumn: 1, gridRow: 1 }} />
        {dayKeys.map((d, i) => (
          <div key={d} className="calendar-hour-grid__day-head" style={{ gridColumn: i + 2, gridRow: 1 }}>
            {formatDayHeader(d, server)}
          </div>
        ))}
        <div className="calendar-hour-grid__time" style={{ gridColumn: 1, gridRow: 2 }}>
          All day
        </div>
        {dayKeys.map((d, i) => (
          <div key={`ad-${d}`} className="calendar-hour-grid__cell" style={{ gridColumn: i + 2, gridRow: 2 }}>
            {renderEntries(`${d}:allday`)}
          </div>
        ))}
        {HOURS.map((hour) => (
          <Fragment key={hour}>
            <div className="calendar-hour-grid__time" style={{ gridColumn: 1, gridRow: hour + 3 }}>
              {formatHourLabel(hour)}
            </div>
            {dayKeys.map((d, i) => (
              <div key={`${d}-${hour}`} className="calendar-hour-grid__cell" style={{ gridColumn: i + 2, gridRow: hour + 3 }}>
                {renderEntries(`${d}:${hour}`)}
              </div>
            ))}
          </Fragment>
        ))}
      </div>
    </div>
  );
}
