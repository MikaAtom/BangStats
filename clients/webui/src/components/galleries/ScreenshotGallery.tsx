import { useState } from "react";
import type { ScreenshotItem, User } from "../../api";
import { EmptyState } from "../ui/EmptyState";
import { SecureImage } from "../ui/SecureImage";
import { CompactScreenshotCard, ScreenshotModal, type ScreenshotModalItem } from "../screenshots/ScreenshotModal";

interface ScreenshotGalleryProps {
  items: ScreenshotItem[];
  server: User["server"];
}

function toModalItem(item: ScreenshotItem): ScreenshotModalItem {
  return {
    ...item,
    image_available: item.image_available,
  };
}

export function ScreenshotGallery({ items, server }: ScreenshotGalleryProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const modalItems: ScreenshotModalItem[] = items.map(toModalItem);

  if (!items.length) return <EmptyState text="No screenshots found." />;

  return (
    <>
      <div className="gallery compact-shot-gallery">
        {items.map((item, index) => (
          <div key={item.id} className="gallery-card compact-shot-wrap">
            <CompactScreenshotCard
              item={toModalItem(item)}
              server={server}
              onOpen={() => setActiveIndex(index)}
              thumb={
                item.image_available && item.image_url ? (
                  <SecureImage path={item.image_url} alt={item.filename || `screenshot-${item.id}`} className="compact-shot-thumb" />
                ) : (
                  <div className="gallery-placeholder compact-shot-thumb">No image</div>
                )
              }
            />
          </div>
        ))}
      </div>
      {activeIndex != null && (
        <ScreenshotModal
          items={modalItems}
          index={activeIndex}
          server={server}
          onClose={() => setActiveIndex(null)}
          onIndexChange={setActiveIndex}
        />
      )}
    </>
  );
}
