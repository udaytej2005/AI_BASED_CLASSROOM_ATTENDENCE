/** Students, faculty, departments and user accounts. All authorisation is enforced by the backend. */

import { apiRequest } from "./apiClient";
import type { CurrentUser, Department, FacultyRecord, Page, Role, StudentRecord } from "../types/api";

export interface StudentQuery {
  q?: string;
  status?: "active" | "inactive";
  page?: number;
  pageSize?: number;
}

function withQuery(path: string, params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

export function listStudents(query: StudentQuery, signal?: AbortSignal): Promise<Page<StudentRecord>> {
  return apiRequest<Page<StudentRecord>>(
    withQuery("/students", {
      q: query.q,
      status: query.status,
      page: query.page ?? 1,
      page_size: query.pageSize ?? 20,
    }),
    { signal },
  );
}

export function getStudent(studentId: number, signal?: AbortSignal): Promise<StudentRecord> {
  return apiRequest<StudentRecord>(`/students/${studentId}`, { signal });
}

export function getMyStudentProfile(signal?: AbortSignal): Promise<StudentRecord> {
  return apiRequest<StudentRecord>("/students/me", { signal });
}

export function listFaculty(
  query: { q?: string; page?: number; pageSize?: number },
  signal?: AbortSignal,
): Promise<Page<FacultyRecord>> {
  return apiRequest<Page<FacultyRecord>>(
    withQuery("/faculty", { q: query.q, page: query.page ?? 1, page_size: query.pageSize ?? 20 }),
    { signal },
  );
}

export function listDepartments(signal?: AbortSignal): Promise<Department[]> {
  return apiRequest<Department[]>("/departments", { signal });
}

export interface UserQuery {
  q?: string;
  role?: Role | "";
  page?: number;
  pageSize?: number;
}

export function listUsers(query: UserQuery, signal?: AbortSignal): Promise<Page<CurrentUser>> {
  return apiRequest<Page<CurrentUser>>(
    withQuery("/users", {
      q: query.q,
      role: query.role || undefined,
      page: query.page ?? 1,
      page_size: query.pageSize ?? 20,
    }),
    { signal },
  );
}

export interface NewUserInput {
  email: string;
  full_name: string;
  role: Role;
  initial_password: string;
}

export function createUser(input: NewUserInput): Promise<CurrentUser> {
  return apiRequest<CurrentUser>("/users", { method: "POST", body: input });
}

export function setUserActive(userId: number, isActive: boolean): Promise<CurrentUser> {
  return apiRequest<CurrentUser>(`/users/${userId}`, { method: "PATCH", body: { is_active: isActive } });
}

export interface StudentInput {
  student_code?: string;
  full_name: string;
  department_id: number;
  year: number;
  section: string;
  email?: string | null;
  status?: "active" | "inactive";
  account?: { email: string; initial_password: string } | null;
}

export function createStudent(input: StudentInput): Promise<StudentRecord> {
  return apiRequest<StudentRecord>("/students", { method: "POST", body: input });
}

export function updateStudent(
  studentId: number,
  input: Partial<Omit<StudentInput, "student_code" | "account">>,
): Promise<StudentRecord> {
  return apiRequest<StudentRecord>(`/students/${studentId}`, { method: "PATCH", body: input });
}

export function getFaculty(facultyId: number, signal?: AbortSignal): Promise<FacultyRecord> {
  return apiRequest<FacultyRecord>(`/faculty/${facultyId}`, { signal });
}

export interface FacultyInput {
  employee_code?: string;
  full_name: string;
  department_id: number;
  email?: string | null;
  status?: "active" | "inactive";
  account?: { email: string; initial_password: string } | null;
}

export function createFaculty(input: FacultyInput): Promise<FacultyRecord> {
  return apiRequest<FacultyRecord>("/faculty", { method: "POST", body: input });
}

export function updateFaculty(
  facultyId: number,
  input: Partial<Omit<FacultyInput, "employee_code" | "account">>,
): Promise<FacultyRecord> {
  return apiRequest<FacultyRecord>(`/faculty/${facultyId}`, { method: "PATCH", body: input });
}
