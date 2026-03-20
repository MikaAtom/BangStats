import { useEffect, useRef, useState } from "react";
import { api } from "../../api";

interface SecureImageProps {
  path: string;
  alt: string;
  className?: string;
}

export function SecureImage({ path, alt, className }: SecureImageProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [shouldLoad, setShouldLoad] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setShouldLoad(false);
  }, [path]);

  useEffect(() => {
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
  }, [path]);

  useEffect(() => {
    if (!shouldLoad) return;
    let active = true;
    let currentUrl: string | null = null;
    setFailed(false);
    setSrc(null);
    void api
      .secureBlob(path)
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
  }, [path, shouldLoad]);

  if (failed) return <div ref={containerRef} className={`image-fallback ${className || ""}`}>Image unavailable</div>;
  if (!src) {
    return (
      <div ref={containerRef} className={`image-fallback ${className || ""}`}>
        {shouldLoad ? "Loading image..." : "Image pending..."}
      </div>
    );
  }
  return <img className={className} src={src} alt={alt} loading="lazy" />;
}
