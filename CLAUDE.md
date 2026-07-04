# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

This is a monorepo of small, independent Linux desktop utilities. Each top-level
directory is a self-contained app with its own language, dependencies and
packaging — they share no code. Add new apps as sibling directories.

- `mouse-jiggler/` — Bash daemon that moves the mouse to prevent screen lock/suspend, packaged as `.deb`.
- `crypto-indicator/` — Python 3 GTK tray indicator showing the CoinGecko Top 20 cryptos.
- `ritmo/` — Python 3 GTK ad-free YouTube music player inspired by SimpMusic.

## mouse-jiggler

The whole app lives inside a Debian package tree; the directory layout **is** the
install layout (`usr/`, `etc/`, `lib/`, `DEBIAN/`). Files are placed where they
land on the target system, and `build.sh` copies these dirs verbatim into the
`.deb`.

Key files:
- `usr/bin/mouse-jiggler` — the daemon/CLI (Bash). Subcommands: `start` (background daemon), `stop`, `status`, `run` (foreground, used by systemd).
- `usr/bin/mouse-jiggler-gui` — GTK GUI front-end (PyGObject).
- `etc/mouse-jiggler.conf` — config sourced by the daemon (`INTERVAL`, `THRESHOLD`, `PIXELS`, `VERBOSE`). CLI flags override it.
- `lib/systemd/system/mouse-jiggler.service` — systemd unit (runs `mouse-jiggler run`).

Architecture note: the daemon auto-detects the display server at runtime —
`WAYLAND_DISPLAY` → `ydotool`, else X11 → `xdotool`. Idle detection uses
`xprintidle`; the mouse is only nudged after `THRESHOLD` seconds of real user
inactivity, then moved and moved back so the cursor doesn't drift. Version is
hardcoded in both `build.sh` (`VERSION=`) and `DEBIAN/control` — keep them in sync.

Build the package:
```bash
cd mouse-jiggler && ./build.sh          # needs fakeroot + dpkg-deb; outputs mouse-jiggler_<ver>_amd64.deb
```
Install / run:
```bash
sudo dpkg -i mouse-jiggler_1.1.0_amd64.deb && sudo apt-get install -f
mouse-jiggler start | stop | status     # CLI
mouse-jiggler-gui                        # GUI
```
Runtime deps (declared in `DEBIAN/control`): `xdotool`, `xprintidle`, `python3-gi`; `ydotool` recommended for Wayland.

`mouse-jiggler.spec` is a parallel RPM spec — update it too if changing packaging.

## crypto-indicator

Single-file Python 3 app (`crypto_indicator.py`). No packaging/build step yet;
run directly:
```bash
python3 crypto-indicator/crypto_indicator.py
```
It builds an `AppIndicator` (falling back from `AppIndicator3` to
`AyatanaAppIndicator3`) whose menu is repopulated with CoinGecko market data.
Network calls run on a background `threading.Thread`; results are marshalled back
to the GTK main loop via `GLib.idle_add`. Auto-refresh interval and API URL are
constants at the top of the file.

Deps: `python3-gi`, `gir1.2-appindicator3` (or ayatana), `python3-requests`.

## ritmo

Single-file Python 3 GTK 3 app (`ritmo.py`); run directly or build a `.deb`:
```bash
python3 ritmo/ritmo.py                  # run from source
cd ritmo && ./build.sh                  # needs fakeroot + dpkg-deb; outputs ritmo_<ver>_all.deb
```
Unlike mouse-jiggler, the app source lives at the top (`ritmo.py`); `build.sh`
copies it into `usr/share/ritmo/` inside the package, plus the `usr/` tree
(`usr/bin/ritmo` launcher, `.desktop`, scalable SVG icon) and `DEBIAN/control`.
Version is hardcoded in `ritmo.py` (`VERSION`), `build.sh` and
`DEBIAN/control` — keep the three in sync.

An ad-free YouTube music player inspired by SimpMusic. Ad blocking is
architectural: `yt-dlp` resolves the direct audio stream URL and GStreamer
`playbin` (audio-only flags) plays it — the YouTube web player is never loaded.

Key pieces, all in `ritmo.py`:
- **Network services** (module-level functions, always called from background
  threads via `run_async`, results marshalled with `GLib.idle_add`):
  `search_youtube` (yt-dlp flat search), `resolve_stream` (tries
  `_STREAM_CONFIGS` in order — default web client first, then the `android`
  player client as fallback for old distro yt-dlp versions), `fetch_radio`
  (YouTube Mix `RD<id>` playlist for endless play), `fetch_lyrics` (LRCLIB
  synced lyrics, with title cleanup + fuzzy search fallback),
  `fetch_sponsor_segments` (SponsorBlock), `download_track` (m4a + embedded
  thumbnail/metadata, needs ffmpeg).
- **Google account** (SimpMusic-style login via browser session, no OAuth):
  `google_connect_browser` imports YouTube/Google cookies from an installed
  browser (yt-dlp's `cookiesfrombrowser`), `google_connect_cookies_file`
  imports a Netscape `cookies.txt`; both persist to
  `~/.config/ritmo/cookies.txt` (mode 0600) which `_ydl` then passes as
  `cookiefile` to every yt-dlp call (personalized results, Premium).
  `fetch_account_info` hits the innertube `account_menu` endpoint with a
  `SAPISIDHASH` Authorization header to get name/email;
  `fetch_liked_songs` reads YouTube Music's `LM` playlist. The "Cuenta"
  sidebar page hosts login controls and the liked-songs list.
- **`Library`** — SQLite persistence (favorites, history/local scrobble) at
  `~/.local/share/ritmo/ritmo.db`; opens a connection per call so it is
  thread-safe.
- **`Player`** — GStreamer playbin wrapper; a 500 ms GLib tick drives the seek
  bar, synced-lyrics highlighting and SponsorBlock skips.
- **`RitmoApp`** — GTK window: sidebar stack (search/favorites/history/queue/
  downloads), lyrics side panel (revealer), bottom player bar. Activating a row
  makes the visible list the play queue; a stale-token counter
  (`_play_token`) discards async results from superseded track selections.

Deps: `python3-gi`, `gir1.2-gtk-3.0`, GStreamer plugins (good/bad),
`yt-dlp`, `python3-requests`, `ffmpeg`. Downloads go to `~/Música/Ritmo`.
