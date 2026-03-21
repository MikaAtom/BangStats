import { useMemo } from "react";
import type { UploadFileItem } from "../../api";
import { useThumbnailPrewarm } from "../../hooks/useThumbnailPrewarm";
import { EmptyState } from "../ui/EmptyState";
import { SecureImage } from "../ui/SecureImage";

interface UploadGalleryProps {
  items: UploadFileItem[];
  userId: number;
}

export function UploadGallery({ items, userId }: UploadGalleryProps) {
  const names = useMemo(() => items.slice(0, 18).map((i) => i.filename), [items]);
  useThumbnailPrewarm(userId, [], names);

  if (!items.length) return <EmptyState text="No uploaded images yet." />;
  return (
    <div className="gallery">
      {items.slice(0, 18).map((item) => (
        <div className="gallery-card" key={item.filename}>
          <SecureImage path={item.image_url} alt={item.filename} className="gallery-image" variant="thumb" />
          <div className="gallery-meta">
            <strong>{item.filename}</strong>
            <span>{Math.round(item.size_bytes / 1024)} KB</span>
          </div>
        </div>
      ))}
    </div>
  );
}
