import { describe, expect, it } from "vitest";

import { validateLogin, validateNewPassword, validateNewUser } from "../src/utils/validation";

describe("validateLogin", () => {
  it("requires an email and a password", () => {
    expect(validateLogin("", "")).toEqual({
      email: "Enter your email address.",
      password: "Enter your password.",
    });
  });

  it("rejects malformed email addresses", () => {
    expect(validateLogin("not-an-email", "x").email).toMatch(/valid email/);
  });

  it("accepts a well-formed login", () => {
    expect(validateLogin("person@college.edu", "secret")).toEqual({});
  });
});

describe("validateNewPassword", () => {
  it("enforces length, variety, difference and confirmation", () => {
    const errors = validateNewPassword("Old-Password-123", "short", "different");
    expect(errors.newPassword).toMatch(/at least 12/);
    expect(errors.confirmation).toMatch(/do not match/);
  });

  it("requires three character classes", () => {
    expect(validateNewPassword("Old-Password-123", "alllowercaseonly", "alllowercaseonly").newPassword).toMatch(
      /three of/,
    );
  });

  it("rejects reuse of the current password", () => {
    expect(validateNewPassword("Same-Password-12", "Same-Password-12", "Same-Password-12").newPassword).toMatch(
      /different/,
    );
  });

  it("accepts a valid new passphrase with matching confirmation", () => {
    expect(validateNewPassword("Old-Password-123", "New-Passphrase-45", "New-Passphrase-45")).toEqual({});
  });
});

describe("validateNewUser", () => {
  it("checks email, name and temporary password length", () => {
    const errors = validateNewUser({ email: "bad", fullName: "A", initialPassword: "short" });
    expect(Object.keys(errors).sort()).toEqual(["email", "fullName", "initialPassword"]);
  });
});
