"""Explicit offline simulation; no credentials, network calls or model loading."""

import argparse
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from sentira.backtest.measurement import measure, render_measured
from sentira.backtest.pilot import write_pilot_lock
from sentira.backtest.positives import count_series, render_count, select_cell
from sentira.backtest.registration import (
    load_locked,
    load_measured,
    load_registration,
    write_lock,
)
from sentira.collectors.cost import project, render_cost
from sentira.config.briefing import load_config
from sentira.config.cases import load_cases
from sentira.config.collection import load_collection_policy
from sentira.config.quota import load_quota_policy
from sentira.config.volume import load_volume
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
    measuring = commands.add_parser("measure", help="Compute the measured addendum once")
    for option in ("registration", "series", "output"):
        measuring.add_argument(f"--{option}", required=True)
    locking = commands.add_parser("lock", help="Lock a registration and measured addendum")
    for option in ("registration", "measured", "series", "output"):
        locking.add_argument(f"--{option}", required=True)
    costing = commands.add_parser("cost", help="Project the quota cost of a policy")
    for option in ("policy", "quota", "volume", "output"):
        costing.add_argument(f"--{option}", required=True)
    costing.add_argument("--overwrite", action="store_true")
    piloting = commands.add_parser("lock-pilot", help="Lock a pilot registration once")
    for option in ("pilot", "policy", "quota", "volume", "locked-at", "output"):
        piloting.add_argument(f"--{option}", required=True)
    args = parser.parse_args(argv)
    if args.command == "lock-pilot":
        return lock_pilot(args)
    if args.command == "cost":
        return cost(args)
    if args.command == "measure":
        return measure_addendum(args)
    if args.command == "lock":
        return lock_registration(args)
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


def refused(action):
    print(
        f"{action} refused: check the registration, series and output destination. "
        "Existing measured addenda and locks are never replaced.",
        file=sys.stderr,
    )
    return 1


def measure_addendum(args):
    try:
        registration, source = Path(args.registration).resolve(), Path(args.series).resolve()
        output = Path(args.output).resolve()
        if output in (registration, source) or output.suffix != ".toml":
            raise ValueError("Output must be a separate TOML file")
        content = render_measured(measure(load_series(source), load_registration(registration)))
        # Exclusive creation: an addendum is computed once and then locked.
        write_report(output, content, overwrite=False)
    except (ValueError, OSError, ArithmeticError):
        return refused("Measurement")
    print("Synthetic measured addendum written.")
    return 0


def lock_registration(args):
    try:
        registration, measured = Path(args.registration).resolve(), Path(args.measured).resolve()
        source, output = Path(args.series).resolve(), Path(args.output).resolve()
        if output in (registration, measured, source):
            raise ValueError("Output must be a separate lock file")
        # A lock certifies an addendum computed from a complete pre-origin span.
        expected = measure(load_series(source), load_registration(registration))
        if expected != load_measured(measured):
            raise ValueError("The measured addendum does not reproduce from the series")
        write_lock(registration, measured, output)
    except (ValueError, OSError, ArithmeticError):
        return refused("Lock")
    print("Synthetic registration lock written.")
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
        counts = count_series(series, locked)
        content = render_count(locked, series, counts, select_cell(counts.test, locked))
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


def cost(args):
    try:
        inputs = [Path(getattr(args, name)).resolve() for name in ("policy", "quota", "volume")]
        output = Path(args.output).resolve()
        if output in inputs or output.suffix != ".md":
            raise ValueError("Output must be a separate Markdown file")
        projection = project(
            load_collection_policy(inputs[0]), load_quota_policy(inputs[1]), load_volume(inputs[2])
        )
        write_report(output, render_cost(projection), overwrite=args.overwrite)
    except (ValueError, OSError, ArithmeticError):
        print(
            "Cost projection refused: check the policy, quota and volume inputs and the output "
            "destination. Existing output requires --overwrite.",
            file=sys.stderr,
        )
        return 1
    print("Synthetic cost projection written.")
    return 0


def lock_pilot(args):
    try:
        names = ("pilot", "policy", "quota", "volume")
        inputs = [Path(getattr(args, name)).resolve() for name in names]
        output = Path(args.output).resolve()
        if output in inputs:
            raise ValueError("Output must be a separate lock file")
        locked_at = utc(datetime.fromisoformat(args.locked_at))
        write_pilot_lock(*inputs, output, locked_at=locked_at)
    except (ValueError, OSError, ArithmeticError):
        return refused("Pilot lock")
    print("Synthetic pilot lock written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
