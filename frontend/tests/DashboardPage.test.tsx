import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import DashboardPage from "../src/pages/DashboardPage";
import { jsonResponse, makeUser, mockApi, renderAs } from "./helpers";

const countPage = (total: number) => jsonResponse({ items: [], total, page: 1, page_size: 1, total_pages: 1 });

describe("DashboardPage", () => {
  it("shows real directory counts to an administrator, including accounts", async () => {
    mockApi({
      "GET /api/v1/students": () => countPage(20),
      "GET /api/v1/faculty": () => countPage(3),
      "GET /api/v1/users": () => countPage(26),
      "GET /api/v1/health": () =>
        jsonResponse({ status: "ok", version: "0.1.0", environment: "development", timezone: "Asia/Kolkata", server_time_utc: "" }),
      "GET /api/v1/health/database": () => jsonResponse({ status: "ok", database: "connected" }),
    });

    renderAs(<DashboardPage />, { user: makeUser("admin", { full_name: "Ada Admin" }) });

    expect(await screen.findByText("20")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("26")).toBeInTheDocument();
    expect(screen.getByText("Welcome, Ada Admin")).toBeInTheDocument();
    expect(await screen.findByText("Operational")).toBeInTheDocument();
  });

  it("does not request account counts for a faculty member", async () => {
    const { calls } = mockApi({
      "GET /api/v1/students": () => countPage(20),
      "GET /api/v1/faculty": () => countPage(3),
    });

    renderAs(<DashboardPage />, { user: makeUser("faculty") });

    expect(await screen.findByText("Registered students")).toBeInTheDocument();
    expect(calls.some((call) => call.url.startsWith("/api/v1/users"))).toBe(false);
    expect(screen.queryByText("User accounts")).not.toBeInTheDocument();
  });

  it("shows a student their own record and states that attendance is not yet available", async () => {
    mockApi({
      "GET /api/v1/students/me": () =>
        jsonResponse({
          id: 7,
          student_code: "CSE001",
          full_name: "Aarav Mehta",
          department_id: 1,
          department_code: "CSE",
          year: 2,
          section: "A",
          email: null,
          status: "active",
          has_login: true,
          is_synthetic: true,
        }),
    });

    renderAs(<DashboardPage />, { user: makeUser("student") });

    expect(await screen.findByText("CSE001 · Aarav Mehta")).toBeInTheDocument();
    expect(screen.getByText("Not yet available")).toBeInTheDocument();
  });
});
