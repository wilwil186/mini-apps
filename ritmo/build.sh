#!/bin/bash
# Construye ritmo_<ver>_all.deb. Necesita fakeroot y dpkg-deb.
# La versión vive aquí, en DEBIAN/control y en ritmo.py (VERSION) — mantenlas en sincronía.
set -e

NAME="ritmo"
VERSION="1.1.0"
ARCH="all"
DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$(mktemp -d "/tmp/${NAME}-build-XXXXXX")"
OUTPUT="${DIR}/${NAME}_${VERSION}_${ARCH}.deb"

trap 'rm -rf "$BUILD_DIR"' EXIT

echo "==> Copiando archivos…"
cp -r "$DIR/DEBIAN" "$BUILD_DIR/"
cp -r "$DIR/usr" "$BUILD_DIR/"
mkdir -p "$BUILD_DIR/usr/share/ritmo"
cp "$DIR/ritmo.py" "$BUILD_DIR/usr/share/ritmo/ritmo.py"
rm -rf "$BUILD_DIR/usr/share/man"   # (sin página man por ahora)

echo "==> Ajustando permisos…"
find "$BUILD_DIR" -type d -exec chmod 755 {} +
find "$BUILD_DIR/usr" -type f -exec chmod 644 {} +
chmod 755 "$BUILD_DIR/usr/bin/ritmo" "$BUILD_DIR/usr/share/ritmo/ritmo.py"

echo "==> Construyendo .deb…"
fakeroot dpkg-deb --build "$BUILD_DIR" "$OUTPUT"

echo ""
echo "✅ Paquete creado: $(basename "$OUTPUT")  ($(du -h "$OUTPUT" | cut -f1))"
echo ""
echo "Para instalar:"
echo "  sudo apt install ./$(basename "$OUTPUT")"
echo ""
echo "Para usar:  ritmo   (o desde el menú de aplicaciones)"
