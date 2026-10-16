import AppShell from "../components/AppShell";
import StatusBadge from "../components/StatusBadge";
import { useHealth } from "../hooks/useHealth";

export default function SystemHealthPage() {
  const { loading, backend, database, error, refresh } = useHealth();

  return (
    <AppShell title="System health" breadcrumbs={["Home", "System health"]}>
      <p className="mb-6 max-w-3xl text-sm text-slate-600">
        Basic readings that the backend can measure today. Camera, recognition and job metrics are added in later phases.
      </p>

      {loading && <p role="status" className="text-sm text-slate-600">Checking…</p>}

      {!loading && error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {error}{" "}
          <button type="button" onClick={refresh} className="font-medium underline">
            Retry
          </button>
        </div>
      )}

      {!loading && backend && database && (
        <dl className="grid max-w-3xl grid-cols-1 gap-x-8 gap-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:grid-cols-2">
          <div>
            <dt className="text-sm text-slate-500">API status</dt>
            <dd className="mt-1">
              <StatusBadge tone={backend.status === "ok" ? "success" : "danger"}>{backend.status}</StatusBadge>
            </dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">Database</dt>
            <dd className="mt-1">
              <StatusBadge tone={database.database === "connected" ? "success" : "danger"}>
                {database.database}
              </StatusBadge>
            </dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">Application version</dt>
            <dd className="mt-1 font-medium text-slate-900">{backend.version}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">Environment</dt>
            <dd className="mt-1 font-medium text-slate-900">{backend.environment}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">Server time (UTC)</dt>
            <dd className="mt-1 font-mono text-sm text-slate-900">{backend.server_time_utc}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">Configured timezone</dt>
            <dd className="mt-1 font-medium text-slate-900">{backend.timezone}</dd>
          </div>
        </dl>
      )}
    </AppShell>
  );
}
