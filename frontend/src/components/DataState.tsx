import type { ReactNode } from "react";

interface DataStateProps {
  loading: boolean;
  error: string | null;
  empty: boolean;
  emptyMessage: string;
  onRetry?: () => void;
  children: ReactNode;
}

/** Shared loading / error / empty handling so every list behaves the same way. */
export default function DataState({ loading, error, empty, emptyMessage, onRetry, children }: DataStateProps) {
  if (error) {
    return (
      <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
        <p>{error}</p>
        {onRetry && (
          <button type="button" onClick={onRetry} className="mt-2 font-medium underline">
            Try again
          </button>
        )}
      </div>
    );
  }
  if (loading) {
    return (
      <p role="status" className="py-8 text-center text-sm text-slate-600">
        Loading…
      </p>
    );
  }
  if (empty) {
    return <p className="rounded-lg border border-dashed border-slate-300 py-10 text-center text-sm text-slate-600">{emptyMessage}</p>;
  }
  return <>{children}</>;
}
