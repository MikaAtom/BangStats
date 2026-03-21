import { useState } from "react";
import type { ScreenshotItem } from "../../api";
import { EmptyState } from "../ui/EmptyState";
import { SecureImage } from "../ui/SecureImage";
import { KeyValueList } from "../data-display/KeyValueList";

interface ScreenshotGalleryProps {
  items: ScreenshotItem[];
}

export function ScreenshotGallery({ items }: ScreenshotGalleryProps) {
  const [active, setActive] = useState<ScreenshotItem | null>(null);
  if (!items.length) return <EmptyState text="No screenshots found." />;
  return (
    <>
      <div className="gallery">
        {items.map((item) => (
          <button className="gallery-card interactive" key={item.id} onClick={() => setActive(item)}>
            {item.image_available && item.image_url ? (
              <SecureImage path={item.image_url} alt={item.filename || `screenshot-${item.id}`} className="gallery-image" />
            ) : (
              <div className="gallery-placeholder">No image</div>
            )}
            <div className="gallery-meta compact-screenshot-meta">
              <strong>{item.song_name || `Song ${item.song_id}`}</strong>
              <span>{item.difficulty}</span>
              <div className="screenshot-stat-grid">
                <span>Perfect</span><span>{item.perfect}</span>
                <span>Fast</span><span>{item.fast}</span>
                <span>Great</span><span>{item.great}</span>
                <span>Slow</span><span>{item.slow}</span>
                <span>Good</span><span>{item.good}</span>
                <span>Max combo</span><span>{item.max_combo}</span>
                <span>Bad</span><span>{item.bad}</span>
                <span>Miss</span><span>{item.miss}</span>
              </div>
            </div>
          </button>
        ))}
      </div>
      {active && (
        <div className="modal-backdrop" onClick={() => setActive(null)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="card-header">
              <h3>{active.song_name || `Song ${active.song_id}`}</h3>
              <button className="button ghost" onClick={() => setActive(null)}>
                Close
              </button>
            </div>
            <div className="layout-two">
              <div>
                {active.image_available && active.image_url ? (
                  <SecureImage path={active.image_url} alt={active.filename || ""} className="viewer-image" />
                ) : (
                  <EmptyState text="Image not available for this screenshot." />
                )}
              </div>
              <div>
                <KeyValueList
                  items={[
                    ["Difficulty", active.difficulty],
                    ["Live type", active.live_type],
                    ["Perfect", String(active.perfect)],
                    ["Fast", String(active.fast)],
                    ["Great", String(active.great)],
                    ["Slow", String(active.slow)],
                    ["Good", String(active.good)],
                    ["Max combo", String(active.max_combo)],
                    ["Bad", String(active.bad)],
                    ["Miss", String(active.miss)],
                    ["Accuracy", `${active.accuracy}%`],
                    ["Score", active.score.toLocaleString()],
                    ["Timestamp", new Date(active.timestamp).toLocaleString()],
                  ]}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
