import { useState } from "react";
import { Link } from "react-router-dom";

import AppShell from "../components/AppShell";
import DataState from "../components/DataState";
import Pagination from "../components/Pagination";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../auth/authContext";
import { useAsyncData } from "../hooks/useAsyncData";
import { useDebounced } from "../hooks/useDebounced";
import * as directory from "../services/directoryService";

export default function FacultyPage() {
  const { user } = useAuth();
  const canManage = user?.role === "admin";
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounced(search.trim());

  const result = useAsyncData(
    (signal) => directory.listFaculty({ q: debouncedSearch, page }, signal),
    [debouncedSearch, page],
  );

  return (
    <AppShell title="Faculty" breadcrumbs={["Directory", "Faculty"]}>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <label htmlFor="faculty-search" className="block text-xs font-medium text-slate-600">
            Search by employee code or name
          </label>
          <input
            id="faculty-search"
            type="search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="mt-1 w-64 rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        {canManage && (
          <Link to="/faculty/new" className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
            Add faculty member
          </Link>
        )}
      </div>

      <DataState
        loading={result.loading}
        error={result.error}
        onRetry={result.reload}
        empty={!result.loading && !result.error && (result.data?.items.length ?? 0) === 0}
        emptyMessage="No faculty members match this search."
      >
        {result.data && (
          <>
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <caption className="sr-only">Faculty directory</caption>
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                  <tr>
                    <th scope="col" className="px-4 py-3">Employee code</th>
                    <th scope="col" className="px-4 py-3">Name</th>
                    <th scope="col" className="px-4 py-3">Department</th>
                    <th scope="col" className="px-4 py-3">Status</th>
                    <th scope="col" className="px-4 py-3">Login</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {result.data.items.map((member) => (
                    <tr key={member.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-mono">
                        {canManage ? (
                          <Link to={`/faculty/${member.id}/edit`} className="font-medium text-brand-700 hover:underline">
                            {member.employee_code}
                          </Link>
                        ) : (
                          member.employee_code
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {member.full_name}
                        {member.is_synthetic && (
                          <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium uppercase text-amber-800">
                            Demo record
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">{member.department_code}</td>
                      <td className="px-4 py-3">
                        <StatusBadge tone={member.status === "active" ? "success" : "neutral"}>{member.status}</StatusBadge>
                      </td>
                      <td className="px-4 py-3">{member.has_login ? "Account linked" : "No account"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={result.data.page} totalPages={result.data.total_pages} total={result.data.total} onChange={setPage} />
          </>
        )}
      </DataState>
    </AppShell>
  );
}
