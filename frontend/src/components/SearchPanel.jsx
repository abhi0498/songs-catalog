import { useState } from "react";
import { describeSearch } from "../lib/searchState.js";
import SongTable from "./SongTable.jsx";

/** Title box + Get Song. Search state lives in App so ratings stay in sync (R-RATE-3). */
export default function SearchPanel({ search, onSearch, onClear, renderRating }) {
  const [text, setText] = useState("");
  const status = describeSearch(search);
  const loading = search.state === "loading";
  const items = search.state === "done" ? search.result.items : [];

  const submit = (e) => {
    e.preventDefault();
    onSearch(text);
  };
  const clear = () => {
    setText("");
    onClear();
  };

  return (
    <section className="search" aria-labelledby="search-heading">
      <h2 id="search-heading">Find a song</h2>
      <form role="search" onSubmit={submit} className="search-form">
        <label htmlFor="title-search">Search by title</label>
        <input id="title-search" type="search" value={text} autoComplete="off"
               placeholder="e.g. Perfect" onChange={(e) => setText(e.target.value)} />
        <button type="submit" disabled={loading}>{loading ? "Searching…" : "Get Song"}</button>
        {search.state !== "idle" && <button type="button" className="secondary" onClick={clear}>Clear</button>}
      </form>
      <p role="status" className={`search-status ${status?.tone ?? ""}`}>{status?.message}</p>
      {items.length > 0 && <SongTable rows={items} label="Search results" renderRating={renderRating} />}
    </section>
  );
}
