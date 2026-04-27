from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from skimage import measure, morphology

from .cutline import CutlineError, CutlineResult, generate_cutline
from .gallery import write_review_html
from .image_io import load_image
from .vectorize import vectorize_with_vtracer


class ProcessingError(RuntimeError):
    """Raised when an image cannot be exported into alpha artifacts."""


@dataclass(frozen=True)
class ProcessingProfile:
    name: str = "faithful-sticker"
    detail_preservation: str = "high"
    speck_removal: str = "conservative"
    shadow_cleanup: str = "medium"
    cutline_offset_mm: float = 2.0
    dpi: int = 300
    background: str = "transparent"
    min_speck_area: int = 8
    preserve_distance_px: int = 36
    simplify_tolerance_px: float = 2.0


@dataclass(frozen=True)
class ProcessingResult:
    name: str
    original_copy: Path
    normalized_png: Path
    mask_png: Path
    clean_png: Path
    cutline_svg: Path
    preview_png: Path
    report_json: Path
    review_html: Path
    warnings: list[str]


def process_image(
    image_path: str | Path,
    out_dir: str | Path,
    profile: ProcessingProfile | None = None,
    *,
    vectorize_art: bool = False,
) -> ProcessingResult:
    profile = profile or ProcessingProfile()
    source = Path(image_path)
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)

    image = load_image(source)
    name = source.stem
    original_copy = output / f"original{source.suffix.lower()}"
    shutil.copy2(source, original_copy)

    normalized_png = output / "normalized.png"
    image.save(normalized_png)

    raw_mask = detect_art_mask(image)
    mask = remove_isolated_specks(
        raw_mask,
        min_speck_area=profile.min_speck_area,
        preserve_distance_px=profile.preserve_distance_px,
    )
    mask = morphology.closing(mask, morphology.disk(1))
    if not np.any(mask):
        raise ProcessingError("No artwork could be detected after background removal.")

    mask_png = output / "mask.png"
    Image.fromarray((mask.astype(np.uint8) * 255), mode="L").save(mask_png)

    clean_png = output / "clean.png"
    clean_image = apply_alpha_mask(image, mask)
    clean_image.save(clean_png, dpi=(profile.dpi, profile.dpi))

    try:
        cutline = generate_cutline(
            mask,
            dpi=profile.dpi,
            offset_mm=profile.cutline_offset_mm,
            simplify_tolerance_px=profile.simplify_tolerance_px,
        )
    except CutlineError as exc:
        raise ProcessingError(str(exc)) from exc

    cutline_svg = output / "cutline.svg"
    cutline_svg.write_text(cutline.svg, encoding="utf-8")

    preview_png = output / "preview.png"
    render_preview(clean_image, cutline).save(preview_png)

    warnings = quality_warnings(image, mask, cutline)
    vector_svg = None
    if vectorize_art:
        vector_svg = output / "artwork.svg"
        warning = vectorize_with_vtracer(clean_png, vector_svg)
        if warning:
            warnings.append(warning)

    report_json = output / "report.json"
    report_json.write_text(
        json.dumps(
            build_report(
                source=source,
                image=image,
                mask=mask,
                profile=profile,
                cutline=cutline,
                warnings=warnings,
                vector_svg=vector_svg if vector_svg and vector_svg.exists() else None,
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = ProcessingResult(
        name=name,
        original_copy=original_copy,
        normalized_png=normalized_png,
        mask_png=mask_png,
        clean_png=clean_png,
        cutline_svg=cutline_svg,
        preview_png=preview_png,
        report_json=report_json,
        review_html=output / "review.html",
        warnings=warnings,
    )
    write_review_html([result], result.review_html, title=f"InkLift Review: {name}")
    return result


def detect_art_mask(image: Image.Image) -> np.ndarray:
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    background = _estimate_background(rgb)
    distance = np.linalg.norm(rgb - background, axis=2)
    luminance = _luminance(rgb)
    background_luminance = float(_luminance(background.reshape(1, 1, 3))[0, 0])
    darkness = background_luminance - luminance
    max_channel = np.max(rgb, axis=2)
    min_channel = np.min(rgb, axis=2)
    saturation = (max_channel - min_channel) / np.maximum(max_channel, 1.0)

    border_distance = _border_values(distance)
    distance_threshold = max(18.0, float(np.percentile(border_distance, 95)) + 10.0)
    return (
        (distance > distance_threshold)
        | (darkness > 18.0)
        | ((saturation > 0.16) & (distance > 10.0))
    )


def remove_isolated_specks(
    mask: np.ndarray,
    *,
    min_speck_area: int,
    preserve_distance_px: int,
) -> np.ndarray:
    labels = measure.label(mask.astype(bool), connectivity=2)
    if labels.max() == 0:
        return mask.astype(bool)

    areas = np.bincount(labels.ravel())
    large_labels = {
        label
        for label, area in enumerate(areas)
        if label != 0 and area >= min_speck_area
    }
    if not large_labels:
        return mask.astype(bool)

    large_mask = np.isin(labels, list(large_labels))
    near_large = morphology.dilation(
        large_mask,
        morphology.disk(max(1, preserve_distance_px)),
    )
    keep = np.zeros_like(mask, dtype=bool)
    for label, area in enumerate(areas):
        if label == 0:
            continue
        component = labels == label
        if area >= min_speck_area or np.any(component & near_large):
            keep |= component
    return keep


def apply_alpha_mask(image: Image.Image, mask: np.ndarray) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    rgba.putalpha(alpha)
    return rgba


def render_preview(clean_image: Image.Image, cutline: CutlineResult) -> Image.Image:
    base = _checkerboard(clean_image.size)
    base.alpha_composite(clean_image)
    draw = ImageDraw.Draw(base)
    points = [(round(x), round(y)) for x, y in cutline.points]
    if len(points) >= 2:
        draw.line(points, fill=(255, 47, 95, 255), width=2, joint="curve")
    return base


def quality_warnings(
    image: Image.Image,
    mask: np.ndarray,
    cutline: CutlineResult,
) -> list[str]:
    warnings: list[str] = []
    width, height = image.size
    if width < 1200 or height < 1200:
        warnings.append("Low resolution for print; aim for at least 1200px on each side.")
    if _blur_score(image) < 0.00025:
        warnings.append("Possible blur detected; a sharper scan/photo may improve the cutline.")

    area_ratio = float(np.count_nonzero(mask)) / float(mask.size)
    if area_ratio < 0.005:
        warnings.append("Weak artwork detection; cleanup may have missed pale marks.")
    if cutline.fragment_count > 1:
        warnings.append(
            f"Cutline fragmentation detected: {cutline.fragment_count} candidate contours found."
        )
    return warnings


def build_report(
    *,
    source: Path,
    image: Image.Image,
    mask: np.ndarray,
    profile: ProcessingProfile,
    cutline: CutlineResult,
    warnings: list[str],
    vector_svg: Path | None,
) -> dict[str, object]:
    alpha_bbox = _mask_bbox(mask)
    return {
        "source": str(source),
        "profile": asdict(profile),
        "dimensions_px": {"width": image.width, "height": image.height},
        "alpha_bbox_px": alpha_bbox,
        "alpha_area_px": int(np.count_nonzero(mask)),
        "warnings": warnings,
        "cutline": {
            "bbox_px": list(cutline.bbox_px),
            "area_px2": cutline.area_px2,
            "fragment_count": cutline.fragment_count,
            "offset_mm": profile.cutline_offset_mm,
            "dpi": profile.dpi,
        },
        "exports": {
            "clean_png": "clean.png",
            "cutline_svg": "cutline.svg",
            "preview_png": "preview.png",
            "vector_svg": str(vector_svg.name) if vector_svg else None,
        },
    }


def _estimate_background(rgb: np.ndarray) -> np.ndarray:
    samples = np.concatenate(
        [
            rgb[: max(1, rgb.shape[0] // 20), :, :].reshape(-1, 3),
            rgb[-max(1, rgb.shape[0] // 20) :, :, :].reshape(-1, 3),
            rgb[:, : max(1, rgb.shape[1] // 20), :].reshape(-1, 3),
            rgb[:, -max(1, rgb.shape[1] // 20) :, :].reshape(-1, 3),
        ],
        axis=0,
    )
    return np.median(samples, axis=0)


def _border_values(values: np.ndarray) -> np.ndarray:
    return np.concatenate(
        [
            values[0, :],
            values[-1, :],
            values[:, 0],
            values[:, -1],
        ]
    )


def _luminance(rgb: np.ndarray) -> np.ndarray:
    return (0.2126 * rgb[..., 0]) + (0.7152 * rgb[..., 1]) + (0.0722 * rgb[..., 2])


def _blur_score(image: Image.Image) -> float:
    gray = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
    edges = Image.fromarray((gray * 255).astype(np.uint8), mode="L").filter(ImageFilter.FIND_EDGES)
    edge_array = np.asarray(edges, dtype=np.float32) / 255.0
    return float(np.var(edge_array))


def _mask_bbox(mask: np.ndarray) -> list[int]:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return [0, 0, 0, 0]
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def _checkerboard(size: tuple[int, int], cell: int = 16) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            if ((x // cell) + (y // cell)) % 2 == 0:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(230, 230, 230, 255))
    return image
