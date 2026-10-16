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

export default function StudentsPage() {
  const { user } = useAuth();
  const canManage = user?.role === "admin";
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | "active" | "inactive">("");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounced(search.trim());

  const result = useAsyncData(
    (signal) => directory.listStudents({ q: debouncedSearch, status: status || undefined, page }, signal),
    [debouncedSearch, status, page],
  );

  return (
    <AppShell title="Students" breadcrumbs={["Directory", "Students"]}>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-wrap gap-3">
          <div>
            <label htmlFor="student-search" className="block text-xs font-medium text-slate-600">
              Search by student ID or name
            </label>
            <input
              id="student-search"
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="e.g. CSE007 or Aarav"
              className="mt-1 w-64 rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="student-status" className="block text-xs font-medium text-slate-600">
              Status
            </label>
            <select
              id="student-status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as "" | "active" | "inactive");
                setPage(1);
              }}
              className="mt-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">All</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
        </div>
        {canManage && (
          <Link
            to="/students/new"
            className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            Add student
          </Link>
        )}
      </div>

      <DataState
        loading={result.loading}
        error={result.error}
        onRetry={result.reload}
        empty={!result.loading && !result.error && (result.data?.items.length ?? 0) === 0}
        emptyMessage="No students match these filters."
      >
        {result.data && (
          <>
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <caption className="sr-only">Student directory</caption>
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                  <tr>
                    <th scope="col" className="px-4 py-3">Student ID</th>
                    <th scope="col" className="px-4 py-3">Name</th>
                    <th scope="col" className="px-4 py-3">Department</th>
                    <th scope="col" className="px-4 py-3">Year / section</th>
                    <th scope="col" className="px-4 py-3">Status</th>
                    <th scope="col" className="px-4 py-3">Login</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {result.data.items.map((student) => (
                    <tr key={student.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-mono">
                        <Link to={`/students/${student.id}`} className="font-medium text-brand-700 hover:underline">
                          {student.student_code}
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        {student.full_name}
                        {student.is_synthetic && (
                          <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium uppercase text-amber-800">
                            Demo record
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">{student.department_code}</td>
                      <td className="px-4 py-3">
                        Year {student.year} · {student.section}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge tone={student.status === "active" ? "success" : "neutral"}>
                          {student.status}
                        </StatusBadge>
                      </td>
                      <td className="px-4 py-3">{student.has_login ? "Account linked" : "No account"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={result.data.page}
              totalPages={result.data.total_pages}
              total={result.data.total}
              onChange={setPage}
            />
          </>
        )}
      </DataState>
    </AppShell>
  );
}
