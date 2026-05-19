#!/bin/bash
# =============================================================================
# PowerStats - Debian Package Builder
# Usage: ./scripts/build.sh [--version VERSION] [--arch ARCH]
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve project root (scripts/ lives one level below root)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
VERSION=""
ARCH="all"

# Parse named args (only --version=X form accepted)
for arg in "$@"; do
    case $arg in
        --version=*) VERSION="${arg#*=}" ;;
        --arch=*)    ARCH="${arg#*=}" ;;
    esac
done

# Read version from version.py if not supplied via flag
if [ -z "$VERSION" ]; then
    # grep is more reliable than python3 import in CI environments
    VERSION=$(grep -Po '(?<=__version__ = ")[^"]+' "$PROJECT_ROOT/version.py" 2>/dev/null || true)
fi

# Final fallback: python3 (handles edge cases like single-quotes in version.py)
if [ -z "$VERSION" ]; then
    VERSION=$(python3 -c "exec(open('$PROJECT_ROOT/version.py').read()); print(__version__)" 2>/dev/null || true)
fi

if [ -z "$VERSION" ]; then
    echo "ERROR: Could not determine version. Pass --version=X.Y.Z or ensure version.py exists." >&2
    exit 1
fi

PACKAGE_NAME="powerstats_${VERSION}_${ARCH}"
BUILD_DIR="$PROJECT_ROOT/build"
STAGE_DIR="$BUILD_DIR/$PACKAGE_NAME"
DEB_OUT="$BUILD_DIR/${PACKAGE_NAME}.deb"

echo "========================================"
echo "  PowerStats Debian Package Builder"
echo "  Version : $VERSION"
echo "  Arch    : $ARCH"
echo "  Output  : $DEB_OUT"
echo "========================================"

# ---------------------------------------------------------------------------
# Clean previous build
# ---------------------------------------------------------------------------
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"

# ---------------------------------------------------------------------------
# Install application source files
# ---------------------------------------------------------------------------
APP_DEST="$STAGE_DIR/usr/share/powerstats"
mkdir -p "$APP_DEST"

SRC_FILES=(
    main.py
    window.py
    usage_view.py
    app_details.py
    analytics_data.py
    daemon.py
    version.py
)

for f in "${SRC_FILES[@]}"; do
    if [ ! -f "$PROJECT_ROOT/$f" ]; then
        echo "ERROR: Missing source file: $f" >&2
        exit 1
    fi
    install -m 644 "$PROJECT_ROOT/$f" "$APP_DEST/$f"
done

# ---------------------------------------------------------------------------
# Install launcher binary -> /usr/bin/powerstats
# ---------------------------------------------------------------------------
BIN_DEST="$STAGE_DIR/usr/bin"
mkdir -p "$BIN_DEST"
install -m 755 "$PROJECT_ROOT/packaging/powerstats-launcher" "$BIN_DEST/powerstats"

# ---------------------------------------------------------------------------
# Install .desktop file -> /usr/share/applications/
# ---------------------------------------------------------------------------
DESKTOP_DEST="$STAGE_DIR/usr/share/applications"
mkdir -p "$DESKTOP_DEST"
install -m 644 "$PROJECT_ROOT/packaging/powerstats.desktop" \
    "$DESKTOP_DEST/io.github.powerstats.PowerStats.desktop"

# ---------------------------------------------------------------------------
# Install icons -> /usr/share/icons/hicolor/
# PNG sizes required for reliable display in GNOME, KDE, XFCE, dock, launcher
# ---------------------------------------------------------------------------
ICON_SCALABLE="$STAGE_DIR/usr/share/icons/hicolor/scalable/apps"
ICON_SYMBOLIC="$STAGE_DIR/usr/share/icons/hicolor/symbolic/apps"
mkdir -p "$ICON_SCALABLE" "$ICON_SYMBOLIC"

install -m 644 "$PROJECT_ROOT/assets/icons/powerstats.svg" \
    "$ICON_SCALABLE/io.github.powerstats.PowerStats.svg"
install -m 644 "$PROJECT_ROOT/assets/icons/powerstats-symbolic.svg" \
    "$ICON_SYMBOLIC/io.github.powerstats.PowerStats-symbolic.svg"

# Install PNG icons at all standard hicolor sizes
ICON_APP_ID="io.github.powerstats.PowerStats"
for size in 16 22 24 32 48 64 128 256 512; do
    PNG_SRC="$PROJECT_ROOT/assets/icons/powerstats-${size}.png"
    if [ -f "$PNG_SRC" ]; then
        PNG_DEST="$STAGE_DIR/usr/share/icons/hicolor/${size}x${size}/apps"
        mkdir -p "$PNG_DEST"
        install -m 644 "$PNG_SRC" "$PNG_DEST/${ICON_APP_ID}.png"
    else
        echo "WARNING: Missing PNG: $PNG_SRC — run: scripts/generate-icons.sh" >&2
    fi
done

# Also install 256x256 as the pixmap fallback (used by legacy launchers)
PIXMAP_DEST="$STAGE_DIR/usr/share/pixmaps"
mkdir -p "$PIXMAP_DEST"
if [ -f "$PROJECT_ROOT/assets/icons/powerstats-256.png" ]; then
    install -m 644 "$PROJECT_ROOT/assets/icons/powerstats-256.png" \
        "$PIXMAP_DEST/powerstats.png"
fi

# ---------------------------------------------------------------------------
# Install systemd user service -> /usr/lib/systemd/user/
# ---------------------------------------------------------------------------
SYSTEMD_DEST="$STAGE_DIR/usr/lib/systemd/user"
mkdir -p "$SYSTEMD_DEST"
install -m 644 "$PROJECT_ROOT/packaging/powerstats-user.service" \
    "$SYSTEMD_DEST/powerstats.service"

# ---------------------------------------------------------------------------
# Install DEBIAN control files
# ---------------------------------------------------------------------------
DEBIAN_DIR="$STAGE_DIR/DEBIAN"
mkdir -p "$DEBIAN_DIR"

# Stamp the actual version into the control file
sed "s/^Version:.*/Version: $VERSION/" \
    "$PROJECT_ROOT/packaging/debian/control" > "$DEBIAN_DIR/control"

install -m 755 "$PROJECT_ROOT/packaging/debian/postinst" "$DEBIAN_DIR/postinst"
install -m 755 "$PROJECT_ROOT/packaging/debian/prerm"    "$DEBIAN_DIR/prerm"
install -m 755 "$PROJECT_ROOT/packaging/debian/postrm"   "$DEBIAN_DIR/postrm"

# ---------------------------------------------------------------------------
# Set correct permissions throughout the staging tree
# ---------------------------------------------------------------------------
find "$STAGE_DIR" -type d -exec chmod 755 {} \;
find "$STAGE_DIR/usr" -type f -exec chmod 644 {} \;
chmod 755 "$STAGE_DIR/usr/bin/powerstats"
chmod 755 "$DEBIAN_DIR/postinst" "$DEBIAN_DIR/prerm" "$DEBIAN_DIR/postrm"

# ---------------------------------------------------------------------------
# Build the .deb
# ---------------------------------------------------------------------------
echo ""
echo "Building .deb package..."
dpkg-deb --build --root-owner-group "$STAGE_DIR" "$DEB_OUT"

echo ""
echo "  SUCCESS: $DEB_OUT"
echo ""
echo "Install with:"
echo "  sudo dpkg -i $DEB_OUT"
echo "  sudo apt --fix-broken install   # if deps are missing"
