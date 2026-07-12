#!/usr/bin/env python3
"""Generate Preceptly PWA/favicon icons from the brand SVG.

Source of truth: ``backend/apps/core/static/brand/preceptly-icon.svg``.

Requires: ``pip install cairosvg pillow`` (dev-only, not needed at runtime).
"""

import sys
from io import BytesIO
from pathlib import Path

try:
    import cairosvg
    from PIL import Image
except ImportError:
    print("Error: please install: pip install cairosvg pillow", file=sys.stderr)
    sys.exit(1)


PWA_SIZES = [72, 96, 128, 144, 152, 192, 384, 512]
FAVICON_PNG_SIZES = [16, 32]
APPLE_TOUCH_SIZE = 180
FAVICON_ICO_SIZES = [16, 32, 48]


def render_png(svg_path: Path, size: int) -> bytes:
    return cairosvg.svg2png(url=str(svg_path), output_width=size, output_height=size)


def main() -> None:
    base_dir = Path(__file__).parent
    icons_dir = base_dir / "icons"
    icons_dir.mkdir(exist_ok=True)
    svg_path = base_dir / "brand" / "preceptly-icon.svg"
    if not svg_path.exists():
        print(f"Error: SVG source not found at {svg_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Rendering icons from {svg_path}")

    for size in PWA_SIZES:
        out = icons_dir / f"icon-{size}x{size}.png"
        out.write_bytes(render_png(svg_path, size))
        print(f"  wrote {out.name}")

    for size in FAVICON_PNG_SIZES:
        out = icons_dir / f"icon-{size}x{size}.png"
        out.write_bytes(render_png(svg_path, size))
        print(f"  wrote {out.name}")

    apple = icons_dir / f"apple-touch-icon-{APPLE_TOUCH_SIZE}x{APPLE_TOUCH_SIZE}.png"
    apple.write_bytes(render_png(svg_path, APPLE_TOUCH_SIZE))
    print(f"  wrote {apple.name}")

    max_ico = max(FAVICON_ICO_SIZES)
    base_img = Image.open(BytesIO(render_png(svg_path, max_ico)))
    ico = icons_dir / "favicon.ico"
    base_img.save(
        ico,
        format="ICO",
        sizes=[(s, s) for s in FAVICON_ICO_SIZES],
    )
    print(f"  wrote {ico.name} ({', '.join(f'{s}x{s}' for s in FAVICON_ICO_SIZES)})")


if __name__ == "__main__":
    main()
