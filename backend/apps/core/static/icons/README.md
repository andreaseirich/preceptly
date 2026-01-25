# PWA Icons

This directory contains icons for the TutorFlow Progressive Web App.

## Generating Icons

To generate all required icon sizes from the SVG source:

```bash
cd backend/apps/core/static
python3 generate_icons.py
```

**Requirements:**
- Python 3
- Pillow: `pip install Pillow`
- cairosvg: `pip install cairosvg`

## Icon Sizes

The following icon sizes are required:
- 72x72
- 96x96
- 128x128
- 144x144
- 152x152
- 192x192
- 384x384
- 512x512

## Manual Alternative

If you prefer to create icons manually:
1. Use the `icon.svg` as a source
2. Export to PNG in all required sizes
3. Place them in this directory with the naming pattern: `icon-{size}x{size}.png`

## Note

For production, consider using a professional icon design tool or service to create high-quality icons that represent your brand.
