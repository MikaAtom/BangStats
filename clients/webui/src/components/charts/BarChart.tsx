interface BarChartProps {
  items: Array<{ label: string; value: number }>;
}

export function BarChart({ items }: BarChartProps) {
  const max = Math.max(...items.map((item) => item.value), 1);
  return (
    <div className="bar-chart">
      {items.map((item) => (
        <div key={item.label} className="bar-row">
          <span className="bar-label" title={item.label}>
            {item.label}
          </span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(item.value / max) * 100}%` }}>
              <span className="bar-value-inline">{item.value}</span>
            </div>
          </div>
          <strong className="bar-value">{item.value}</strong>
        </div>
      ))}
    </div>
  );
}
