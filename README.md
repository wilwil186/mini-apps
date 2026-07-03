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

## Estructura

```
mini-apps/
├── mouse-jiggler/      # Jiggler de ratón con GUI y empaquetado .deb/.rpm
└── crypto-indicator/   # Indicador de bandeja con el Top 20 de criptos
```
