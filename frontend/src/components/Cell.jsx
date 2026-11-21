import { reasonText } from "../lib/reasons.js";

/**
 * One table cell. Values are shown exactly as served (U3). A null becomes "—" with the
 * reason from field_flags shown on hover and focus (R-NULL-1/2).
 */
export default function Cell({ song, column }) {
  const value = song[column.key];
  if (value === null || value === undefined) {
    const reason = reasonText(song.field_flags?.[column.key]);
    return (
      <span className="null" tabIndex={0} title={reason} aria-label={`No value: ${reason}`}>—</span>
    );
  }
  return <>{String(value)}</>;
}
