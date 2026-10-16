import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import StudentsPage from "../src/pages/StudentsPage";
import { jsonResponse, makeUser, mockApi, renderAs } from "./helpers";

const page = (items: object[], total = items.length) => ({
  items,
  total,
  page: 1,
  page_size: 20,
  total_pages: 1,
});

const student = (code: string, name: string, overrides: object = {}) => ({
  id: Number(code.slice(3)),
  student_code: code,
  full_name: name,
  department_id: 1,
  department_code: "CSE",
  year: 2,
  section: "A",
  email: null,
  status: "active",
  has_login: true,
  is_synthetic: true,
  ...overrides,
});

describe("StudentsPage", () => {
  it("lists students from the API and marks demo records", async () => {
    mockApi({
      "GET /api/v1/students": () => jsonResponse(page([student("CSE001", "Aarav Mehta")])),
    });

    renderAs(<StudentsPage />, { user: makeUser("faculty") });

    expect(await screen.findByRole("link", { name: "CSE001" })).toBeInTheDocument();
    expect(screen.getByText("Aarav Mehta")).toBeInTheDocument();
    expect(screen.getByText("Demo record")).toBeInTheDocument();
  });

  it("sends the search text to the server after the user types", async () => {
    const { calls } = mockApi({
      "GET /api/v1/students": () => jsonResponse(page([student("CSE001", "Aarav Mehta")])),
    });

    renderAs(<StudentsPage />, { user: makeUser("faculty") });
    await screen.findByRole("link", { name: "CSE001" });
    await userEvent.type(screen.getByLabelText("Search by student ID or name"), "aarav");

    await waitFor(() =>
      expect(calls.some((call) => call.url.includes("q=aarav"))).toBe(true),
    );
  });

  it("shows an empty state when no students match", async () => {
    mockApi({ "GET /api/v1/students": () => jsonResponse(page([])) });
    renderAs(<StudentsPage />, { user: makeUser("principal") });
    expect(await screen.findByText("No students match these filters.")).toBeInTheDocument();
  });

  it("shows an error with a retry action when the request fails", async () => {
    let attempts = 0;
    mockApi({
      "GET /api/v1/students": () => {
        attempts += 1;
        return attempts === 1 ? jsonResponse({ detail: "Server exploded." }, 500) : jsonResponse(page([]));
      },
    });
    renderAs(<StudentsPage />, { user: makeUser("admin") });

    expect(await screen.findByRole("alert")).toHaveTextContent("Server exploded.");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No students match these filters.")).toBeInTheDocument();
  });

  it("offers 'Add student' only to administrators", async () => {
    mockApi({ "GET /api/v1/students": () => jsonResponse(page([])) });
    const { unmount } = renderAs(<StudentsPage />, { user: makeUser("faculty") });
    await screen.findByText("No students match these filters.");
    expect(screen.queryByRole("link", { name: "Add student" })).not.toBeInTheDocument();
    unmount();

    renderAs(<StudentsPage />, { user: makeUser("admin") });
    expect(await screen.findByRole("link", { name: "Add student" })).toHaveAttribute("href", "/students/new");
  });
});
