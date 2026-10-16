/** Primary navigation definition. Kept outside component files so it can be shared and tested. */

export interface NavItem {
  label: string;
  to: string;
  /** Items that are not built yet are shown as clearly unavailable instead of being dead links. */
  available: boolean;
}

// Navigation for later phases is listed now so the information architecture is visible,
// but unavailable items are disabled and labelled rather than leading to placeholder pages.
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", to: "/", available: true },
  { label: "Students", to: "/students", available: false },
  { label: "Timetable", to: "/timetable", available: false },
  { label: "Attendance sessions", to: "/sessions", available: false },
  { label: "Reports", to: "/reports", available: false },
  { label: "System health", to: "/system", available: true },
];

