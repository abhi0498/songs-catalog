import { describe, expect, it } from "vitest";
import { reasonText } from "./reasons.js";

describe("reasonText", () => {
  it.each([
    ["out_of_range", "Value out of valid range in the source; rejected"],
    ["source_conflict", "The two source files disagree; neither was chosen"],
    ["missing_absent", "Missing in the source"],
    ["missing_null", "Missing in the source"],
    ["missing_na", "Missing in the source"],
    ["missing_empty", "Missing in the source"],
    ["not_in_source", "This source file has no such field"],
    ["unparseable", "Source value isn't a valid number; rejected"],
    ["not_integer", "Source value isn't a whole number; rejected"],
    ["implausible_duration", "Duration doesn't fit its segment count; rejected"],
  ])("%s", (code, text) => {
    expect(reasonText([code])).toBe(text);
  });

  it("joins several codes and drops repeated texts", () => {
    expect(reasonText(["missing_na", "missing_null"])).toBe("Missing in the source");
    expect(reasonText(["missing_null", "not_in_source"]))
      .toBe("Missing in the source; This source file has no such field");
  });

  it("shows unknown codes raw", () => {
    expect(reasonText(["something_new"])).toBe("something_new");
  });

  it("no codes", () => {
    expect(reasonText([])).toBe("No value");
    expect(reasonText(undefined)).toBe("No value");
  });
});
