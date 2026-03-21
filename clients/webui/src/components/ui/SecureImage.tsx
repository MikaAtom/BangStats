import { useEffect, useRef, useState } from "react";
import { api, type ImageBlobLoadKind } from "../../api";

function imagePathWithVariant(path: string, variant: "full" | "thumb"): string {
  if (variant === "full") return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}variant=thumb`;
}

interface SecureImageProps {
  path: string;
  alt: string;
  className?: string;
  /** Load immediately (modal hero, above-the-fold). */
  priority?: boolean;
  /** Use server-resized thumbnail for grids and previews; modals should use full. */
  variant?: "full" | "thumb";
}

export function SecureImage({ path, alt, className, priority, variant = "full" }: SecureImageProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [shouldLoad, setShouldLoad] = useState(Boolean(priority));
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setShouldLoad(Boolean(priority));
  }, [path, priority, variant]);

  useEffect(() => {
    if (priority) return;
    const element = containerRef.current;
    if (!element) return;

    if (typeof IntersectionObserver === "undefined") {
      setShouldLoad(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting || entry.intersectionRatio > 0)) {
          setShouldLoad(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" },
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, [path, priority, variant]);

  useEffect(() => {
    if (!shouldLoad) return;
    let active = true;
    let currentUrl: string | null = null;
    setFailed(false);
    setSrc(null);
    const fetchPath = imagePathWithVariant(path, variant);
    const loadKind: ImageBlobLoadKind = variant === "thumb" ? "thumb" : "full";
    void api
      .secureBlob(fetchPath, { loadKind })
      .then((blob) => {
        if (!active) return;
        currentUrl = URL.createObjectURL(blob);
        setSrc(currentUrl);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
      if (currentUrl) URL.revokeObjectURL(currentUrl);
    };
  }, [path, shouldLoad, variant]);

  if (failed) return <div ref={containerRef} className={`image-fallback ${className || ""}`}>Image unavailable</div>;
  if (!src) {
    return (
      <div ref={containerRef} className={`image-fallback ${className || ""}`}>
        {shouldLoad ? "Loading image..." : "Image pending..."}
      </div>
    );
  }
  return (
    <img
      className={className}
      src={src}
      alt={alt}
      loading={priority ? "eager" : "lazy"}
      decoding="async"
    />
  );
}
