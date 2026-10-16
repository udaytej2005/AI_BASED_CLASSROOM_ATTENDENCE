import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AppShell from "../src/components/AppShell";
import { navItemsFor } from "../src/config/navigation";
import { makeUser, renderAs } from "./helpers";

function linksFor(role: Parameters<typeof makeUser>[0]) {
  renderAs(<AppShell title="Test">content</AppShell>, { user: makeUser(role) });
  const nav = screen.getByRole("navigation", { name: "Main navigation" });
  return within(nav)
    .queryAllByRole("link")
    .map((link) => link.textContent);
}

describe("role-specific navigation", () => {
  it("students see their profile but not administration or the directory", () => {
    const links = linksFor("student");
    expect(links).toContain("My profile");
    expect(links).not.toContain("Students");
    expect(links).not.toContain("User accounts");
    expect(links).not.toContain("System health");
  });

  it("administrators see user management and system health", () => {
    const links = linksFor("admin");
    expect(links).toEqual(expect.arrayContaining(["Students", "Faculty", "User accounts", "System health"]));
    expect(links).not.toContain("My profile");
  });

  it("technical operators see only the dashboard and system health", () => {
    expect(linksFor("technical")).toEqual(["Dashboard", "System health"]);
  });

  it("planned pages are disabled labels, never dead links", () => {
    renderAs(<AppShell title="Test">content</AppShell>, { user: makeUser("admin") });
    const planned = screen.getByText("Timetable").closest("[aria-disabled]");
    expect(planned).toHaveAttribute("aria-disabled", "true");
    expect(screen.queryByRole("link", { name: "Timetable" })).not.toBeInTheDocument();
  });

  it("navItemsFor returns nothing when signed out", () => {
    expect(navItemsFor(undefined)).toEqual([]);
  });

  it("shows the signed-in user and a sign-out button", () => {
    renderAs(<AppShell title="Test">content</AppShell>, { user: makeUser("faculty", { full_name: "Dr Ada" }) });
    expect(screen.getByText("Dr Ada")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });
});
