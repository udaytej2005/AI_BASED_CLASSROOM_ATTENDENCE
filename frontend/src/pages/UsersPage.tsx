import { useState, type FormEvent } from "react";

import AppShell from "../components/AppShell";
import ConfirmDialog from "../components/ConfirmDialog";
import DataState from "../components/DataState";
import Pagination from "../components/Pagination";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../auth/authContext";
import { errorMessage, useAsyncData } from "../hooks/useAsyncData";
import { useDebounced } from "../hooks/useDebounced";
import * as directory from "../services/directoryService";
import type { CurrentUser, Role } from "../types/api";
import { validateNewUser, type FieldErrors } from "../utils/validation";

const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: "admin", label: "Administrator" },
  { value: "principal", label: "Principal" },
  { value: "faculty", label: "Faculty" },
  { value: "student", label: "Student" },
  { value: "technical", label: "Technical operator" },
];

export default function UsersPage() {
  const { user: me } = useAuth();
  const [search, setSearch] = useState("");
  const [role, setRole] = useState<Role | "">("");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounced(search.trim());
  const [notice, setNotice] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [pendingToggle, setPendingToggle] = useState<CurrentUser | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const result = useAsyncData(
    (signal) => directory.listUsers({ q: debouncedSearch, role, page }, signal),
    [debouncedSearch, role, page],
  );

  async function confirmToggle() {
    if (!pendingToggle) return;
    setBusy(true);
    setActionError(null);
    try {
      const updated = await directory.setUserActive(pendingToggle.id, !pendingToggle.is_active);
      setNotice(`${updated.full_name} is now ${updated.is_active ? "active" : "deactivated"}.`);
      setPendingToggle(null);
      result.reload();
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell title="User accounts" breadcrumbs={["Administration", "User accounts"]}>
      {notice && (
        <p role="status" className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
          {notice}
        </p>
      )}
      {actionError && (
        <p role="alert" className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {actionError}
        </p>
      )}

      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-wrap gap-3">
          <div>
            <label htmlFor="user-search" className="block text-xs font-medium text-slate-600">Search name or email</label>
            <input
              id="user-search"
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="mt-1 w-64 rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="user-role" className="block text-xs font-medium text-slate-600">Role</label>
            <select
              id="user-role"
              value={role}
              onChange={(e) => {
                setRole(e.target.value as Role | "");
                setPage(1);
              }}
              className="mt-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">All roles</option>
              {ROLE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate((open) => !open)}
          aria-expanded={showCreate}
          className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          {showCreate ? "Close form" : "Create account"}
        </button>
      </div>

      {showCreate && (
        <CreateUserForm
          onCreated={(created) => {
            setNotice(`Account created for ${created.email}. The person must change the temporary password at first sign-in.`);
            setShowCreate(false);
            result.reload();
          }}
        />
      )}

      <DataState
        loading={result.loading}
        error={result.error}
        onRetry={result.reload}
        empty={!result.loading && !result.error && (result.data?.items.length ?? 0) === 0}
        emptyMessage="No accounts match these filters."
      >
        {result.data && (
          <>
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <caption className="sr-only">User accounts</caption>
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                  <tr>
                    <th scope="col" className="px-4 py-3">Name</th>
                    <th scope="col" className="px-4 py-3">Email</th>
                    <th scope="col" className="px-4 py-3">Role</th>
                    <th scope="col" className="px-4 py-3">State</th>
                    <th scope="col" className="px-4 py-3"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {result.data.items.map((account) => {
                    const isSelf = account.id === me?.id;
                    return (
                      <tr key={account.id}>
                        <td className="px-4 py-3">{account.full_name}</td>
                        <td className="px-4 py-3 font-mono text-xs">{account.email}</td>
                        <td className="px-4 py-3">{ROLE_OPTIONS.find((o) => o.value === account.role)?.label ?? account.role}</td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap gap-1">
                            <StatusBadge tone={account.is_active ? "success" : "neutral"}>
                              {account.is_active ? "Active" : "Deactivated"}
                            </StatusBadge>
                            {account.must_change_password && <StatusBadge tone="warning">Must change password</StatusBadge>}
                            {account.is_synthetic && <StatusBadge tone="warning">Demo</StatusBadge>}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            type="button"
                            disabled={isSelf}
                            title={isSelf ? "You cannot deactivate your own account." : undefined}
                            onClick={() => setPendingToggle(account)}
                            className="rounded-md px-3 py-1.5 text-sm font-medium text-slate-700 ring-1 ring-slate-300 hover:bg-slate-100 disabled:opacity-50"
                          >
                            {account.is_active ? "Deactivate" : "Activate"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pagination page={result.data.page} totalPages={result.data.total_pages} total={result.data.total} onChange={setPage} />
          </>
        )}
      </DataState>

      <ConfirmDialog
        open={pendingToggle !== null}
        title={pendingToggle?.is_active ? "Deactivate this account?" : "Reactivate this account?"}
        message={
          pendingToggle?.is_active
            ? `${pendingToggle.full_name} will be signed out and cannot sign in until the account is reactivated. Their records are kept.`
            : `${pendingToggle?.full_name ?? "This person"} will be able to sign in again.`
        }
        confirmLabel={pendingToggle?.is_active ? "Deactivate" : "Activate"}
        destructive={Boolean(pendingToggle?.is_active)}
        busy={busy}
        onConfirm={confirmToggle}
        onCancel={() => setPendingToggle(null)}
      />
    </AppShell>
  );
}

function CreateUserForm({ onCreated }: { onCreated: (user: CurrentUser) => void }) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<Role>("faculty");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setServerError(null);
    const found = validateNewUser({ email, fullName, initialPassword: password });
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setSubmitting(true);
    try {
      const created = await directory.createUser({
        email: email.trim(),
        full_name: fullName.trim(),
        role,
        initial_password: password,
      });
      setEmail("");
      setFullName("");
      setPassword("");
      onCreated(created);
    } catch (error) {
      setServerError(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate aria-label="Create user account" className="mb-6 grid gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:grid-cols-2">
      {serverError && (
        <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800 sm:col-span-2">
          {serverError}
        </p>
      )}
      <div>
        <label htmlFor="new-user-name" className="block text-sm font-medium text-slate-700">Full name</label>
        <input id="new-user-name" value={fullName} onChange={(e) => setFullName(e.target.value)} aria-invalid={Boolean(errors.fullName)} className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
        {errors.fullName && <p className="mt-1 text-sm text-red-700">{errors.fullName}</p>}
      </div>
      <div>
        <label htmlFor="new-user-email" className="block text-sm font-medium text-slate-700">Email</label>
        <input id="new-user-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} aria-invalid={Boolean(errors.email)} className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
        {errors.email && <p className="mt-1 text-sm text-red-700">{errors.email}</p>}
      </div>
      <div>
        <label htmlFor="new-user-role" className="block text-sm font-medium text-slate-700">Role</label>
        <select id="new-user-role" value={role} onChange={(e) => setRole(e.target.value as Role)} className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm">
          {ROLE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="new-user-password" className="block text-sm font-medium text-slate-700">Temporary password</label>
        <input id="new-user-password" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} aria-invalid={Boolean(errors.initialPassword)} aria-describedby="new-user-password-hint" className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
        <p id="new-user-password-hint" className="mt-1 text-xs text-slate-500">At least 12 characters. Share it securely; it must be changed at first sign-in.</p>
        {errors.initialPassword && <p className="mt-1 text-sm text-red-700">{errors.initialPassword}</p>}
      </div>
      <div className="sm:col-span-2 flex justify-end">
        <button type="submit" disabled={submitting} className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60">
          {submitting ? "Creating…" : "Create account"}
        </button>
      </div>
    </form>
  );
}
