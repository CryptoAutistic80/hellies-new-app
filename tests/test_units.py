from pathlib import Path

import numpy as np
import pytest


def test_mm_to_px_uses_300_dpi():
    from inklift.cutline import mm_to_px

    assert mm_to_px(2, 300) == 24


def test_load_image_rejects_bad_file(tmp_path: Path):
    from inklift.image_io import ImageLoadError, load_image

    bad_file = tmp_path / "not-an-image.txt"
    bad_file.write_text("not actually an image", encoding="utf-8")

    with pytest.raises(ImageLoadError):
        load_image(bad_file)


def test_cutline_svg_contains_one_closed_primary_path():
    from inklift.cutline import generate_cutline

    mask = np.zeros((80, 100), dtype=bool)
    mask[20:60, 25:75] = True

    cutline = generate_cutline(mask, dpi=300, offset_mm=2)

    assert "<path" in cutline.svg
    assert cutline.svg.count("<path") == 1
    assert cutline.svg.count("Z") == 1
    assert cutline.fragment_count == 1


def test_conservative_speck_cleanup_preserves_near_details():
    from inklift.processing import remove_isolated_specks

    mask = np.zeros((90, 120), dtype=bool)
    mask[30:60, 40:80] = True
    mask[24:26, 50:52] = True  # tiny intentional mark near the main art
    mask[5:7, 5:7] = True  # isolated accidental speck

    cleaned = remove_isolated_specks(mask, min_speck_area=8, preserve_distance_px=12)

    assert cleaned[25, 51]
    assert not cleaned[6, 6]
