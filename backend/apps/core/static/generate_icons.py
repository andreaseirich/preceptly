#!/usr/bin/env python3
"""
Script to generate PWA icons from SVG source.
Requires: pip install cairosvg
"""

from pathlib import Path

try:
    import cairosvg
except ImportError:
    print("Error: Please install required packages:")
    print("  pip install cairosvg")
    exit(1)

# Icon sizes needed for PWA
ICON_SIZES = [72, 96, 128, 144, 152, 192, 384, 512]


def generate_icons():
    """Generate PNG icons from SVG source."""
    base_dir = Path(__file__).parent
    icons_dir = base_dir / "icons"
    svg_path = icons_dir / "icon.svg"

    if not svg_path.exists():
        print(f"Error: SVG source not found at {svg_path}")
        return

    print(f"Generating icons from {svg_path}...")

    for size in ICON_SIZES:
        png_path = icons_dir / f"icon-{size}x{size}.png"

        # Convert SVG to PNG using cairosvg
        png_data = cairosvg.svg2png(url=str(svg_path), output_width=size, output_height=size)

        # Save PNG
        with open(png_path, "wb") as f:
            f.write(png_data)

        print(f"  ✓ Generated {png_path.name}")

    print("\nAll icons generated successfully!")


if __name__ == "__main__":
    generate_icons()
