from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import re
import sys

from .gallery import write_review_html
from .image_io import ImageLoadError, SUPPORTED_EXTENSIONS
from .processing import ProcessingError, ProcessingProfile, process_image


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    profile = ProcessingProfile(
        dpi=args.dpi,
        cutline_offset_mm=args.cutline_offset_mm,
    )

    try:
        if args.command == "process":
            result = process_image(
                args.image,
                args.out,
                profile,
                vectorize_art=args.vectorize_art,
            )
            _print_result(result)
            return 0
        if args.command == "bench":
            return _bench(args, profile)
    except (ImageLoadError, ProcessingError, OSError) as exc:
        print(f"inklift: {exc}", file=sys.stderr)
        return 1

    parser.print_help(sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inklift",
        description="Local alpha engine for hand-drawn sticker cleanup and cutline export.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    process = subparsers.add_parser("process", help="Process one image into alpha artifacts.")
    process.add_argument("image", type=Path)
    process.add_argument("--out", type=Path, required=True)
    _add_common_args(process)

    bench = subparsers.add_parser("bench", help="Process a folder of private sample images.")
    bench.add_argument("samples", type=Path)
    bench.add_argument(
        "--out",
        type=Path,
        default=Path("runs") / datetime.now().strftime("%Y%m%d-%H%M%S"),
    )
    _add_common_args(bench)
    return parser


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--cutline-offset-mm", type=float, default=2.0)
    parser.add_argument("--vectorize-art", action="store_true")


def _bench(args: argparse.Namespace, profile: ProcessingProfile) -> int:
    sample_dir = Path(args.samples)
    output = Path(args.out)
    if not sample_dir.exists() or not sample_dir.is_dir():
        print(f"inklift: sample folder does not exist: {sample_dir}", file=sys.stderr)
        return 1

    images = [
        path
        for path in sorted(sample_dir.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    if not images:
        print(f"inklift: no supported images found in {sample_dir}", file=sys.stderr)
        return 1

    output.mkdir(parents=True, exist_ok=True)
    results = []
    failures = 0
    used_names: set[str] = set()
    for image in images:
        run_name = _unique_slug(image.stem, used_names)
        try:
            result = process_image(
                image,
                output / run_name,
                profile,
                vectorize_art=args.vectorize_art,
            )
            results.append(result)
            _print_result(result)
        except (ImageLoadError, ProcessingError, OSError) as exc:
            failures += 1
            print(f"inklift: failed {image}: {exc}", file=sys.stderr)

    if results:
        write_review_html(results, output / "review.html", title="InkLift Bench Review")
    return 1 if failures else 0


def _print_result(result: object) -> None:
    print(f"Processed {getattr(result, 'name')}:")
    print(f"  clean: {getattr(result, 'clean_png')}")
    print(f"  cutline: {getattr(result, 'cutline_svg')}")
    print(f"  review: {getattr(result, 'review_html')}")
    for warning in getattr(result, "warnings", []):
        print(f"  warning: {warning}")


def _unique_slug(name: str, used: set[str]) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-._").lower() or "artwork"
    candidate = slug
    index = 2
    while candidate in used:
        candidate = f"{slug}-{index}"
        index += 1
    used.add(candidate)
    return candidate
