import type { CalendarResponse } from "../../api";

interface CalendarHeatmapProps {
  data: CalendarResponse;
  onDayClick?: (isoDate: string) => void;
}

export function CalendarHeatmap({ data, onDayClick }: CalendarHeatmapProps) {
  const maxPlays = Math.max(...data.days.map((item) => item.plays), 1);
  const map = new Map(data.days.map((item) => [item.date, item]));
  const daysInMonth = new Date(data.year, data.month, 0).getDate();
  const cells = Array.from({ length: daysInMonth }, (_, index) => {
    const day = index + 1;
    const date = `${data.year}-${String(data.month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const item = map.get(date);
    const intensity = item ? Math.max(0.15, item.plays / maxPlays) : 0;
    return { day, item, intensity };
  });
  return (
    <div className="calendar-grid">
      {cells.map((cell) => {
        const date = `${data.year}-${String(data.month).padStart(2, "0")}-${String(cell.day).padStart(2, "0")}`;
        return (
          <div
            key={cell.day}
            role={onDayClick ? "button" : undefined}
            tabIndex={onDayClick ? 0 : undefined}
            className={`calendar-cell${onDayClick ? " interactive" : ""}`}
            style={{ opacity: cell.intensity || 0.08 }}
            title={cell.item ? `${cell.item.date}: ${cell.item.plays} plays` : `Day ${cell.day}`}
            onClick={() => onDayClick?.(date)}
            onKeyDown={(event) => {
              if (onDayClick && (event.key === "Enter" || event.key === " ")) {
                event.preventDefault();
                onDayClick(date);
              }
            }}
          >
            <span>{cell.day}</span>
            <strong>{cell.item?.plays || 0}</strong>
          </div>
        );
      })}
    </div>
  );
}
