#!/bin/bash
set -e

NAME="mouse-jiggler"
VERSION="1.0.0"
ARCH="amd64"
DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="/tmp/${NAME}-build-$$"
OUTPUT="${DIR}/${NAME}_${VERSION}_${ARCH}.deb"

echo "==> Creando estructura de paquete..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

echo "==> Copiando archivos..."
cp -r "$DIR/DEBIAN" "$BUILD_DIR/"
cp -r "$DIR/usr"    "$BUILD_DIR/"
cp -r "$DIR/etc"    "$BUILD_DIR/"
cp -r "$DIR/lib"    "$BUILD_DIR/"

echo "==> Ajustando permisos..."
chmod 755 "$BUILD_DIR/usr/bin/mouse-jiggler"
chmod 644 "$BUILD_DIR/etc/mouse-jiggler.conf"
chmod 644 "$BUILD_DIR/lib/systemd/system/mouse-jiggler.service"
chmod 644 "$BUILD_DIR/usr/share/man/man1/mouse-jiggler.1"
chmod 755 "$BUILD_DIR/DEBIAN/postinst" 2>/dev/null || true
chmod 755 "$BUILD_DIR/DEBIAN/prerm" 2>/dev/null || true

echo "==> Construyendo .deb..."
fakeroot dpkg-deb --build "$BUILD_DIR" "$OUTPUT"

echo "==> Limpiando..."
rm -rf "$BUILD_DIR"

echo ""
echo "✅ Paquete creado: $(basename "$OUTPUT")"
echo "   Tamaño: $(du -h "$OUTPUT" | cut -f1)"
echo ""
echo "Para instalar:"
echo "  sudo dpkg -i $(basename "$OUTPUT")"
echo "  sudo apt-get install -f   # instala dependencias"
echo ""
echo "Para usar:"
echo "  mouse-jiggler start     # iniciar"
echo "  mouse-jiggler status    # ver estado"
echo "  mouse-jiggler stop      # detener"
