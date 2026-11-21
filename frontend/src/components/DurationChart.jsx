import { chartPoints, linearScale, niceTicks } from "../lib/chart.js";

const W = 640;
const H = 380;
const M = { top: 20, right: 20, bottom: 48, left: 64 };

const seconds = (ms) => Number((ms / 1000).toFixed(1));

function label(p) {
  const base = `${p.title ?? p.id}: ${seconds(p.y)} s, ${p.x} segments`;
  return p.corrected ? `${base} (stored as ${p.storedAs}, read as seconds)` : base;
}

/**
 * Scatter of duration vs num_segments, with unit-corrected songs highlighted (R-CHART).
 * Corrected points sit on the same trend as the rest, which is the evidence for the fix.
 */
export default function DurationChart({ songs }) {
  const { points, excluded } = chartPoints(songs);
  const corrected = points.filter((p) => p.corrected);
  const normal = points.filter((p) => !p.corrected);

  const maxX = Math.max(0, ...points.map((p) => p.x));
  const maxS = Math.max(0, ...points.map((p) => p.y / 1000));
  const xTicks = niceTicks(0, maxX || 1, 5);
  const yTicks = niceTicks(0, maxS || 1, 5);
  const x = linearScale([0, Math.max(xTicks.at(-1), maxX)], [M.left, W - M.right]);
  const y = linearScale([0, Math.max(yTicks.at(-1), maxS)], [H - M.bottom, M.top]);

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby="chart-title" aria-describedby="chart-desc">
        <title id="chart-title">Duration vs number of segments</title>
        <desc id="chart-desc">
          Each song's duration in seconds against its segment count. The {corrected.length} songs whose
          duration was stored in seconds and corrected to milliseconds fall on the same trend as the others.
        </desc>

        {yTicks.map((t) => (
          <g key={`y${t}`} className="tick">
            <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} className="grid" />
            <text x={M.left - 8} y={y(t)} dy="0.32em" textAnchor="end">{t}</text>
          </g>
        ))}
        {xTicks.map((t) => (
          <g key={`x${t}`} className="tick">
            <line x1={x(t)} x2={x(t)} y1={H - M.bottom} y2={H - M.bottom + 5} className="axis" />
            <text x={x(t)} y={H - M.bottom + 18} textAnchor="middle">{t}</text>
          </g>
        ))}
        <line x1={M.left} x2={W - M.right} y1={H - M.bottom} y2={H - M.bottom} className="axis" />
        <line x1={M.left} x2={M.left} y1={M.top} y2={H - M.bottom} className="axis" />
        <text className="axis-label" x={(M.left + W - M.right) / 2} y={H - 8} textAnchor="middle">
          Segments (num_segments)
        </text>
        <text className="axis-label" transform={`translate(16 ${(M.top + H - M.bottom) / 2}) rotate(-90)`}
              textAnchor="middle">Duration (s)</text>

        {normal.map((p) => (
          <g key={p.id} tabIndex={0} role="img" aria-label={label(p)}>
            <title>{label(p)}</title>
            <circle className="pt" cx={x(p.x)} cy={y(p.y / 1000)} r={5} />
          </g>
        ))}
        {corrected.map((p) => {
          const cx = x(p.x);
          const cy = y(p.y / 1000);
          return (
            <g key={p.id} tabIndex={0} role="img" aria-label={label(p)}>
              <title>{label(p)}</title>
              <path className="pt corrected" d={`M${cx},${cy - 8} L${cx + 8},${cy} L${cx},${cy + 8} L${cx - 8},${cy} Z`} />
            </g>
          );
        })}
      </svg>

      <ul className="legend">
        <li><span className="swatch dot" aria-hidden="true" />Other songs ({normal.length})</li>
        <li><span className="swatch diamond" aria-hidden="true" />Corrected from seconds ({corrected.length})</li>
      </ul>
      <figcaption>
        Duration grows with segment count. The highlighted songs were stored as seconds (e.g. 158), which
        would put them near zero. Read as milliseconds they land on the same line as every other song,
        which is the evidence for the ×1000 fix.
      </figcaption>
      {excluded > 0 && (
        <p className="muted">{excluded} {excluded === 1 ? "song" : "songs"} not plotted (missing values)</p>
      )}
    </figure>
  );
}
