import { EmptyState } from "../ui/EmptyState";

interface KeyValueListProps {
  items: Array<[string, string]>;
  emptyLabel?: string;
}

export function KeyValueList({ items, emptyLabel }: KeyValueListProps) {
  if (!items.length) return <EmptyState text={emptyLabel || "Nothing to show."} />;
  return (
    <dl className="kv-list">
      {items.map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
