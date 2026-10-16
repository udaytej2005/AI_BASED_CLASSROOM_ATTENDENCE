/** Shapes of API responses. Keep in sync with backend/app/schemas. */

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

export type Role = "admin" | "principal" | "faculty" | "student" | "technical";

export interface CurrentUser {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  must_change_password: boolean;
  is_synthetic: boolean;
  last_login_at: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export type RecordStatus = "active" | "inactive";

export interface Department {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
}

export interface StudentRecord {
  id: number;
  student_code: string;
  full_name: string;
  department_id: number;
  department_code: string;
  year: number;
  section: string;
  /** Null for viewers who are not administrators or principals. */
  email: string | null;
  status: RecordStatus;
  has_login: boolean;
  is_synthetic: boolean;
}

export interface FacultyRecord {
  id: number;
  employee_code: string;
  full_name: string;
  department_id: number;
  department_code: string;
  email: string | null;
  status: RecordStatus;
  has_login: boolean;
  is_synthetic: boolean;
}
