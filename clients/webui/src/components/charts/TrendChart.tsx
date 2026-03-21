import type { ProgressionResponse } from "../../api";

interface TrendChartProps {
  data: ProgressionResponse;
  summaryMode?: "grid" | "list";
}

export function TrendChart({ data, summaryMode = "grid" }: TrendChartProps) {
  if (!data.points.length) {
    return <div className="empty-state">No progression points in this range — try another scope or filters.</div>;
  }

  const width = 1000;
  const height = 220;
  const padding = 28;
  const scores = data.points.map((point) => point.skill_score);
  const minScore = Math.min(...scores);
  const maxScore = Math.max(...scores);
  const scoreSpan = Math.max(maxScore - minScore, 0.5);

  const points = data.points.map((point, index) => {
    const x = padding + (index * (width - padding * 2)) / Math.max(data.points.length - 1, 1);
    const normalized = (point.skill_score - minScore) / scoreSpan;
    const y = height - padding - normalized * (height - padding * 2);
    return { ...point, x, y };
  });

  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");

  return (
    <div className="stack">
      <div className="inline-meta">Line: skill score per period · Hover dots for full stats</div>
      <div className="trend-chart-shell">
        <svg viewBox={`0 0 ${width} ${height}`} className="trend-chart" role="img" aria-label="Skill progression chart">
          <path d={path} className="trend-line" />
          {points.map((point) => (
            <g key={point.label}>
              <circle cx={point.x} cy={point.y} r="5" className="trend-dot">
                <title>{`${point.label}: skill ${point.skill_score}, ${point.plays} plays, ${point.accuracy}% acc, ${point.fc} FC / ${point.ap} AP`}</title>
              </circle>
              <text x={point.x} y={point.y - 10} textAnchor="middle" className="trend-value-label">
                {point.skill_score}
              </text>
            </g>
          ))}
        </svg>
      </div>
      {summaryMode === "list" ? (
        <div className="trend-summary-list">
          {data.points.map((point) => (
            <div key={point.label} className="trend-summary-list-row">
              <strong>{point.label}</strong>
              <span>{point.skill_score} skill</span>
              <span>
                {point.plays} plays · {point.fc} FC · {point.ap} AP
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div className="trend-point-grid">
          {data.points.map((point) => (
            <div key={point.label} className="trend-summary-card">
              <strong>{point.skill_score}</strong>
              <span>{point.label}</span>
              <small>
                {point.plays} plays · {point.fc} FC · {point.ap} AP
              </small>
            </div>
          ))}
        </div>
      )}
      <div className="inline-meta">
        Delta vs previous: {data.delta_skill_score} skill score, {data.delta_accuracy}% accuracy
      </div>
    </div>
  );
}
