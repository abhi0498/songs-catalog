import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { makeSong } from "../test/fakeApi.js";
import Cell from "./Cell.jsx";

describe("Cell", () => {
  it("null shows a dash with the reason on hover and focus", () => {
    const song = makeSong(1, { tempo: null, field_flags: { tempo: ["out_of_range"] } });
    render(<Cell song={song} column={{ key: "tempo" }} />);
    const dash = screen.getByText("—");
    expect(dash).toHaveAttribute("title", "Value out of valid range in the source; rejected");
    expect(dash).toHaveAttribute("tabindex", "0");
    expect(dash).toHaveAccessibleName("No value: Value out of valid range in the source; rejected");
  });

  it("values render as served", () => {
    render(<Cell song={makeSong(1, { tempo: 108.73 })} column={{ key: "tempo" }} />);
    expect(screen.getByText("108.73")).toBeInTheDocument();
  });

  it("zero is a value, not a null", () => {
    render(<Cell song={makeSong(1, { mood: 0 })} column={{ key: "mood" }} />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });
});
