import json
from pathlib import Path

from PIL import Image, ImageDraw


def make_synthetic_drawing(path: Path) -> None:
    image = Image.new("RGB", (240, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((60, 45, 170, 135), fill=(244, 79, 83), outline=(21, 21, 21), width=5)
    draw.rectangle((102, 72, 142, 108), fill=(77, 154, 241))
    draw.ellipse((176, 84, 180, 88), fill=(18, 18, 18))
    draw.ellipse((184, 92, 188, 96), fill=(18, 18, 18))
    draw.point((10, 10), fill=(0, 0, 0))
    image.save(path)


def test_process_image_writes_alpha_cutline_preview_and_report(tmp_path: Path):
    from inklift.processing import ProcessingProfile, process_image

    source = tmp_path / "drawing.png"
    out_dir = tmp_path / "run"
    make_synthetic_drawing(source)

    result = process_image(source, out_dir, ProcessingProfile())

    assert result.clean_png.exists()
    assert result.cutline_svg.exists()
    assert result.preview_png.exists()
    assert result.report_json.exists()
    assert result.review_html.exists()

    clean = Image.open(result.clean_png)
    assert clean.mode == "RGBA"
    assert clean.size == (240, 180)
    assert clean.getbbox() is not None

    report = json.loads(result.report_json.read_text(encoding="utf-8"))
    alpha_bbox = report["alpha_bbox_px"]
    cutline_bbox = report["cutline"]["bbox_px"]

    assert cutline_bbox[0] <= alpha_bbox[0]
    assert cutline_bbox[1] <= alpha_bbox[1]
    assert cutline_bbox[2] >= alpha_bbox[2]
    assert cutline_bbox[3] >= alpha_bbox[3]


def test_cli_process_returns_zero_and_writes_review(tmp_path: Path):
    from inklift.cli import main

    source = tmp_path / "drawing.png"
    out_dir = tmp_path / "cli-run"
    make_synthetic_drawing(source)

    exit_code = main(["process", str(source), "--out", str(out_dir)])

    assert exit_code == 0
    assert (out_dir / "clean.png").exists()
    assert (out_dir / "review.html").exists()


def test_bench_creates_per_image_runs_and_gallery(tmp_path: Path):
    from inklift.cli import main

    samples = tmp_path / "samples"
    out_dir = tmp_path / "bench"
    samples.mkdir()
    make_synthetic_drawing(samples / "first.png")
    make_synthetic_drawing(samples / "second.jpg")

    exit_code = main(["bench", str(samples), "--out", str(out_dir)])

    assert exit_code == 0
    assert (out_dir / "review.html").exists()
    assert len(list(out_dir.glob("*/clean.png"))) == 2
