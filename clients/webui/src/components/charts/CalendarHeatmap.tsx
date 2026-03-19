import type { CalendarResponse } from "../../api";

interface CalendarHeatmapProps {
  data: CalendarResponse;
}

export function CalendarHeatmap({ data }: CalendarHeatmapProps) {
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
      {cells.map((cell) => (
        <div
          key={cell.day}
          className="calendar-cell"
          style={{ opacity: cell.intensity || 0.08 }}
          title={cell.item ? `${cell.item.date}: ${cell.item.plays} plays` : `Day ${cell.day}`}
        >
          <span>{cell.day}</span>
          <strong>{cell.item?.plays || 0}</strong>
        </div>
      ))}
    </div>
  );
}
