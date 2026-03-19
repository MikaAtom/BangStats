export type DateRangeValue = {
  preset: "7d" | "30d" | "90d" | "1y" | "custom";
  from: string;
  to: string;
};

interface DateRangePickerProps {
  value: DateRangeValue;
  onChange: (value: DateRangeValue) => void;
}

const PRESETS: Array<{ label: string; value: DateRangeValue["preset"] }> = [
  { label: "7d", value: "7d" },
  { label: "30d", value: "30d" },
  { label: "90d", value: "90d" },
  { label: "1y", value: "1y" },
  { label: "Custom", value: "custom" },
];

export function DateRangePicker({ value, onChange }: DateRangePickerProps) {
  return (
    <div className="date-range-picker">
      <div className="date-range-presets">
        {PRESETS.map((preset) => (
          <button
            key={preset.value}
            type="button"
            className={`button ${value.preset === preset.value ? "primary" : "ghost"}`}
            onClick={() => onChange({ ...value, preset: preset.value })}
          >
            {preset.label}
          </button>
        ))}
      </div>
      {value.preset === "custom" && (
        <div className="date-range-inputs">
          <label className="field">
            <span>From</span>
            <input
              type="date"
              value={value.from}
              onChange={(event) => onChange({ ...value, preset: "custom", from: event.target.value })}
            />
          </label>
          <label className="field">
            <span>To</span>
            <input
              type="date"
              value={value.to}
              onChange={(event) => onChange({ ...value, preset: "custom", to: event.target.value })}
            />
          </label>
        </div>
      )}
    </div>
  );
}
