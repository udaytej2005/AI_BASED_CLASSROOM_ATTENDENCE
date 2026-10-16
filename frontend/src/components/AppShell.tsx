import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { NAV_ITEMS } from "../config/navigation";

interface AppShellProps {
  children: ReactNode;
  title: string;
  breadcrumbs?: string[];
}

export default function AppShell({ children, title, breadcrumbs = [] }: AppShellProps) {
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
        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV_ITEMS.map((item) =>
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
        <p className="border-t border-slate-200 px-5 py-4 text-xs text-slate-500">
          Not signed in. Authentication arrives in Phase 2.
        </p>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 md:px-8">
          <div className="min-w-0">
            {breadcrumbs.length > 0 && (
              <nav aria-label="Breadcrumb" className="text-xs text-slate-500">
                <ol className="flex flex-wrap gap-1">
                  {breadcrumbs.map((crumb, index) => (
                    <li key={crumb}>
                      {index > 0 && <span className="mr-1" aria-hidden="true">/</span>}
                      {crumb}
                    </li>
                  ))}
                </ol>
              </nav>
            )}
            <h1 className="truncate text-xl font-semibold text-slate-900">{title}</h1>
          </div>
          <span className="ml-4 shrink-0 rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800 ring-1 ring-amber-200">
            Prototype: demo data only
          </span>
        </header>

        <main id="main-content" className="flex-1 px-4 py-6 md:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
