import { useMemo } from "react";
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

type Vector = {
  x: number;
  y: number;
};

type PlacedPointLabel = {
  x: number;
  y: number;
  text: string;
  rect: Rect;
};

type PlacedDeltaLabel = {
  key: string;
  x: number;
  y: number;
  label: string;
  rect: Rect;
};

type Rect = {
  left: number;
  right: number;
  top: number;
  bottom: number;
};

function overlaps(a: Rect, b: Rect) {
  return !(a.right < b.left || a.left > b.right || a.bottom < b.top || a.top > b.bottom);
}

function expandRect(rect: Rect, dx: number, dy: number): Rect {
  return {
    left: rect.left - dx,
    right: rect.right + dx,
    top: rect.top - dy,
    bottom: rect.bottom + dy,
  };
}

function vectorLength(vector: Vector) {
  return Math.hypot(vector.x, vector.y);
}

function normalize(vector: Vector): Vector {
  const length = vectorLength(vector) || 1;
  return { x: vector.x / length, y: vector.y / length };
}

function rectFromCenter(x: number, y: number, width: number, height: number): Rect {
  return {
    left: x - width / 2,
    right: x + width / 2,
    top: y - height / 2,
    bottom: y + height / 2,
  };
}

function collectShiftSeries(limit: number, step: number) {
  const values = [0];
  if (limit <= 0 || step <= 0) return values;
  let distance = step;
  while (distance <= limit + step * 0.5) {
    values.push(distance, -distance);
    distance += step;
  }
  return values;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function estimateTextWidth(text: string, fontSize: number) {
  return Math.max(fontSize * 2.6, text.length * fontSize * 0.62 + fontSize * 0.7);
}

function estimateTextHeight(fontSize: number) {
  return fontSize * 1.15;
}

export function TrendChart({ data, variant = "default", server = "en" }: TrendChartProps) {
  if (!data.points.length) {
    return <div className="empty-state">No progression points in this range — try another scope or filters.</div>;
  }

  const n = data.points.length;
  const vbW = 100;
  const vbH = variant === "overview" ? 86 : 44;
  const padLeft = variant === "overview" ? 9 : 6;
  const padRight = variant === "overview" ? 9 : 6;
  const padTop = variant === "overview" ? 13 : 7;
  const padBottom = variant === "overview" ? 20 : 7;
  const innerW = vbW - padLeft - padRight;

  const scores = data.points.map((point) => point.skill_score);
  const minScore = Math.min(...scores);
  const maxScore = Math.max(...scores);
  const scoreSpan = Math.max(maxScore - minScore, 0.5);
  const dotRadius = variant === "overview" ? 1.8 : 1.55;
  const valueFontSize = variant === "overview" ? 3.2 : 0;
  const deltaFontSize = variant === "overview" ? 2.3 : 0;
  const valueLabelHeight = estimateTextHeight(valueFontSize);
  const deltaLabelHeight = estimateTextHeight(deltaFontSize);
  const topValueBand = variant === "overview" ? valueLabelHeight + dotRadius * 2.4 : 0;
  const bottomValueBand = variant === "overview" ? valueLabelHeight + dotRadius * 2.6 : 0;
  const deltaBand = variant === "overview" ? deltaLabelHeight + dotRadius * 1.8 : 0;
  const plotTop = padTop + topValueBand + deltaBand;
  const plotBottom = vbH - padBottom - bottomValueBand;
  const innerH = (variant === "overview" ? plotBottom - plotTop : vbH - padTop - padBottom);

  const points = useMemo(
    () =>
      data.points.map((point, index) => {
        const t = n <= 1 ? 0.5 : index / (n - 1);
        const x = padLeft + t * innerW;
        const normalized = (point.skill_score - minScore) / scoreSpan;
        const y = (variant === "overview" ? plotTop : padTop) + innerH - normalized * innerH;
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
      }),
    [data.points, innerH, innerW, minScore, n, padLeft, padTop, plotTop, scoreSpan, server, variant],
  );
  const axisLabels = useMemo(
    () =>
      points.map((point) => {
        const width = Math.max(8.2, point.axisLabel.length * 1.35);
        const left = Math.min(Math.max(point.x - width / 2, 1.2), vbW - 1.2 - width);
        return { x: left + width / 2, label: point.axisLabel };
      }),
    [points, vbW],
  );
  const path = useMemo(
    () => points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(3)} ${point.y.toFixed(3)}`).join(" "),
    [points],
  );
  const overviewLayout = useMemo(() => {
    if (variant !== "overview") return null;

    const horizontalBounds = {
      left: 1.2,
      right: vbW - 1.2,
    };
    const valueOffset = dotRadius + valueLabelHeight / 2 + valueFontSize * 0.55;
    const deltaOffset = dotRadius + deltaLabelHeight / 2 + deltaFontSize * 0.85;
    const pointLabels: PlacedPointLabel[] = points.map((point) => {
      const text = String(point.skill_score);
      const width = estimateTextWidth(text, valueFontSize);
      const x = clamp(point.x, horizontalBounds.left + width / 2, horizontalBounds.right - width / 2);
      const y = point.isValley ? point.y + valueOffset : point.y - valueOffset;
      return {
        x,
        y,
        text,
        rect: rectFromCenter(x, y, width, valueLabelHeight),
      };
    });

    const pointLabelRects = pointLabels.map((label) => label.rect);
    const segmentDeltas: PlacedDeltaLabel[] = points.slice(0, -1).map((point, index) => {
      const next = points[index + 1]!;
      const delta = Number((next.skill_score - point.skill_score).toFixed(2));
      const label = `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`;
      const width = estimateTextWidth(label, deltaFontSize);
      const height = deltaLabelHeight;
      const start = { x: point.x, y: point.y };
      const end = { x: next.x, y: next.y };
      const midpoint = { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
      const tangent = normalize({ x: end.x - start.x, y: end.y - start.y });
      const normal = normalize({ x: -tangent.y, y: tangent.x });
      const upperNormal = normal.y <= 0 ? normal : { x: -normal.x, y: -normal.y };
      const halfSpan = Math.abs(end.x - start.x) / 2;
      const tangentLimit = Math.max(0, halfSpan - width / 2 - dotRadius * 1.4);
      const pointGap = valueLabelHeight * 0.35;
      let tangentShift = 0;
      let rect = rectFromCenter(midpoint.x, midpoint.y + upperNormal.y * deltaOffset, width, height);

      const overlapsStart = overlaps(expandRect(rect, pointGap, pointGap), pointLabelRects[index]!);
      const overlapsEnd = overlaps(expandRect(rect, pointGap, pointGap), pointLabelRects[index + 1]!);
      if (overlapsStart || overlapsEnd) {
        const awayFromStart = { x: tangent.x, y: tangent.y };
        const awayFromEnd = { x: -tangent.x, y: -tangent.y };
        const preferredDirection = overlapsStart && !overlapsEnd ? awayFromStart : overlapsEnd && !overlapsStart ? awayFromEnd : (point.y < next.y ? awayFromEnd : awayFromStart);
        tangentShift = tangentLimit * Math.sign(preferredDirection.x || 1);
      }

      const x = clamp(
        midpoint.x + upperNormal.x * deltaOffset + tangent.x * tangentShift,
        Math.min(start.x, end.x) + width / 2,
        Math.max(start.x, end.x) - width / 2,
      );
      const y = midpoint.y + upperNormal.y * deltaOffset + tangent.y * tangentShift;
      rect = rectFromCenter(x, y, width, height);

      return {
        key: `${point.label}-${next.label}`,
        x,
        y,
        label,
        rect,
      };
    });

    return { pointLabels, segmentDeltas };
  }, [deltaFontSize, deltaLabelHeight, dotRadius, points, valueFontSize, valueLabelHeight, variant, vbW]);

  const gridLines = [0, 0.5, 1].map((fraction) => {
    const y = (variant === "overview" ? plotTop : padTop) + innerH - fraction * innerH;
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
                  x={overviewLayout?.pointLabels[index]?.x ?? point.x}
                  y={overviewLayout?.pointLabels[index]?.y ?? point.y}
                  textAnchor="middle"
                  dominantBaseline="middle"
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
            {(overviewLayout?.segmentDeltas ?? []).map((item) => (
              <text key={item.key} x={item.x} y={item.y} textAnchor="middle" dominantBaseline="middle" className="trend-delta-label">
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
