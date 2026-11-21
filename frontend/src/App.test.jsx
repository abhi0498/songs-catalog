import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import App from "./App.jsx";
import { installFakeApi, json } from "./test/fakeApi.js";

function songRequests(calls) {
  return calls
    .filter((c) => c.url.pathname === "/songs" && c.url.searchParams.get("size") === "10")
    .map((c) => Object.fromEntries(c.url.searchParams));
}

function bodyRows() {
  const table = screen.getByRole("table", { name: /songs/i });
  return within(table).getAllByRole("row").slice(1);
}

describe("App table", () => {
  it("loads page 1, size 10, sorted by id asc", async () => {
    const { calls } = installFakeApi();
    render(<App />);
    await waitFor(() => expect(bodyRows()).toHaveLength(10));
    expect(songRequests(calls)[0]).toEqual({ page: "1", size: "10", sort: "id", order: "asc" });
    expect(screen.getByText(/Page 1 of 3 · 25 songs/)).toBeInTheDocument();
  });

  it("header click sorts via the API and toggles", async () => {
    const user = userEvent.setup();
    const { calls } = installFakeApi();
    render(<App />);
    await waitFor(() => expect(bodyRows()).toHaveLength(10));

    const tempo = screen.getByRole("button", { name: /^Tempo/ });
    await user.click(tempo);
    await waitFor(() =>
      expect(songRequests(calls).at(-1)).toMatchObject({ sort: "tempo", order: "asc", page: "1" }));
    expect(tempo.closest("th")).toHaveAttribute("aria-sort", "ascending");

    await user.click(tempo);
    await waitFor(() => expect(songRequests(calls).at(-1)).toMatchObject({ order: "desc" }));
    expect(tempo.closest("th")).toHaveAttribute("aria-sort", "descending");
    await waitFor(() => expect(within(bodyRows()[0]).getByText("Song 25")).toBeInTheDocument());
  });

  it("changing sort resets to page 1", async () => {
    const user = userEvent.setup();
    const { calls } = installFakeApi();
    render(<App />);
    await waitFor(() => expect(bodyRows()).toHaveLength(10));
    await user.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => expect(songRequests(calls).at(-1).page).toBe("2"));
    await user.click(screen.getByRole("button", { name: /^Energy/ }));
    await waitFor(() => expect(songRequests(calls).at(-1)).toMatchObject({ page: "1", sort: "energy" }));
  });

  it("prev/next are disabled at the ends", async () => {
    const user = userEvent.setup();
    installFakeApi();
    render(<App />);
    await waitFor(() => expect(bodyRows()).toHaveLength(10));
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next page" }));
    await user.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => expect(bodyRows()).toHaveLength(5));
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });

  it("shows an error with Retry that refetches", async () => {
    const user = userEvent.setup();
    let fail = true;
    installFakeApi(undefined, (url) =>
      (fail && url.pathname === "/songs" && url.searchParams.get("size") === "10")
        ? json(500, { detail: "boom" }) : undefined);
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
    fail = false;
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(bodyRows()).toHaveLength(10));
  });
});
