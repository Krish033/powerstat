#!/bin/bash
# =============================================================================
# PowerStats - One-shot installer (for users without .deb, running from source)
# Installs system files, daemon, and desktop entry for the current user.
# Usage: sudo ./scripts/install.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VERSION=$(grep -Po '(?<=__version__ = ")[^"]+' "$PROJECT_ROOT/version.py" 2>/dev/null || echo "1.0.0")
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(eval echo "~$REAL_USER")

echo "========================================"
echo "  PowerStats v$VERSION Installer"
echo "  Installing for user: $REAL_USER"
echo "========================================"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must be run with sudo." >&2
    exit 1
fi

# Check dependencies
MISSING_DEPS=""
for pkg in python3-gi python3-gi-cairo python3-psutil upower; do
    dpkg -s "$pkg" >/dev/null 2>&1 || MISSING_DEPS="$MISSING_DEPS $pkg"
done

if [ -n "$MISSING_DEPS" ]; then
    echo ""
    echo "Installing missing dependencies:$MISSING_DEPS"
    apt-get install -y $MISSING_DEPS
fi

# Install app source
echo ""
echo "Installing application files..."
install -d /usr/share/powerstats
for f in main.py window.py usage_view.py app_details.py analytics_data.py daemon.py version.py; do
    install -m 644 "$PROJECT_ROOT/$f" "/usr/share/powerstats/$f"
done

# Install launcher
install -m 755 "$PROJECT_ROOT/packaging/powerstats-launcher" /usr/bin/powerstats

# Install desktop file
install -d /usr/share/applications
install -m 644 "$PROJECT_ROOT/packaging/powerstats.desktop" \
    /usr/share/applications/io.github.powerstats.PowerStats.desktop

# Install icons — SVG, symbolic, and PNG at all hicolor sizes
install -d /usr/share/icons/hicolor/scalable/apps
install -m 644 "$PROJECT_ROOT/assets/icons/powerstats.svg" \
    /usr/share/icons/hicolor/scalable/apps/io.github.powerstats.PowerStats.svg
install -d /usr/share/icons/hicolor/symbolic/apps
install -m 644 "$PROJECT_ROOT/assets/icons/powerstats-symbolic.svg" \
    /usr/share/icons/hicolor/symbolic/apps/io.github.powerstats.PowerStats-symbolic.svg

for size in 16 22 24 32 48 64 128 256 512; do
    PNG="$PROJECT_ROOT/assets/icons/powerstats-${size}.png"
    if [ -f "$PNG" ]; then
        install -d "/usr/share/icons/hicolor/${size}x${size}/apps"
        install -m 644 "$PNG" \
            "/usr/share/icons/hicolor/${size}x${size}/apps/io.github.powerstats.PowerStats.png"
    fi
done

install -d /usr/share/pixmaps
if [ -f "$PROJECT_ROOT/assets/icons/powerstats-256.png" ]; then
    install -m 644 "$PROJECT_ROOT/assets/icons/powerstats-256.png" \
        /usr/share/pixmaps/powerstats.png
fi

# Install systemd user service
install -d /usr/lib/systemd/user
install -m 644 "$PROJECT_ROOT/packaging/powerstats-user.service" \
    /usr/lib/systemd/user/powerstats.service

# Refresh caches
gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true

# Enable daemon for real user
echo ""
echo "Enabling daemon for $REAL_USER..."
su - "$REAL_USER" -c \
    "systemctl --user daemon-reload && systemctl --user enable --now powerstats.service" \
    2>/dev/null && echo "Daemon enabled." || echo "Could not auto-enable daemon. Run manually after login."

echo ""
echo "========================================"
echo "  PowerStats v$VERSION installed!"
echo ""
echo "  Launch: powerstats"
echo "  Or open from your Applications menu."
echo "========================================"
