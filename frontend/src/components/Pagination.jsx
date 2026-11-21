export default function Pagination({ page, totalPages, total, onPage, busy }) {
  return (
    <nav className="pagination" aria-label="Pagination">
      <button type="button" aria-label="Previous page" onClick={() => onPage(page - 1)}
              disabled={busy || page <= 1}>‹ Prev</button>
      <span>Page {page} of {Math.max(totalPages, 1)} · {total} songs</span>
      <button type="button" aria-label="Next page" onClick={() => onPage(page + 1)}
              disabled={busy || page >= totalPages}>Next ›</button>
    </nav>
  );
}
