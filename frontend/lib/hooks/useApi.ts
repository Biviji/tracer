"use client";

import { useCallback, useEffect, useEffectEvent, useState } from "react";

interface State<T> {
  key: string | null;
  data?: T;
  error?: unknown;
}

/**
 * Minimal data hook: fetches when `key` changes, keeps stale data on reload.
 * Pass `null` as key to skip fetching.
 */
export function useApi<T>(key: string | null, fetcher: () => Promise<T>) {
  const [state, setState] = useState<State<T>>({ key: null });
  const [nonce, setNonce] = useState(0);
  const load = useEffectEvent(fetcher);

  useEffect(() => {
    if (key === null) return;
    let alive = true;
    load().then(
      (data) => alive && setState({ key, data }),
      (error: unknown) => alive && setState((s) => ({ key, data: s.key === key ? s.data : undefined, error })),
    );
    return () => {
      alive = false;
    };
  }, [key, nonce]);

  const current = state.key === key ? state : { key, data: undefined, error: undefined };
  const reload = useCallback(() => setNonce((n) => n + 1), []);

  return {
    data: current.data,
    error: current.error,
    loading: key !== null && current.data === undefined && current.error === undefined,
    reload,
  };
}
