#!/bin/bash
# =============================================================================
# PowerStats - Release Script
# Builds, validates, tags git, and optionally uploads via gh CLI.
# Usage: ./scripts/release.sh [--version VERSION] [--push] [--upload]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VERSION=""
DO_PUSH=false
DO_UPLOAD=false

for arg in "$@"; do
    case $arg in
        --version=*) VERSION="${arg#*=}" ;;
        --push)      DO_PUSH=true ;;
        --upload)    DO_UPLOAD=true ;;
    esac
done

if [ -z "$VERSION" ]; then
    VERSION=$(python3 -c "import sys; sys.path.insert(0,'$PROJECT_ROOT'); from version import __version__; print(__version__)" 2>/dev/null)
fi

echo "========================================"
echo "  PowerStats Release: v$VERSION"
echo "========================================"

# 1. Run tests first — never release broken code
echo ""
echo "[1/5] Running test suite..."
cd "$PROJECT_ROOT"
python3 -m unittest tests/test_analytics.py -v 2>&1
echo "All tests passed."

# 2. Build .deb
echo ""
echo "[2/5] Building .deb package..."
bash "$SCRIPT_DIR/build.sh" --version="$VERSION"

DEB_FILE=$(find "$PROJECT_ROOT/build" -name "powerstats_${VERSION}_*.deb" | head -1)
echo "Built: $DEB_FILE"

# 3. Validate .deb
echo ""
echo "[3/5] Validating package..."
bash "$SCRIPT_DIR/package.sh" "$DEB_FILE"

# 4. Git tag
echo ""
echo "[4/5] Tagging git commit..."
if git -C "$PROJECT_ROOT" tag -l "v$VERSION" | grep -q "v$VERSION"; then
    echo "Tag v$VERSION already exists — skipping."
else
    git -C "$PROJECT_ROOT" tag -a "v$VERSION" -m "PowerStats v$VERSION"
    echo "Tagged v$VERSION"
fi

if $DO_PUSH; then
    echo "Pushing tag to origin..."
    git -C "$PROJECT_ROOT" push origin "v$VERSION"
fi

# 5. Upload release artifact via GitHub CLI
echo ""
echo "[5/5] Release artifact..."
if $DO_UPLOAD; then
    if ! command -v gh >/dev/null 2>&1; then
        echo "ERROR: 'gh' CLI not installed. Install from https://cli.github.com/" >&2
        exit 1
    fi
    gh release create "v$VERSION" \
        --title "PowerStats v$VERSION" \
        --notes-file "$PROJECT_ROOT/CHANGELOG.md" \
        "$DEB_FILE" 2>/dev/null || \
    gh release upload "v$VERSION" "$DEB_FILE"
    echo "Uploaded to GitHub Releases."
else
    echo "Skipped upload (pass --upload to upload via gh CLI)."
    echo "Manual upload: gh release create v$VERSION '$DEB_FILE'"
fi

echo ""
echo "========================================"
echo "  Release v$VERSION complete!"
echo "  .deb: $DEB_FILE"
echo "========================================"
