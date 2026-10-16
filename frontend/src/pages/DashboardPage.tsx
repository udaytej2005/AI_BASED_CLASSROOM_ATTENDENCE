import { Link } from "react-router-dom";

import { useAuth } from "../auth/authContext";
import AppShell from "../components/AppShell";
import { ROLE_LABELS } from "../config/roles";
import DataState from "../components/DataState";
import StatusBadge from "../components/StatusBadge";
import StatusCard from "../components/StatusCard";
import { useAsyncData } from "../hooks/useAsyncData";
import { useHealth } from "../hooks/useHealth";
import * as directory from "../services/directoryService";
import type { CurrentUser } from "../types/api";

export default function DashboardPage() {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <AppShell title="Dashboard" breadcrumbs={["Home"]}>
      <div className="mb-6 max-w-3xl">
        <h2 className="text-2xl font-semibold text-slate-900">Welcome, {user.full_name}</h2>
        <p className="mt-2 text-sm text-slate-600">
          Signed in as <span className="font-medium">{ROLE_LABELS[user.role]}</span>. Figures below come
          from the database through the API. Attendance dashboards arrive in later phases.
        </p>
      </div>

      {(user.role === "admin" || user.role === "principal" || user.role === "faculty") && <DirectoryCounts user={user} />}
      {user.role === "student" && <StudentSummary />}
      {(user.role === "admin" || user.role === "technical") && <HealthSummary />}
    </AppShell>
  );
}

function DirectoryCounts({ user }: { user: CurrentUser }) {
  const counts = useAsyncData(
    async (signal) => {
      const [students, faculty, accounts] = await Promise.all([
        directory.listStudents({ pageSize: 1 }, signal),
        directory.listFaculty({ pageSize: 1 }, signal),
        user.role === "admin" ? directory.listUsers({ pageSize: 1 }, signal) : Promise.resolve(null),
      ]);
      return {
        students: students.total,
        faculty: faculty.total,
        accounts: accounts?.total ?? null,
      };
    },
    [user.id, user.role],
  );

  return (
    <DataState loading={counts.loading} error={counts.error} onRetry={counts.reload} empty={false} emptyMessage="">
      {counts.data && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <StatusCard title="Registered students" value={counts.data.students} description="Student profiles in the directory (active and inactive)." footer={<Link className="text-sm font-medium text-brand-700 hover:underline" to="/students">Open student directory</Link>} />
          <StatusCard title="Faculty members" value={counts.data.faculty} description="Faculty profiles in the directory." footer={<Link className="text-sm font-medium text-brand-700 hover:underline" to="/faculty">Open faculty directory</Link>} />
          {counts.data.accounts !== null && (
            <StatusCard title="User accounts" value={counts.data.accounts} description="Sign-in accounts of all roles." footer={<Link className="text-sm font-medium text-brand-700 hover:underline" to="/users">Manage accounts</Link>} />
          )}
        </div>
      )}
    </DataState>
  );
}

function StudentSummary() {
  const profile = useAsyncData((signal) => directory.getMyStudentProfile(signal), []);
  return (
    <DataState loading={profile.loading} error={profile.error} onRetry={profile.reload} empty={false} emptyMessage="">
      {profile.data && (
        <div className="grid gap-4 md:grid-cols-2">
          <StatusCard
            title="Your student record"
            value={`${profile.data.student_code} · ${profile.data.full_name}`}
            description={`Year ${profile.data.year}, section ${profile.data.section} · ${profile.data.department_code}`}
            footer={<Link className="text-sm font-medium text-brand-700 hover:underline" to="/profile">View my profile</Link>}
          />
          <StatusCard
            title="Attendance"
            value={<StatusBadge tone="neutral">Not yet available</StatusBadge>}
            description="Your subject-wise attendance will appear here once attendance sessions are recorded (later phase)."
          />
        </div>
      )}
    </DataState>
  );
}

function HealthSummary() {
  const { loading, backend, database, error, refresh } = useHealth();
  return (
    <DataState loading={loading} error={error} onRetry={refresh} empty={false} emptyMessage="">
      {backend && database && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <StatusCard
            title="Backend API"
            value={<StatusBadge tone={backend.status === "ok" ? "success" : "danger"}>{backend.status === "ok" ? "Operational" : "Degraded"}</StatusBadge>}
            description={`Version ${backend.version} (${backend.environment})`}
            footer={<Link className="text-sm font-medium text-brand-700 hover:underline" to="/system">Open system health</Link>}
          />
          <StatusCard
            title="Database"
            value={<StatusBadge tone={database.database === "connected" ? "success" : "danger"}>{database.database === "connected" ? "Connected" : "Unreachable"}</StatusBadge>}
            description="Connectivity check only; credentials are never shown."
          />
          <StatusCard title="Institution timezone" value={backend.timezone} description="Timetable times and timestamps use this timezone." />
        </div>
      )}
    </DataState>
  );
}
