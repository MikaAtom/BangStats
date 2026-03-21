interface LoadingCardProps {
  label: string;
}

export function LoadingCard({ label }: LoadingCardProps) {
  return <div className="card loading-card">{label}</div>;
}

export function LoadingInline() {
  return <div className="inline-meta">Loading...</div>;
}

export function LoadingSpinner({ centered = false }: { centered?: boolean }) {
  return (
    <div className={`loading-spinner${centered ? " loading-spinner--centered" : ""}`}>
      <div className="loading-spinner__stage">
        <div className="loading-spinner__character" />
        <div className="loading-spinner__shadow" />
      </div>
    </div>
  );
}
