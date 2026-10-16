import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ChangePasswordPage from "../src/pages/ChangePasswordPage";
import { jsonResponse, makeUser, mockApi, renderAs } from "./helpers";

describe("ChangePasswordPage", () => {
  it("explains a forced change and blocks mismatched confirmation", async () => {
    const { calls } = mockApi({});
    renderAs(<ChangePasswordPage />, { user: makeUser("student", { must_change_password: true }), route: "/account/password" });

    expect(screen.getByRole("status")).toHaveTextContent("set by an administrator");
    await userEvent.type(screen.getByLabelText("Current password"), "Temporary-Pass-1");
    await userEvent.type(screen.getByLabelText("New password"), "Brand-New-Passphrase-2");
    await userEvent.type(screen.getByLabelText("Confirm new password"), "Different-Passphrase-3");
    await userEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(screen.getByText("The two passwords do not match.")).toBeInTheDocument();
    expect(calls).toHaveLength(0);
  });

  it("sends the change, updates the cached user and leaves the forced page", async () => {
    const setUser = vi.fn();
    const { calls } = mockApi({
      "POST /api/v1/auth/change-password": () =>
        jsonResponse(makeUser("student", { must_change_password: false })),
    });
    renderAs(<ChangePasswordPage />, {
      user: makeUser("student", { must_change_password: true }),
      route: "/account/password",
      auth: { setUser },
    });

    await userEvent.type(screen.getByLabelText("Current password"), "Temporary-Pass-1");
    await userEvent.type(screen.getByLabelText("New password"), "Brand-New-Passphrase-2");
    await userEvent.type(screen.getByLabelText("Confirm new password"), "Brand-New-Passphrase-2");
    await userEvent.click(screen.getByRole("button", { name: "Change password" }));

    await waitFor(() => expect(setUser).toHaveBeenCalled());
    expect(calls).toContainEqual({
      method: "POST",
      url: "/api/v1/auth/change-password",
      body: { current_password: "Temporary-Pass-1", new_password: "Brand-New-Passphrase-2" },
    });
  });
});
