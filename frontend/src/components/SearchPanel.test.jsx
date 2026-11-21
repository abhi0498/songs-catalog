import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import App from "../App.jsx";
import { installFakeApi, json, makeSong } from "../test/fakeApi.js";

const SONGS = [
  makeSong(1, { id: "p1", title: "Perfect" }),
  makeSong(2, { id: "p2", title: "Perfect" }),
  makeSong(3, { id: "g1", title: "21 Guns", tempo: null, field_flags: { tempo: ["out_of_range"] } }),
  makeSong(4, { id: "t1", title: "21" }),
];

function searchCalls(calls) {
  return calls.filter((c) => c.url.pathname === "/songs/search");
}

async function setup(overrides) {
  const user = userEvent.setup();
  const api = installFakeApi(SONGS.map((s) => ({ ...s })), overrides);
  render(<App />);
  await screen.findByRole("table", { name: "Songs" });
  return { user, ...api };
}

describe("search panel", () => {
  it("Get Song button searches and shows every exact match", async () => {
    const { user, calls } = await setup();
    await user.type(screen.getByLabelText("Search by title"), "Perfect");
    await user.click(screen.getByRole("button", { name: "Get Song" }));
    expect(await screen.findByText('2 songs titled "Perfect" (titles aren\'t unique)')).toBeInTheDocument();
    const results = screen.getByRole("table", { name: "Search results" });
    expect(within(results).getAllByRole("row")).toHaveLength(3);
    expect(searchCalls(calls)[0].url.searchParams.get("title")).toBe("Perfect");
  });

  it("Enter also searches; partial matches are labelled", async () => {
    const { user } = await setup();
    await user.type(screen.getByLabelText("Search by title"), "gun{Enter}");
    expect(await screen.findByText('No exact match for "gun", showing 1 partial match')).toBeInTheDocument();
    const results = screen.getByRole("table", { name: "Search results" });
    expect(within(results).getByTitle("Value out of valid range in the source; rejected"))
      .toHaveTextContent("—");
  });

  it("result headers are not sort buttons", async () => {
    const { user } = await setup();
    await user.type(screen.getByLabelText("Search by title"), "21{Enter}");
    const results = await screen.findByRole("table", { name: "Search results" });
    expect(within(results).queryAllByRole("button", { name: /^Tempo/ })).toHaveLength(0);
    expect(screen.getByText('1 song titled "21"')).toBeInTheDocument();
  });

  it("no match", async () => {
    const { user } = await setup();
    await user.type(screen.getByLabelText("Search by title"), "zzz{Enter}");
    expect(await screen.findByText('No songs match "zzz"')).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Search results" })).not.toBeInTheDocument();
  });

  it("empty query doesn't call the API", async () => {
    const { user, calls } = await setup();
    await user.type(screen.getByLabelText("Search by title"), "   ");
    await user.click(screen.getByRole("button", { name: "Get Song" }));
    expect(screen.getByText("Enter a title to search")).toBeInTheDocument();
    expect(searchCalls(calls)).toHaveLength(0);
  });

  it("422 shows the API's message", async () => {
    const { user } = await setup((url) =>
      url.pathname === "/songs/search"
        ? json(422, { detail: [{ msg: "title must contain at least one letter or digit" }] }) : undefined);
    await user.type(screen.getByLabelText("Search by title"), "!!!{Enter}");
    expect(await screen.findByText("title must contain at least one letter or digit")).toBeInTheDocument();
  });

  it("button reads Searching… while pending, and Clear hides the panel", async () => {
    let release;
    const gate = new Promise((r) => { release = r; });
    const { user } = await setup(async (url) => {
      if (url.pathname === "/songs/search") { await gate; }
      return undefined;
    });
    await user.type(screen.getByLabelText("Search by title"), "Perfect{Enter}");
    expect(screen.getByRole("button", { name: "Searching…" })).toBeDisabled();
    release();
    await screen.findByRole("table", { name: "Search results" });
    await user.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.queryByRole("table", { name: "Search results" })).not.toBeInTheDocument();
    expect(screen.queryByRole("status")).toBeEmptyDOMElement();
    await waitFor(() => expect(screen.getByLabelText("Search by title")).toHaveValue(""));
  });
});
