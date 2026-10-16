import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import UsersPage from "../src/pages/UsersPage";
import { jsonResponse, makeUser, mockApi, renderAs } from "./helpers";

const account = (id: number, overrides: object = {}) => ({
  id,
  email: `user${id}@example.test`,
  full_name: `Person ${id}`,
  role: "faculty",
  is_active: true,
  must_change_password: false,
  is_synthetic: false,
  last_login_at: null,
  ...overrides,
});

const listing = (items: object[]) => jsonResponse({ items, total: items.length, page: 1, page_size: 20, total_pages: 1 });

describe("UsersPage", () => {
  it("asks for confirmation before deactivating an account, then calls the API", async () => {
    const { calls } = mockApi({
      "GET /api/v1/users": () => listing([account(2)]),
      "PATCH /api/v1/users/2": () => jsonResponse(account(2, { is_active: false })),
    });

    renderAs(<UsersPage />, { user: makeUser("admin", { id: 1 }) });
    await userEvent.click(await screen.findByRole("button", { name: "Deactivate" }));

    const dialog = screen.getByRole("dialog", { name: "Deactivate this account?" });
    expect(within(dialog).getByText(/cannot sign in until the account is reactivated/)).toBeInTheDocument();
    expect(calls.some((call) => call.method === "PATCH")).toBe(false);

    await userEvent.click(within(dialog).getByRole("button", { name: "Deactivate" }));

    await waitFor(() =>
      expect(calls).toContainEqual({ method: "PATCH", url: "/api/v1/users/2", body: { is_active: false } }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent("is now deactivated");
  });

  it("cannot deactivate the signed-in administrator's own account", async () => {
    mockApi({ "GET /api/v1/users": () => listing([account(1, { full_name: "Me Admin", role: "admin" })]) });
    renderAs(<UsersPage />, { user: makeUser("admin", { id: 1 }) });
    expect(await screen.findByRole("button", { name: "Deactivate" })).toBeDisabled();
  });

  it("validates the create-account form before sending anything", async () => {
    const { calls } = mockApi({ "GET /api/v1/users": () => listing([]) });
    renderAs(<UsersPage />, { user: makeUser("admin") });

    await userEvent.click(await screen.findByRole("button", { name: "Create account" }));
    await userEvent.click(within(screen.getByRole("form", { name: "Create user account" })).getByRole("button", { name: "Create account" }));

    expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter the person's full name.")).toBeInTheDocument();
    expect(screen.getByText(/needs at least 12 characters/)).toBeInTheDocument();
    expect(calls.some((call) => call.method === "POST")).toBe(false);
  });

  it("shows the server's conflict message when the email is already in use", async () => {
    mockApi({
      "GET /api/v1/users": () => listing([]),
      "POST /api/v1/users": () => jsonResponse({ detail: "An account with this email already exists." }, 409),
    });
    renderAs(<UsersPage />, { user: makeUser("admin") });

    await userEvent.click(await screen.findByRole("button", { name: "Create account" }));
    const form = screen.getByRole("form", { name: "Create user account" });
    await userEvent.type(within(form).getByLabelText("Full name"), "New Person");
    await userEvent.type(within(form).getByLabelText("Email"), "taken@example.test");
    await userEvent.type(within(form).getByLabelText("Temporary password"), "Initial-Password-1");
    await userEvent.click(within(form).getByRole("button", { name: "Create account" }));

    expect(await within(form).findByRole("alert")).toHaveTextContent("already exists");
  });
});
