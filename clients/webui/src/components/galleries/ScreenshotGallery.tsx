import { useEffect, useMemo, useRef, useState } from "react";
import type { ScreenshotItem, User } from "../../api";
import { useThumbnailPrewarm } from "../../hooks/useThumbnailPrewarm";
import { EmptyState } from "../ui/EmptyState";
import { SecureImage } from "../ui/SecureImage";
import { CompactScreenshotCard, ScreenshotModal, type ScreenshotModalItem } from "../screenshots/ScreenshotModal";

interface ScreenshotGalleryProps {
  items: ScreenshotItem[];
  server: User["server"];
  userId: number;
}

const VIRTUAL_THRESHOLD = 20;
const EST_ROW_PX = 132;
const MIN_COL_WIDTH = 200;

function toModalItem(item: ScreenshotItem): ScreenshotModalItem {
  return {
    ...item,
    image_available: item.image_available,
  };
}

function screenshotIdsForPrewarm(slice: ScreenshotItem[]) {
  return slice.filter((i) => i.image_available && i.image_url).map((i) => i.id);
}

function VirtualizedScreenshotBody({
  items,
  server,
  userId,
  activeIndex,
  setActiveIndex,
  modalItems,
}: {
  items: ScreenshotItem[];
  server: User["server"];
  userId: number;
  activeIndex: number | null;
  setActiveIndex: (n: number | null) => void;
  modalItems: ScreenshotModalItem[];
}) {
  const outerRef = useRef<HTMLDivElement>(null);
  const [cols, setCols] = useState(3);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewH, setViewH] = useState(640);

  useEffect(() => {
    const el = outerRef.current;
    if (!el) return;
    const onScroll = () => setScrollTop(el.scrollTop);
    el.addEventListener("scroll", onScroll, { passive: true });
    const ro = new ResizeObserver(() => {
      setViewH(el.clientHeight || 640);
      const w = el.clientWidth;
      const nextCols = Math.max(1, Math.min(6, Math.floor(w / MIN_COL_WIDTH)));
      setCols(nextCols);
    });
    ro.observe(el);
    setViewH(el.clientHeight || 640);
    const w0 = el.clientWidth;
    setCols(Math.max(1, Math.min(6, Math.floor(w0 / MIN_COL_WIDTH))));
    return () => {
      el.removeEventListener("scroll", onScroll);
      ro.disconnect();
    };
  }, []);

  const n = items.length;
  const rowCount = Math.ceil(n / cols);
  const totalH = Math.max(EST_ROW_PX, rowCount * EST_ROW_PX);

  const firstRow = Math.max(0, Math.floor(scrollTop / EST_ROW_PX) - 1);
  const lastRow = Math.min(rowCount - 1, Math.ceil((scrollTop + viewH) / EST_ROW_PX) + 1);

  const prewarmVisibleIds = useMemo(() => {
    const ids: number[] = [];
    for (let r = firstRow; r <= lastRow; r++) {
      for (let c = 0; c < cols; c++) {
        const idx = r * cols + c;
        if (idx >= n) continue;
        const item = items[idx];
        if (item.image_available && item.image_url) ids.push(item.id);
      }
    }
    return ids;
  }, [items, firstRow, lastRow, cols, n]);

  useThumbnailPrewarm(userId, prewarmVisibleIds);

  const rows = useMemo(() => {
    const out: ScreenshotItem[][] = [];
    for (let r = firstRow; r <= lastRow; r++) {
      const row: ScreenshotItem[] = [];
      for (let c = 0; c < cols; c++) {
        const idx = r * cols + c;
        if (idx < n) row.push(items[idx]);
      }
      if (row.length) out.push(row);
    }
    return out;
  }, [items, firstRow, lastRow, cols, n]);

  return (
    <>
      <div ref={outerRef} className="virtual-screenshot-gallery" style={{ maxHeight: "72vh", overflowY: "auto" }}>
        <div style={{ height: totalH, position: "relative" }}>
          <div
            className="virtual-screenshot-gallery__inner"
            style={{
              position: "absolute",
              top: firstRow * EST_ROW_PX,
              left: 0,
              right: 0,
              display: "flex",
              flexDirection: "column",
              gap: "1rem",
            }}
          >
            {rows.map((row, ri) => {
              const rowIndex = firstRow + ri;
              return (
                <div
                  key={rowIndex}
                  style={{
                    display: "grid",
                    gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
                    gap: "1rem",
                    minHeight: EST_ROW_PX - 16,
                    alignItems: "start",
                  }}
                >
                  {row.map((item, ci) => {
                    const globalIndex = rowIndex * cols + ci;
                    return (
                      <div key={item.id} className="gallery-card compact-shot-wrap">
                        <CompactScreenshotCard
                          item={toModalItem(item)}
                          server={server}
                          onOpen={() => setActiveIndex(globalIndex)}
                          thumb={
                            item.image_available && item.image_url ? (
                              <SecureImage
                                path={item.image_url}
                                alt={item.filename || `screenshot-${item.id}`}
                                className="compact-shot-thumb"
                                variant="thumb"
                              />
                            ) : (
                              <div className="gallery-placeholder compact-shot-thumb">No image</div>
                            )
                          }
                        />
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
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

export function ScreenshotGallery({ items, server, userId }: ScreenshotGalleryProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const modalItems: ScreenshotModalItem[] = items.map(toModalItem);

  const flatPrewarmIds = useMemo(() => screenshotIdsForPrewarm(items).slice(0, 120), [items]);
  useThumbnailPrewarm(userId, items.length > VIRTUAL_THRESHOLD ? [] : flatPrewarmIds);

  if (!items.length) return <EmptyState text="No screenshots found." />;

  if (items.length > VIRTUAL_THRESHOLD) {
    return (
      <VirtualizedScreenshotBody
        items={items}
        server={server}
        userId={userId}
        activeIndex={activeIndex}
        setActiveIndex={setActiveIndex}
        modalItems={modalItems}
      />
    );
  }

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
                  <SecureImage path={item.image_url} alt={item.filename || `screenshot-${item.id}`} className="compact-shot-thumb" variant="thumb" />
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
