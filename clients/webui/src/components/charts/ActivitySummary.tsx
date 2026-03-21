import type { ActivityResponse } from "../../api";
import { MetricCard } from "../ui/MetricCard";

interface ActivitySummaryProps {
  data: ActivityResponse;
}

/** Activity metrics as comparable cards (avoids mixed-scale bar lengths). */
export function ActivitySummary({ data }: ActivitySummaryProps) {
  return (
    <div className="stack activity-summary">
      <div className="stats-grid activity-summary__grid">
        <MetricCard label="Plays" value={data.summary.total_plays || 0} />
        <MetricCard label="Active days" value={data.active_days} />
        <MetricCard label="Streak" value={data.range_streak_days} />
        <MetricCard label="Avg plays/day" value={Number(data.avg_plays_per_day.toFixed(2))} />
      </div>
      <div className="inline-meta">
        Delta vs previous: {data.delta_vs_previous.plays_delta} plays, {data.delta_vs_previous.accuracy_delta}% accuracy
      </div>
    </div>
  );
}
