import { apiRequest } from "./apiClient";
import type { CurrentUser } from "../types/api";

export function fetchCurrentUser(signal?: AbortSignal): Promise<CurrentUser> {
  return apiRequest<CurrentUser>("/auth/me", { signal });
}

export function login(email: string, password: string): Promise<CurrentUser> {
  return apiRequest<CurrentUser>("/auth/login", { method: "POST", body: { email, password } });
}

export function logout(): Promise<{ status: string }> {
  return apiRequest<{ status: string }>("/auth/logout", { method: "POST" });
}

export function changePassword(currentPassword: string, newPassword: string): Promise<CurrentUser> {
  return apiRequest<CurrentUser>("/auth/change-password", {
    method: "POST",
    body: { current_password: currentPassword, new_password: newPassword },
  });
}
