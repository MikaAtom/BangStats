import type { ActivityResponse } from "../../api";
import { BarChart } from "./BarChart";

interface ActivityBarsProps {
  data: ActivityResponse;
}

export function ActivityBars({ data }: ActivityBarsProps) {
  const items = [
    { label: "Plays", value: data.summary.total_plays || 0 },
    { label: "Active days", value: data.active_days },
    { label: "Streak", value: data.range_streak_days },
    { label: "Avg plays/day", value: Number(data.avg_plays_per_day.toFixed(2)) },
  ];
  return (
    <div className="stack">
      <BarChart items={items} />
      <div className="inline-meta">
        Delta vs previous: {data.delta_vs_previous.plays_delta} plays, {data.delta_vs_previous.accuracy_delta}% accuracy
      </div>
    </div>
  );
}
