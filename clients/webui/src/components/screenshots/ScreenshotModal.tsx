import { useEffect, type ReactNode } from "react";
import type { User } from "../../api";
import { EmptyState } from "../ui/EmptyState";
import { SecureImage } from "../ui/SecureImage";
import { formatDifficulty } from "../../utils/format";
import { ResultStatGrid, type ResultStatSource } from "./ResultStatGrid";

export type ScreenshotModalItem = ResultStatSource & {
  song_name?: string | null;
  song_id?: number;
  difficulty?: string;
  level?: number | null;
  filename?: string | null;
  image_url?: string | null;
  image_available?: boolean;
  full_combo?: boolean;
  all_perfect?: boolean;
  anomaly?: boolean;
};

type ScreenshotModalProps = {
  items: ScreenshotModalItem[];
  index: number;
  server: User["server"];
  onClose: () => void;
  onIndexChange: (next: number) => void;
  /** Renders above another open modal (e.g. calendar explorer). */
  elevated?: boolean;
};

export function ScreenshotModal({ items, index, server, onClose, onIndexChange, elevated }: ScreenshotModalProps) {
  const item = items[index];
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowLeft" && index > 0) onIndexChange(index - 1);
      if (event.key === "ArrowRight" && index < items.length - 1) onIndexChange(index + 1);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, items.length, onClose, onIndexChange]);

  if (!item) return null;

  const title = item.song_name || (item.song_id != null ? `Song ${item.song_id}` : "Screenshot");
  const diffLabel = item.difficulty ? formatDifficulty(item.difficulty) : "";

  return (
    <div className={`modal-backdrop${elevated ? " modal-backdrop--stack" : ""}`} role="presentation" onClick={onClose}>
      <div className="modal modal-wide" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3>{title}</h3>
            <div className="inline-meta">
              {diffLabel}
              {typeof item.level === "number" && item.level > 0 ? ` · Lv.${item.level}` : ""}
              {item.full_combo ? " · FC" : ""}
              {item.all_perfect ? " · AP" : ""}
              {item.anomaly ? " · Anomaly" : ""}
            </div>
          </div>
          <div className="button-row tight">
            <button className="button ghost" type="button" disabled={index <= 0} onClick={() => onIndexChange(index - 1)}>
              Prev
            </button>
            <button className="button ghost" type="button" disabled={index >= items.length - 1} onClick={() => onIndexChange(index + 1)}>
              Next
            </button>
            <button className="button ghost" type="button" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
        <div className="screenshot-modal-layout">
          <div>
            {item.image_url && item.image_available !== false ? (
              <SecureImage path={item.image_url} alt={item.filename || title} className="viewer-image" priority />
            ) : (
              <EmptyState text="Image not available for this screenshot." />
            )}
          </div>
          <div className="stack">
            <ResultStatGrid item={item} server={server} showMetaFooter />
          </div>
        </div>
      </div>
    </div>
  );
}

export function CompactScreenshotCard({
  item,
  server,
  onOpen,
  thumb,
}: {
  item: ScreenshotModalItem;
  server: User["server"];
  onOpen: () => void;
  thumb?: ReactNode;
}) {
  const title = item.song_name || (item.song_id != null ? `Song ${item.song_id}` : "Screenshot");
  const diffLabel = item.difficulty ? formatDifficulty(item.difficulty) : "";

  return (
    <button type="button" className={`compact-shot-card${thumb ? "" : " compact-shot-card--no-thumb"}`} onClick={onOpen}>
      {thumb ? <div className="compact-shot-card__thumb">{thumb}</div> : null}
      <div className="compact-shot-card__body">
        <div className="compact-shot-card__head">
          <span className="compact-shot-card__title">
            {diffLabel} · {title}
          </span>
          <div className="badge-row">
            {item.full_combo ? <span className="badge fc">FC</span> : null}
            {item.all_perfect ? <span className="badge ap">AP</span> : null}
            {item.anomaly ? <span className="badge warn">!</span> : null}
          </div>
        </div>
        <ResultStatGrid item={item} server={server} showMetaFooter={false} />
      </div>
    </button>
  );
}
