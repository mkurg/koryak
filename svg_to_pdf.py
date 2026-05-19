#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CACHE_DIR = PROJECT_ROOT / ".tools" / "cache"


def find_rsvg_convert() -> str | None:
    candidates = [
        os.environ.get("KORYAK_RSVG_CONVERT", ""),
        shutil.which("rsvg-convert") or "",
        "/opt/homebrew/bin/rsvg-convert",
        "/usr/local/bin/rsvg-convert",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def find_magick() -> str | None:
    candidates = [
        os.environ.get("KORYAK_MAGICK", ""),
        shutil.which("magick") or "",
        "/opt/homebrew/bin/magick",
        "/usr/local/bin/magick",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def convert_with_cairosvg(svg: Path, pdf: Path) -> bool:
    try:
        import cairosvg
    except ImportError:
        return False

    cairosvg.svg2pdf(url=str(svg), write_to=str(pdf))
    return True


def convert_with_rsvg(svg: Path, pdf: Path) -> bool:
    executable = find_rsvg_convert()
    if executable is None:
        return False

    subprocess.run([executable, "-f", "pdf", "-o", str(pdf), str(svg)], check=True)
    return True


def convert_with_magick(svg: Path, pdf: Path, density: int) -> bool:
    executable = find_magick()
    if executable is None:
        return False

    subprocess.run(
        [
            executable,
            "-density",
            str(density),
            str(svg),
            "-background",
            "white",
            "-alpha",
            "remove",
            "-alpha",
            "off",
            str(pdf),
        ],
        check=True,
    )
    return True


def convert_svg_to_pdf(
    svg_path: str | Path,
    pdf_path: str | Path | None = None,
    density: int = 96,
    allow_raster_fallback: bool = False,
) -> Path:
    """Convert an SVG to PDF using vector renderers by default.

    Preferred order is librsvg's rsvg-convert, then CairoSVG. ImageMagick is only
    used when allow_raster_fallback=True because it rasterizes these plots and can
    drop SVG strokes.
    """
    svg = Path(svg_path)
    if pdf_path is None:
        pdf = svg.with_suffix(".pdf")
    else:
        pdf = Path(pdf_path)

    if not svg.exists():
        raise FileNotFoundError(svg)

    pdf.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("XDG_CACHE_HOME", str(DEFAULT_CACHE_DIR))

    if convert_with_rsvg(svg, pdf):
        return pdf
    if convert_with_cairosvg(svg, pdf):
        return pdf
    if allow_raster_fallback and convert_with_magick(svg, pdf, density):
        return pdf

    raise RuntimeError(
        "No vector SVG-to-PDF converter found. Install librsvg for rsvg-convert "
        "or install CairoSVG. ImageMagick fallback is disabled by default because "
        "it rasterizes these graphs and can omit line strokes."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert SVG files to PDF without Chrome.")
    parser.add_argument("svg", nargs="+", help="SVG file(s) to convert.")
    parser.add_argument("--density", type=int, default=96, help="Input density in DPI. Default keeps CSS px at 0.75 PDF pt.")
    parser.add_argument("--output", help="Output PDF path. Only valid with one input SVG.")
    parser.add_argument(
        "--allow-raster-fallback",
        action="store_true",
        help="Allow ImageMagick fallback if no vector converter is available. Not recommended for final graphs.",
    )
    args = parser.parse_args()

    if args.output and len(args.svg) != 1:
        raise SystemExit("--output can only be used with one SVG input.")

    for svg in args.svg:
        pdf = convert_svg_to_pdf(
            svg,
            args.output,
            density=args.density,
            allow_raster_fallback=args.allow_raster_fallback,
        )
        print(pdf)


if __name__ == "__main__":
    main()
