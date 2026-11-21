import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import App from "../App.jsx";
import { installFakeApi, json, makeSong } from "../test/fakeApi.js";

function rowOf(tableName, title) {
  const table = screen.getByRole("table", { name: tableName });
  return within(table).getByText(title).closest("tr");
}

function pressed(row) {
  return within(row).getAllByRole("button", { name: /^Rate \d of 5$/ })
    .map((b) => b.getAttribute("aria-pressed") === "true");
}

async function setup(overrides) {
  const user = userEvent.setup();
  const songs = [makeSong(1, { title: "Alpha", rating: 3 }), makeSong(2, { title: "Beta" })];
  const api = installFakeApi(songs, overrides);
  render(<App />);
  await screen.findByRole("table", { name: "Songs" });
  return { user, ...api };
}

const puts = (calls) => calls.filter((c) => c.method === "PUT");

describe("star rating", () => {
  it("shows the current rating and unrated as empty", async () => {
    await setup();
    expect(pressed(rowOf("Songs", "Alpha"))).toEqual([true, true, true, false, false]);
    expect(pressed(rowOf("Songs", "Beta"))).toEqual([false, false, false, false, false]);
  });

  it("click sends PUT {stars} and disables the stars while pending", async () => {
    let release;
    const gate = new Promise((r) => { release = r; });
    const { user, calls } = await setup(async (url, init) => {
      if (init.method === "PUT") await gate;
      return undefined;
    });
    const row = rowOf("Songs", "Beta");
    await user.click(within(row).getByRole("button", { name: "Rate 4 of 5" }));
    expect(puts(calls)[0].url.pathname).toBe("/songs/s02/rating");
    expect(puts(calls)[0].body).toEqual({ stars: 4 });
    within(row).getAllByRole("button", { name: /^Rate/ }).forEach((b) => expect(b).toBeDisabled());
    release();
    await waitFor(() => expect(pressed(rowOf("Songs", "Beta"))).toEqual([true, true, true, true, false]));
    within(rowOf("Songs", "Beta")).getAllByRole("button", { name: /^Rate/ })
      .forEach((b) => expect(b).toBeEnabled());
  });

  it("success updates the same song in the search results too", async () => {
    const { user } = await setup();
    await user.type(screen.getByLabelText("Search by title"), "Alpha{Enter}");
    await screen.findByRole("table", { name: "Search results" });
    await user.click(within(rowOf("Search results", "Alpha")).getByRole("button", { name: "Rate 5 of 5" }));
    await waitFor(() => expect(pressed(rowOf("Songs", "Alpha"))).toEqual([true, true, true, true, true]));
    expect(pressed(rowOf("Search results", "Alpha"))).toEqual([true, true, true, true, true]);
  });

  it("a 500 keeps the old rating and shows a retry message", async () => {
    const { user } = await setup((url, init) =>
      init.method === "PUT" ? json(500, { detail: "db down" }) : undefined);
    const row = rowOf("Songs", "Alpha");
    await user.click(within(row).getByRole("button", { name: "Rate 1 of 5" }));
    expect(await within(row).findByRole("alert")).toHaveTextContent("Couldn't save rating. Try again.");
    expect(pressed(row)).toEqual([true, true, true, false, false]);
  });

  it("a network error shows the same retry message", async () => {
    const { user } = await setup((url, init) => {
      if (init.method === "PUT") throw new TypeError("Failed to fetch");
      return undefined;
    });
    const row = rowOf("Songs", "Alpha");
    await user.click(within(row).getByRole("button", { name: "Rate 2 of 5" }));
    expect(await within(row).findByRole("alert")).toHaveTextContent("Couldn't save rating. Try again.");
  });

  it("a 422 shows the API's detail, and a later success clears it", async () => {
    let fail = true;
    const { user } = await setup((url, init) =>
      fail && init.method === "PUT" ? json(422, { detail: [{ msg: "Input should be a valid integer" }] }) : undefined);
    const row = rowOf("Songs", "Beta");
    await user.click(within(row).getByRole("button", { name: "Rate 2 of 5" }));
    expect(await within(row).findByRole("alert")).toHaveTextContent("Input should be a valid integer");
    fail = false;
    await user.click(within(row).getByRole("button", { name: "Rate 2 of 5" }));
    await waitFor(() => expect(within(rowOf("Songs", "Beta")).queryByRole("alert")).not.toBeInTheDocument());
    expect(pressed(rowOf("Songs", "Beta"))).toEqual([true, true, false, false, false]);
  });
});
