#!/bin/bash
# =============================================================================
# PowerStats - Icon Generator
# Converts the master SVG into PNG files at all required hicolor sizes.
# Requires: librsvg2-bin (rsvg-convert) OR inkscape
# Usage: ./scripts/generate-icons.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ICONS_DIR="$(cd "$SCRIPT_DIR/../assets/icons" && pwd)"
SVG="$ICONS_DIR/powerstats.svg"

if [ ! -f "$SVG" ]; then
    echo "ERROR: SVG not found: $SVG" >&2
    exit 1
fi

# Pick a renderer
if command -v rsvg-convert >/dev/null 2>&1; then
    RENDERER="rsvg"
elif command -v inkscape >/dev/null 2>&1; then
    RENDERER="inkscape"
else
    echo "ERROR: Install librsvg2-bin or inkscape to generate icons." >&2
    echo "  sudo apt-get install librsvg2-bin" >&2
    exit 1
fi

SIZES=(16 22 24 32 48 64 128 256 512)

echo "Generating PNG icons from $SVG using $RENDERER..."
for size in "${SIZES[@]}"; do
    OUT="$ICONS_DIR/powerstats-${size}.png"
    if [ "$RENDERER" = "rsvg" ]; then
        rsvg-convert -w "$size" -h "$size" "$SVG" -o "$OUT"
    else
        inkscape --export-png="$OUT" -w "$size" -h "$size" "$SVG" 2>/dev/null
    fi
    echo "  [OK] ${size}x${size} -> $(basename "$OUT")"
done

echo ""
echo "All icons generated in: $ICONS_DIR"
echo "Run git add assets/icons/*.png to commit them."
