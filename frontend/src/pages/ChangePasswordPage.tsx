import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import AppShell from "../components/AppShell";
import { useAuth } from "../auth/authContext";
import { errorMessage } from "../hooks/useAsyncData";
import * as authService from "../services/authService";
import { validateNewPassword, type FieldErrors } from "../utils/validation";

export default function ChangePasswordPage() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const forced = Boolean(user?.must_change_password);

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setServerError(null);
    setSaved(false);
    const validation = validateNewPassword(current, next, confirmation);
    setErrors(validation);
    if (Object.keys(validation).length > 0) return;

    setSubmitting(true);
    try {
      const updated = await authService.changePassword(current, next);
      setUser(updated);
      setCurrent("");
      setNext("");
      setConfirmation("");
      setSaved(true);
      if (forced) navigate("/", { replace: true });
    } catch (error) {
      setServerError(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AppShell title="Change password" breadcrumbs={["Account", "Change password"]}>
      <div className="max-w-md">
        {forced && (
          <p role="status" className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            Your password was set by an administrator. Choose your own password before continuing.
          </p>
        )}
        {saved && !forced && (
          <p role="status" className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
            Your password has been changed. Other sessions were signed out.
          </p>
        )}
        {serverError && (
          <div role="alert" className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            {serverError}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="space-y-5 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <Field
            id="current-password"
            label="Current password"
            value={current}
            onChange={setCurrent}
            error={errors.currentPassword}
            autoComplete="current-password"
          />
          <Field
            id="new-password"
            label="New password"
            value={next}
            onChange={setNext}
            error={errors.newPassword}
            autoComplete="new-password"
            hint="At least 12 characters, mixing three of: lower case, upper case, digits, symbols."
          />
          <Field
            id="confirm-password"
            label="Confirm new password"
            value={confirmation}
            onChange={setConfirmation}
            error={errors.confirmation}
            autoComplete="new-password"
          />
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {submitting ? "Saving…" : "Change password"}
          </button>
        </form>
      </div>
    </AppShell>
  );
}

interface FieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  hint?: string;
  autoComplete: string;
}

function Field({ id, label, value, onChange, error, hint, autoComplete }: FieldProps) {
  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(" ") || undefined;
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={id}
        type="password"
        autoComplete={autoComplete}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
        className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600"
      />
      {hint && (
        <p id={`${id}-hint`} className="mt-1 text-xs text-slate-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-1 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
