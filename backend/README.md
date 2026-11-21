# Backend

## Data pipeline

Normalizes `data/songs_part1.json` and `data/songs_part2.json` into a clean
dataset. Spec: [`specs/data/`](../specs/data/) (requirements, design, tasks).

Requires Python ≥ 3.11, standard library only. Run it from this folder:

```bash
python -m pipeline
```

Options: `--data-dir` (default `../data`), `--out-dir` (default `../data/normalized`).

It writes three files to `data/normalized/`:

| File | Contents |
|---|---|
| `songs.json` | One record per unique id, sorted by id. Rejected values are `null`. `field_flags` says why each field ended up as it did, `flags` is the union, `sources` lists the file and row each record came from. |
| `issues.json` | Every finding: id, field, source, raw value, final value, reason code, severity, detail. |
| `report.json` | Input hashes, the duration band, and counts by field, reason and severity. |

Rules in short: values are never invented or clamped, bad values become `null`
with a reason code, conflicts between files become `null` (neither file wins),
and a duration is only fixed (seconds → ms) when its `num_segments` backs it up.
The same input always gives byte-identical output, and the generated files are
committed. Rerun the command after changing the inputs or the rules.

Exit code 0 on success, 1 on a structural problem with the inputs (the message
names the file and column). Nothing is written in that case.

## Tests

```bash
pip install pytest   # only dev dependency
python -m pytest
```
