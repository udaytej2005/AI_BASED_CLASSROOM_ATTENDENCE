import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import AppShell from "../components/AppShell";
import DataState from "../components/DataState";
import { errorMessage, useAsyncData } from "../hooks/useAsyncData";
import * as directory from "../services/directoryService";
import type { StudentRecord } from "../types/api";
import { EMAIL_PATTERN, MIN_PASSWORD_LENGTH } from "../utils/validation";

type FormErrors = Record<string, string>;

export default function StudentFormPage() {
  const { id } = useParams();
  const editing = id !== undefined;
  const navigate = useNavigate();

  const departments = useAsyncData((signal) => directory.listDepartments(signal), []);
  const existing = useAsyncData(
    (signal) => (editing ? directory.getStudent(Number(id), signal) : Promise.resolve(null)),
    [id],
  );

  return (
    <AppShell
      title={editing ? "Edit student" : "Add student"}
      breadcrumbs={["Directory", "Students", editing ? "Edit" : "New"]}
    >
      <DataState
        loading={departments.loading || existing.loading}
        error={departments.error ?? existing.error}
        onRetry={existing.reload}
        empty={false}
        emptyMessage=""
      >
        {departments.data && (
          <StudentForm
            key={existing.data?.id ?? "new"}
            existing={existing.data}
            departments={departments.data.filter((d) => d.is_active)}
            onSaved={(record) => navigate(`/students/${record.id}`, { replace: true })}
            onCancel={() => navigate(editing ? `/students/${id}` : "/students")}
          />
        )}
      </DataState>
    </AppShell>
  );
}

interface StudentFormProps {
  existing: StudentRecord | null;
  departments: { id: number; code: string; name: string }[];
  onSaved: (record: StudentRecord) => void;
  onCancel: () => void;
}

function StudentForm({ existing, departments, onSaved, onCancel }: StudentFormProps) {
  const [code, setCode] = useState(existing?.student_code ?? "");
  const [fullName, setFullName] = useState(existing?.full_name ?? "");
  const [departmentId, setDepartmentId] = useState(String(existing?.department_id ?? departments[0]?.id ?? ""));
  const [year, setYear] = useState(String(existing?.year ?? 1));
  const [section, setSection] = useState(existing?.section ?? "A");
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
      found.code = "Use 2-32 letters, digits or hyphens, for example CSE001.";
    }
    if (fullName.trim().length < 2) found.fullName = "Enter the student's full name.";
    if (!departmentId) found.department = "Select a department.";
    if (!/^[A-Za-z0-9]{1,10}$/.test(section.trim())) found.section = "Section: 1-10 letters or digits.";
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
      const common = {
        full_name: fullName.trim(),
        department_id: Number(departmentId),
        year: Number(year),
        section: section.trim(),
        email: email.trim() || null,
      };
      const saved = existing
        ? await directory.updateStudent(existing.id, { ...common, status })
        : await directory.createStudent({
            ...common,
            student_code: code.trim(),
            account: withLogin
              ? { email: loginEmail.trim(), initial_password: loginPassword }
              : null,
          });
      onSaved(saved);
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
        <TextField
          id="student-code"
          label="Student ID (roll number)"
          value={code}
          onChange={setCode}
          error={errors.code}
          disabled={Boolean(existing)}
          hint={existing ? "The student ID cannot be changed." : undefined}
        />
        <TextField id="full-name" label="Full name" value={fullName} onChange={setFullName} error={errors.fullName} />
        <div>
          <label htmlFor="department" className="block text-sm font-medium text-slate-700">Department</label>
          <select
            id="department"
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
          <label htmlFor="year" className="block text-sm font-medium text-slate-700">Year</label>
          <select
            id="year"
            value={year}
            onChange={(e) => setYear(e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            {[1, 2, 3, 4, 5, 6].map((y) => (
              <option key={y} value={y}>
                Year {y}
              </option>
            ))}
          </select>
        </div>
        <TextField id="section" label="Section" value={section} onChange={setSection} error={errors.section} />
        <TextField id="email" label="Contact email (optional)" value={email} onChange={setEmail} error={errors.email} type="email" />
        {existing && (
          <div>
            <label htmlFor="status" className="block text-sm font-medium text-slate-700">Status</label>
            <select
              id="status"
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
          <legend className="px-1 text-sm font-medium text-slate-800">Student login (optional)</legend>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={withLogin} onChange={(e) => setWithLogin(e.target.checked)} />
            Create a login so the student can view their own attendance
          </label>
          {withLogin && (
            <div className="grid gap-5 sm:grid-cols-2">
              <TextField id="login-email" label="Login email" value={loginEmail} onChange={setLoginEmail} error={errors.loginEmail} type="email" />
              <TextField
                id="login-password"
                label="Temporary password"
                value={loginPassword}
                onChange={setLoginPassword}
                error={errors.loginPassword}
                type="password"
                hint="The student must change this at first sign-in."
              />
            </div>
          )}
        </fieldset>
      )}

      <div className="flex items-center justify-end gap-3">
        <Link to={existing ? `/students/${existing.id}` : "/students"} onClick={onCancel} className="rounded-md px-4 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-300 hover:bg-slate-100">
          Cancel
        </Link>
        <button type="submit" disabled={submitting} className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60">
          {submitting ? "Saving…" : existing ? "Save changes" : "Create student"}
        </button>
      </div>
    </form>
  );
}

interface TextFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  hint?: string;
  type?: string;
  disabled?: boolean;
}

function TextField({ id, label, value, onChange, error, hint, type = "text", disabled = false }: TextFieldProps) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">{label}</label>
      <input
        id={id}
        type={type}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
        className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
      />
      {hint && <p id={`${id}-hint`} className="mt-1 text-xs text-slate-500">{hint}</p>}
      {error && <p id={`${id}-error`} className="mt-1 text-sm text-red-700">{error}</p>}
    </div>
  );
}
