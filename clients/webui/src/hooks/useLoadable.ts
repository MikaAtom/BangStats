import { useEffect, useState } from "react";

export type Loadable<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
};

export function useLoadable<T>(
  loader: (() => Promise<T>) | null,
  deps: unknown[] = [],
): Loadable<T> & { reload: () => Promise<void> } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(loader));
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    if (!loader) return;
    setLoading(true);
    setError(null);
    try {
      const next = await loader();
      setData(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mirror prior App.tsx dependency list contract
  }, deps);

  return { data, loading, error, reload };
}
