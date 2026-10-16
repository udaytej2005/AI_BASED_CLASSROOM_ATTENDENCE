import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import DashboardPage from "../src/pages/DashboardPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );
}

const HEALTHY = {
  status: "ok",
  version: "0.1.0",
  environment: "development",
  timezone: "Asia/Kolkata",
  server_time_utc: "2026-10-16T00:00:00+00:00",
};

describe("DashboardPage", () => {
  it("shows live backend and database status from the API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/v1/health") return new Response(JSON.stringify(HEALTHY), { status: 200 });
        return new Response(JSON.stringify({ status: "ok", database: "connected" }), { status: 200 });
      }),
    );

    renderPage();

    expect(await screen.findByText("Operational")).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("Asia/Kolkata")).toBeInTheDocument();
    expect(screen.getByText("Version 0.1.0 (development)")).toBeInTheDocument();
  });

  it("shows a clear error and lets the user retry when the backend is down", async () => {
    let attempts = 0;
    const fetchMock = vi.fn(async (url: string) => {
      attempts += 1;
      if (attempts <= 2) throw new TypeError("Failed to fetch");
      if (url === "/api/v1/health") return new Response(JSON.stringify(HEALTHY), { status: 200 });
      return new Response(JSON.stringify({ status: "ok", database: "connected" }), { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("The backend is not reachable.");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalled();
  });
});
