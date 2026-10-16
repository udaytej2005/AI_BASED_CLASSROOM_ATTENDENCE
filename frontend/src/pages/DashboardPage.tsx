import { useHealth } from "../hooks/useHealth";
import AppShell from "../components/AppShell";
import StatusBadge from "../components/StatusBadge";
import StatusCard from "../components/StatusCard";

export default function DashboardPage() {
  const { loading, backend, database, error, refresh } = useHealth();

  return (
    <AppShell title="Dashboard" breadcrumbs={["Home"]}>
      <div className="mb-6 max-w-3xl">
        <h2 className="text-2xl font-semibold text-slate-900">Welcome</h2>
        <p className="mt-2 text-sm text-slate-600">
          This is the Phase 1 foundation. Role-based dashboards with real attendance data are added in later phases.
          The cards below are live readings from the backend API.
        </p>
      </div>

      {loading && (
        <p role="status" className="text-sm text-slate-600">
          Checking the server…
        </p>
      )}

      {!loading && error && (
        <div role="alert" className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <p className="font-semibold">The backend is not reachable.</p>
          <p className="mt-1">{error}</p>
          <button
            type="button"
            onClick={refresh}
            className="mt-3 rounded-md bg-white px-3 py-1.5 font-medium text-red-800 ring-1 ring-red-300 hover:bg-red-100"
          >
            Try again
          </button>
        </div>
      )}

      {!loading && backend && database && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <StatusCard
            title="Backend API"
            value={
              <StatusBadge tone={backend.status === "ok" ? "success" : "danger"}>
                {backend.status === "ok" ? "Operational" : "Degraded"}
              </StatusBadge>
            }
            description={`Version ${backend.version} (${backend.environment})`}
          />
          <StatusCard
            title="Database"
            value={
              <StatusBadge tone={database.database === "connected" ? "success" : "danger"}>
                {database.database === "connected" ? "Connected" : "Unreachable"}
              </StatusBadge>
            }
            description="Connectivity check only; credentials are never shown."
          />
          <StatusCard
            title="Institution timezone"
            value={backend.timezone}
            description="Timetable times and timestamps are shown in this timezone."
          />
        </div>
      )}
    </AppShell>
  );
}
