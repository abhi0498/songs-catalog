/** Header-click sort logic (R-SORT-1). Sorting itself is done by the API. */
export const DEFAULT_SORT = { sort: "id", order: "asc" };

export function nextSort(current, column) {
  return current.sort === column
    ? { sort: column, order: current.order === "asc" ? "desc" : "asc" }
    : { sort: column, order: "asc" };
}
