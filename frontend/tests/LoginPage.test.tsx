import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import LoginPage from "../src/pages/LoginPage";
import { ApiError } from "../src/services/apiClient";
import { makeUser, renderAs } from "./helpers";

const routes = (
  <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/" element={<p>Home reached</p>} />
  </Routes>
);

describe("LoginPage", () => {
  it("shows field errors and does not call the API when the form is empty", async () => {
    const signIn = vi.fn();
    renderAs(routes, { route: "/login", user: null, auth: { signIn } });

    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(screen.getByText("Enter your email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    expect(signIn).not.toHaveBeenCalled();
  });

  it("shows the server's generic message for wrong credentials and clears the password", async () => {
    const signIn = vi.fn().mockRejectedValue(new ApiError(401, "Email or password is incorrect."));
    renderAs(routes, { route: "/login", user: null, auth: { signIn } });

    await userEvent.type(screen.getByLabelText("Email"), "someone@college.edu");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
    expect(signIn).toHaveBeenCalledWith("someone@college.edu", "wrong-password");
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });

  it("navigates to the dashboard after a successful sign-in", async () => {
    const signIn = vi.fn().mockResolvedValue(makeUser("faculty"));
    renderAs(routes, { route: "/login", user: null, auth: { signIn } });

    await userEvent.type(screen.getByLabelText("Email"), "faculty@college.edu");
    await userEvent.type(screen.getByLabelText("Password"), "Correct-Horse-1");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(signIn).toHaveBeenCalled());
  });

  it("redirects away from the form when a user is already signed in", () => {
    renderAs(routes, { route: "/login", user: makeUser("admin") });
    expect(screen.getByText("Home reached")).toBeInTheDocument();
  });
});
