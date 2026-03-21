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

function expandRect(rect: LabelRect, dx: number, dy: number): LabelRect {
  return {
    left: rect.left - dx,
    right: rect.right + dx,
    top: rect.top - dy,
    bottom: rect.bottom + dy,
  };
}

export function TrendChart({ data, variant = "default", server = "en" }: TrendChartProps) {
  if (!data.points.length) {
    return <div className="empty-state">No progression points in this range — try another scope or filters.</div>;
  }

  const n = data.points.length;
  const vbW = 100;
  const vbH = variant === "overview" ? 82 : 44;
  const padLeft = variant === "overview" ? 9 : 6;
  const padRight = variant === "overview" ? 9 : 6;
  const padTop = variant === "overview" ? 16 : 7;
  const padBottom = variant === "overview" ? 19 : 7;
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
  const clampLabelLeft = (left: number, width: number) => Math.min(Math.max(left, 1.2), vbW - 1.2 - width);
  const dotRects = points.map((point) => expandRect({ left: point.x - 1.9, right: point.x + 1.9, top: point.y - 1.9, bottom: point.y + 1.9 }, 0.8, 0.8));

  const pointLabelRects: LabelRect[] = [];
  const pointLabels = points.map((point, index) => {
    const text = String(point.skill_score);
    const width = Math.max(8.8, text.length * 1.9);
    const height = 5.1;
    const anchor = (index === 0 ? "start" : index === n - 1 ? "end" : "middle") as "start" | "middle" | "end";
    const desiredLeft =
      anchor === "start" ? point.x + 0.5 : anchor === "end" ? point.x - width - 0.5 : point.x - width / 2;
    const left = clampLabelLeft(desiredLeft, width);
    const x = anchor === "start" ? left : anchor === "end" ? left + width : left + width / 2;
    const candidateYs = point.isValley ? [point.y + 6.2, point.y - 4.8] : [point.y - 4.8, point.y + 6.2];

    for (const baselineY of candidateYs) {
      const rect = {
        left,
        right: left + width,
        top: baselineY - height + 0.35,
        bottom: baselineY + 0.35,
      };
      const inside = rect.top >= 1.2 && rect.bottom <= vbH - padBottom - 2.2;
      const blocked =
        pointLabelRects.some((other) => overlaps(expandRect(rect, 0.5, 0.25), other)) ||
        dotRects.some((other) => overlaps(expandRect(rect, 0.2, 0.2), other));
      if (inside && !blocked) {
        pointLabelRects.push(rect);
        return { x, y: baselineY, anchor, text };
      }
    }

    const fallbackY = Math.max(point.y - 4.8, 3.8);
    const fallbackRect = {
      left,
      right: left + width,
      top: fallbackY - height + 0.35,
      bottom: fallbackY + 0.35,
    };
    pointLabelRects.push(fallbackRect);
    return { x, y: fallbackY, anchor, text };
  });

  const axisLabels = points.map((point) => {
    const width = Math.max(8.2, point.axisLabel.length * 1.35);
    const left = clampLabelLeft(point.x - width / 2, width);
    return { x: left + width / 2, label: point.axisLabel };
  });

  const deltaRects: LabelRect[] = [];
  const segmentDeltas = points
    .slice(0, -1)
    .map((point, index) => {
      const next = points[index + 1]!;
      const delta = Number((next.skill_score - point.skill_score).toFixed(2));
      const label = `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`;
      const width = Math.max(7.2, label.length * 1.5);
      const height = 4;
      const midX = (point.x + next.x) / 2;
      const midY = (point.y + next.y) / 2;
      const dx = next.x - point.x;
      const dy = next.y - point.y;
      const length = Math.hypot(dx, dy) || 1;
      const normalX = -dy / length;
      const normalY = dx / length;
      const candidateOffsets = [6.6, 8.4];
      const signedSides = [
        { sx: normalX, sy: normalY },
        { sx: -normalX, sy: -normalY },
      ].sort((a, b) => {
        const aY = midY + a.sy * candidateOffsets[0]!;
        const bY = midY + b.sy * candidateOffsets[0]!;
        const aRoom = Math.min(aY - 2, vbH - padBottom - 3 - aY);
        const bRoom = Math.min(bY - 2, vbH - padBottom - 3 - bY);
        return bRoom - aRoom;
      });

      for (const side of signedSides) {
        for (const offset of candidateOffsets) {
          const cx = midX + side.sx * offset;
          const cy = midY + side.sy * offset;
          const left = clampLabelLeft(cx - width / 2, width);
          const rect = {
            left,
            right: left + width,
            top: cy - height + 0.25,
            bottom: cy + 0.25,
          };
          const inside = rect.top >= 2 && rect.bottom <= vbH - padBottom - 3.2;
          const blocked =
            pointLabelRects.some((other) => overlaps(expandRect(rect, 0.4, 0.2), other)) ||
            deltaRects.some((other) => overlaps(expandRect(rect, 0.4, 0.2), other)) ||
            dotRects.some((other) => overlaps(expandRect(rect, 0.3, 0.2), other));
          if (inside && !blocked) {
            deltaRects.push(rect);
            return {
              key: `${point.label}-${next.label}`,
              x: left + width / 2,
              y: cy,
              label,
            };
          }
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
                  textAnchor={pointLabels[index]!.anchor}
                  className="trend-skill-label"
                >
                  {point.skill_score}
                </text>
                <circle cx={point.x} cy={point.y} r="1.8" className="trend-dot" vectorEffect="non-scaling-stroke" />
                <text x={axisLabels[index]!.x} y={vbH - 6.2} textAnchor="middle" className="trend-axis-tick">
                  {axisLabels[index]!.label}
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
