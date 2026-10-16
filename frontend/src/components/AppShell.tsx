import { useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/authContext";
import { ROLE_LABELS } from "../config/roles";
import { navItemsFor } from "../config/navigation";

interface AppShellProps {
  children: ReactNode;
  title: string;
  breadcrumbs?: string[];
}

export default function AppShell({ children, title, breadcrumbs = [] }: AppShellProps) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [signingOut, setSigningOut] = useState(false);
  const visibleItems = navItemsFor(user?.role);

  async function handleSignOut() {
    setSigningOut(true);
    try {
      await signOut();
    } finally {
      setSigningOut(false);
      navigate("/login", { replace: true });
    }
  }

  return (
    <div className="flex min-h-screen">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:shadow"
      >
        Skip to main content
      </a>

      <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white md:flex" aria-label="Primary">
        <div className="border-b border-slate-200 px-5 py-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">Academic prototype</p>
          <p className="mt-1 text-base font-semibold text-slate-900">Smart Attendance</p>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4" aria-label="Main navigation">
          {visibleItems.map((item) =>
            item.available ? (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `block rounded-md px-3 py-2 text-sm font-medium ${
                    isActive ? "bg-brand-50 text-brand-900" : "text-slate-700 hover:bg-slate-100"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ) : (
              <span
                key={item.to}
                aria-disabled="true"
                className="flex items-center justify-between rounded-md px-3 py-2 text-sm text-slate-400"
              >
                {item.label}
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
                  Planned
                </span>
              </span>
            ),
          )}
        </nav>
        {user && (
          <div className="border-t border-slate-200 px-5 py-4 text-xs text-slate-500">
            <p className="font-medium text-slate-700">{user.full_name}</p>
            <p>{ROLE_LABELS[user.role]}</p>
          </div>
        )}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-slate-200 bg-white px-4 py-3 md:px-8">
          <div className="min-w-0">
            {breadcrumbs.length > 0 && (
              <nav aria-label="Breadcrumb" className="text-xs text-slate-500">
                <ol className="flex flex-wrap gap-1">
                  {breadcrumbs.map((crumb, index) => (
                    <li key={crumb}>
                      {index > 0 && (
                        <span className="mr-1" aria-hidden="true">
                          /
                        </span>
                      )}
                      {crumb}
                    </li>
                  ))}
                </ol>
              </nav>
            )}
            <h1 className="truncate text-xl font-semibold text-slate-900">{title}</h1>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <span className="hidden rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800 ring-1 ring-amber-200 sm:inline">
              Prototype: demo data only
            </span>
            {user && (
              <button
                type="button"
                onClick={handleSignOut}
                disabled={signingOut}
                className="rounded-md px-3 py-1.5 text-sm font-medium text-slate-700 ring-1 ring-slate-300 hover:bg-slate-100 disabled:opacity-60"
              >
                {signingOut ? "Signing out…" : "Sign out"}
              </button>
            )}
          </div>
        </header>

        <main id="main-content" className="flex-1 px-4 py-6 md:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
