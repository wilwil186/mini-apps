# 🎵 Ritmo

Reproductor de música de **YouTube** para escritorio Linux, escrito en
**Python 3 + GTK 3**. Inspirado en [SimpMusic](https://github.com/maxrave-dev/SimpMusic),
pero reimaginado como una mini-app ligera de escritorio.

**Sin anuncios por diseño**: Ritmo nunca carga el reproductor web de YouTube.
Usa `yt-dlp` para extraer el stream de audio directo y lo reproduce con
GStreamer, así que los anuncios simplemente no existen en la cadena de
reproducción.

## ✨ Funciones

- 🔍 **Búsqueda** de canciones y artistas en YouTube.
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
> actualizado (`pipx install yt-dlp`) obtendrás los formatos de audio de mayor
> calidad.

## 🚀 Uso

```bash
python3 ritmo.py
```

1. Escribe en la barra de búsqueda y pulsa Enter.
2. Doble clic (o Enter) sobre una canción para reproducirla — la lista visible
   se convierte en tu cola.
3. ⭐ para guardarla en favoritos, ⬇ para descargarla.
4. Con la **radio** activada (botón junto al volumen), la música no se detiene:
   al acabar la cola se añaden canciones similares automáticamente.

## ⚖️ Aviso

Proyecto personal, educativo y sin ánimo de lucro. Actúa como un navegador
especializado sobre contenido públicamente accesible de YouTube, igual que
un navegador con extensión de bloqueo de anuncios. Todo el crédito conceptual
a [SimpMusic](https://github.com/maxrave-dev/SimpMusic).
