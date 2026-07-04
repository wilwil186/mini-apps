# 🎵 Ritmo

Reproductor de música de **YouTube** para escritorio Linux, escrito en
**Python 3 + GTK 3**. Inspirado en [SimpMusic](https://github.com/maxrave-dev/SimpMusic),
pero reimaginado como una mini-app ligera de escritorio.

**Sin anuncios por diseño**: Ritmo nunca carga el reproductor web de YouTube.
Usa `yt-dlp` para extraer el stream de audio directo y lo reproduce con
GStreamer, así que los anuncios simplemente no existen en la cadena de
reproducción.

## ✨ Funciones

- 🏠 **Inicio con recomendaciones** de YouTube Music (el mismo feed que la
  portada de SimpMusic): «Selecciones rápidas», «Vuelve a escucharlo», mixes
  personalizados, playlists de la comunidad… Personalizado con tu cuenta de
  Google conectada; genérico si no. Activar un mix/playlist lo convierte en
  tu cola de reproducción.
- 🔍 **Búsqueda** de canciones y artistas en YouTube.
- 👤 **Cuenta de Google** (como el login de SimpMusic): importa la sesión de tu
  navegador (Firefox, Chrome, Chromium, Brave…) o un `cookies.txt`, y Ritmo
  muestra tus **Me gusta** de YouTube Music, personaliza búsqueda/radio con tu
  cuenta y aprovecha tu suscripción **Premium** si la tienes. La sesión se
  guarda en `~/.config/ritmo/cookies.txt` (solo lectura para tu usuario).
- ▶️ **Streaming sin anuncios** (audio directo vía `yt-dlp` + GStreamer `playbin`).
- ⭐ **Favoritos** persistentes (SQLite en `~/.local/share/ritmo/ritmo.db`).
- 🕘 **Historial** de reproducción (scrobble local, como SimpMusic).
- 📻 **Radio infinita**: al agotarse la cola, sigue con el Mix de YouTube de la
  canción actual (canciones similares, sin cortes).
- ⬇️ **Descargas** en `m4a` con carátula y metadatos embebidos (ffmpeg), a
  `~/Música/Ritmo`.
- 📝 **Letras sincronizadas** de [LRCLIB](https://lrclib.net) (la misma fuente
  que usa SimpMusic), resaltadas línea a línea mientras suena la canción.
- ⏭️ **SponsorBlock**: salta automáticamente segmentos que no son música
  (patrocinios, intros habladas…) usando la API pública de sponsor.ajay.app.
- 💤 **Temporizador de sueño** (15/30/60 min).
- 🎚️ Cola de reproducción, barra de progreso con seek, control de volumen.

## 📦 Dependencias

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 python3-requests yt-dlp ffmpeg \
                 gstreamer1.0-plugins-good gstreamer1.0-plugins-bad
```

> **Nota**: si el `yt-dlp` de tu distro es viejo, Ritmo recurre automáticamente
> al cliente `android` de YouTube (audio AAC ~128 kbps). Con un `yt-dlp`
> actualizado obtendrás mejor calidad de audio, y además es **necesario** para
> que la lista de «Me gusta» de la cuenta de Google se llene (el de Debian
> estable no parsea el formato nuevo de YouTube y devuelve una lista vacía):
> ```bash
> pip install --user --break-system-packages -U "yt-dlp[default]"
> ```
> El extra `[default]` incluye `yt-dlp-ejs`, que junto a **node o deno**
> resuelve los desafíos JavaScript de YouTube — necesario para reproducir con
> la cuenta conectada (sin runtime JS, Ritmo recurre a reproducir sin cookies).

## 📦 Instalación con .deb (recomendado)

```bash
./build.sh                              # necesita fakeroot + dpkg-deb
sudo apt install ./ritmo_1.2.0_all.deb  # instala también las dependencias
```

Queda disponible como `ritmo` en la terminal y como **Ritmo** en el menú de
aplicaciones. `python3-secretstorage` (Recommends) hace falta para importar
cookies de navegadores basados en Chromium.

## 🚀 Uso

```bash
ritmo              # instalado con el .deb
python3 ritmo.py   # o directamente desde el repositorio
```

1. Escribe en la barra de búsqueda y pulsa Enter.
2. Doble clic (o Enter) sobre una canción para reproducirla — la lista visible
   se convierte en tu cola.
3. ⭐ para guardarla en favoritos, ⬇ para descargarla.
4. Con la **radio** activada (botón junto al volumen), la música no se detiene:
   al acabar la cola se añaden canciones similares automáticamente.
5. En la página **Cuenta** de la barra lateral: inicia sesión en `youtube.com`
   con tu navegador, elígelo en el desplegable y pulsa **Conectar con Google**.
   (Con Chrome/Chromium/Brave cierra el navegador antes de conectar; con
   Firefox no hace falta.)

## 📱 ¿Y en Android?

Ritmo es Python + GTK, tecnología de escritorio Linux: no se puede compilar a
APK. El equivalente Android es el propio
[fork de SimpMusic](https://github.com/wilwil186/SimpMusic). En este repo hay
un APK debug universal ya compilado en [`../simpmusic-apk/`](../simpmusic-apk/),
y se puede recompilar con `./gradlew androidApp:assembleDebug` en el fork.

## ⚖️ Aviso

Proyecto personal, educativo y sin ánimo de lucro. Actúa como un navegador
especializado sobre contenido públicamente accesible de YouTube, igual que
un navegador con extensión de bloqueo de anuncios. Todo el crédito conceptual
a [SimpMusic](https://github.com/maxrave-dev/SimpMusic).
