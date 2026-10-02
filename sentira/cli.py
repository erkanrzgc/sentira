"""Explicit offline simulation; no credentials, network calls or model loading."""

import argparse
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from sentira.backtest.positives import count_grid, render_count, select_cell
from sentira.backtest.registration import load_locked
from sentira.config.briefing import load_config
from sentira.config.cases import load_cases
from sentira.core.document import utc
from sentira.core.evidence import load_evidence
from sentira.report.briefing import render_briefing
from sentira.report.cases import render_cases
from sentira.series.synthetic import load_series
from sentira.storage.evidence import EvidenceLedger


def write_report(path, content, *, overwrite):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects existing operator output, including a race.
    if not overwrite:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        return
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as stream:
            name = stream.name
            stream.write(content)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    briefing = commands.add_parser("briefing", help="Render a fictional, offline briefing")
    for option in ("config", "evidence", "observed-at", "cutoff", "issued-at", "output"):
        briefing.add_argument(f"--{option}", required=True)
    briefing.add_argument("--overwrite", action="store_true")
    cases = commands.add_parser("case-report", help="Render fictional procedural evidence")
    for option in ("input", "cutoff", "issued-at", "output"):
        cases.add_argument(f"--{option}", required=True)
    cases.add_argument("--overwrite", action="store_true")
    counting = commands.add_parser("count", help="Count surges in a fictional series")
    for option in ("registration", "measured", "lock", "series", "output"):
        counting.add_argument(f"--{option}", required=True)
    counting.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "case-report":
        return case_report(args)
    if args.command == "count":
        return count(args)
    try:
        directory, evidence_path = Path(args.config).resolve(), Path(args.evidence).resolve()
        output = Path(args.output).resolve()
        inputs = {
            evidence_path,
            *(
                (directory / f"{name}.toml").resolve()
                for name in ("domains", "sources", "questions", "reporting")
            ),
        }
        if output in inputs or output.suffix != ".md":
            raise ValueError("Output must be a separate Markdown file")
        observed = utc(datetime.fromisoformat(args.observed_at))
        cutoff = utc(datetime.fromisoformat(args.cutoff))
        issued = utc(datetime.fromisoformat(args.issued_at))
        config, records = load_config(directory), load_evidence(evidence_path)
        with EvidenceLedger(":memory:", clock=lambda: observed) as ledger:
            ledger.ingest(config, records)
            content = render_briefing(config, ledger.view(config, cutoff), issued_at=issued)
        write_report(output, content, overwrite=args.overwrite)
    except (ValueError, OSError):
        print(
            "Briefing failed: check input contracts, timestamps and output destination. "
            "Existing output requires --overwrite.",
            file=sys.stderr,
        )
        return 1
    print("Synthetic briefing written.")
    return 0


def case_report(args):
    try:
        source, output = Path(args.input).resolve(), Path(args.output).resolve()
        if source == output or output.suffix != ".md":
            raise ValueError("Output must be a separate Markdown file")
        snapshot = load_cases(source)
        content = render_cases(
            snapshot,
            cutoff=utc(datetime.fromisoformat(args.cutoff)),
            issued_at=utc(datetime.fromisoformat(args.issued_at)),
        )
        write_report(output, content, overwrite=args.overwrite)
    except (ValueError, OSError):
        print(
            "Case report failed: check input contracts, timestamps and output destination. "
            "Existing output requires --overwrite.",
            file=sys.stderr,
        )
        return 1
    print("Synthetic case report written.")
    return 0


def count(args):
    try:
        inputs = [
            Path(getattr(args, name)).resolve()
            for name in ("registration", "measured", "lock", "series")
        ]
        output = Path(args.output).resolve()
        if output in inputs or output.suffix != ".md":
            raise ValueError("Output must be a separate Markdown file")
        # The lock is verified before any series is read or counted.
        locked = load_locked(*inputs[:3])
        series = load_series(inputs[3])
        counts = count_grid(series.topics, locked, start=series.start, end=series.end)
        content = render_count(locked, series, counts, select_cell(counts, locked))
        write_report(output, content, overwrite=args.overwrite)
    except (ValueError, OSError, ArithmeticError):
        print(
            "Count refused: check the registration lock, series input and output destination. "
            "Existing output requires --overwrite.",
            file=sys.stderr,
        )
        return 1
    print("Synthetic count report written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
