import { COLUMNS } from "../lib/columns.js";
import Cell from "./Cell.jsx";

const ARIA = { asc: "ascending", desc: "descending" };

/**
 * Songs as a table. With `onSort`, headers are sort buttons (R-SORT-1..3).
 * Without it (search results), headers are plain text, since the API doesn't sort those.
 * `renderRating(song)` renders the rating cell. It defaults to the plain value.
 */
export default function SongTable({ rows, label = "Songs", sortState, onSort, busy, renderRating }) {
  return (
    <div className="table-wrap">
      <table aria-label={label} aria-busy={busy ? "true" : "false"} className={busy ? "busy" : ""}>
        <thead>
          <tr>
            {COLUMNS.map((col) => {
              const active = sortState?.sort === col.key;
              return (
                <th key={col.key} scope="col" className={col.numeric ? "num" : ""}
                    aria-sort={onSort && active ? ARIA[sortState.order] : undefined}>
                  {onSort ? (
                    <button type="button" className="sort" onClick={() => onSort(col.key)}>
                      {col.label}
                      <span aria-hidden="true" className="arrow">
                        {active ? (sortState.order === "asc" ? " ▲" : " ▼") : ""}
                      </span>
                    </button>
                  ) : col.label}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((song) => (
            <tr key={song.id}>
              {COLUMNS.map((col) => (
                <td key={col.key} className={col.numeric ? "num" : ""}>
                  {col.key === "rating" && renderRating
                    ? renderRating(song)
                    : <Cell song={song} column={col} />}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
