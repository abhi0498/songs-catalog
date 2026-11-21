/** Data prep and scales for the duration vs segments scatter (R-CHART-1..4). */
export const CORRECTED = "unit_corrected_s_to_ms";

export function chartPoints(songs) {
  const points = [];
  let excluded = 0;
  for (const s of songs) {
    if (s.duration_ms === null || s.duration_ms === undefined
        || s.num_segments === null || s.num_segments === undefined) {
      excluded += 1;
      continue;
    }
    const corrected = (s.field_flags?.duration_ms ?? []).includes(CORRECTED);
    points.push({
      id: s.id,
      title: s.title,
      x: s.num_segments,
      y: s.duration_ms,
      corrected,
      // The pipeline's only duration fix is ×1000 (data D4), so this is exact.
      storedAs: corrected ? s.duration_ms / 1000 : null,
    });
  }
  return { points, excluded };
}

export function linearScale([d0, d1], [r0, r1]) {
  if (d0 === d1) return () => (r0 + r1) / 2;
  return (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
}

function niceStep(raw) {
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const nice = norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10;
  return nice * mag;
}

/** Round tick values from min to max (inclusive where they land on max). */
export function niceTicks(min, max, count = 5) {
  if (max <= min) return [min];
  const step = niceStep((max - min) / count);
  const ticks = [];
  for (let i = Math.ceil(min / step); i * step <= max + step * 1e-9; i += 1) {
    ticks.push(Number((i * step).toFixed(10)));
  }
  return ticks;
}
