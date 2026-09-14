#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  Hotspot Manager GUI — .deb builder
#  Run this once: ./build_deb.sh
#  It checks for what's needed to build a .deb, skips whatever is
#  already installed, and installs whatever is missing. You don't
#  need to do anything else manually.
# ─────────────────────────────────────────────────────────────
set -e

APP_NAME="hotspot-manager-gui"
VERSION="2.0.0"
ARCH="all"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$SCRIPT_DIR/pkgroot"
OUT_DEB="$SCRIPT_DIR/${APP_NAME}_${VERSION}_${ARCH}.deb"

echo "================================================"
echo "  Hotspot Manager GUI — .deb Builder"
echo "================================================"
echo ""

if ! command -v apt-get >/dev/null 2>&1; then
    echo "ERROR: This script requires a Debian-based system (apt-get not found)."
    exit 1
fi

need_pkg() {
    dpkg -s "$1" >/dev/null 2>&1
}

echo "[1/4] Checking build dependencies..."
BUILD_DEPS="dpkg-dev fakeroot"
MISSING=""
for pkg in $BUILD_DEPS; do
    if need_pkg "$pkg"; then
        echo "  [OK]   $pkg already installed — skipping."
    else
        echo "  [..]   $pkg not found — will install."
        MISSING="$MISSING $pkg"
    fi
done

if [ -n "$MISSING" ]; then
    echo ""
    echo "  Installing:$MISSING"
    sudo apt-get update -qq
    sudo apt-get install -y $MISSING
fi

echo ""
echo "[2/4] Verifying package tree..."
if [ ! -d "$PKG_ROOT" ]; then
    echo "ERROR: pkgroot/ directory not found next to this script."
    exit 1
fi
echo "  [OK]   pkgroot/ found."

echo ""
echo "[3/4] Setting correct permissions..."
find "$PKG_ROOT" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$PKG_ROOT" -name "*.pyc" -delete 2>/dev/null || true
find "$PKG_ROOT" -type d -exec chmod 755 {} \;
find "$PKG_ROOT" -type f -exec chmod 644 {} \;
chmod 755 "$PKG_ROOT/DEBIAN/postinst" "$PKG_ROOT/DEBIAN/postrm" "$PKG_ROOT/DEBIAN/prerm"
chmod 755 "$PKG_ROOT/usr/bin/hotspot-manager"
chmod 755 "$PKG_ROOT/usr/lib/hotspot-manager/main.py"
chmod 755 "$PKG_ROOT/usr/lib/hotspot-manager/cli.py"
echo "  [OK]   Permissions set."

echo ""
echo "[4/4] Building .deb package..."
rm -f "$OUT_DEB"
fakeroot dpkg-deb --root-owner-group --build "$PKG_ROOT" "$OUT_DEB"

echo ""
echo "================================================"
echo "  ✓ Build complete!"
echo "  Package: $(basename "$OUT_DEB")"
echo ""
echo "  Install with:"
echo "    sudo apt install \"$OUT_DEB\""
echo "  or:"
echo "    sudo dpkg -i \"$OUT_DEB\" && sudo apt-get install -f"
echo "================================================"
