/** Response shape of GET /api/v1/health (mirrors backend app/api/v1/health.py). */
export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  timezone: string;
  server_time_utc: string;
}

/** Response shape of GET /api/v1/health/database. */
export interface DatabaseHealthResponse {
  status: "ok" | "unavailable";
  database: "connected" | "unreachable";
}

/** Standard error body returned by the API (FastAPI default `detail` field). */
export interface ApiErrorBody {
  detail: string | Array<{ msg: string }>;
}
