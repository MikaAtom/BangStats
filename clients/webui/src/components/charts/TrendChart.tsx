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

type LabelRect = {
  left: number;
  right: number;
  top: number;
  bottom: number;
};

function overlaps(a: LabelRect, b: LabelRect) {
  return !(a.right < b.left || a.left > b.right || a.bottom < b.top || a.top > b.bottom);
}

export function TrendChart({ data, variant = "default", server = "en" }: TrendChartProps) {
  if (!data.points.length) {
    return <div className="empty-state">No progression points in this range — try another scope or filters.</div>;
  }

  const n = data.points.length;
  const vbW = 100;
  const vbH = variant === "overview" ? 76 : 44;
  const padLeft = variant === "overview" ? 8 : 6;
  const padRight = variant === "overview" ? 8 : 6;
  const padTop = variant === "overview" ? 14 : 7;
  const padBottom = variant === "overview" ? 18 : 7;
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
    const prev = data.points[index - 1]?.skill_score;
    const next = data.points[index + 1]?.skill_score;
    const isValley = typeof prev === "number" && typeof next === "number" && point.skill_score < prev && point.skill_score < next;
    return {
      ...point,
      x,
      y,
      axisLabel: formatAxisLabel(point.from_date, server),
      accuracyLabel: formatAccuracy(point.accuracy),
      isValley,
    };
  });

  const clampCenterX = (x: number, width: number) => Math.min(Math.max(x, padLeft + width / 2), vbW - padRight - width / 2);
  const pointLabelRects: LabelRect[] = [];
  const pointLabels = points.map((point) => {
    const text = String(point.skill_score);
    const width = Math.max(8.8, text.length * 1.95);
    const height = 5.2;
    const candidateYs = point.isValley ? [point.y + 5.8, point.y - 4.8] : [point.y - 4.8, point.y + 5.8];
    for (const y of candidateYs) {
      const x = clampCenterX(point.x, width);
      const rect = {
        left: x - width / 2,
        right: x + width / 2,
        top: y - height + 0.4,
        bottom: y + 0.4,
      };
      const inside = rect.top >= padTop - 8 && rect.bottom <= vbH - padBottom - 0.4;
      if (inside && pointLabelRects.every((other) => !overlaps(rect, other))) {
        pointLabelRects.push(rect);
        return { x, y, text };
      }
    }
    const fallbackX = clampCenterX(point.x, width);
    const fallbackY = Math.max(point.y - 4.8, padTop + 1.4);
    const fallbackRect = {
      left: fallbackX - width / 2,
      right: fallbackX + width / 2,
      top: fallbackY - height + 0.4,
      bottom: fallbackY + 0.4,
    };
    pointLabelRects.push(fallbackRect);
    return { x: fallbackX, y: fallbackY, text };
  });

  const axisLabels = points.map((point) => {
    const width = Math.max(7.6, point.axisLabel.length * 1.35);
    return {
      ...point,
      axisX: clampCenterX(point.x, width),
    };
  });

  const deltaRects: LabelRect[] = [];
  const segmentDeltas = points
    .slice(0, -1)
    .map((point, index) => {
      const next = points[index + 1]!;
      const delta = Number((next.skill_score - point.skill_score).toFixed(2));
      const label = `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`;
      const width = Math.max(7.8, label.length * 1.55);
      const height = 4.2;
      const midX = (point.x + next.x) / 2;
      const midY = (point.y + next.y) / 2;
      const dx = next.x - point.x;
      const dy = next.y - point.y;
      const length = Math.hypot(dx, dy) || 1;
      const normalX = (-dy / length) * 4.4;
      const normalY = (dx / length) * 4.4;
      const candidates = [
        { x: midX + normalX, y: midY + normalY },
        { x: midX - normalX, y: midY - normalY },
        { x: midX, y: midY - 5.2 },
        { x: midX, y: midY + 5.2 },
      ];

      for (const candidate of candidates) {
        const x = clampCenterX(candidate.x, width);
        const rect = {
          left: x - width / 2,
          right: x + width / 2,
          top: candidate.y - height + 0.2,
          bottom: candidate.y + 0.2,
        };
        const inside = rect.top >= padTop - 6 && rect.bottom <= vbH - padBottom - 3.2;
        const blocked =
          pointLabelRects.some((other) => overlaps(rect, other)) || deltaRects.some((other) => overlaps(rect, other));
        if (inside && !blocked) {
          deltaRects.push(rect);
          return {
            key: `${point.label}-${next.label}`,
            x,
            y: candidate.y,
            label,
          };
        }
      }
      return null;
    })
    .filter((item): item is { key: string; x: number; y: number; label: string } => item != null);

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
            {points.map((point, index) => (
              <g key={point.label}>
                <line
                  x1={point.x}
                  x2={point.x}
                  y1={point.y + 2.3}
                  y2={vbH - padBottom + 1.2}
                  className="trend-guide-line"
                  vectorEffect="non-scaling-stroke"
                />
                <text
                  x={pointLabels[index]!.x}
                  y={pointLabels[index]!.y}
                  textAnchor="middle"
                  className="trend-skill-label"
                >
                  {point.skill_score}
                </text>
                <circle cx={point.x} cy={point.y} r="1.8" className="trend-dot" vectorEffect="non-scaling-stroke" />
                <text x={axisLabels[index]!.axisX} y={vbH - 6.2} textAnchor="middle" className="trend-axis-tick">
                  {point.axisLabel}
                </text>
              </g>
            ))}
            {segmentDeltas.map((item) => (
              <text key={item.key} x={item.x} y={item.y} textAnchor="middle" className="trend-delta-label">
                {item.label}
              </text>
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
