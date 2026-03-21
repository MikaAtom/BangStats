import { useLayoutEffect, useMemo, useRef, useState } from "react";
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

type Vector = {
  x: number;
  y: number;
};

type MeasuredTextBox = LabelRect & {
  width: number;
  height: number;
};

type PlacedPointLabel = {
  x: number;
  y: number;
  text: string;
  rect: LabelRect;
};

type PlacedDeltaLabel = {
  key: string;
  x: number;
  y: number;
  label: string;
  rect: LabelRect;
};

type OverviewLayout = {
  pointLabels: PlacedPointLabel[];
  segmentDeltas: PlacedDeltaLabel[];
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

function rectWidth(rect: LabelRect) {
  return rect.right - rect.left;
}

function rectHeight(rect: LabelRect) {
  return rect.bottom - rect.top;
}

function translateRect(rect: LabelRect, dx: number, dy: number): LabelRect {
  return {
    left: rect.left + dx,
    right: rect.right + dx,
    top: rect.top + dy,
    bottom: rect.bottom + dy,
  };
}

function rectInsideBounds(rect: LabelRect, bounds: LabelRect) {
  return rect.left >= bounds.left && rect.right <= bounds.right && rect.top >= bounds.top && rect.bottom <= bounds.bottom;
}

function vectorLength(vector: Vector) {
  return Math.hypot(vector.x, vector.y);
}

function normalize(vector: Vector): Vector {
  const length = vectorLength(vector) || 1;
  return { x: vector.x / length, y: vector.y / length };
}

function dot(a: Vector, b: Vector) {
  return a.x * b.x + a.y * b.y;
}

function rectFromMeasured(box: MeasuredTextBox, x: number, y: number): LabelRect {
  return {
    left: x + box.left,
    right: x + box.right,
    top: y + box.top,
    bottom: y + box.bottom,
  };
}

function clampRectToBounds(rect: LabelRect, bounds: LabelRect): LabelRect {
  const width = rectWidth(rect);
  const height = rectHeight(rect);
  const shiftX = Math.min(Math.max(0, bounds.left - rect.left), bounds.right - rect.right) || Math.max(Math.min(0, bounds.right - rect.right), bounds.left - rect.left);
  const shiftY = Math.min(Math.max(0, bounds.top - rect.top), bounds.bottom - rect.bottom) || Math.max(Math.min(0, bounds.bottom - rect.bottom), bounds.top - rect.top);
  const clamped = translateRect(rect, shiftX, shiftY);
  return {
    left: Math.min(Math.max(clamped.left, bounds.left), bounds.right - width),
    right: Math.min(Math.max(clamped.right, bounds.left + width), bounds.right),
    top: Math.min(Math.max(clamped.top, bounds.top), bounds.bottom - height),
    bottom: Math.min(Math.max(clamped.bottom, bounds.top + height), bounds.bottom),
  };
}

function pointInRect(point: Vector, rect: LabelRect) {
  return point.x >= rect.left && point.x <= rect.right && point.y >= rect.top && point.y <= rect.bottom;
}

function orientation(a: Vector, b: Vector, c: Vector) {
  return (b.y - a.y) * (c.x - b.x) - (b.x - a.x) * (c.y - b.y);
}

function onSegment(a: Vector, b: Vector, c: Vector) {
  return (
    Math.min(a.x, c.x) <= b.x &&
    b.x <= Math.max(a.x, c.x) &&
    Math.min(a.y, c.y) <= b.y &&
    b.y <= Math.max(a.y, c.y)
  );
}

function segmentsIntersect(a1: Vector, a2: Vector, b1: Vector, b2: Vector) {
  const o1 = orientation(a1, a2, b1);
  const o2 = orientation(a1, a2, b2);
  const o3 = orientation(b1, b2, a1);
  const o4 = orientation(b1, b2, a2);

  if (o1 === 0 && onSegment(a1, b1, a2)) return true;
  if (o2 === 0 && onSegment(a1, b2, a2)) return true;
  if (o3 === 0 && onSegment(b1, a1, b2)) return true;
  if (o4 === 0 && onSegment(b1, a2, b2)) return true;

  return (o1 > 0) !== (o2 > 0) && (o3 > 0) !== (o4 > 0);
}

function segmentIntersectsRect(start: Vector, end: Vector, rect: LabelRect) {
  if (pointInRect(start, rect) || pointInRect(end, rect)) return true;
  const corners = [
    { x: rect.left, y: rect.top },
    { x: rect.right, y: rect.top },
    { x: rect.right, y: rect.bottom },
    { x: rect.left, y: rect.bottom },
  ];
  for (let index = 0; index < corners.length; index += 1) {
    const edgeStart = corners[index]!;
    const edgeEnd = corners[(index + 1) % corners.length]!;
    if (segmentsIntersect(start, end, edgeStart, edgeEnd)) return true;
  }
  return false;
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

function getMeasuredTextBox(node: SVGTextElement | null): MeasuredTextBox | null {
  if (!node) return null;
  const bbox = node.getBBox();
  return {
    left: bbox.x,
    right: bbox.x + bbox.width,
    top: bbox.y,
    bottom: bbox.y + bbox.height,
    width: bbox.width,
    height: bbox.height,
  };
}

function layoutEquals(a: OverviewLayout | null, b: OverviewLayout | null) {
  if (!a || !b) return a === b;
  if (a.pointLabels.length !== b.pointLabels.length || a.segmentDeltas.length !== b.segmentDeltas.length) return false;
  const pointMatch = a.pointLabels.every((label, index) => {
    const other = b.pointLabels[index];
    return other && label.text === other.text && Math.abs(label.x - other.x) < 0.01 && Math.abs(label.y - other.y) < 0.01;
  });
  if (!pointMatch) return false;
  return a.segmentDeltas.every((label, index) => {
    const other = b.segmentDeltas[index];
    return other && label.key === other.key && Math.abs(label.x - other.x) < 0.01 && Math.abs(label.y - other.y) < 0.01;
  });
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

  const points = useMemo(
    () =>
      data.points.map((point, index) => {
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
      }),
    [data.points, innerH, innerW, minScore, n, padLeft, padTop, scoreSpan, server],
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

  const pointMeasureRefs = useRef<(SVGTextElement | null)[]>([]);
  const deltaMeasureRefs = useRef<(SVGTextElement | null)[]>([]);
  const [overviewLayout, setOverviewLayout] = useState<OverviewLayout | null>(null);

  useLayoutEffect(() => {
    if (variant !== "overview") {
      setOverviewLayout(null);
      return;
    }

    const pointBoxes = points.map((_, index) => getMeasuredTextBox(pointMeasureRefs.current[index] ?? null));
    const deltaBoxes = points.slice(0, -1).map((_, index) => getMeasuredTextBox(deltaMeasureRefs.current[index] ?? null));
    if (pointBoxes.some((box) => !box) || deltaBoxes.some((box) => !box)) return;

    const dotRadius = Math.max(innerW / (n * 12), innerH / 20);
    const lineWidth = Math.max(innerH / 55, 0.6);
    const guideWidth = Math.max(lineWidth * 0.9, dotRadius * 0.16);
    const boundsMargin = Math.max(lineWidth, dotRadius * 0.2);
    const chartBounds: LabelRect = {
      left: boundsMargin,
      right: vbW - boundsMargin,
      top: boundsMargin,
      bottom: vbH - padBottom - boundsMargin,
    };
    const guideBottom = vbH - padBottom + Math.max(dotRadius * 0.65, lineWidth);
    const dotRects = points.map((point) =>
      expandRect(
        {
          left: point.x - dotRadius,
          right: point.x + dotRadius,
          top: point.y - dotRadius,
          bottom: point.y + dotRadius,
        },
        dotRadius * 0.45,
        dotRadius * 0.45,
      ),
    );
    const guideRects = points.map((point) =>
      expandRect(
        {
          left: point.x - guideWidth / 2,
          right: point.x + guideWidth / 2,
          top: point.y + dotRadius,
          bottom: guideBottom,
        },
        guideWidth * 1.5,
        guideWidth,
      ),
    );
    const segments = points.slice(0, -1).map((point, index) => {
      const next = points[index + 1]!;
      return {
        start: { x: point.x, y: point.y },
        end: { x: next.x, y: next.y },
      };
    });

    const lineBlocked = (rect: LabelRect, box: MeasuredTextBox) =>
      segments.some(({ start, end }) =>
        segmentIntersectsRect(start, end, expandRect(rect, Math.max(lineWidth * 2, box.height * 0.28), Math.max(lineWidth * 2, box.height * 0.28))),
      );

    const pointLabels: PlacedPointLabel[] = new Array(points.length);
    const pointLabelRects: LabelRect[] = [];
    const placementOrder = points
      .map((point, index) => {
        const horizontalRoom = Math.min(point.x - chartBounds.left, chartBounds.right - point.x);
        const verticalRoom = Math.min(point.y - chartBounds.top, chartBounds.bottom - point.y);
        return { index, room: Math.min(horizontalRoom, verticalRoom) };
      })
      .sort((a, b) => a.room - b.room)
      .map((item) => item.index);

    for (const index of placementOrder) {
      const point = points[index]!;
      const box = pointBoxes[index]!;
      const prev = points[index - 1];
      const next = points[index + 1];
      const prefersBelow = point.isValley || (!prev && next && next.y < point.y) || (!next && prev && prev.y < point.y);
      const verticalDirection = prefersBelow ? 1 : -1;
      const baseDistance = dotRadius + box.height / 2 + Math.max(box.height * 0.35, lineWidth * 3);
      const distanceStep = Math.max(box.height * 0.7, dotRadius * 0.85);
      const horizontalStep = Math.max(box.width / 4, dotRadius * 0.9);
      const horizontalLimit = Math.max(box.width * 0.75, innerW / Math.max(4, n));
      let placed: PlacedPointLabel | null = null;

      for (const distance of [baseDistance, baseDistance + distanceStep, baseDistance + distanceStep * 2, baseDistance + distanceStep * 3]) {
        for (const horizontalShift of collectShiftSeries(horizontalLimit, horizontalStep)) {
          const x = clamp(point.x + horizontalShift, chartBounds.left + box.width / 2, chartBounds.right - box.width / 2);
          const y = clamp(point.y + verticalDirection * distance, chartBounds.top - box.top, chartBounds.bottom - box.bottom);
          const rect = rectFromMeasured(box, x, y);
          const blocked =
            pointLabelRects.some((other) => overlaps(expandRect(rect, box.height * 0.22, box.height * 0.18), other)) ||
            dotRects.some((other) => overlaps(expandRect(rect, box.height * 0.16, box.height * 0.16), other)) ||
            guideRects.some((other) => overlaps(expandRect(rect, box.height * 0.08, box.height * 0.08), other)) ||
            lineBlocked(rect, box);
          if (!blocked && rectInsideBounds(rect, chartBounds)) {
            placed = { x, y, text: String(point.skill_score), rect };
            break;
          }
        }
        if (placed) break;
      }

      if (!placed) {
        const fallbackRect = clampRectToBounds(rectFromMeasured(box, point.x, point.y + verticalDirection * baseDistance), chartBounds);
        placed = {
          x: fallbackRect.left - box.left,
          y: fallbackRect.top - box.top,
          text: String(point.skill_score),
          rect: fallbackRect,
        };
      }

      pointLabels[index] = placed;
      pointLabelRects.push(placed.rect);
    }

    const deltaRects: LabelRect[] = [];
    const segmentDeltas: PlacedDeltaLabel[] = [];
    points.slice(0, -1).forEach((point, index) => {
      const next = points[index + 1]!;
      const box = deltaBoxes[index]!;
      const delta = Number((next.skill_score - point.skill_score).toFixed(2));
      const label = `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`;
      const start = { x: point.x, y: point.y };
      const end = { x: next.x, y: next.y };
      const tangent = normalize({ x: end.x - start.x, y: end.y - start.y });
      const normal = normalize({ x: -tangent.y, y: tangent.x });
      const midpoint = { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
      const segmentLength = Math.max(vectorLength({ x: end.x - start.x, y: end.y - start.y }), 1);
      const normalBase = dotRadius + box.height / 2 + Math.max(lineWidth * 3, box.height * 0.4);
      const normalStep = Math.max(box.height * 0.75, dotRadius * 0.8);
      const maxNormal = Math.max(normalBase + normalStep * 4, innerH / 3);
      const tangentLimit = Math.max(0, segmentLength / 2 - Math.max(dotRadius * 1.6, box.width * 0.22));
      const tangentStep = Math.max(box.width / 3.8, dotRadius * 0.8);
      const upperSide = midpoint.y + normal.y * normalBase < midpoint.y + -normal.y * normalBase ? normal : { x: -normal.x, y: -normal.y };
      const lowerSide = upperSide === normal ? { x: -normal.x, y: -normal.y } : normal;
      const sideVectors = [upperSide, lowerSide];
      let placed: PlacedDeltaLabel | null = null;

      for (const side of sideVectors) {
        let normalDistance = normalBase;
        while (normalDistance <= maxNormal + normalStep * 0.5) {
          for (const tangentShift of collectShiftSeries(tangentLimit, tangentStep)) {
            const x = clamp(
              midpoint.x + side.x * normalDistance + tangent.x * tangentShift,
              chartBounds.left + box.width / 2,
              chartBounds.right - box.width / 2,
            );
            const y = clamp(
              midpoint.y + side.y * normalDistance + tangent.y * tangentShift,
              chartBounds.top - box.top,
              chartBounds.bottom - box.bottom,
            );
            const rect = rectFromMeasured(box, x, y);
            const blocked =
              pointLabelRects.some((other) => overlaps(expandRect(rect, box.height * 0.24, box.height * 0.2), other)) ||
              deltaRects.some((other) => overlaps(expandRect(rect, box.height * 0.22, box.height * 0.18), other)) ||
              dotRects.some((other) => overlaps(expandRect(rect, box.height * 0.14, box.height * 0.14), other)) ||
              guideRects.some((other) => overlaps(expandRect(rect, box.height * 0.14, box.height * 0.14), other)) ||
              lineBlocked(rect, box);
            if (!blocked && rectInsideBounds(rect, chartBounds)) {
              placed = { key: `${point.label}-${next.label}`, x, y, label, rect };
              break;
            }
          }
          if (placed) break;
          normalDistance += normalStep;
        }
        if (placed) break;
      }

      if (placed) {
        deltaRects.push(placed.rect);
        segmentDeltas.push(placed);
      }
    });

    const nextLayout = { pointLabels, segmentDeltas };
    setOverviewLayout((previous) => (layoutEquals(previous, nextLayout) ? previous : nextLayout));
  }, [innerH, innerW, n, padBottom, points, variant, vbH, vbW]);

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
            <g aria-hidden="true" opacity="0" pointerEvents="none">
              {points.map((point, index) => (
                <text
                  key={`measure-point-${point.label}`}
                  ref={(node) => {
                    pointMeasureRefs.current[index] = node;
                  }}
                  x={0}
                  y={0}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="trend-skill-label"
                >
                  {point.skill_score}
                </text>
              ))}
              {points.slice(0, -1).map((point, index) => {
                const next = points[index + 1]!;
                const delta = Number((next.skill_score - point.skill_score).toFixed(2));
                const label = `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`;
                return (
                  <text
                    key={`measure-delta-${point.label}-${next.label}`}
                    ref={(node) => {
                      deltaMeasureRefs.current[index] = node;
                    }}
                    x={0}
                    y={0}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className="trend-delta-label"
                  >
                    {label}
                  </text>
                );
              })}
            </g>
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
