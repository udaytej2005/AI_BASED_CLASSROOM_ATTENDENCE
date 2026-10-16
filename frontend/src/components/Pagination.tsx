interface PaginationProps {
  page: number;
  totalPages: number;
  total: number;
  onChange: (page: number) => void;
}

export default function Pagination({ page, totalPages, total, onChange }: PaginationProps) {
  return (
    <nav aria-label="Pagination" className="mt-4 flex items-center justify-between text-sm text-slate-600">
      <span>
        {total} {total === 1 ? "record" : "records"} · page {page} of {totalPages}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onChange(page - 1)}
          disabled={page <= 1}
          className="rounded-md px-3 py-1.5 ring-1 ring-slate-300 hover:bg-slate-100 disabled:opacity-50"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={() => onChange(page + 1)}
          disabled={page >= totalPages}
          className="rounded-md px-3 py-1.5 ring-1 ring-slate-300 hover:bg-slate-100 disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </nav>
  );
}
