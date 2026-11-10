#!/usr/bin/env python3
"""Render ``banner.svg`` to ``banner.png`` for the README.

The SVG is the source of truth; the generated PNG is committed so the README
renders on GitHub without any build step. Backends are tried in order:

1. PyQt6 ``QtSvg`` (already available in the development environment);
2. ``cairosvg``;
3. ``rsvg-convert``;
4. Inkscape (``--export-type=png``).

Examples:

    python3 docs/assets/render-banner.py
    python3 docs/assets/render-banner.py --scale 3
    python3 docs/assets/render-banner.py --output /tmp/banner.png --scale 1

The default scale is 2, so the committed PNG is 2560x720 for crisp rendering on
high-density displays. Pass ``--scale 1`` for an exact 1280x360 image.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path


ASSETS_DIR = Path(__file__).resolve().parent
SOURCE_PATH = ASSETS_DIR / "banner.svg"
DEFAULT_OUTPUT = ASSETS_DIR / "banner.png"


def _svg_size(path: Path) -> tuple[float, float]:
    """Return the declared width and height of *path* in user units."""
    root = ElementTree.parse(path).getroot()

    def number(value: str | None, fallback: float) -> float:
        if not value:
            return fallback
        digits = "".join(character for character in value if character.isdigit() or character == ".")
        return float(digits) if digits else fallback

    return number(root.get("width"), 1280.0), number(root.get("height"), 360.0)


def _render_with_pyqt6(source: Path, output: Path, width: int, height: int) -> str:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtGui import QGuiApplication, QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer

    application = QGuiApplication.instance() or QGuiApplication([])
    # Keep the application alive until the renderer has finished.
    _ = application
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise RuntimeError("QtSvg could not parse the SVG")

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    try:
        renderer.render(painter)
    finally:
        painter.end()

    if not image.save(str(output), "PNG"):
        raise RuntimeError("Qt could not write the PNG")
    return "PyQt6 QtSvg"


def _render_with_cairosvg(source: Path, output: Path, width: int, height: int) -> str:
    import cairosvg

    cairosvg.svg2png(
        url=str(source),
        write_to=str(output),
        output_width=width,
        output_height=height,
    )
    return "cairosvg"


def _render_with_rsvg(source: Path, output: Path, width: int, height: int) -> str:
    executable = shutil.which("rsvg-convert")
    if executable is None:
        raise RuntimeError("rsvg-convert is not installed")
    subprocess.run(
        [executable, "-w", str(width), "-h", str(height), "-o", str(output), str(source)],
        check=True,
    )
    return "rsvg-convert"


def _render_with_inkscape(source: Path, output: Path, width: int, height: int) -> str:
    executable = shutil.which("inkscape")
    if executable is None:
        raise RuntimeError("Inkscape is not installed")
    subprocess.run(
        [
            executable,
            str(source),
            "--export-type=png",
            f"--export-filename={output}",
            f"--export-width={width}",
            f"--export-height={height}",
        ],
        check=True,
    )
    return "Inkscape"


BACKENDS = {
    "pyqt6": _render_with_pyqt6,
    "cairosvg": _render_with_cairosvg,
    "rsvg": _render_with_rsvg,
    "inkscape": _render_with_inkscape,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the README banner SVG to PNG")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"output PNG (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=2.0,
        help="pixel scale applied to the SVG size (default: 2)",
    )
    parser.add_argument(
        "--backend",
        choices=tuple(BACKENDS),
        help="force one backend instead of trying all of them",
    )
    args = parser.parse_args()

    base_width, base_height = _svg_size(SOURCE_PATH)
    width = max(1, round(base_width * args.scale))
    height = max(1, round(base_height * args.scale))
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    names = (args.backend,) if args.backend else tuple(BACKENDS)
    failures: list[str] = []
    for name in names:
        try:
            used = BACKENDS[name](SOURCE_PATH, output, width, height)
        except Exception as error:  # Try the next renderer.
            failures.append(f"{name}: {error}")
            continue
        print(f"Rendered {output} ({width}x{height}) with {used}")
        return 0

    print("Could not render the banner. Install one of: PyQt6, cairosvg, rsvg-convert, Inkscape.", file=sys.stderr)
    for failure in failures:
        print(f"  {failure}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
