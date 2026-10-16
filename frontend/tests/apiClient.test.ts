import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "../src/services/apiClient";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiRequest", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("calls the same-origin versioned API path and returns parsed JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { status: "ok" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiRequest<{ status: string }>("/health");

    expect(result).toEqual({ status: "ok" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/health");
    expect(fetchMock.mock.calls[0][1].credentials).toBe("same-origin");
  });

  it("surfaces the server's detail message on HTTP errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(403, { detail: "Forbidden here." })));

    await expect(apiRequest("/secret")).rejects.toMatchObject({
      name: "ApiError",
      status: 403,
      message: "Forbidden here.",
    });
  });

  it("falls back to a generic message when the error body is not JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>oops</html>", { status: 500 })));

    const error = await apiRequest("/broken").catch((err: unknown) => err);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe("Request failed with status 500.");
  });

  it("reports unreachable servers in plain language", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(apiRequest("/health")).rejects.toMatchObject({
      status: 0,
      message: "The server could not be reached. Check that the backend is running.",
    });
  });

  it("sends a JSON body only when one is provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, {}));
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/things", { method: "POST", body: { name: "x" } });

    const init = fetchMock.mock.calls[0][1];
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ name: "x" }));
  });
});
