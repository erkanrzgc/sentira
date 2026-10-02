"""Explicit, local-only synthetic OCR experiment; not a Sentira ingestion path."""

import argparse
import base64
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path
from time import perf_counter


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def verify_external(registration):
    for name, expected in registration["external_files"].items():
        path = Path(name)
        if not path.is_file() or digest(path) != expected:
            raise ValueError("Registered dependency changed or is unavailable")


def verify_versions(registration):
    if platform.python_version() != registration["python_version"]:
        raise ValueError("Registered Python version changed")
    for name, expected in registration["libraries"].items():
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise ValueError("Registered library version unavailable") from exc
        if actual != expected:
            raise ValueError("Registered library version changed")


def verify_code(registration):
    current = {p.name: digest(p) for p in Path(__file__).parent.glob("*.py")}
    if registration.get("code_files") != current:
        raise ValueError("Running experiment code does not match registration")


def _text(value):
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""


def _encoded(value):
    raw = value if isinstance(value, bytes) else (value or "").encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def recognise(image, engine, data, language, timeout, psm, oem):
    result = {"raw_text": "", "stderr": "", "elapsed_seconds": None}
    if not (Path(data) / f"{language}.traineddata").is_file():
        return result | {"status": "not_run_missing_recognition_data"}
    command = [
        str(engine),
        str(image),
        "stdout",
        "--tessdata-dir",
        str(data),
        "-l",
        language,
        "--oem",
        str(oem),
        "--psm",
        str(psm),
    ]
    start = perf_counter()
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        result.update(
            status="ok" if process.returncode == 0 else "engine_error",
            raw_text=_text(process.stdout),
            stderr=_text(process.stderr),
            raw_stdout_base64=_encoded(process.stdout),
            raw_stderr_base64=_encoded(process.stderr),
            returncode=process.returncode,
        )
        if isinstance(process.stdout, bytes):
            try:
                result["raw_text"] = process.stdout.decode("utf-8")
            except UnicodeDecodeError:
                result["raw_text"] = ""
                if process.returncode == 0:
                    result["status"] = "unreadable_output"
    except subprocess.TimeoutExpired as exc:
        result.update(
            status="timeout",
            raw_text=_text(exc.stdout),
            stderr=_text(exc.stderr),
            raw_stdout_base64=_encoded(exc.stdout),
            raw_stderr_base64=_encoded(exc.stderr),
        )
    except OSError as exc:
        result.update(status="engine_unavailable", stderr=type(exc).__name__)
    result["elapsed_seconds"] = perf_counter() - start
    return result


def pdf_text(path):
    from pypdf import PdfReader

    start = perf_counter()
    try:
        pages = PdfReader(path).pages
        if len(pages) != 1:
            raise ValueError("Experiment requires one page per fixture")
        text = pages[0].extract_text()
        return {"status": "ok", "raw_text": text, "elapsed_seconds": perf_counter() - start}
    except Exception as exc:
        return {
            "status": "extraction_error",
            "raw_text": "",
            "error": type(exc).__name__,
            "elapsed_seconds": perf_counter() - start,
        }


def compare(directory, output):
    from experiments.ocr.scoring import (
        baseline_predictions,
        extract_fields,
        score_fields,
        verify_lock,
    )

    directory, output = Path(directory).resolve(), Path(output).resolve()
    registration = verify_lock(directory)
    verify_external(registration)
    verify_versions(registration)
    verify_code(registration)
    try:
        review = json.loads((directory / "visual-review.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Visual review record is missing or invalid") from exc
    if review != {
        "all_eight_pages_inspected": True,
        "registration_sha256": digest(directory / "registration.json"),
    }:
        raise ValueError("Visual review does not match registration")
    output.mkdir(parents=True, exist_ok=False)
    settings = registration["config"]
    labels = settings["labels"]
    baseline = baseline_predictions(settings["families"], list(labels), settings["seed"])
    families = {family["id"]: family for family in settings["families"]}
    results = []
    for page in registration["pages"]:
        family = families[page["family"]]
        for method in ("pdf_text", "ocr"):
            if method == "pdf_text":
                result = pdf_text(directory / page["pdf"])
            else:
                result = recognise(
                    directory / page["png"],
                    registration["engine"],
                    registration["data"],
                    registration["language"],
                    settings["timeout"],
                    settings["psm"],
                    settings["oem"],
                )
            raw_file = f"{page['id']}-{method}.txt"
            (output / raw_file).write_text(result["raw_text"], encoding="utf-8")
            # Failed/partial recognition is never treated as a successful prediction.
            fields = extract_fields(result["raw_text"] if result["status"] == "ok" else "", labels)
            results.append(
                {
                    "page": page["id"],
                    "family": page["family"],
                    "representation": page["representation"],
                    "method": method,
                    **result,
                    "raw_file": raw_file,
                    "fields": score_fields(family["fields"], fields),
                    "baselines": baseline[page["family"]],
                }
            )
    report = {
        "registration_sha256": digest(directory / "registration.json"),
        "synthetic_development_only": True,
        "human_review_seconds": None,
        "results": results,
    }
    write_json(output / "results.json", report)
    (output / "results.md").write_text(render_report(report), encoding="utf-8")
    return report


def render_report(report):
    lines = [
        "# Synthetic OCR development comparison",
        "",
        "Counts are calculated from retained local outputs. Process times are measured.",
        "Four authored families; paired representations are not independent samples.",
        "No human timing, target-corpus accuracy or forecasting claim is established.",
        "",
        "| Method | Representation | Exact fields | Majority | Seeded random |",
        "| --- | --- | --- | --- | --- |",
    ]
    for method in ("pdf_text", "ocr"):
        for representation in ("text", "image"):
            rows = [
                r
                for r in report["results"]
                if r["method"] == method and r["representation"] == representation
            ]
            total = sum(len(r["fields"]) for r in rows)
            correct = sum(f["match"] for r in rows for f in r["fields"].values())
            counts = {
                b: sum(
                    r["baselines"][b][name] == field["expected"]
                    for r in rows
                    for name, field in r["fields"].items()
                )
                for b in ("majority", "random")
            }
            lines.append(
                f"| {method} | {representation} | {correct}/{total} | "
                f"{counts['majority']}/{total} | {counts['random']}/{total} |"
            )
    lines += [
        "",
        "Baselines use the authored development inventory; lexical majority ties",
        "and seeded hash selection are fixed before comparison.",
        "",
        "## Page outcomes",
        "",
        "| Page | Method | Status | Exact fields | Seconds |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report["results"]:
        correct = sum(f["match"] for f in row["fields"].values())
        seconds = row["elapsed_seconds"]
        timing = "not run" if seconds is None else f"{seconds:.4f}"
        lines.append(
            f"| {row['page']} | {row['method']} | {row['status']} | "
            f"{correct}/{len(row['fields'])} | {timing} |"
        )
    lines += [
        "",
        "Per-field expected/actual values, missing or ambiguous results and raw",
        "outputs are retained in results.json. Failed pages remain in denominators.",
        "",
    ]
    return "\n".join(lines)


def lock(directory, reviewed):
    from experiments.ocr.scoring import _registered_path, verify_lock

    directory = Path(directory)
    if not reviewed:
        raise ValueError("Visual inspection acknowledgement required")
    registration = json.loads((directory / "registration.json").read_text(encoding="utf-8"))
    verify_external(registration)
    # Check every registered name before writing the lock, so a rejected
    # registration never leaves a half-locked directory behind.
    root = directory.resolve()
    for name, expected in registration["files"].items():
        if digest(_registered_path(root, name)) != expected:
            raise ValueError("Fixture changed before locking")
    with (directory / "registration.sha256").open("x", encoding="ascii") as stream:
        stream.write(digest(directory / "registration.json") + "\n")
    verify_lock(directory)
    write_json(
        directory / "visual-review.json",
        {
            "all_eight_pages_inspected": True,
            "registration_sha256": digest(directory / "registration.json"),
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    for name in ("config", "font", "poppler", "engine", "data", "language", "output"):
        prepare.add_argument(f"--{name}", required=True)
    freezing = commands.add_parser("lock")
    freezing.add_argument("--directory", required=True)
    freezing.add_argument("--reviewed-all-pages", action="store_true")
    running = commands.add_parser("compare")
    running.add_argument("--directory", required=True)
    running.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            from experiments.ocr.fixtures import prepare

            prepare(args)
        elif args.command == "lock":
            lock(args.directory, args.reviewed_all_pages)
        else:
            compare(args.directory, args.output)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"Experiment refused: {exc}\n")


if __name__ == "__main__":
    main()
