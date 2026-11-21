import { useState } from "react";
import { rateSong } from "../lib/api.js";

const STARS = [1, 2, 3, 4, 5];
const RETRY = "Couldn't save rating. Try again.";

/**
 * Five star buttons that write to the API (R-RATE-1..4). The shown rating only changes
 * when the API confirms it. On failure the old rating stays and an inline error appears.
 */
export default function StarRating({ song, onRated }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  const rating = song.rating ?? 0;

  const rate = async (stars) => {
    setPending(true);
    try {
      const updated = await rateSong(song.id, stars);
      setError(null);
      onRated(updated);
    } catch (err) {
      setError(err.status >= 400 && err.status < 500 ? err.message : RETRY);
    } finally {
      setPending(false);
    }
  };

  return (
    <span className="stars">
      <span role="group" aria-label={`Rating for ${song.title ?? song.id}`}>
        {STARS.map((n) => (
          <button key={n} type="button" className={n <= rating ? "star on" : "star"}
                  aria-label={`Rate ${n} of 5`} aria-pressed={n <= rating}
                  disabled={pending} onClick={() => rate(n)}>
            {n <= rating ? "★" : "☆"}
          </button>
        ))}
      </span>
      {error && <span role="alert" className="rating-error">{error}</span>}
    </span>
  );
}
