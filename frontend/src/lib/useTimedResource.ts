import { useCallback, useEffect, useRef, useState } from 'react';
import { isBackendOfflineError } from '../api/client';

type ResourceState<T> = {
  data: T | null;
  loading: boolean;
  timedOut: boolean;
  error: string | null;
  refresh: () => Promise<void>;
};

export function useTimedResource<T>(
  loader: () => Promise<T>,
  deps: readonly unknown[] = [],
  timeoutMs = 15000,
): ResourceState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [timedOut, setTimedOut] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const callId = useRef(0);

  const refresh = useCallback(async () => {
    const id = ++callId.current;
    setLoading(true);
    setTimedOut(false);
    setError(null);

    const timer = window.setTimeout(() => {
      if (callId.current === id) {
        setTimedOut(true);
        // Don't stop loading — still allow late data to arrive
      }
    }, timeoutMs);

    try {
      const next = await loader();
      if (callId.current === id) {
        setData(next);
        setTimedOut(false);
        setError(null);
      }
    } catch (err) {
      if (callId.current === id) {
        if (isBackendOfflineError(err)) {
          setError('Backend offline. Start the API server and try again.');
        } else {
          setError(err instanceof Error ? err.message : 'Unable to load data');
        }
      }
    } finally {
      window.clearTimeout(timer);
      if (callId.current === id) {
        setLoading(false);
      }
    }
  }, [loader, timeoutMs]);

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, timedOut, error, refresh };
}
