import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import * as authService from "../services/authService";
import type { CurrentUser } from "../types/api";
import { AuthContext, type AuthState } from "./authContext";

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    authService
      .fetchCurrentUser(controller.signal)
      .then((current) => setUser(current))
      .catch(() => {
        // A 401 means "not signed in". Any other failure also leaves the user signed out.
        if (!controller.signal.aborted) setUser(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const signedIn = await authService.login(email, password);
    setUser(signedIn);
    return signedIn;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await authService.logout();
    } finally {
      // Always clear local state, even if the server could not be reached.
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthState>(
    () => ({ loading, user, signIn, signOut, setUser }),
    [loading, user, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
