import { apiRequest } from "./apiClient";
import type { DatabaseHealthResponse, HealthResponse } from "../types/api";

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest<HealthResponse>("/health", { signal });
}

export function getDatabaseHealth(signal?: AbortSignal): Promise<DatabaseHealthResponse> {
  return apiRequest<DatabaseHealthResponse>("/health/database", { signal });
}
