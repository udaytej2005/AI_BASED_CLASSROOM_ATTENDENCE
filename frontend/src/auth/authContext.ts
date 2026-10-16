import { createContext, useContext } from "react";

import type { CurrentUser } from "../types/api";

export interface AuthState {
  /** True while the initial "who am I" request is in flight. */
  loading: boolean;
  user: CurrentUser | null;
  signIn: (email: string, password: string) => Promise<CurrentUser>;
  signOut: () => Promise<void>;
  /** Replace the cached user after a change such as a completed password change. */
  setUser: (user: CurrentUser) => void;
}

export const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (value === null) {
    throw new Error("useAuth must be used inside <AuthProvider>.");
  }
  return value;
}
