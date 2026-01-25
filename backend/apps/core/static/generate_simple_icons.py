#!/usr/bin/env python3
"""
Simple script to generate placeholder PWA icons.
Creates simple colored square icons without external dependencies.
For production, replace with proper icons.
"""

import base64
from pathlib import Path

# Simple PNG data for a 1x1 pixel blue square (will be scaled by browser)
# This is a minimal valid PNG: 1x1 blue pixel
MINIMAL_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


def create_simple_icon(size):
    """Create a simple colored icon using base64 encoded minimal PNG."""
    # For now, we'll create a simple text file that indicates the size
    # In production, these should be replaced with actual PNG files
    return f"""# Placeholder icon {size}x{size}
# Replace this with an actual PNG icon file
# Use icon.svg as source and export to PNG at {size}x{size} pixels
"""


def generate_placeholder_icons():
    """Generate placeholder icon files."""
    base_dir = Path(__file__).parent
    icons_dir = base_dir / "icons"
    icons_dir.mkdir(exist_ok=True)

    ICON_SIZES = [72, 96, 128, 144, 152, 192, 384, 512]

    print("Creating placeholder icon files...")
    print("NOTE: These are placeholders. For production, replace with actual PNG icons.")
    print("You can use icon.svg as a source and export to PNG in all required sizes.\n")

    for size in ICON_SIZES:
        # Create a simple 1x1 PNG file (minimal valid PNG)
        # This is a workaround - in production, use proper icons
        png_path = icons_dir / f"icon-{size}x{size}.png"

        # Decode base64 and write minimal PNG
        png_data = base64.b64decode(MINIMAL_PNG_BASE64)

        with open(png_path, "wb") as f:
            f.write(png_data)

        print(f"  ✓ Created placeholder {png_path.name}")

    print("\nPlaceholder icons created!")
    print("For production, replace these with proper icons generated from icon.svg")


if __name__ == "__main__":
    generate_placeholder_icons()
