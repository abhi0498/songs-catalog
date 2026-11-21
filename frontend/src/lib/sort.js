/** Header-click sort logic (R-SORT-1). Sorting itself is done by the API. */
// Title A→Z reads naturally. Sorting by id looked random to users.
export const DEFAULT_SORT = { sort: "title", order: "asc" };

export function nextSort(current, column) {
  return current.sort === column
    ? { sort: column, order: current.order === "asc" ? "desc" : "asc" }
    : { sort: column, order: "asc" };
}
