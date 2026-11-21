/** Plain-English text for the pipeline's reason codes (R-NULL-2). */
const MISSING = "Missing in the source";

export const REASON_TEXT = {
  out_of_range: "Value out of valid range in the source; rejected",
  source_conflict: "The two source files disagree; neither was chosen",
  missing_absent: MISSING,
  missing_null: MISSING,
  missing_na: MISSING,
  missing_empty: MISSING,
  not_in_source: "This source file has no such field",
  unparseable: "Source value isn't a valid number; rejected",
  not_integer: "Source value isn't a whole number; rejected",
  implausible_duration: "Duration doesn't fit its segment count; rejected",
};

export function reasonText(codes = []) {
  if (!codes || codes.length === 0) return "No value";
  const texts = codes.map((c) => REASON_TEXT[c] ?? c);
  return [...new Set(texts)].join("; ");
}
