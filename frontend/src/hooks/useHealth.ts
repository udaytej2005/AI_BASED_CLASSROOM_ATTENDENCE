import { useEffect, useState } from "react";

import { getDatabaseHealth, getHealth } from "../services/healthService";
import type { DatabaseHealthResponse, HealthResponse } from "../types/api";

export interface HealthState {
  loading: boolean;
  backend: HealthResponse | null;
  database: DatabaseHealthResponse | null;
  error: string | null;
  refresh: () => void;
}

/** Loads backend and database health from the real API. Nothing here is hardcoded. */
export function useHealth(): HealthState {
  const [backend, setBackend] = useState<HealthResponse | null>(null);
  const [database, setDatabase] = useState<DatabaseHealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);

    Promise.all([getHealth(controller.signal), getDatabaseHealth(controller.signal)])
      .then(([backendHealth, databaseHealth]) => {
        setBackend(backendHealth);
        setDatabase(databaseHealth);
        setError(null);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setBackend(null);
        setDatabase(null);
        setError(err instanceof Error ? err.message : "Unknown error while contacting the server.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [reloadKey]);

  return { loading, backend, database, error, refresh: () => setReloadKey((k) => k + 1) };
}
