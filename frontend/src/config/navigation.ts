/**
 * Navigation definition. Role lists mirror the backend permission table; the backend is still the
 * authority. Hiding a link here is a usability feature, never a security control.
 */

import type { Role } from "../types/api";

export interface NavItem {
  label: string;
  to: string;
  /** Roles that may see this item. */
  roles: Role[];
  /** Items not built yet are shown disabled with a "Planned" label rather than as dead links. */
  available: boolean;
}

const ALL_ROLES: Role[] = ["admin", "principal", "faculty", "student", "technical"];

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", to: "/", roles: ALL_ROLES, available: true },
  { label: "My profile", to: "/profile", roles: ["student"], available: true },
  { label: "Students", to: "/students", roles: ["admin", "principal", "faculty"], available: true },
  { label: "Faculty", to: "/faculty", roles: ["admin", "principal", "faculty"], available: true },
  { label: "User accounts", to: "/users", roles: ["admin"], available: true },
  { label: "Timetable", to: "/timetable", roles: ["admin", "faculty"], available: false },
  { label: "Attendance sessions", to: "/sessions", roles: ["faculty"], available: false },
  { label: "Reports", to: "/reports", roles: ["admin", "principal"], available: false },
  { label: "Audit log", to: "/audit", roles: ["admin"], available: false },
  { label: "System health", to: "/system", roles: ["admin", "technical"], available: true },
];

export function navItemsFor(role: Role | undefined): NavItem[] {
  if (!role) return [];
  return NAV_ITEMS.filter((item) => item.roles.includes(role));
}
