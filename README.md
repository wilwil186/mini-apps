# mini-apps

Colección de pequeñas aplicaciones y utilidades que voy creando para Linux.
Cada carpeta es una app independiente con su propio propósito, código y empaquetado.

## Apps

### 🖱️ mouse-jiggler
Utilidad que **mueve el ratón automáticamente** para evitar que la pantalla se
bloquee o el equipo se suspenda. Solo actúa cuando detecta inactividad real del
usuario, con movimientos aleatorios (no predecibles).

- Soporta **X11** (`xdotool`) y **Wayland** (`ydotool`).
- Detección inteligente de inactividad con `xprintidle`.
- Daemon con PID file y **servicio systemd** incluido.
- **Interfaz gráfica GTK** (`mouse-jiggler-gui`).
- Configurable vía `/etc/mouse-jiggler.conf`, CLI o GUI.
- Empaquetado como `.deb` (y `.spec` para RPM).

Versión actual: **1.1.0**

### 📈 crypto-indicator
Indicador de bandeja del sistema (**AppIndicator / GTK**) que muestra el
**Top 20 de criptomonedas** por capitalización de mercado usando la API de
CoinGecko.

- Precio actual y variación de las últimas 24h de cada moneda.
- Refresco automático cada 2 minutos + opción "Actualizar ahora".
- Escrito en **Python 3** (`PyGObject` + `requests`).

### 🎵 ritmo
Reproductor de **música de YouTube sin anuncios** (GTK), inspirado en
[SimpMusic](https://github.com/maxrave-dev/SimpMusic). Extrae el audio directo
con `yt-dlp` y lo reproduce con GStreamer, así que no hay anuncios en la cadena
de reproducción.

- **Inicio con recomendaciones** de YouTube Music (mixes, selecciones rápidas,
  playlists de la comunidad), personalizado con tu cuenta.
- **Cuenta de Google**: importa la sesión del navegador (como SimpMusic) para
  ver tus «Me gusta», recomendaciones personalizadas y Premium.
- Búsqueda en YouTube, favoritos e historial (SQLite).
- **Radio infinita** con el Mix de YouTube al agotarse la cola.
- **Letras sincronizadas** (LRCLIB) resaltadas en tiempo real.
- **SponsorBlock** (salta segmentos que no son música) y temporizador de sueño.
- Descargas en `m4a` con carátula y metadatos a `~/Música/Ritmo`.
- Escrito en **Python 3** (`PyGObject` + `yt-dlp` + GStreamer).
- Empaquetado como `.deb` (`ritmo/build.sh`).

Versión actual: **1.2.0**

### 📱 simpmusic-apk
APK **debug universal de Android** del
[fork de SimpMusic](https://github.com/wilwil186/SimpMusic) — el equivalente
Android de Ritmo — listo para instalar en el móvil.

## Estructura

```
mini-apps/
├── mouse-jiggler/      # Jiggler de ratón con GUI y empaquetado .deb/.rpm
├── crypto-indicator/   # Indicador de bandeja con el Top 20 de criptos
├── ritmo/              # Reproductor de música de YouTube sin anuncios (.deb)
└── simpmusic-apk/      # APK Android compilado del fork de SimpMusic
```
