import type { Role } from "../types/api";

/** Human-readable role names. Keep in sync with the roles accepted by the backend. */
export const ROLE_LABELS: Record<Role, string> = {
  admin: "Administrator",
  principal: "Principal",
  faculty: "Faculty",
  student: "Student",
  technical: "Technical operator",
};
