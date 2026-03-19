import type { UploadFileItem } from "../../api";
import { EmptyState } from "../ui/EmptyState";
import { SecureImage } from "../ui/SecureImage";

interface UploadGalleryProps {
  items: UploadFileItem[];
}

export function UploadGallery({ items }: UploadGalleryProps) {
  if (!items.length) return <EmptyState text="No uploaded images yet." />;
  return (
    <div className="gallery">
      {items.slice(0, 18).map((item) => (
        <div className="gallery-card" key={item.filename}>
          <SecureImage path={item.image_url} alt={item.filename} className="gallery-image" />
          <div className="gallery-meta">
            <strong>{item.filename}</strong>
            <span>{Math.round(item.size_bytes / 1024)} KB</span>
          </div>
        </div>
      ))}
    </div>
  );
}
