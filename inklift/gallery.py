from html import escape
from pathlib import Path
from typing import Iterable


def write_review_html(results: Iterable[object], output_path: str | Path, *, title: str) -> Path:
    html_path = Path(output_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_render_result(result, html_path.parent) for result in results]
    html = _page(title, "\n".join(rows))
    html_path.write_text(html, encoding="utf-8")
    return html_path


def _render_result(result: object, root: Path) -> str:
    name = escape(str(getattr(result, "name", "Artwork")))
    warnings = getattr(result, "warnings", [])
    warning_html = "".join(f"<li>{escape(str(warning))}</li>" for warning in warnings)
    warning_block = f"<ul class=\"warnings\">{warning_html}</ul>" if warnings else ""

    cards = [
        ("Original", getattr(result, "original_copy")),
        ("Normalized", getattr(result, "normalized_png")),
        ("Mask", getattr(result, "mask_png")),
        ("Clean PNG", getattr(result, "clean_png")),
        ("Preview", getattr(result, "preview_png")),
    ]
    card_html = "\n".join(_image_card(label, path, root) for label, path in cards)
    report = _relative(getattr(result, "report_json"), root)
    cutline = _relative(getattr(result, "cutline_svg"), root)
    return (
        f"<section class=\"item\"><header><h2>{name}</h2>{warning_block}</header>"
        f"<div class=\"grid\">{card_html}</div>"
        f"<p class=\"links\"><a href=\"{report}\">report.json</a> "
        f"<a href=\"{cutline}\">cutline.svg</a></p></section>"
    )


def _image_card(label: str, path: Path, root: Path) -> str:
    src = _relative(path, root)
    return (
        "<figure>"
        f"<img src=\"{src}\" alt=\"{escape(label)}\" loading=\"lazy\">"
        f"<figcaption>{escape(label)}</figcaption>"
        "</figure>"
    )


def _relative(path: str | Path, root: Path) -> str:
    return escape(Path(path).resolve().relative_to(root.resolve()).as_posix())


def _page(title: str, body: str) -> str:
    escaped_title = escape(title)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    body {{ margin: 0; background: #f6f4ef; color: #20201d; }}
    main {{ width: min(1180px, calc(100vw - 32px)); margin: 32px auto 56px; }}
    h1 {{ font-size: 28px; margin: 0 0 24px; }}
    .item {{ background: #fff; border: 1px solid #d8d2c6; border-radius: 8px; padding: 18px; margin: 18px 0; }}
    .item header {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }}
    h2 {{ font-size: 18px; margin: 0 0 14px; }}
    .warnings {{ margin: 0 0 12px; color: #9c3c19; font-size: 13px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    figure {{ margin: 0; border: 1px solid #e4ded3; border-radius: 6px; overflow: hidden; background:
      linear-gradient(45deg, #eee 25%, transparent 25%),
      linear-gradient(-45deg, #eee 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, #eee 75%),
      linear-gradient(-45deg, transparent 75%, #eee 75%);
      background-size: 20px 20px; background-position: 0 0, 0 10px, 10px -10px, -10px 0; }}
    img {{ display: block; width: 100%; aspect-ratio: 4 / 3; object-fit: contain; }}
    figcaption {{ background: rgba(255,255,255,.88); border-top: 1px solid #e4ded3; font-size: 12px; padding: 8px; }}
    .links {{ display: flex; gap: 14px; font-size: 13px; margin: 14px 0 0; }}
    a {{ color: #265c9d; }}
  </style>
</head>
<body>
  <main>
    <h1>{escaped_title}</h1>
    {body}
  </main>
</body>
</html>
"""
