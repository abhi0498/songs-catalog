import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DurationChart from "./DurationChart.jsx";

const REAL = JSON.parse(readFileSync(resolve(process.cwd(), "../data/normalized/songs.json"), "utf-8"));

describe("DurationChart", () => {
  it("draws 22 circles and 3 highlighted diamonds with a legend", () => {
    const { container } = render(<DurationChart songs={REAL} />);
    expect(container.querySelectorAll("circle.pt")).toHaveLength(22);
    expect(container.querySelectorAll("path.pt.corrected")).toHaveLength(3);
    expect(screen.getByText("Corrected from seconds (3)")).toBeInTheDocument();
    expect(screen.getByText("Other songs (22)")).toBeInTheDocument();
    expect(screen.queryByText(/not plotted/)).not.toBeInTheDocument();
  });

  it("corrected points say what was stored", () => {
    render(<DurationChart songs={REAL} />);
    expect(screen.getByRole("img", { name: /^Sunflower:/ }))
      .toHaveAccessibleName("Sunflower: 158 s, 560 segments (stored as 158, read as seconds)");
  });

  it("has an accessible title and description", () => {
    render(<DurationChart songs={REAL} />);
    const svg = screen.getByRole("img", { name: "Duration vs number of segments" });
    expect(svg).toHaveAccessibleDescription(/same trend/);
  });

  it("notes songs it couldn't plot", () => {
    const songs = [...REAL.slice(0, 3), { ...REAL[3], num_segments: null }];
    render(<DurationChart songs={songs} />);
    expect(screen.getByText("1 song not plotted (missing values)")).toBeInTheDocument();
  });
});
