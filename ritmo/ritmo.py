#!/usr/bin/env python3
"""
Ritmo — reproductor de música de YouTube para escritorio Linux.

Inspirado en SimpMusic (https://github.com/maxrave-dev/SimpMusic):
reproduce música de YouTube sin anuncios (extrae el stream de audio
directo con yt-dlp, nunca carga el reproductor web), con favoritos,
historial, descargas, letras sincronizadas (LRCLIB), radio infinita
(Mix de YouTube), SponsorBlock y temporizador de sueño.

Dependencias: python3-gi, gir1.2-gtk-3.0, GStreamer (playbin),
              yt-dlp, python3-requests, ffmpeg (para descargas).

Uso:  python3 ritmo.py
"""

import os
import re
import json
import sqlite3
import threading
from dataclasses import dataclass, field

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gst, GdkPixbuf, Pango  # noqa: E402

import requests  # noqa: E402
import yt_dlp  # noqa: E402

APP_NAME = "Ritmo"
VERSION = "1.0.0"

DATA_DIR = os.path.join(GLib.get_user_data_dir(), "ritmo")
DB_PATH = os.path.join(DATA_DIR, "ritmo.db")
MUSIC_DIR = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_MUSIC) or os.path.expanduser("~/Música")
DOWNLOAD_DIR = os.path.join(MUSIC_DIR, "Ritmo")

SEARCH_LIMIT = 20
RADIO_LIMIT = 25
LRCLIB_API = "https://lrclib.net/api/get"
SPONSORBLOCK_API = "https://sponsor.ajay.app/api/skipSegments"
SPONSORBLOCK_CATEGORIES = ["sponsor", "selfpromo", "music_offtopic"]
HTTP_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

@dataclass
class Track:
    video_id: str
    title: str
    artist: str = ""
    duration: int = 0  # segundos; 0 = desconocida

    @property
    def thumb_url(self):
        return f"https://i.ytimg.com/vi/{self.video_id}/mqdefault.jpg"

    @property
    def watch_url(self):
        return f"https://www.youtube.com/watch?v={self.video_id}"


def fmt_time(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Base de datos (favoritos + historial)
# ---------------------------------------------------------------------------

class Library:
    """Persistencia en SQLite. Cada operación abre su propia conexión,
    así es seguro llamarla desde cualquier hilo."""

    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        with self._conn() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS tracks (
                    video_id TEXT PRIMARY KEY,
                    title    TEXT NOT NULL,
                    artist   TEXT DEFAULT '',
                    duration INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS favorites (
                    video_id TEXT PRIMARY KEY REFERENCES tracks(video_id),
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS history (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id  TEXT REFERENCES tracks(video_id),
                    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def _conn(self):
        return sqlite3.connect(self.path)

    def _upsert_track(self, db, t: Track):
        db.execute(
            "INSERT INTO tracks (video_id, title, artist, duration) VALUES (?,?,?,?) "
            "ON CONFLICT(video_id) DO UPDATE SET title=excluded.title, "
            "artist=excluded.artist, duration=excluded.duration",
            (t.video_id, t.title, t.artist, t.duration),
        )

    def add_favorite(self, t: Track):
        with self._conn() as db:
            self._upsert_track(db, t)
            db.execute("INSERT OR IGNORE INTO favorites (video_id) VALUES (?)", (t.video_id,))

    def remove_favorite(self, video_id):
        with self._conn() as db:
            db.execute("DELETE FROM favorites WHERE video_id=?", (video_id,))

    def is_favorite(self, video_id):
        with self._conn() as db:
            row = db.execute("SELECT 1 FROM favorites WHERE video_id=?", (video_id,)).fetchone()
        return row is not None

    def favorites(self):
        with self._conn() as db:
            rows = db.execute(
                "SELECT t.video_id, t.title, t.artist, t.duration FROM favorites f "
                "JOIN tracks t USING (video_id) ORDER BY f.added_at DESC"
            ).fetchall()
        return [Track(*r) for r in rows]

    def add_history(self, t: Track):
        with self._conn() as db:
            self._upsert_track(db, t)
            db.execute("INSERT INTO history (video_id) VALUES (?)", (t.video_id,))

    def history(self, limit=200):
        with self._conn() as db:
            rows = db.execute(
                "SELECT t.video_id, t.title, t.artist, t.duration, MAX(h.id) AS last "
                "FROM history h JOIN tracks t USING (video_id) "
                "GROUP BY t.video_id ORDER BY last DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [Track(*r[:4]) for r in rows]


# ---------------------------------------------------------------------------
# Servicios de red (se llaman siempre desde hilos de fondo)
# ---------------------------------------------------------------------------

def _ydl(extra=None):
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
    if extra:
        opts.update(extra)
    return yt_dlp.YoutubeDL(opts)


def _entry_to_track(e):
    return Track(
        video_id=e.get("id") or "",
        title=e.get("title") or "(sin título)",
        artist=e.get("channel") or e.get("uploader") or "",
        duration=int(e.get("duration") or 0),
    )


def search_youtube(query):
    """Busca en YouTube y devuelve una lista de Track."""
    with _ydl({"extract_flat": True}) as ydl:
        info = ydl.extract_info(f"ytsearch{SEARCH_LIMIT}:{query}", download=False)
    return [_entry_to_track(e) for e in info.get("entries") or [] if e.get("id")]


# Configuraciones de extracción, en orden de preferencia. Las versiones
# viejas de yt-dlp no obtienen formatos con el cliente web de YouTube,
# así que se recurre al cliente "android" (da audio AAC dentro del
# formato 18; playbin descarta el vídeo).
_STREAM_CONFIGS = [
    {"format": "bestaudio/best"},
    {"format": "bestaudio/best",
     "extractor_args": {"youtube": {"player_client": ["android"]}}},
]


def resolve_stream(video_id):
    """Devuelve (url_de_audio, Track con metadatos completos).
    Aquí está el «bloqueo de anuncios»: se extrae el stream de audio
    directo, sin pasar por el reproductor web de YouTube."""
    info = None
    last_err = None
    for cfg in _STREAM_CONFIGS:
        try:
            with _ydl(cfg) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            break
        except yt_dlp.utils.DownloadError as exc:
            last_err = exc
    if info is None:
        raise last_err
    track = Track(
        video_id=video_id,
        title=info.get("title") or "(sin título)",
        artist=info.get("artist") or info.get("channel") or info.get("uploader") or "",
        duration=int(info.get("duration") or 0),
    )
    return info["url"], track


def fetch_radio(video_id):
    """Radio infinita: canciones del Mix de YouTube (lista RD<id>)."""
    url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
    with _ydl({"extract_flat": True, "noplaylist": False, "playlistend": RADIO_LIMIT}) as ydl:
        info = ydl.extract_info(url, download=False)
    tracks = [_entry_to_track(e) for e in info.get("entries") or [] if e.get("id")]
    return [t for t in tracks if t.video_id != video_id]


def _clean_title(title):
    """Quita el ruido típico de los títulos de YouTube para casar mejor
    con LRCLIB: paréntesis/corchetes, «ft./feat.», «Video Oficial», etc."""
    t = re.sub(r"[\(\[][^)\]]*[\)\]]", " ", title)
    t = re.sub(r"(?i)\b(ft\.?|feat\.?)\s.*", " ", t)
    t = re.sub(r"(?i)\b(official|oficial|video|audio|lyrics?|letra|hd|4k)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip(" -–|")


def _parse_lrc(synced):
    lines = []
    for m in re.finditer(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)", synced):
        ts = int(m.group(1)) * 60 + float(m.group(2))
        lines.append((ts, m.group(3).strip()))
    return sorted(lines) or None


def fetch_lyrics(track: Track):
    """Letras sincronizadas desde LRCLIB (misma fuente que SimpMusic).
    Devuelve una lista [(segundos, línea)] o None."""
    title = _clean_title(track.title)
    # 1) Coincidencia exacta título+artista(+duración)
    params = {"track_name": title, "artist_name": track.artist}
    if track.duration:
        params["duration"] = track.duration
    r = requests.get(LRCLIB_API, params=params, timeout=HTTP_TIMEOUT)
    if r.status_code == 200 and r.json().get("syncedLyrics"):
        return _parse_lrc(r.json()["syncedLyrics"])
    # 2) Búsqueda difusa; se toma el primer resultado con letra sincronizada
    #    y duración parecida (±10 s) si se conoce
    r = requests.get(f"{LRCLIB_API.rsplit('/', 1)[0]}/search",
                     params={"q": f"{title} {track.artist}".strip()}, timeout=HTTP_TIMEOUT)
    if r.status_code != 200:
        return None
    for hit in r.json():
        if not hit.get("syncedLyrics"):
            continue
        if track.duration and abs(hit.get("duration", 0) - track.duration) > 10:
            continue
        return _parse_lrc(hit["syncedLyrics"])
    return None


def fetch_sponsor_segments(video_id):
    """Segmentos de SponsorBlock a saltar: [(inicio, fin)] en segundos."""
    r = requests.get(
        SPONSORBLOCK_API,
        params={"videoID": video_id, "categories": json.dumps(SPONSORBLOCK_CATEGORIES)},
        timeout=HTTP_TIMEOUT,
    )
    if r.status_code != 200:
        return []
    return [tuple(seg["segment"]) for seg in r.json()]


def download_track(track: Track, progress_cb):
    """Descarga el audio a DOWNLOAD_DIR con metadatos y carátula embebidos."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                progress_cb(d.get("downloaded_bytes", 0) / total)
        elif d["status"] == "finished":
            progress_cb(1.0)

    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s [%(id)s].%(ext)s"),
        "progress_hooks": [hook],
        "writethumbnail": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"},
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ],
    }
    last_err = None
    for cfg in _STREAM_CONFIGS:
        try:
            with _ydl({**opts, **cfg}) as ydl:
                ydl.download([track.watch_url])
            return
        except yt_dlp.utils.DownloadError as exc:
            last_err = exc
    raise last_err


# ---------------------------------------------------------------------------
# Reproductor GStreamer
# ---------------------------------------------------------------------------

class Player:
    """Envoltorio de playbin. Emite callbacks (en el hilo GTK) para
    fin de pista, cambio de estado y errores."""

    def __init__(self, on_eos, on_error):
        Gst.init(None)
        self.playbin = Gst.ElementFactory.make("playbin", "ritmo")
        # Solo audio + volumen por software: si el stream trae vídeo
        # (p. ej. formato 18 del cliente android), no abrir ventana.
        self.playbin.set_property("flags", 0x02 | 0x10)
        bus = self.playbin.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", lambda *_: on_eos())
        bus.connect("message::error", self._on_error)
        self._on_error_cb = on_error

    def _on_error(self, _bus, msg):
        err, _dbg = msg.parse_error()
        self.stop()
        self._on_error_cb(err.message)

    def play_uri(self, uri):
        self.playbin.set_state(Gst.State.NULL)
        self.playbin.set_property("uri", uri)
        self.playbin.set_state(Gst.State.PLAYING)

    def toggle_pause(self):
        """Alterna pausa. Devuelve True si quedó reproduciendo."""
        _ok, state, _pending = self.playbin.get_state(0)
        if state == Gst.State.PLAYING:
            self.playbin.set_state(Gst.State.PAUSED)
            return False
        self.playbin.set_state(Gst.State.PLAYING)
        return True

    def pause(self):
        self.playbin.set_state(Gst.State.PAUSED)

    def stop(self):
        self.playbin.set_state(Gst.State.NULL)

    def seek(self, seconds):
        self.playbin.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            int(seconds * Gst.SECOND),
        )

    def position(self):
        ok, pos = self.playbin.query_position(Gst.Format.TIME)
        return pos / Gst.SECOND if ok else None

    def duration(self):
        ok, dur = self.playbin.query_duration(Gst.Format.TIME)
        return dur / Gst.SECOND if ok else None

    def set_volume(self, value):
        self.playbin.set_property("volume", value)

    def is_playing(self):
        _ok, state, _pending = self.playbin.get_state(0)
        return state == Gst.State.PLAYING


# ---------------------------------------------------------------------------
# Utilidades GTK
# ---------------------------------------------------------------------------

def run_async(fn, callback, *args):
    """Ejecuta fn(*args) en un hilo; llama callback(result, error) en el
    hilo principal de GTK."""

    def worker():
        try:
            result = fn(*args)
            GLib.idle_add(callback, result, None)
        except Exception as exc:  # noqa: BLE001 — se muestra al usuario
            GLib.idle_add(callback, None, exc)

    threading.Thread(target=worker, daemon=True).start()


class ThumbCache:
    """Descarga miniaturas en segundo plano y las cachea como Pixbuf."""

    def __init__(self):
        self._cache = {}

    def get(self, url, size, callback):
        key = (url, size)
        if key in self._cache:
            callback(self._cache[key])
            return

        def fetch(_url):
            data = requests.get(_url, timeout=HTTP_TIMEOUT).content
            loader = GdkPixbuf.PixbufLoader()
            loader.write(data)
            loader.close()
            pix = loader.get_pixbuf()
            w, h = pix.get_width(), pix.get_height()
            scale = size / min(w, h)
            return pix.scale_simple(int(w * scale), int(h * scale), GdkPixbuf.InterpType.BILINEAR)

        def done(pix, err):
            if pix and not err:
                self._cache[key] = pix
                callback(pix)

        run_async(fetch, done, url)


THUMBS = ThumbCache()


class TrackRow(Gtk.ListBoxRow):
    """Fila de la lista: miniatura, título/artista, duración y acciones."""

    def __init__(self, track: Track, app, removable_fav=False):
        super().__init__()
        self.track = track
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(8)
        box.set_margin_end(8)

        self.thumb = Gtk.Image.new_from_icon_name("audio-x-generic", Gtk.IconSize.DIALOG)
        self.thumb.set_size_request(64, 48)
        box.pack_start(self.thumb, False, False, 0)
        THUMBS.get(track.thumb_url, 48, self._set_thumb)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label=track.title, xalign=0)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        artist = Gtk.Label(label=track.artist, xalign=0)
        artist.set_ellipsize(Pango.EllipsizeMode.END)
        artist.get_style_context().add_class("dim-label")
        labels.pack_start(title, False, False, 0)
        labels.pack_start(artist, False, False, 0)
        box.pack_start(labels, True, True, 0)

        if track.duration:
            dur = Gtk.Label(label=fmt_time(track.duration))
            dur.get_style_context().add_class("dim-label")
            box.pack_start(dur, False, False, 0)

        self.fav_btn = Gtk.Button()
        self.fav_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.fav_btn.set_tooltip_text("Quitar de favoritos" if removable_fav else "Añadir a favoritos")
        self._update_fav_icon(app.library.is_favorite(track.video_id))
        self.fav_btn.connect("clicked", lambda *_: app.toggle_favorite(self))
        box.pack_start(self.fav_btn, False, False, 0)

        dl_btn = Gtk.Button.new_from_icon_name("folder-download-symbolic", Gtk.IconSize.BUTTON)
        dl_btn.set_relief(Gtk.ReliefStyle.NONE)
        dl_btn.set_tooltip_text("Descargar")
        dl_btn.connect("clicked", lambda *_: app.download(track))
        box.pack_start(dl_btn, False, False, 0)

        self.add(box)
        self.show_all()

    def _set_thumb(self, pixbuf):
        self.thumb.set_from_pixbuf(pixbuf)

    def _update_fav_icon(self, is_fav):
        icon = "starred-symbolic" if is_fav else "non-starred-symbolic"
        img = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
        self.fav_btn.set_image(img)


# ---------------------------------------------------------------------------
# Aplicación principal
# ---------------------------------------------------------------------------

class RitmoApp:
    def __init__(self):
        self.library = Library(DB_PATH)
        self.player = Player(on_eos=self._on_track_finished, on_error=self._on_player_error)

        # Estado de reproducción
        self.queue = []          # lista de Track
        self.queue_pos = -1
        self.current = None      # Track sonando
        self.radio_mode = True
        self._radio_pending = False
        self._play_token = 0     # invalida resoluciones de stream obsoletas
        self.lyrics = None       # [(ts, línea)] de la pista actual
        self._lyrics_index = -1
        self.sponsor_segments = []
        self._sleep_timer_id = None

        self._build_ui()
        GLib.timeout_add(500, self._tick)

    # -- Interfaz ----------------------------------------------------------

    def _build_ui(self):
        self.win = Gtk.Window(title=APP_NAME)
        self.win.set_default_size(1000, 680)
        self.win.set_icon_name("multimedia-player")
        self.win.connect("destroy", self.quit)

        header = Gtk.HeaderBar(title=APP_NAME, subtitle="Música de YouTube sin anuncios")
        header.set_show_close_button(True)
        self.header = header
        self.win.set_titlebar(header)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Buscar canciones, artistas…")
        self.search_entry.set_size_request(320, -1)
        self.search_entry.connect("activate", self._on_search)
        header.pack_start(self.search_entry)

        header.pack_end(self._build_sleep_menu())

        # Estructura: sidebar | lista principal | panel de letras
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.win.add(outer)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        outer.pack_start(body, True, True, 0)

        self.sidebar = Gtk.StackSidebar()
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.sidebar.set_stack(self.stack)
        self.sidebar.set_size_request(150, -1)
        body.pack_start(self.sidebar, False, False, 0)
        body.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)
        body.pack_start(self.stack, True, True, 0)

        self.search_list = self._make_track_list("search", "Buscar")
        self.fav_list = self._make_track_list("favorites", "Favoritos")
        self.hist_list = self._make_track_list("history", "Historial")
        self.queue_list = self._make_track_list("queue", "Cola")
        self._build_downloads_page()
        self.stack.connect("notify::visible-child-name", lambda *_: self._refresh_current_page())

        # Panel lateral de letras
        self.lyrics_revealer = Gtk.Revealer()
        self.lyrics_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        lyr_scroll = Gtk.ScrolledWindow()
        lyr_scroll.set_size_request(300, -1)
        self.lyrics_view = Gtk.TextView(editable=False, cursor_visible=False)
        self.lyrics_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.lyrics_view.set_margin_start(12)
        self.lyrics_view.set_margin_end(12)
        self.lyrics_view.set_margin_top(12)
        buf = self.lyrics_view.get_buffer()
        self.lyrics_tag = buf.create_tag("current", weight=Pango.Weight.BOLD, scale=1.15)
        lyr_scroll.add(self.lyrics_view)
        self.lyrics_revealer.add(lyr_scroll)
        body.pack_start(self.lyrics_revealer, False, False, 0)

        outer.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
        outer.pack_start(self._build_player_bar(), False, False, 0)

        self.win.show_all()
        self.lyrics_revealer.set_reveal_child(False)

    def _make_track_list(self, name, title):
        scroll = Gtk.ScrolledWindow()
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        listbox.connect("row-activated", self._on_row_activated, name)
        scroll.add(listbox)
        self.stack.add_titled(scroll, name, title)
        return listbox

    def _build_downloads_page(self):
        scroll = Gtk.ScrolledWindow()
        self.dl_list = Gtk.ListBox()
        self.dl_list.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.add(self.dl_list)
        self.stack.add_titled(scroll, "downloads", "Descargas")

    def _build_sleep_menu(self):
        btn = Gtk.MenuButton()
        btn.set_image(Gtk.Image.new_from_icon_name("alarm-symbolic", Gtk.IconSize.BUTTON))
        btn.set_tooltip_text("Temporizador de sueño")
        menu = Gtk.Menu()
        for label, minutes in [("Desactivado", 0), ("15 minutos", 15), ("30 minutos", 30), ("60 minutos", 60)]:
            item = Gtk.MenuItem(label=label)
            item.connect("activate", self._on_sleep_timer, minutes)
            menu.append(item)
        menu.show_all()
        btn.set_popup(menu)
        return btn

    def _build_player_bar(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for setter in (bar.set_margin_top, bar.set_margin_bottom, bar.set_margin_start, bar.set_margin_end):
            setter(8)

        self.now_thumb = Gtk.Image.new_from_icon_name("audio-x-generic", Gtk.IconSize.DIALOG)
        bar.pack_start(self.now_thumb, False, False, 0)

        now = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.now_title = Gtk.Label(label="Nada en reproducción", xalign=0)
        self.now_title.set_ellipsize(Pango.EllipsizeMode.END)
        self.now_title.set_max_width_chars(28)
        self.now_artist = Gtk.Label(label="", xalign=0)
        self.now_artist.set_ellipsize(Pango.EllipsizeMode.END)
        self.now_artist.get_style_context().add_class("dim-label")
        now.pack_start(self.now_title, False, False, 0)
        now.pack_start(self.now_artist, False, False, 0)
        bar.pack_start(now, False, False, 0)

        prev_btn = Gtk.Button.new_from_icon_name("media-skip-backward-symbolic", Gtk.IconSize.BUTTON)
        prev_btn.connect("clicked", lambda *_: self.previous_track())
        self.play_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        self.play_btn.connect("clicked", self._on_play_pause)
        next_btn = Gtk.Button.new_from_icon_name("media-skip-forward-symbolic", Gtk.IconSize.BUTTON)
        next_btn.connect("clicked", lambda *_: self.next_track())
        for b in (prev_btn, self.play_btn, next_btn):
            b.set_relief(Gtk.ReliefStyle.NONE)
            bar.pack_start(b, False, False, 0)

        self.pos_label = Gtk.Label(label="0:00")
        bar.pack_start(self.pos_label, False, False, 0)
        self.seek_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.seek_scale.set_draw_value(False)
        self._seek_handler = self.seek_scale.connect("change-value", self._on_seek)
        bar.pack_start(self.seek_scale, True, True, 0)
        self.dur_label = Gtk.Label(label="0:00")
        bar.pack_start(self.dur_label, False, False, 0)

        self.radio_btn = Gtk.ToggleButton()
        self.radio_btn.set_image(Gtk.Image.new_from_icon_name("media-playlist-shuffle-symbolic", Gtk.IconSize.BUTTON))
        self.radio_btn.set_tooltip_text("Radio infinita: al acabar la cola, sigue con canciones similares (Mix de YouTube)")
        self.radio_btn.set_active(True)
        self.radio_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.radio_btn.connect("toggled", lambda b: setattr(self, "radio_mode", b.get_active()))
        bar.pack_start(self.radio_btn, False, False, 0)

        lyr_btn = Gtk.ToggleButton()
        lyr_btn.set_image(Gtk.Image.new_from_icon_name("format-justify-center-symbolic", Gtk.IconSize.BUTTON))
        lyr_btn.set_tooltip_text("Mostrar letras sincronizadas (LRCLIB)")
        lyr_btn.set_relief(Gtk.ReliefStyle.NONE)
        lyr_btn.connect("toggled", lambda b: self.lyrics_revealer.set_reveal_child(b.get_active()))
        bar.pack_start(lyr_btn, False, False, 0)

        vol = Gtk.VolumeButton()
        vol.set_value(1.0)
        vol.connect("value-changed", lambda _b, v: self.player.set_volume(v))
        bar.pack_start(vol, False, False, 0)
        return bar

    # -- Estado / avisos ----------------------------------------------------

    def status(self, text):
        self.header.set_subtitle(text)

    def _refresh_current_page(self):
        name = self.stack.get_visible_child_name()
        if name == "favorites":
            self._fill_list(self.fav_list, self.library.favorites(), removable_fav=True)
        elif name == "history":
            self._fill_list(self.hist_list, self.library.history())
        elif name == "queue":
            self._fill_list(self.queue_list, self.queue)
        elif name == "downloads":
            self._refresh_downloads()

    def _fill_list(self, listbox, tracks, removable_fav=False):
        for child in listbox.get_children():
            listbox.remove(child)
        for t in tracks:
            listbox.add(TrackRow(t, self, removable_fav=removable_fav))

    def _refresh_downloads(self):
        for child in self.dl_list.get_children():
            self.dl_list.remove(child)
        try:
            files = sorted(os.listdir(DOWNLOAD_DIR))
        except FileNotFoundError:
            files = []
        if not files:
            row = Gtk.Label(label=f"No hay descargas todavía.\nSe guardan en {DOWNLOAD_DIR}", justify=Gtk.Justification.CENTER)
            row.set_margin_top(24)
            self.dl_list.add(row)
        for f in files:
            if f.endswith((".part", ".webp", ".jpg")):
                continue
            row = Gtk.Label(label=f, xalign=0)
            row.set_margin_start(8)
            row.set_margin_top(4)
            self.dl_list.add(row)
        self.dl_list.show_all()

    # -- Búsqueda ------------------------------------------------------------

    def _on_search(self, entry):
        query = entry.get_text().strip()
        if not query:
            return
        self.stack.set_visible_child_name("search")
        self.status(f"Buscando «{query}»…")
        run_async(search_youtube, self._on_search_done, query)

    def _on_search_done(self, tracks, err):
        if err:
            self.status(f"Error al buscar: {err}")
            return
        self._fill_list(self.search_list, tracks)
        self.status(f"{len(tracks)} resultados")

    # -- Reproducción --------------------------------------------------------

    def _on_row_activated(self, listbox, row, page_name):
        """Doble propósito: reproduce la fila y convierte la lista visible
        en la cola de reproducción (como en SimpMusic)."""
        tracks = [r.track for r in listbox.get_children() if isinstance(r, TrackRow)]
        if page_name != "queue":
            self.queue = tracks
        try:
            self.queue_pos = self.queue.index(row.track)
        except ValueError:
            self.queue = tracks
            self.queue_pos = tracks.index(row.track)
        self.play_track(row.track)

    def play_track(self, track: Track):
        self._play_token += 1
        token = self._play_token
        self.current = track
        self.lyrics = None
        self._lyrics_index = -1
        self.sponsor_segments = []
        self.now_title.set_text(track.title)
        self.now_artist.set_text(track.artist)
        THUMBS.get(track.thumb_url, 48, self.now_thumb.set_from_pixbuf)
        self.status(f"Cargando «{track.title}»…")
        self._set_lyrics_text("Buscando letra…")

        run_async(resolve_stream, lambda res, err: self._on_stream_ready(token, res, err), track.video_id)

    def _on_stream_ready(self, token, result, err):
        if token != self._play_token:
            return  # el usuario ya pidió otra canción
        if err:
            self.status(f"No se pudo reproducir: {err}")
            return
        url, full_track = result
        self.current = full_track
        self.now_title.set_text(full_track.title)
        self.now_artist.set_text(full_track.artist)
        self.player.play_uri(url)
        self._set_play_icon(True)
        self.status(f"♪ {full_track.title} — {full_track.artist}")
        self.library.add_history(full_track)

        run_async(fetch_lyrics, lambda r, e: self._on_lyrics(token, r, e), full_track)
        run_async(fetch_sponsor_segments, lambda r, e: self._on_sponsors(token, r, e), full_track.video_id)

        # Si la cola se está acabando y la radio está activa, pedir el Mix
        if self.radio_mode and self.queue_pos >= len(self.queue) - 2 and not self._radio_pending:
            self._radio_pending = True
            run_async(fetch_radio, self._on_radio, full_track.video_id)

    def _on_lyrics(self, token, lines, err):
        if token != self._play_token:
            return
        if err or not lines:
            self.lyrics = None
            self._set_lyrics_text("No se encontró letra sincronizada para esta canción.")
            return
        self.lyrics = lines
        self._set_lyrics_text("\n".join(line for _ts, line in lines))

    def _on_sponsors(self, token, segments, err):
        if token == self._play_token and not err and segments:
            self.sponsor_segments = segments
            self.status(f"SponsorBlock: {len(segments)} segmento(s) se saltarán")

    def _on_radio(self, tracks, err):
        self._radio_pending = False
        if err or not tracks:
            return
        known = {t.video_id for t in self.queue}
        new = [t for t in tracks if t.video_id not in known]
        self.queue.extend(new)
        if self.stack.get_visible_child_name() == "queue":
            self._refresh_current_page()
        if new:
            self.status(f"Radio: {len(new)} canciones añadidas a la cola")

    def next_track(self):
        if self.queue_pos + 1 < len(self.queue):
            self.queue_pos += 1
            self.play_track(self.queue[self.queue_pos])
        elif self.radio_mode and self.current and not self._radio_pending:
            # Cola agotada: esperar a la radio
            self._radio_pending = True
            self.status("Radio: buscando canciones similares…")
            run_async(fetch_radio, self._on_radio_then_play, self.current.video_id)

    def _on_radio_then_play(self, tracks, err):
        self._on_radio(tracks, err)
        if not err and self.queue_pos + 1 < len(self.queue):
            self.queue_pos += 1
            self.play_track(self.queue[self.queue_pos])

    def previous_track(self):
        pos = self.player.position()
        if pos and pos > 5:
            self.player.seek(0)  # como los reproductores clásicos
        elif self.queue_pos > 0:
            self.queue_pos -= 1
            self.play_track(self.queue[self.queue_pos])

    def _on_track_finished(self):
        self.next_track()

    def _on_player_error(self, message):
        self.status(f"Error de reproducción: {message}")
        self._set_play_icon(False)

    def _on_play_pause(self, _btn):
        if not self.current:
            return
        playing = self.player.toggle_pause()
        self._set_play_icon(playing)

    def _set_play_icon(self, playing):
        icon = "media-playback-pause-symbolic" if playing else "media-playback-start-symbolic"
        self.play_btn.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR))

    def _on_seek(self, _scale, _scroll, value):
        self.player.seek(value)
        return False

    # -- Tick periódico: barra de progreso, letras y SponsorBlock ------------

    def _tick(self):
        pos = self.player.position()
        dur = self.player.duration() or (self.current.duration if self.current else 0)
        if pos is not None:
            self.pos_label.set_text(fmt_time(pos))
            self.dur_label.set_text(fmt_time(dur or 0))
            if dur:
                self.seek_scale.handler_block(self._seek_handler)
                self.seek_scale.set_range(0, dur)
                self.seek_scale.set_value(pos)
                self.seek_scale.handler_unblock(self._seek_handler)

            # SponsorBlock: saltar segmentos no musicales
            for start, end in self.sponsor_segments:
                if start <= pos < end - 1:
                    self.player.seek(end)
                    self.status(f"SponsorBlock: saltado hasta {fmt_time(end)}")
                    break

            self._sync_lyrics(pos)
        return True  # mantener el timeout

    def _sync_lyrics(self, pos):
        if not self.lyrics or not self.lyrics_revealer.get_reveal_child():
            return
        index = -1
        for i, (ts, _line) in enumerate(self.lyrics):
            if ts <= pos:
                index = i
            else:
                break
        if index == self._lyrics_index:
            return
        self._lyrics_index = index
        buf = self.lyrics_view.get_buffer()
        buf.remove_tag(self.lyrics_tag, buf.get_start_iter(), buf.get_end_iter())
        if index >= 0:
            start = buf.get_iter_at_line(index)
            end = buf.get_iter_at_line(index + 1)
            buf.apply_tag(self.lyrics_tag, start, end)
            mark = buf.create_mark(None, start, True)
            self.lyrics_view.scroll_to_mark(mark, 0.2, True, 0.0, 0.35)
            buf.delete_mark(mark)

    def _set_lyrics_text(self, text):
        self.lyrics_view.get_buffer().set_text(text)
        self._lyrics_index = -1

    # -- Favoritos / descargas / temporizador ---------------------------------

    def toggle_favorite(self, row: TrackRow):
        t = row.track
        if self.library.is_favorite(t.video_id):
            self.library.remove_favorite(t.video_id)
            row._update_fav_icon(False)
            self.status(f"«{t.title}» quitada de favoritos")
        else:
            self.library.add_favorite(t)
            row._update_fav_icon(True)
            self.status(f"«{t.title}» añadida a favoritos ★")
        if self.stack.get_visible_child_name() == "favorites":
            self._refresh_current_page()

    def download(self, track: Track):
        self.status(f"Descargando «{track.title}»… 0%")

        def progress(frac):
            GLib.idle_add(self.status, f"Descargando «{track.title}»… {int(frac * 100)}%")

        def done(_res, err):
            if err:
                self.status(f"Error al descargar: {err}")
            else:
                self.status(f"Descargada «{track.title}» en {DOWNLOAD_DIR} ✓")
                if self.stack.get_visible_child_name() == "downloads":
                    self._refresh_downloads()

        run_async(download_track, done, track, progress)

    def _on_sleep_timer(self, _item, minutes):
        if self._sleep_timer_id:
            GLib.source_remove(self._sleep_timer_id)
            self._sleep_timer_id = None
        if minutes == 0:
            self.status("Temporizador de sueño desactivado")
            return
        self._sleep_timer_id = GLib.timeout_add_seconds(minutes * 60, self._sleep_fire)
        self.status(f"Temporizador de sueño: la música se pausará en {minutes} min")

    def _sleep_fire(self):
        self._sleep_timer_id = None
        self.player.pause()
        self._set_play_icon(False)
        self.status("Temporizador de sueño: música pausada 💤")
        return False

    # -- Ciclo de vida --------------------------------------------------------

    def quit(self, *_args):
        self.player.stop()
        Gtk.main_quit()

    def run(self):
        Gtk.main()


def main():
    app = RitmoApp()
    app.run()


if __name__ == "__main__":
    main()
