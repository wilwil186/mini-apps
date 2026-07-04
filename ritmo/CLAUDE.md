# CLAUDE.md — ritmo

Guidance for Claude Code when working inside `ritmo/`. See the repo-root
`CLAUDE.md` for monorepo conventions.

## What this is

Single-file Python 3 GTK 3 YouTube music player (`ritmo.py`), inspired by
SimpMusic. Ad blocking is architectural: `yt-dlp` resolves the direct audio
stream URL and GStreamer `playbin` (audio-only flags) plays it — the YouTube
web player is never loaded.

## Run / build / test

```bash
python3 ritmo.py        # run from source (run from THIS directory: `import ritmo`
                        # from the repo root imports the folder, not the module)
./build.sh              # .deb package; needs fakeroot + dpkg-deb → ritmo_<ver>_all.deb
python3 -m py_compile ritmo.py   # quick syntax gate
timeout 10 python3 ritmo.py      # GUI smoke test: exit 124/143 = started fine
```

Version is hardcoded in **three** places — `ritmo.py` (`VERSION`), `build.sh`
(`VERSION=`) and `DEBIAN/control` (`Version:`) — keep them in sync and rebuild
the `.deb` after changes (the built `.deb` is committed to the repo).

Network functions can be tested headless from a Python one-liner
(`ritmo.fetch_home()`, `ritmo.fetch_liked_songs()`, …); they don't need GTK.

## Architecture (all in `ritmo.py`)

- **Threading rule**: network functions are module-level, always called from
  background threads via `run_async(fn, callback, *args)`; the callback runs
  on the GTK main loop via `GLib.idle_add`. Never touch widgets from a thread.
- **`_ydl(extra)`** — yt-dlp factory; automatically adds `cookiefile` when the
  Google account is connected, so every call (search, stream, radio, download)
  is authenticated.
- **Google account** (SimpMusic-style: browser session, no OAuth):
  `google_connect_browser` imports YouTube/Google cookies from an installed
  browser (yt-dlp `cookiesfrombrowser`), `google_connect_cookies_file` imports
  a Netscape `cookies.txt`. Persisted at `~/.config/ritmo/cookies.txt` (0600)
  plus `~/.config/ritmo/account.json` (display name cache).
  `_auth_session(origin)` builds a requests Session with the cookie jar and
  `SAPISIDHASH` Authorization header for innertube calls — the jar must be
  passed whole (a flattened name→value dict makes YouTube treat the request
  as anonymous; this was a real bug).
- **Innertube consumers**: `fetch_account_info` (`account_menu`, name/email;
  raises if `loggedOut`), `fetch_home` (`FEmusic_home` browse with pagination
  continuations → sections of `Track` / `PlaylistItem`).
- **Playback data**: `search_youtube`, `resolve_stream` (tries
  `_STREAM_CONFIGS` in order: web client, then `android` fallback),
  `fetch_radio` (Mix `RD<id>`), `fetch_playlist_tracks` (home playlists/mixes
  → queue), `fetch_liked_songs` (playlist `LM`), `fetch_lyrics` (LRCLIB),
  `fetch_sponsor_segments` (SponsorBlock), `download_track` (m4a, ffmpeg).
- **`Library`** — SQLite (favorites/history) at
  `~/.local/share/ritmo/ritmo.db`; one connection per call → thread-safe.
- **`Player`** — playbin wrapper; a 500 ms tick drives seek bar, synced
  lyrics and SponsorBlock skips.
- **`RitmoApp`** — sidebar stack pages: `home` (default, loads on startup),
  `search`, `favorites`, `history`, `queue`, `downloads`, `account`.
  Activating a row makes the visible list the queue; `PlaylistRow` activation
  resolves the playlist first. `_play_token` discards stale async results.
  Pages refresh lazily on `notify::visible-child-name`
  (`_refresh_current_page`).

## Gotchas

- **Old yt-dlp breaks account features**: Debian stable's yt-dlp can't parse
  YouTube "lockup view models", so liked songs / home playlists come back
  empty *without errors*. Needs a recent yt-dlp
  (`pip install --user --break-system-packages -U yt-dlp`).
- **Chromium-family cookie import needs `python3-secretstorage`** (cookies are
  encrypted with the desktop keyring). `google_connect_browser` raises a
  friendly error if missing; Firefox doesn't need it. It's a `Recommends` in
  `DEBIAN/control`.
- Innertube JSON is parsed defensively with `_find_key` / `_find_all`
  (recursive key search) instead of hardcoded paths — YouTube reshuffles the
  tree often. `_parse_home_item` handles `musicResponsiveListItemRenderer`
  (songs) and `musicTwoRowItemRenderer` (songs/playlists/mixes).
- Texts shown to the user are Spanish; code identifiers and comments follow
  the existing style (Spanish comments).
