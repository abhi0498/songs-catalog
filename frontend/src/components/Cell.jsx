/** One table cell, with the value exactly as served (U3). */
export default function Cell({ song, column }) {
  const value = song[column.key];
  if (value === null || value === undefined) return <span className="null">—</span>;
  return <>{String(value)}</>;
}
