import { useEffect, useState } from "react";
import { api } from "../../api";

interface SecureImageProps {
  path: string;
  alt: string;
  className?: string;
}

export function SecureImage({ path, alt, className }: SecureImageProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
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
  }, [path]);

  if (failed) return <div className={`image-fallback ${className || ""}`}>Image unavailable</div>;
  if (!src) return <div className={`image-fallback ${className || ""}`}>Loading image...</div>;
  return <img className={className} src={src} alt={alt} />;
}
