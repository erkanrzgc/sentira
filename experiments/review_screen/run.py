"""Generate a standalone screen from locked synthetic review inputs."""

import argparse
import base64
import hashlib
import json
from pathlib import Path

from experiments.field_review.core import build_packet, packet_digest


def generate(fixtures: Path, results: Path, output: Path) -> Path:
    """Validate all input bytes before creating a fresh output directory."""
    if output.exists():
        raise FileExistsError(f"Output must be a fresh directory: {output}")
    packet = build_packet(fixtures, results)
    images = {}
    root = fixtures.resolve()
    for field in packet["fields"]:
        name = field["image"]
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Image path escapes fixtures")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != field["image_sha256"]:
            raise ValueError("Image digest mismatch")
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Registered source must be a PNG image")
        images[name] = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    payload = {"packet": packet, "packet_sha256": packet_digest(packet), "images": images}
    data = json.dumps(payload, ensure_ascii=True).replace("<", "\\u003c")
    assets = Path(__file__).parent
    page = (assets / "screen.html").read_text(encoding="utf-8")
    # Replace each template slot once; payload text is never interpreted as a template.
    parts = page.split("<!-- DATA -->")
    prefix = parts[0].replace("/* STYLE */", (assets / "screen.css").read_text(encoding="utf-8"))
    suffix = parts[1].replace("/* MODEL */", (assets / "model.js").read_text(encoding="utf-8"))
    suffix = suffix.replace("/* APP */", (assets / "app.js").read_text(encoding="utf-8"))
    rendered = prefix + data + suffix
    output.mkdir(parents=True)
    target = output / "index.html"
    target.write_text(rendered, encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        target = generate(args.fixtures, args.results, args.output)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Review screen generation failed: {exc}\n")
    print(target)


if __name__ == "__main__":
    main()
