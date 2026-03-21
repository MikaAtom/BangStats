import type { ProgressionResponse, User } from "../../api";
import { webLocale } from "../../utils/format";

interface TrendChartProps {
  data: ProgressionResponse;
  variant?: "default" | "overview";
  server?: User["server"];
}

function formatAxisLabel(fromDate: string, server: User["server"]) {
  const parsed = new Date(fromDate);
  if (Number.isNaN(parsed.getTime())) return fromDate;
  return parsed.toLocaleDateString(webLocale(server), { month: "short", year: "2-digit" });
}

function formatAccuracy(value: number) {
  return `${value.toFixed(2)}%`;
}

export function TrendChart({ data, variant = "default", server = "en" }: TrendChartProps) {
  if (!data.points.length) {
    return <div className="empty-state">No progression points in this range — try another scope or filters.</div>;
  }

  const n = data.points.length;
  const vbW = 100;
  const vbH = variant === "overview" ? 68 : 44;
  const padLeft = variant === "overview" ? 7 : 6;
  const padRight = variant === "overview" ? 7 : 6;
  const padTop = variant === "overview" ? 10 : 7;
  const padBottom = variant === "overview" ? 16 : 7;
  const innerW = vbW - padLeft - padRight;
  const innerH = vbH - padTop - padBottom;

  const scores = data.points.map((point) => point.skill_score);
  const minScore = Math.min(...scores);
  const maxScore = Math.max(...scores);
  const scoreSpan = Math.max(maxScore - minScore, 0.5);

  const points = data.points.map((point, index) => {
    const t = n <= 1 ? 0.5 : index / (n - 1);
    const x = padLeft + t * innerW;
    const normalized = (point.skill_score - minScore) / scoreSpan;
    const y = padTop + innerH - normalized * innerH;
    return {
      ...point,
      x,
      y,
      axisLabel: formatAxisLabel(point.from_date, server),
      accuracyLabel: formatAccuracy(point.accuracy),
      textAnchor: (index === 0 ? "start" : index === n - 1 ? "end" : "middle") as "start" | "end" | "middle",
      skillLabelY: y > padTop + innerH * 0.72 ? Math.min(y + 5.5, vbH - padBottom - 1.2) : Math.max(y - 4.2, padTop + 1.4),
    };
  });

  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(3)} ${point.y.toFixed(3)}`)
    .join(" ");

  const gridLines = [0, 0.5, 1].map((fraction) => {
    const y = padTop + innerH - fraction * innerH;
    return { key: fraction, y };
  });

  if (variant === "overview") {
    return (
      <div className="stack trend-chart-overview">
        <div className="trend-chart-overview__plot">
          <svg viewBox={`0 0 ${vbW} ${vbH}`} preserveAspectRatio="none" className="trend-chart trend-chart--overview" role="img" aria-label="Monthly skill progression chart">
            {gridLines.map((line) => (
              <line
                key={line.key}
                x1={padLeft}
                x2={vbW - padRight}
                y1={line.y}
                y2={line.y}
                className={`trend-grid-line${line.key === 0 ? " trend-grid-line--base" : ""}`}
                vectorEffect="non-scaling-stroke"
              />
            ))}
            <path d={path} className="trend-line" vectorEffect="non-scaling-stroke" />
            {points.map((point) => (
              <g key={point.label}>
                <line
                  x1={point.x}
                  x2={point.x}
                  y1={point.y + 2.3}
                  y2={vbH - padBottom + 1.2}
                  className="trend-guide-line"
                  vectorEffect="non-scaling-stroke"
                />
                <text x={point.x} y={point.skillLabelY} textAnchor={point.textAnchor} className="trend-skill-label">
                  {point.skill_score}
                </text>
                <circle cx={point.x} cy={point.y} r="1.8" className="trend-dot" vectorEffect="non-scaling-stroke" />
                <text x={point.x} y={vbH - 6.2} textAnchor={point.textAnchor} className="trend-axis-tick">
                  {point.axisLabel}
                </text>
              </g>
            ))}
          </svg>
        </div>
        <div className="trend-chart-overview__meta" style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }}>
          {points.map((point) => (
            <div key={point.label} className="trend-chart-overview__meta-col">
              <strong>{point.skill_score}</strong>
              <span>{point.accuracyLabel}</span>
              <span>{point.plays} plays</span>
              <span>{point.fc} FC · {point.ap} AP</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="stack trend-chart-synced">
      <div className="trend-chart-synced__plot">
        <svg
          viewBox={`0 0 ${vbW} ${vbH}`}
          preserveAspectRatio="xMidYMid meet"
          className="trend-chart trend-chart--synced"
          role="img"
          aria-label="Skill progression chart"
        >
          <path d={path} className="trend-line" vectorEffect="non-scaling-stroke" />
          {points.map((point) => (
            <g key={point.label}>
              <circle cx={point.x} cy={point.y} r="1.55" className="trend-dot" vectorEffect="non-scaling-stroke">
                <title>{`${point.label}: skill ${point.skill_score}, ${point.plays} plays, ${point.accuracy}% acc, ${point.fc} FC / ${point.ap} AP`}</title>
              </circle>
            </g>
          ))}
        </svg>
      </div>
      <div className="trend-chart-synced__columns" style={{ gridTemplateColumns: `repeat(${n}, minmax(5rem, 1fr))` }}>
        {points.map((point) => (
          <div key={point.label} className="trend-chart-synced__col">
            <span className="trend-axis-label">{point.label}</span>
            <div className="trend-summary-card trend-summary-card--under">
              <strong>{point.skill_score}</strong>
              <small>
                {point.plays} plays · {point.fc} FC · {point.ap} AP
              </small>
            </div>
          </div>
        ))}
      </div>
      <div className="inline-meta">
        Delta vs previous: {data.delta_skill_score} skill score, {data.delta_accuracy}% accuracy
      </div>
    </div>
  );
}
