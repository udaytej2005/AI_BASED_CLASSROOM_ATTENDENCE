import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { AuthContext, type AuthState } from "../src/auth/authContext";
import type { CurrentUser, Role } from "../src/types/api";

export function makeUser(role: Role, overrides: Partial<CurrentUser> = {}): CurrentUser {
  return {
    id: 1,
    email: `${role}@example.test`,
    full_name: `Test ${role}`,
    role,
    is_active: true,
    must_change_password: false,
    is_synthetic: true,
    last_login_at: null,
    ...overrides,
  };
}

/** Renders UI inside a router and an auth context holding the given user (no network calls). */
export function renderAs(
  ui: ReactElement,
  options: { user: CurrentUser | null; route?: string; loading?: boolean; auth?: Partial<AuthState> },
) {
  const value: AuthState = {
    loading: options.loading ?? false,
    user: options.user,
    signIn: vi.fn(async () => options.user as CurrentUser),
    signOut: vi.fn(async () => undefined),
    setUser: vi.fn(),
    ...options.auth,
  };
  return render(
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={[options.route ?? "/"]}>{ui}</MemoryRouter>
    </AuthContext.Provider>,
  );
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Replaces global fetch with a router keyed by "METHOD path" (query string ignored unless the key contains "?").
 * Unmatched calls fail the test, so every request the UI makes must be expected.
 */
export function mockApi(routes: Record<string, (init: RequestInit, url: URL) => Response | Promise<Response>>) {
  const calls: { method: string; url: string; body: unknown }[] = [];
  const fetchMock = vi.fn(async (input: string, init: RequestInit = {}) => {
    const url = new URL(input, "http://frontend.test");
    const method = (init.method ?? "GET").toUpperCase();
    const body = init.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, url: `${url.pathname}${url.search}`, body });
    const exact = routes[`${method} ${url.pathname}${url.search}`];
    const byPath = routes[`${method} ${url.pathname}`];
    const handler = exact ?? byPath;
    if (!handler) {
      throw new Error(`Unexpected request: ${method} ${url.pathname}${url.search}`);
    }
    return handler(init, url);
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, calls };
}
