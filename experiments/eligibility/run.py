"""List eligible synthetic field candidates without authoring case events."""

import argparse
import hashlib
import json
import tomllib
from pathlib import Path

from experiments.eligibility.core import evaluate, render_report
from experiments.field_review.core import build_packet


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("fixtures", "results", "decisions", "context", "output"):
        parser.add_argument(f"--{option}", type=Path, required=True)
    parser.add_argument("--cutoff", required=True)
    args = parser.parse_args(argv)
    try:
        packet = build_packet(args.fixtures, args.results)
        decisions_raw, context_raw = args.decisions.read_bytes(), args.context.read_bytes()
        decisions = tomllib.loads(decisions_raw.decode("utf-8"))
        context = tomllib.loads(context_raw.decode("utf-8"))
        result = evaluate(packet, decisions, context, args.cutoff)
        result["input_sha256"] = {
            "registration": packet["registration_sha256"],
            "results": packet["results_sha256"],
            "decisions": hashlib.sha256(decisions_raw).hexdigest(),
            "context": hashlib.sha256(context_raw).hexdigest(),
        }
        markdown = render_report(result)
        serialised = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        args.output.mkdir(parents=True, exist_ok=False)
        with (args.output / "eligibility.json").open("x", encoding="utf-8") as stream:
            stream.write(serialised)
        with (args.output / "report.md").open("x", encoding="utf-8") as stream:
            stream.write(markdown)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Eligibility refused: {exc}\n")


if __name__ == "__main__":
    main()
