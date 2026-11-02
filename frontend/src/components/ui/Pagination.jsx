import Button from './Button';

export default function Pagination({ page, pages, onChange }) {
  if (!pages || pages <= 1) return null;
  return (
    <nav className="pagination" aria-label="Pagination">
      <Button variant="ghost" size="sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        Previous
      </Button>
      <span>
        Page {page} of {pages}
      </span>
      <Button variant="ghost" size="sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>
        Next
      </Button>
    </nav>
  );
}
