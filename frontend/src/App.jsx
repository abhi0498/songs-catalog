import { useEffect, useRef, useState } from "react";
import { fetchSongs, searchSongs } from "./lib/api.js";
import { csvFilename, downloadCsv, toCsv } from "./lib/csv.js";
import { DEFAULT_SORT, nextSort } from "./lib/sort.js";
import Pagination from "./components/Pagination.jsx";
import SearchPanel from "./components/SearchPanel.jsx";
import SongTable from "./components/SongTable.jsx";
import StarRating from "./components/StarRating.jsx";

export default function App() {
  const [query, setQuery] = useState({ page: 1, ...DEFAULT_SORT });
  const [pageData, setPageData] = useState(null);
  const [status, setStatus] = useState({ state: "loading", error: null });
  const [reload, setReload] = useState(0);
  const [search, setSearch] = useState({ state: "idle" });
  const searchSeq = useRef(0); // only the latest search may update the panel

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

  const onSearch = (text) => {
    const q = text.trim();
    const seq = ++searchSeq.current;
    if (!q) { setSearch({ state: "empty" }); return; }
    setSearch({ state: "loading", query: q });
    searchSongs(q).then(
      (result) => { if (seq === searchSeq.current) setSearch({ state: "done", query: q, result }); },
      (error) => { if (seq === searchSeq.current) setSearch({ state: "error", query: q, error }); },
    );
  };
  const onClearSearch = () => { searchSeq.current++; setSearch({ state: "idle" }); };

  // R-RATE-3: put the API's updated song everywhere it's shown, without re-sorting (R-RATE-5).
  const onRated = (updated) => {
    const swap = (items) => items.map((s) => (s.id === updated.id ? updated : s));
    setPageData((d) => (d ? { ...d, items: swap(d.items) } : d));
    setSearch((s) => (s.state === "done" ? { ...s, result: { ...s.result, items: swap(s.result.items) } } : s));
  };
  const renderRating = (song) => <StarRating song={song} onRated={onRated} />;

  return (
    <main className="app">
      <header className="app-header">
        <h1>Songs</h1>
      </header>

      <SearchPanel search={search} onSearch={onSearch} onClear={onClearSearch}
                   renderRating={renderRating} />

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
              : <SongTable rows={pageData.items} sortState={sortState} onSort={onSort}
                           busy={loading} renderRating={renderRating} />}
            <Pagination page={pageData.page} totalPages={pageData.total_pages}
                        total={pageData.total} onPage={onPage} busy={loading} />
          </>
        )}
        {!pageData && loading && <p className="muted">Loading songs…</p>}
      </section>
    </main>
  );
}
