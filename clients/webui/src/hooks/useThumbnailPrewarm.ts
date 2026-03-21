import { useEffect, useMemo, useRef } from "react";
import { api } from "../api";

/**
 * Ask the server to generate cached thumbnails before SecureImage fetches them.
 * Uses a direct fetch so POST does not clear the in-memory blob cache.
 */
export function useThumbnailPrewarm(
  userId: number | undefined,
  screenshotIds: readonly number[],
  uploadFilenames: readonly string[] = [],
  debounceMs = 160,
) {
  const sidKey = useMemo(() => {
    const s = [...screenshotIds].filter((id) => id > 0);
    s.sort((a, b) => a - b);
    return s.join(",");
  }, [screenshotIds]);

  const upKey = useMemo(() => {
    const u = [...uploadFilenames].map((x) => String(x));
    u.sort();
    return u.join("\0");
  }, [uploadFilenames]);

  const lastSent = useRef("");

  useEffect(() => {
    if (userId == null) return;
    if (!sidKey && !upKey) return;

    const handle = window.setTimeout(() => {
      const key = `${userId}|${sidKey}|${upKey}`;
      if (key === lastSent.current) return;
      lastSent.current = key;

      const screenshot_ids = sidKey
        ? sidKey.split(",").map((x) => Number(x)).filter((n) => Number.isFinite(n) && n > 0).slice(0, 120)
        : [];
      const upload_filenames = upKey ? upKey.split("\0").filter(Boolean).slice(0, 80) : [];

      void api.warmThumbnails(userId, { screenshot_ids, upload_filenames }).catch(() => {
        /* best-effort */
      });
    }, debounceMs);

    return () => window.clearTimeout(handle);
  }, [userId, sidKey, upKey, debounceMs]);
}
