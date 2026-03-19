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
            <div className="gallery-meta">
              <strong>{item.song_name || `Song ${item.song_id}`}</strong>
              <span>
                {item.difficulty} | {item.live_type}
              </span>
              <span>
                {new Date(item.timestamp).toLocaleString()} | {item.accuracy}% acc
              </span>
              <small>
                Score {item.score.toLocaleString()}
              </small>
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
            {active.image_available && active.image_url ? (
              <SecureImage path={active.image_url} alt={active.filename || ""} className="viewer-image" />
            ) : (
              <EmptyState text="Image not available for this screenshot." />
            )}
            <KeyValueList
              items={[
                ["Difficulty", active.difficulty],
                ["Live type", active.live_type],
                ["Accuracy", `${active.accuracy}%`],
                ["Score", active.score.toLocaleString()],
                ["Timestamp", new Date(active.timestamp).toLocaleString()],
              ]}
            />
          </div>
        </div>
      )}
    </>
  );
}
