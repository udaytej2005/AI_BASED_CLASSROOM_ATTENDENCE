import { Link, useParams } from "react-router-dom";

import AppShell from "../components/AppShell";
import DataState from "../components/DataState";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../auth/authContext";
import { useAsyncData } from "../hooks/useAsyncData";
import * as directory from "../services/directoryService";

interface StudentDetailPageProps {
  /** "me" renders the signed-in student's own profile (route /profile). */
  mode?: "record" | "me";
}

export default function StudentDetailPage({ mode = "record" }: StudentDetailPageProps) {
  const { id } = useParams();
  const { user } = useAuth();
  const isOwnProfile = mode === "me";

  const student = useAsyncData(
    (signal) => (isOwnProfile ? directory.getMyStudentProfile(signal) : directory.getStudent(Number(id), signal)),
    [id, mode],
  );

  const canEdit = user?.role === "admin" && !isOwnProfile && student.data !== null;

  return (
    <AppShell
      title={isOwnProfile ? "My profile" : (student.data?.full_name ?? "Student")}
      breadcrumbs={isOwnProfile ? ["Me", "Profile"] : ["Directory", "Students", student.data?.student_code ?? ""]}
    >
      <DataState
        loading={student.loading}
        error={student.error}
        onRetry={student.reload}
        empty={false}
        emptyMessage=""
      >
        {student.data && (
          <div className="grid gap-6 lg:grid-cols-3">
            <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2" aria-labelledby="profile-heading">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 id="profile-heading" className="text-lg font-semibold text-slate-900">
                    {student.data.full_name}
                  </h2>
                  <p className="font-mono text-sm text-slate-600">{student.data.student_code}</p>
                </div>
                <div className="flex items-center gap-3">
                  <StatusBadge tone={student.data.status === "active" ? "success" : "neutral"}>
                    {student.data.status}
                  </StatusBadge>
                  {canEdit && (
                    <Link
                      to={`/students/${student.data.id}/edit`}
                      className="rounded-md px-3 py-1.5 text-sm font-medium text-brand-700 ring-1 ring-brand-200 hover:bg-brand-50"
                    >
                      Edit
                    </Link>
                  )}
                </div>
              </div>
              <dl className="mt-6 grid gap-x-8 gap-y-4 sm:grid-cols-2">
                <Detail label="Department" value={student.data.department_code} />
                <Detail label="Year and section" value={`Year ${student.data.year} · Section ${student.data.section}`} />
                <Detail label="Contact email" value={student.data.email ?? "Not shown to your role"} />
                <Detail label="Login account" value={student.data.has_login ? "Linked" : "None"} />
              </dl>
            </section>

            <section className="rounded-xl border border-dashed border-slate-300 bg-white p-6" aria-labelledby="attendance-heading">
              <h2 id="attendance-heading" className="text-base font-semibold text-slate-900">
                Attendance
              </h2>
              <p className="mt-2 text-sm text-slate-600">
                Attendance by subject, the recent history and percentages appear here once the timetable and attendance
                sessions are built (Phase 3 and Phase 5). No attendance figures are shown until real records exist.
              </p>
            </section>
          </div>
        )}
      </DataState>
    </AppShell>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className="mt-1 font-medium text-slate-900">{value}</dd>
    </div>
  );
}
