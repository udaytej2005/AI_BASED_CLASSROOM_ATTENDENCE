import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import ForbiddenPage from "../pages/ForbiddenPage";
import type { Role } from "../types/api";
import { useAuth } from "./authContext";

export const PASSWORD_CHANGE_PATH = "/account/password";

interface RequireAuthProps {
  children: ReactNode;
  /** When given, only these roles may open the route. */
  roles?: Role[];
}

/**
 * Route guard. It is a usability layer: every API call is still checked on the server.
 * Order of checks: signed in -> password change not pending -> role allowed.
 */
export default function RequireAuth({ children, roles }: RequireAuthProps) {
  const { loading, user } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div role="status" className="flex min-h-screen items-center justify-center text-sm text-slate-600">
        Checking your session…
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (user.must_change_password && location.pathname !== PASSWORD_CHANGE_PATH) {
    return <Navigate to={PASSWORD_CHANGE_PATH} replace />;
  }

  if (roles && !roles.includes(user.role)) {
    return <ForbiddenPage />;
  }

  return <>{children}</>;
}
