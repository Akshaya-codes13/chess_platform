export default function Pagination({ page, pages, total, onChange, label = 'results' }) {
  if (!total) return null;

  return (
    <nav className="tr-pagination" aria-label="Pagination">
      <span className="tr-muted">
        {total} {label}
        {pages > 1 && ` · page ${page} of ${pages}`}
      </span>
      {pages > 1 && (
        <span className="tr-pagination__buttons">
          <button
            type="button"
            className="tr-btn tr-btn--ghost tr-btn--sm"
            disabled={page <= 1}
            onClick={() => onChange(page - 1)}
          >
            ← Previous
          </button>
          <button
            type="button"
            className="tr-btn tr-btn--ghost tr-btn--sm"
            disabled={page >= pages}
            onClick={() => onChange(page + 1)}
          >
            Next →
          </button>
        </span>
      )}
    </nav>
  );
}
