"""Author original synthetic PDF pairs for an explicitly invoked local experiment."""

import importlib.metadata
import platform
import re
import shutil
import subprocess
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from experiments.ocr.run import digest, pdf_text, write_json


def _line(value):
    if not isinstance(value, str) or not value or len(value) > 65:
        raise ValueError("Fixture text must be a short nonempty line")
    if any(ord(char) < 32 for char in value) or value != value.strip():
        raise ValueError("Fixture text must not contain controls or outer whitespace")


def validate_config(config):
    keys = {
        "synthetic",
        "seed",
        "title",
        "footer",
        "dpi",
        "font_size",
        "timeout",
        "psm",
        "oem",
        "labels",
        "families",
    }
    fields = {"decision", "date", "scale", "duration"}
    if not isinstance(config, dict) or set(config) != keys or config["synthetic"] is not True:
        raise ValueError("Original synthetic fixture configuration required")
    for key, low, high in (
        ("dpi", 72, 300),
        ("font_size", 10, 24),
        ("timeout", 1, 60),
        ("psm", 6, 6),
        ("oem", 1, 1),
        ("seed", 0, 2**32 - 1),
    ):
        if type(config[key]) is not int or not low <= config[key] <= high:
            raise ValueError(f"Invalid bounded setting: {key}")
    for key in ("title", "footer"):
        _line(config[key])
    if not isinstance(config["labels"], dict) or set(config["labels"]) != fields:
        raise ValueError("Exactly four registered field labels required")
    for label in config["labels"].values():
        _line(label)
        if ":" in label:
            raise ValueError("Field labels cannot contain separators")
    if len(set(config["labels"].values())) != 4:
        raise ValueError("Field labels must be distinct")
    families = config["families"]
    if not isinstance(families, list) or len(families) != 4:
        raise ValueError("Exactly four synthetic development families required")
    seen = set()
    for family in families:
        if not isinstance(family, dict) or set(family) != {"id", "institution", "fields"}:
            raise ValueError("Invalid fixture family")
        name = family["id"]
        if not isinstance(name, str) or not re.fullmatch(r"fixture-[a-z0-9-]{1,24}", name):
            raise ValueError("Invalid fixture identifier")
        if name in seen:
            raise ValueError("Duplicate fixture identifier")
        seen.add(name)
        _line(family["institution"])
        if not isinstance(family["fields"], dict) or set(family["fields"]) != fields:
            raise ValueError("Exactly four expected fields required")
        for value in family["fields"].values():
            _line(value)


def _render(poppler, pdf, png, dpi):
    subprocess.run(
        [str(poppler), "-r", str(dpi), "-singlefile", "-png", str(pdf), str(png.with_suffix(""))],
        capture_output=True,
        check=True,
        timeout=30,
    )


def prepare(args):
    # Optional authoring dependencies never enter the installed application path.
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen.canvas import Canvas

    config_path = Path(args.config).resolve()
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    validate_config(config)
    if not re.fullmatch(r"[a-z_]{2,20}", args.language) or args.language == "osd":
        raise ValueError("One explicit text-recognition language is required")
    paths = {key: Path(getattr(args, key)).resolve() for key in ("font", "poppler", "engine")}
    data = Path(args.data).resolve()
    recognition = data / f"{args.language}.traineddata"
    if not recognition.is_file():
        raise ValueError("not_run_missing_recognition_data")
    for path in paths.values():
        if not path.is_file():
            raise ValueError("A required local dependency is missing")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(config_path, output / "fixtures.toml")
    pdfmetrics.registerFont(TTFont("ExperimentFont", str(paths["font"])))
    pages = []
    for family in config["families"]:
        stem = family["id"]
        pdf = output / f"{stem}-text.pdf"
        canvas = Canvas(str(pdf), pagesize=(595, 842), invariant=1)
        canvas.setFont("ExperimentFont", config["font_size"])
        lines = (
            [config["title"], family["institution"], ""]
            + [f"{label}: {family['fields'][name]}" for name, label in config["labels"].items()]
            + ["", config["footer"]]
        )
        for index, line in enumerate(lines):
            if pdfmetrics.stringWidth(line, "ExperimentFont", config["font_size"]) > 511:
                raise ValueError("Fixture line would exceed page width")
            canvas.drawString(42, 780 - index * 40, line)
        canvas.save()
        png = output / f"{stem}-text.png"
        _render(paths["poppler"], pdf, png, config["dpi"])
        image_pdf = output / f"{stem}-image.pdf"
        canvas = Canvas(str(image_pdf), pagesize=(595, 842), invariant=1)
        canvas.drawImage(str(png), 0, 0, width=595, height=842)
        canvas.save()
        image_text = pdf_text(image_pdf)
        if image_text["status"] != "ok" or image_text["raw_text"].strip():
            raise ValueError("Image-only page must contain no extractable text")
        _render(paths["poppler"], image_pdf, output / f"{stem}-image.png", config["dpi"])
        for representation in ("text", "image"):
            page_id = f"{stem}-{representation}"
            pages.append(
                {
                    "id": page_id,
                    "family": stem,
                    "representation": representation,
                    "pdf": f"{page_id}.pdf",
                    "png": f"{page_id}.png",
                }
            )
    external = list(paths.values()) + [recognition] + list(Path(__file__).parent.glob("*.py"))
    version = subprocess.run(
        [str(paths["engine"]), "--version"], capture_output=True, text=True, check=True, timeout=30
    )
    raster_version = subprocess.run(
        [str(paths["poppler"]), "-v"], capture_output=True, text=True, check=True, timeout=30
    )
    registration = {
        "created_at": datetime.now(UTC).isoformat(),
        "config": config,
        "pages": pages,
        "files": {path.name: digest(path) for path in sorted(output.iterdir())},
        "external_files": {str(path.resolve()): digest(path) for path in external},
        "code_files": {p.name: digest(p) for p in Path(__file__).parent.glob("*.py")},
        "engine": str(paths["engine"]),
        "data": str(data),
        "language": args.language,
        "engine_version": version.stdout + version.stderr,
        "raster_version": raster_version.stdout + raster_version.stderr,
        "python_version": platform.python_version(),
        "libraries": {
            name: importlib.metadata.version(name) for name in ("reportlab", "pypdf", "pillow")
        },
        "rendering": {
            "page_points": [595, 842],
            "dpi": config["dpi"],
            "font_sha256": digest(paths["font"]),
        },
        "rules": "Exact labelled lines; outer whitespace only; repeated fields ambiguous.",
        "review_status": "awaiting_visual_inspection_before_lock",
    }
    write_json(output / "registration.json", registration)
