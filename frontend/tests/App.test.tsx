import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "../src/App";
import { makeUser, renderAs } from "./helpers";

describe("App routing", () => {
  it("renders a helpful not-found page for unknown routes", () => {
    renderAs(<App />, { user: makeUser("admin"), route: "/does-not-exist" });
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });

  it("sends anonymous visitors from protected pages to sign-in", () => {
    renderAs(<App />, { user: null, route: "/users" });
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("denies the user administration page to faculty", () => {
    renderAs(<App />, { user: makeUser("faculty"), route: "/users" });
    expect(screen.getByRole("heading", { name: "You do not have access to this page" })).toBeInTheDocument();
  });
});
