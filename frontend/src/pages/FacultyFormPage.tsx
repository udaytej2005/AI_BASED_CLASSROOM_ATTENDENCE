import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";

import AppShell from "../components/AppShell";
import DataState from "../components/DataState";
import { errorMessage, useAsyncData } from "../hooks/useAsyncData";
import * as directory from "../services/directoryService";
import type { FacultyRecord } from "../types/api";
import { EMAIL_PATTERN, MIN_PASSWORD_LENGTH } from "../utils/validation";

type FormErrors = Record<string, string>;

export default function FacultyFormPage() {
  const { id } = useParams();
  const editing = id !== undefined;
  const navigate = useNavigate();

  const departments = useAsyncData((signal) => directory.listDepartments(signal), []);
  const existing = useAsyncData(
    (signal) => (editing ? directory.getFaculty(Number(id), signal) : Promise.resolve(null)),
    [id],
  );

  return (
    <AppShell title={editing ? "Edit faculty member" : "Add faculty member"} breadcrumbs={["Directory", "Faculty", editing ? "Edit" : "New"]}>
      <DataState
        loading={departments.loading || existing.loading}
        error={departments.error ?? existing.error}
        onRetry={existing.reload}
        empty={false}
        emptyMessage=""
      >
        {departments.data && (
          <FacultyForm
            key={existing.data?.id ?? "new"}
            existing={existing.data}
            departments={departments.data.filter((d) => d.is_active)}
            onSaved={() => navigate("/faculty", { replace: true })}
            onCancel={() => navigate("/faculty")}
          />
        )}
      </DataState>
    </AppShell>
  );
}

interface FacultyFormProps {
  existing: FacultyRecord | null;
  departments: { id: number; code: string; name: string }[];
  onSaved: () => void;
  onCancel: () => void;
}

function FacultyForm({ existing, departments, onSaved, onCancel }: FacultyFormProps) {
  const [code, setCode] = useState(existing?.employee_code ?? "");
  const [fullName, setFullName] = useState(existing?.full_name ?? "");
  const [departmentId, setDepartmentId] = useState(String(existing?.department_id ?? departments[0]?.id ?? ""));
  const [email, setEmail] = useState(existing?.email ?? "");
  const [status, setStatus] = useState<"active" | "inactive">(existing?.status ?? "active");
  const [withLogin, setWithLogin] = useState(false);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function validate(): FormErrors {
    const found: FormErrors = {};
    if (!existing && !/^[A-Za-z0-9][A-Za-z0-9-]{1,31}$/.test(code.trim())) {
      found.code = "Use 2-32 letters, digits or hyphens.";
    }
    if (fullName.trim().length < 2) found.fullName = "Enter the full name.";
    if (!departmentId) found.department = "Select a department.";
    if (email && !EMAIL_PATTERN.test(email.trim())) found.email = "Enter a valid email address.";
    if (withLogin) {
      if (!EMAIL_PATTERN.test(loginEmail.trim())) found.loginEmail = "Enter the login email address.";
      if (loginPassword.length < MIN_PASSWORD_LENGTH) {
        found.loginPassword = `Temporary password: at least ${MIN_PASSWORD_LENGTH} characters.`;
      }
    }
    return found;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setServerError(null);
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setSubmitting(true);
    try {
      const common = { full_name: fullName.trim(), department_id: Number(departmentId), email: email.trim() || null };
      if (existing) {
        await directory.updateFaculty(existing.id, { ...common, status });
      } else {
        await directory.createFaculty({
          ...common,
          employee_code: code.trim(),
          account: withLogin ? { email: loginEmail.trim(), initial_password: loginPassword } : null,
        });
      }
      onSaved();
    } catch (error) {
      setServerError(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="max-w-2xl space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      {serverError && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {serverError}
        </div>
      )}
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="employee-code" className="block text-sm font-medium text-slate-700">Employee code</label>
          <input
            id="employee-code"
            value={code}
            disabled={Boolean(existing)}
            onChange={(e) => setCode(e.target.value)}
            aria-invalid={Boolean(errors.code)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
          />
          {errors.code && <p className="mt-1 text-sm text-red-700">{errors.code}</p>}
        </div>
        <div>
          <label htmlFor="faculty-name" className="block text-sm font-medium text-slate-700">Full name</label>
          <input
            id="faculty-name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            aria-invalid={Boolean(errors.fullName)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          {errors.fullName && <p className="mt-1 text-sm text-red-700">{errors.fullName}</p>}
        </div>
        <div>
          <label htmlFor="faculty-department" className="block text-sm font-medium text-slate-700">Department</label>
          <select
            id="faculty-department"
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.code} — {d.name}
              </option>
            ))}
          </select>
          {errors.department && <p className="mt-1 text-sm text-red-700">{errors.department}</p>}
        </div>
        <div>
          <label htmlFor="faculty-email" className="block text-sm font-medium text-slate-700">Contact email (optional)</label>
          <input
            id="faculty-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-invalid={Boolean(errors.email)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          {errors.email && <p className="mt-1 text-sm text-red-700">{errors.email}</p>}
        </div>
        {existing && (
          <div>
            <label htmlFor="faculty-status" className="block text-sm font-medium text-slate-700">Status</label>
            <select
              id="faculty-status"
              value={status}
              onChange={(e) => setStatus(e.target.value as "active" | "inactive")}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive (kept for history)</option>
            </select>
          </div>
        )}
      </div>

      {!existing && (
        <fieldset className="space-y-4 rounded-lg border border-slate-200 p-4">
          <legend className="px-1 text-sm font-medium text-slate-800">Faculty login (optional)</legend>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={withLogin} onChange={(e) => setWithLogin(e.target.checked)} />
            Create a login for this faculty member
          </label>
          {withLogin && (
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label htmlFor="faculty-login-email" className="block text-sm font-medium text-slate-700">Login email</label>
                <input id="faculty-login-email" type="email" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                {errors.loginEmail && <p className="mt-1 text-sm text-red-700">{errors.loginEmail}</p>}
              </div>
              <div>
                <label htmlFor="faculty-login-password" className="block text-sm font-medium text-slate-700">Temporary password</label>
                <input id="faculty-login-password" type="password" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                <p className="mt-1 text-xs text-slate-500">The faculty member must change this at first sign-in.</p>
                {errors.loginPassword && <p className="mt-1 text-sm text-red-700">{errors.loginPassword}</p>}
              </div>
            </div>
          )}
        </fieldset>
      )}

      <div className="flex items-center justify-end gap-3">
        <button type="button" onClick={onCancel} className="rounded-md px-4 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-300 hover:bg-slate-100">
          Cancel
        </button>
        <button type="submit" disabled={submitting} className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60">
          {submitting ? "Saving…" : existing ? "Save changes" : "Add faculty member"}
        </button>
      </div>
    </form>
  );
}
