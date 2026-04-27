from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class ImageLoadError(RuntimeError):
    """Raised when an input cannot be used as artwork."""


def load_image(path: str | Path) -> Image.Image:
    image_path = Path(path)
    if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ImageLoadError(
            f"Unsupported image format '{image_path.suffix}'. "
            "Use JPG, JPEG, PNG, or WEBP."
        )

    try:
        with Image.open(image_path) as image:
            normalized = ImageOps.exif_transpose(image)
            return normalized.convert("RGB")
    except (FileNotFoundError, UnidentifiedImageError, OSError) as exc:
        raise ImageLoadError(f"Could not read image '{image_path}': {exc}") from exc
