"""CLI entry point: python -m pipeline (design §6).

Exit 0 on success with a short summary. Exit 1 on a PipelineError (bad input
structure, missing file, no duration band), with nothing written.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .output import write_outputs
from .run import build
from .schema import PipelineError


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pipeline",
                                     description="Normalize the song exports.")
    parser.add_argument("--data-dir", type=Path, default=Path("../data"))
    parser.add_argument("--out-dir", type=Path, default=Path("../data/normalized"))
    args = parser.parse_args(argv)

    try:
        out = build(args.data_dir)
    except PipelineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    write_outputs(args.out_dir, out.songs, out.issues, out.report)
    print(summary(out.report, args.out_dir))
    return 0


def summary(report: dict, out_dir: Path) -> str:
    rows = sum(i["rows"] for i in report["inputs"])
    lines = [
        f"{rows} source rows -> {report['records']} records ({report['merged']} merged)",
        f"corrections: {report['corrections']}  conflicts: {report['conflicts']}  "
        f"possible duplicate pairs: {report['possible_duplicate_pairs']}",
        "nulls: " + (", ".join(
            f"{field} {sum(c.values())}" for field, c in report["nulls_by_field_and_reason"].items()
        ) or "none"),
        f"wrote {out_dir}/",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
