#!/bin/bash
set -e

NAME="mouse-jiggler"
VERSION="1.1.0"
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
chmod 755 "$BUILD_DIR/usr/bin/mouse-jiggler-gui"
chmod 644 "$BUILD_DIR/etc/mouse-jiggler.conf"
chmod 644 "$BUILD_DIR/lib/systemd/system/mouse-jiggler.service"
chmod 644 "$BUILD_DIR/usr/share/man/man1/mouse-jiggler.1"
chmod 644 "$BUILD_DIR/usr/share/applications/mouse-jiggler.desktop"
chmod 644 "$BUILD_DIR/usr/share/icons/hicolor/scalable/apps/mouse-jiggler.svg"
chmod 755 "$BUILD_DIR/DEBIAN/postinst" 2>/dev/null || true
chmod 755 "$BUILD_DIR/DEBIAN/prerm" 2>/dev/null || true

echo "==> Construyendo .deb..."
fakeroot dpkg-deb --build "$BUILD_DIR" "$OUTPUT"
GUI_DEB="${DIR}/${NAME}-gui.deb"
cp "$OUTPUT" "$GUI_DEB"

echo "==> Creando copia mouse-jiggler-gui.deb..."
cp "$OUTPUT" "$GUI_DEB"

echo "==> Limpiando viejos .deb..."
rm -f "$DIR/${NAME}"_*.deb.old 2>/dev/null || true

echo "==> Limpiando..."
rm -rf "$BUILD_DIR"

echo ""
echo "✅ Paquetes creados:"
echo "   $(basename "$DIR/${NAME}_${VERSION}_${ARCH}.deb")"
echo "   mouse-jiggler-gui.deb  (copia para fácil acceso)"
echo "   Tamaño: $(du -h "$DIR/${NAME}_${VERSION}_${ARCH}.deb" | cut -f1)"
echo ""
echo "Para instalar:"
echo "  sudo dpkg -i mouse-jiggler_${VERSION}_${ARCH}.deb"
echo "  sudo apt-get install -f   # instala dependencias"
echo ""
echo "Para usar:"
echo "  mouse-jiggler start        # CLI: iniciar daemon"
echo "  mouse-jiggler status       # CLI: ver estado"
echo "  mouse-jiggler stop         # CLI: detener"
echo "  mouse-jiggler-gui          # GUI: interfaz gráfica"
