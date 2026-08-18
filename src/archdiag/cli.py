from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from archdiag.llm import NullProposer
from archdiag.pipeline import interpret_notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate an architecture diagram from unstructured technical notes."
    )
    parser.add_argument("notes_path", nargs="?", help="Path to a notes text file")
    parser.add_argument("--text", help="Raw notes instead of a file")
    parser.add_argument("--svg", help="Write the SVG diagram to this path")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Force catalog-only extraction (ignore ARCHDIAG_LLM_PROVIDER).",
    )
    args = parser.parse_args(argv)

    if args.text:
        notes = args.text
    elif args.notes_path:
        notes = Path(args.notes_path).read_text(encoding="utf-8")
    else:
        parser.error("Provide a notes file or --text")

    proposer = NullProposer() if args.no_llm else None
    model = interpret_notes(notes, proposer=proposer)
    if args.svg:
        Path(args.svg).write_text(model.svg, encoding="utf-8")

    dump = model.model_dump()
    dump.pop("svg", None)
    dump["svg_written"] = args.svg
    json.dump(dump, sys.stdout, indent=2 if args.pretty else None, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
