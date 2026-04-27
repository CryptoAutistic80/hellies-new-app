from pathlib import Path
import shutil
import subprocess


def vectorize_with_vtracer(input_png: str | Path, output_svg: str | Path) -> str | None:
    """Try to produce SVG artwork with VTracer.

    Returns a warning string when VTracer is unavailable or fails. The alpha
    engine treats vector artwork as optional, so callers should not fail the
    sticker PNG/cutline run when this returns a warning.
    """

    input_path = Path(input_png)
    output_path = Path(output_svg)

    import_warning = _try_python_vtracer(input_path, output_path)
    if import_warning is None:
        return None

    executable = shutil.which("vtracer")
    if executable:
        completed = subprocess.run(
            [
                executable,
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--colormode",
                "color",
                "--hierarchical",
                "stacked",
                "--mode",
                "spline",
                "--filter_speckle",
                "4",
                "--color_precision",
                "6",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0 and output_path.exists():
            return None
        message = completed.stderr.strip() or completed.stdout.strip()
        return f"VTracer command failed: {message or 'unknown error'}"

    return import_warning


def _try_python_vtracer(input_path: Path, output_path: Path) -> str | None:
    try:
        import vtracer  # type: ignore[import-not-found]
    except ImportError:
        return "VTracer is not installed; skipped optional vectorized artwork."

    try:
        vtracer.convert_image_to_svg_py(
            str(input_path),
            str(output_path),
            colormode="color",
            hierarchical="stacked",
            mode="spline",
            filter_speckle=4,
            color_precision=6,
            layer_difference=16,
            corner_threshold=60,
            length_threshold=4.0,
            max_iterations=10,
            splice_threshold=45,
            path_precision=3,
        )
    except Exception as exc:  # pragma: no cover - depends on optional native package.
        return f"VTracer Python adapter failed: {exc}"

    if output_path.exists():
        return None
    return "VTracer Python adapter finished without writing artwork.svg."
