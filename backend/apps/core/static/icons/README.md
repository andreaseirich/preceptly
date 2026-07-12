# App Icons

Rasterised icons for favicons, Apple touch icons, and the PWA manifest.

**Source of truth:** `../brand/preceptly-icon.svg`

## Regenerate

```bash
pip install -r requirements-dev.txt          # provides cairosvg + Pillow
python3 backend/apps/core/static/generate_icons.py
```

The script emits:
- `favicon.ico` (16x16 + 32x32 + 48x48 multi-frame)
- `icon-16x16.png`, `icon-32x32.png`
- `apple-touch-icon-180x180.png`
- `icon-{72,96,128,144,152,192,384,512}x{...}.png` (PWA manifest)
