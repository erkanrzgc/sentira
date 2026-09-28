"""Prepare and apply explicit review decisions for synthetic OCR development only."""

import argparse
import hashlib
import json
import tomllib
from pathlib import Path

from experiments.field_review.core import (
    apply_decisions,
    build_packet,
    packet_digest,
    render_report,
)


def _write_json(path, content):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(content, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("packet", "report"):
        command = commands.add_parser(name)
        for option in ("fixtures", "results", "output"):
            command.add_argument(f"--{option}", type=Path, required=True)
        if name == "report":
            command.add_argument("--decisions", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        packet = build_packet(args.fixtures, args.results)
        binding = packet_digest(packet)
        if args.command == "report":
            decision_bytes = args.decisions.read_bytes()
            decisions = tomllib.loads(decision_bytes.decode("utf-8"))
            reviewed = apply_decisions(packet, decisions)
            markdown = render_report(packet, reviewed)
        args.output.mkdir(parents=True, exist_ok=False)
        if args.command == "packet":
            _write_json(args.output / "packet.json", packet)
            with (args.output / "decisions.toml").open("x", encoding="utf-8") as stream:
                stream.write(
                    "# Synthetic development workflow only; no decisions preselected.\n"
                    f'packet_sha256 = "{binding}"\nreviews = []\n'
                )
        else:
            _write_json(
                args.output / "reviewed.json",
                {
                    "synthetic_development_only": True,
                    "packet_sha256": binding,
                    "decisions_sha256": hashlib.sha256(decision_bytes).hexdigest(),
                    "fields": reviewed,
                },
            )
            with (args.output / "report.md").open("x", encoding="utf-8") as stream:
                stream.write(markdown)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Field review refused: {exc}\n")


if __name__ == "__main__":
    main()
