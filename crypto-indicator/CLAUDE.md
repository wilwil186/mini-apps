# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

This directory is one app inside the `mini-apps` monorepo (see the root
`CLAUDE.md` for the repo layout). It shares no code with the sibling apps.

## Running / building

Single-file Python 3 app; run from source or build/install the `.deb`:

```bash
python3 crypto_indicator.py     # run from source
./build.sh                      # needs fakeroot + dpkg-deb; outputs crypto-indicator_<ver>_all.deb
sudo apt install ./crypto-indicator_1.0.0_all.deb
```

Packaging follows the ritmo pattern: the app source lives at the top
(`crypto_indicator.py`); `build.sh` copies it into `usr/share/crypto-indicator/`
plus the `usr/` tree (`usr/bin/crypto-indicator` launcher, `.desktop`, scalable
SVG icon) and `etc/xdg/autostart/` (starts on login; `NoDisplay=true` so it
only shows once in app menus). Version is hardcoded in `crypto_indicator.py`
(`VERSION`), `build.sh` and `DEBIAN/control` — keep the three in sync.

Runtime deps (declared in `DEBIAN/control`): `python3-gi`, `python3-requests`,
`gir1.2-ayatanaappindicator3-0.1` (or `gir1.2-appindicator3-0.1`), `gir1.2-gtk-3.0`.
On GNOME Shell the indicator is only visible with the
`gnome-shell-extension-appindicator` extension installed **and enabled**
(`gnome-extensions enable ubuntu-appindicators@ubuntu.com`).

## Architecture

Everything lives in `crypto_indicator.py`. It shows a GTK 3 tray indicator:
the **panel label** shows the Bitcoin price + 24 h change permanently (like the
battery %), and the dropdown menu lists the CoinGecko Top 20, each row with a
**submenu** of details (high/low 24 h, market cap, volume, CoinGecko link).

- **AppIndicator fallback**: at import time it tries `AppIndicator3` and falls
  back to `AyatanaAppIndicator3` (Debian/Ubuntu ship one or the other). Both
  are aliased to `AppIndicator`, so the rest of the code is backend-agnostic.
- **Threading model**: network fetches never run on the GTK main loop.
  `refresh_data` spawns a daemon `threading.Thread` (`fetch_data`), and the
  result — or the error — is marshalled back to the main loop with
  `GLib.idle_add(...)`. Any new network or blocking work must follow the same
  pattern; never touch GTK widgets from a background thread.
- **Offline handling**: `Gio.NetworkMonitor` gates every fetch — when offline
  the app doesn't hit the API, shows a "Sin conexión" notice (keeping the last
  data with a ⚠ stale marker if any) and refreshes immediately on the
  `network-changed` signal when connectivity returns. Failed fetches schedule
  a single 30 s retry (`schedule_retry` guards against stacking timers).
- **Menu as the whole UI**: there is no window. The menu is cleared and fully
  rebuilt on every refresh; data rows/details are insensitive `Gtk.MenuItem`s,
  actionable items are "Ver en CoinGecko…", "Actualizar ahora" and "Salir".
- **Single instance**: an abstract UNIX socket lock (`already_running`)
  prevents duplicates from autostart + manual launch.
- **Config is constants**: API URL, refresh interval (120 s), retry interval
  (30 s) and request timeout live as module-level constants at the top.
- UI strings are in Spanish — keep new user-facing text in Spanish.
