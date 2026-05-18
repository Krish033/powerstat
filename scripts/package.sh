#!/bin/bash
# =============================================================================
# PowerStats - Package Validator + Linter
# Validates the .deb before releasing. Run after build.sh.
# Usage: ./scripts/package.sh [path/to/powerstats_*.deb]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"

# Find the .deb if not supplied
DEB_FILE="${1:-}"
if [ -z "$DEB_FILE" ]; then
    DEB_FILE=$(find "$BUILD_DIR" -name "*.deb" | sort -V | tail -1)
fi

if [ -z "$DEB_FILE" ] || [ ! -f "$DEB_FILE" ]; then
    echo "ERROR: No .deb file found. Run ./scripts/build.sh first." >&2
    exit 1
fi

echo "========================================"
echo "  PowerStats Package Validator"
echo "  Package: $DEB_FILE"
echo "========================================"
echo ""

PASS=0
FAIL=0

check() {
    local desc="$1"
    local result="$2"
    if [ "$result" = "ok" ]; then
        echo "  [PASS] $desc"
        PASS=$((PASS+1))
    else
        echo "  [FAIL] $desc  => $result"
        FAIL=$((FAIL+1))
    fi
}

# -- dpkg-deb info
echo "--- Package info ---"
dpkg-deb --info "$DEB_FILE"
echo ""

# -- File listing
echo "--- Installed files ---"
dpkg-deb --contents "$DEB_FILE"
echo ""

# -- Required fields in control
CONTROL=$(dpkg-deb --field "$DEB_FILE")

for field in Package Version Architecture Depends Description; do
    echo "$CONTROL" | grep -q "^$field:" \
        && check "Control has $field" "ok" \
        || check "Control has $field" "MISSING"
done

# -- Required files inside the deb
for path in \
    "./usr/bin/powerstats" \
    "./usr/share/powerstats/main.py" \
    "./usr/share/powerstats/daemon.py" \
    "./usr/share/applications/io.github.powerstats.PowerStats.desktop" \
    "./usr/share/icons/hicolor/scalable/apps/io.github.powerstats.PowerStats.svg" \
    "./usr/lib/systemd/user/powerstats.service"
do
    dpkg-deb --contents "$DEB_FILE" | grep -q "$path" \
        && check "Contains $path" "ok" \
        || check "Contains $path" "MISSING"
done

# -- Validate desktop file if desktop-file-validate is available
DESKTOP_TMP=$(mktemp /tmp/powerstats_XXXXXX.desktop)
dpkg-deb --fsys-tarfile "$DEB_FILE" | \
    tar -xO --wildcards "*/io.github.powerstats.PowerStats.desktop" \
    > "$DESKTOP_TMP" 2>/dev/null || true

if [ -s "$DESKTOP_TMP" ] && command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$DESKTOP_TMP" \
        && check "desktop-file-validate" "ok" \
        || check "desktop-file-validate" "INVALID"
else
    echo "  [SKIP] desktop-file-validate not installed"
fi
rm -f "$DESKTOP_TMP"

# -- Size check
SIZE_BYTES=$(stat -c%s "$DEB_FILE")
SIZE_KB=$((SIZE_BYTES / 1024))
echo ""
echo "  Package size: ${SIZE_KB} KB"

# -- Summary
echo ""
echo "========================================"
echo "  Results: $PASS passed, $FAIL failed"
echo "========================================"
[ "$FAIL" -eq 0 ] || exit 1
