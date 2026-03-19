interface LoadingCardProps {
  label: string;
}

export function LoadingCard({ label }: LoadingCardProps) {
  return <div className="card loading-card">{label}</div>;
}

export function LoadingInline() {
  return <div className="inline-meta">Loading...</div>;
}
