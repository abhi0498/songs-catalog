import { useEffect, useState } from "react";
import { fetchSongs } from "./lib/api.js";
import { csvFilename, downloadCsv, toCsv } from "./lib/csv.js";
import { DEFAULT_SORT, nextSort } from "./lib/sort.js";
import Pagination from "./components/Pagination.jsx";
import SongTable from "./components/SongTable.jsx";

export default function App() {
  const [query, setQuery] = useState({ page: 1, ...DEFAULT_SORT });
  const [pageData, setPageData] = useState(null);
  const [status, setStatus] = useState({ state: "loading", error: null });
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let ignore = false; // drop responses for queries that are no longer current
    setStatus({ state: "loading", error: null });
    fetchSongs(query).then(
      (data) => { if (!ignore) { setPageData(data); setStatus({ state: "ok", error: null }); } },
      (error) => { if (!ignore) setStatus({ state: "error", error }); },
    );
    return () => { ignore = true; };
  }, [query, reload]);

  const sortState = { sort: query.sort, order: query.order };
  const onSort = (column) => setQuery({ page: 1, ...nextSort(sortState, column) });
  const onPage = (page) => setQuery((q) => ({ ...q, page }));
  const loading = status.state === "loading";
  const rows = pageData?.items ?? [];
  const onDownload = () => downloadCsv(toCsv(rows), csvFilename(query));

  return (
    <main className="app">
      <header className="app-header">
        <h1>Songs</h1>
      </header>

      <div className="toolbar">
        <button type="button" onClick={onDownload} disabled={rows.length === 0}>
          Download CSV
        </button>
      </div>

      <section aria-labelledby="table-heading">
        <h2 id="table-heading" className="visually-hidden">All songs</h2>
        {status.state === "error" && (
          <div role="alert" className="error">
            Couldn't load songs: {status.error.message}{" "}
            <button type="button" onClick={() => setReload((n) => n + 1)}>Retry</button>
          </div>
        )}
        {pageData && (
          <>
            {pageData.items.length === 0
              ? <p className="muted">No songs</p>
              : <SongTable rows={pageData.items} sortState={sortState} onSort={onSort} busy={loading} />}
            <Pagination page={pageData.page} totalPages={pageData.total_pages}
                        total={pageData.total} onPage={onPage} busy={loading} />
          </>
        )}
        {!pageData && loading && <p className="muted">Loading songs…</p>}
      </section>
    </main>
  );
}
