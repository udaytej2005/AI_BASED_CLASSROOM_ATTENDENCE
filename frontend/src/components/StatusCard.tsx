import type { ReactNode } from "react";

interface StatusCardProps {
  title: string;
  value: ReactNode;
  description?: string;
  footer?: ReactNode;
}

export default function StatusCard({ title, value, description, footer }: StatusCardProps) {
  return (
    <section className="flex flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm" aria-label={title}>
      <h2 className="text-sm font-medium text-slate-500">{title}</h2>
      <div className="mt-2 text-lg font-semibold text-slate-900">{value}</div>
      {description && <p className="mt-1 text-sm text-slate-600">{description}</p>}
      {footer && <div className="mt-4">{footer}</div>}
    </section>
  );
}
