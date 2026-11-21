/** Table / CSV columns, left to right (R-TBL-2). Keys match the API's sortable columns. */
export const COLUMNS = [
  { key: "title", label: "Title", numeric: false },
  { key: "danceability", label: "Danceability", numeric: true },
  { key: "energy", label: "Energy", numeric: true },
  { key: "acousticness", label: "Acousticness", numeric: true },
  { key: "valence", label: "Valence", numeric: true },
  { key: "tempo", label: "Tempo", numeric: true },
  { key: "duration_ms", label: "Duration (ms)", numeric: true },
  { key: "num_sections", label: "Sections", numeric: true },
  { key: "num_segments", label: "Segments", numeric: true },
  { key: "mood", label: "Mood", numeric: true },
  { key: "rating", label: "Rating", numeric: true },
  // id is left out on purpose: it's the key in the data and API, but meaningless to a user.
];
