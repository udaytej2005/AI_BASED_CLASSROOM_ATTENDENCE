import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import RequireAuth from "../src/auth/RequireAuth";
import LoginPage from "../src/pages/LoginPage";
import { makeUser, renderAs } from "./helpers";

function guarded(roles?: Parameters<typeof makeUser>[0][]) {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/account/password" element={<p>Password change page</p>} />
      <Route path="/" element={<RequireAuth roles={roles}><p>Protected content</p></RequireAuth>} />
    </Routes>
  );
}

describe("RequireAuth", () => {
  it("sends anonymous visitors to the sign-in page", () => {
    renderAs(guarded(), { user: null });
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("shows a status message while the session is being checked", () => {
    renderAs(guarded(), { user: null, loading: true });
    expect(screen.getByRole("status")).toHaveTextContent("Checking your session");
    expect(screen.queryByRole("heading", { name: "Sign in" })).not.toBeInTheDocument();
  });

  it("forces a password change before any other page", () => {
    renderAs(guarded(), { user: makeUser("student", { must_change_password: true }) });
    expect(screen.getByText("Password change page")).toBeInTheDocument();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("shows a clear 403 page when the role is not allowed", () => {
    renderAs(guarded(["admin"]), { user: makeUser("student") });
    expect(screen.getByRole("heading", { name: "You do not have access to this page" })).toBeInTheDocument();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("renders the page for an allowed role", () => {
    renderAs(guarded(["admin"]), { user: makeUser("admin") });
    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });
});
