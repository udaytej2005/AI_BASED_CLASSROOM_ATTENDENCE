import { Link } from "react-router-dom";

export default function ForbiddenPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 text-center">
      <p className="text-sm font-semibold text-brand-700">403</p>
      <h1 className="mt-2 text-2xl font-semibold text-slate-900">You do not have access to this page</h1>
      <p className="mt-2 max-w-md text-sm text-slate-600">
        Your role does not include this area. If you believe this is a mistake, ask an administrator.
      </p>
      <Link to="/" className="mt-6 rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
        Go to my dashboard
      </Link>
    </div>
  );
}
