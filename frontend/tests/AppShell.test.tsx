import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import AppShell from "../src/components/AppShell";

describe("AppShell navigation", () => {
  it("links available pages and marks planned pages as unavailable (no dead links)", () => {
    render(
      <MemoryRouter>
        <AppShell title="Test page">
          <p>content</p>
        </AppShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "System health" })).toHaveAttribute("href", "/system");

    const planned = screen.getByText("Students").closest("[aria-disabled]");
    expect(planned).toHaveAttribute("aria-disabled", "true");
    expect(screen.queryByRole("link", { name: "Students" })).not.toBeInTheDocument();
  });

  it("renders the page title as the main heading and the demo-data notice", () => {
    render(
      <MemoryRouter>
        <AppShell title="Test page" breadcrumbs={["Home", "Test page"]}>
          <p>content</p>
        </AppShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { level: 1, name: "Test page" })).toBeInTheDocument();
    expect(screen.getByText("Prototype: demo data only")).toBeInTheDocument();
    const crumbs = screen.getAllByRole("listitem").map((item) => item.textContent?.replace("/", "").trim());
    expect(crumbs).toEqual(["Home", "Test page"]);
  });
});
