from dataclasses import dataclass

import numpy as np
from skimage import measure, morphology


class CutlineError(RuntimeError):
    """Raised when a usable cutline cannot be generated."""


@dataclass(frozen=True)
class CutlineResult:
    svg: str
    points: list[tuple[float, float]]
    bbox_px: tuple[float, float, float, float]
    area_px2: float
    fragment_count: int


def mm_to_px(mm: float, dpi: int) -> int:
    return int(round((mm / 25.4) * dpi))


def generate_cutline(
    mask: np.ndarray,
    *,
    dpi: int,
    offset_mm: float,
    simplify_tolerance_px: float = 2.0,
) -> CutlineResult:
    if mask.ndim != 2:
        raise CutlineError("Cutline mask must be a 2D array.")
    if not np.any(mask):
        raise CutlineError("Cutline mask is empty.")

    height, width = mask.shape
    offset_px = max(0, mm_to_px(offset_mm, dpi))
    pad = max(4, offset_px + 4)
    padded = np.pad(mask.astype(bool), pad_width=pad, mode="constant", constant_values=False)

    if offset_px:
        padded = morphology.dilation(padded, morphology.disk(offset_px))
    padded = morphology.closing(padded, morphology.disk(2))

    contours = [
        contour
        for contour in measure.find_contours(padded.astype(float), 0.5)
        if len(contour) >= 4
    ]
    if not contours:
        raise CutlineError("No cutline contour could be found.")

    point_sets = [_contour_to_points(contour, pad, width, height) for contour in contours]
    point_sets = [points for points in point_sets if len(points) >= 4]
    if not point_sets:
        raise CutlineError("No usable cutline contour could be found.")

    primary = max(point_sets, key=lambda points: abs(_polygon_area(points)))
    simplified = measure.approximate_polygon(
        np.array([[y, x] for x, y in primary], dtype=float),
        tolerance=simplify_tolerance_px,
    )
    points = [(float(x), float(y)) for y, x in simplified]
    points = _ensure_closed(points)

    bbox = _bbox(points)
    area = abs(_polygon_area(points))
    svg = _render_svg(points, width=width, height=height, dpi=dpi)
    return CutlineResult(
        svg=svg,
        points=points,
        bbox_px=bbox,
        area_px2=area,
        fragment_count=len(point_sets),
    )


def _contour_to_points(
    contour: np.ndarray,
    pad: int,
    width: int,
    height: int,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for row, col in contour:
        x = float(np.clip(col - pad, 0, width - 1))
        y = float(np.clip(row - pad, 0, height - 1))
        points.append((x, y))
    return _ensure_closed(points)


def _ensure_closed(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not points:
        return points
    first = points[0]
    last = points[-1]
    if abs(first[0] - last[0]) > 0.01 or abs(first[1] - last[1]) > 0.01:
        return [*points, first]
    return points


def _bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        area += (x1 * y2) - (x2 * y1)
    return area / 2.0


def _render_svg(
    points: list[tuple[float, float]],
    *,
    width: int,
    height: int,
    dpi: int,
) -> str:
    width_mm = (width / dpi) * 25.4
    height_mm = (height / dpi) * 25.4
    start = points[0]
    commands = [f"M {start[0]:.2f} {start[1]:.2f}"]
    commands.extend(f"L {x:.2f} {y:.2f}" for x, y in points[1:-1])
    path = " ".join(commands) + " Z"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width_mm:.3f}mm" height="{height_mm:.3f}mm" '
        f'viewBox="0 0 {width} {height}">\n'
        '  <g id="inklift-cutline" data-spot-color="CutContour">\n'
        f'    <path id="cutline" d="{path}" fill="none" stroke="#ff2f5f" '
        'stroke-width="1" vector-effect="non-scaling-stroke"/>\n'
        "  </g>\n"
        "</svg>\n"
    )
