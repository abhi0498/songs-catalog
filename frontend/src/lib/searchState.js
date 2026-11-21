/** What the search panel says for each outcome (R-SRCH-2, R-SRCH-4). */
const plural = (n, one, many) => (n === 1 ? one : many);

export function describeSearch(search) {
  const { state, query, result, error } = search;
  switch (state) {
    case "empty":
      return { tone: "muted", message: "Enter a title to search" };
    case "loading":
      return { tone: "muted", message: `Searching for "${query}"…` };
    case "error":
      return {
        tone: "error",
        message: error.status >= 400 && error.status < 500 ? error.message : `Search failed: ${error.message}`,
      };
    case "done": {
      const n = result.items.length;
      if (result.match_type === "exact") {
        return {
          tone: "info",
          message: n === 1 ? `1 song titled "${query}"` : `${n} songs titled "${query}" (titles aren't unique)`,
        };
      }
      if (result.match_type === "partial") {
        return {
          tone: "warn",
          message: `No exact match for "${query}", showing ${n} ${plural(n, "partial match", "partial matches")}`,
        };
      }
      return { tone: "muted", message: `No songs match "${query}"` };
    }
    default:
      return null; // idle
  }
}
