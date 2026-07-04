#!/usr/bin/env python3
"""Indicador de criptomonedas para la barra del sistema.

Muestra el precio de Bitcoin directamente en el panel y, al desplegar el
menú, el Top 20 de criptomonedas de CoinGecko; cada moneda tiene un submenú
con más detalles. Solo consulta la red cuando hay conexión
(Gio.NetworkMonitor) y reintenta solo cuando vuelve internet.
"""
import socket
import sys
import threading
from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as AppIndicator
except (ValueError, ImportError):
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator

from gi.repository import Gio, GLib, Gtk
import requests

VERSION = "1.0.0"
APP_ID = "crypto-indicator"
INDICATOR_ICON = "crypto-indicator"
COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&order=market_cap_desc&per_page=20&page=1&sparkline=false"
)
COIN_PAGE_URL = "https://www.coingecko.com/es/monedas/{coin_id}"
REFRESH_INTERVAL_SECONDS = 120
RETRY_INTERVAL_SECONDS = 30
REQUEST_TIMEOUT_SECONDS = 10


def already_running():
    """Evita instancias duplicadas (autostart + lanzamiento manual)."""
    global _lock_socket
    _lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        _lock_socket.bind("\0crypto-indicator-lock")
        return False
    except OSError:
        return True


def format_price(value):
    if value >= 1000:
        return f"${value:,.0f}"
    if value >= 1:
        return f"${value:,.2f}"
    return f"${value:.4f}"


def format_big_number(value):
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if value >= threshold:
            return f"${value / threshold:,.2f} {suffix}"
    return f"${value:,.0f}"


class CryptoIndicator:
    def __init__(self):
        self.indicator = AppIndicator.Indicator.new(
            APP_ID,
            INDICATOR_ICON,
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_title("Criptomonedas")
        self.set_panel_label("Cargando…")

        self.menu = Gtk.Menu()
        self.indicator.set_menu(self.menu)

        self.coins = []
        self.last_update = None
        self.fetching = False
        self.retry_pending = False

        self.network = Gio.NetworkMonitor.get_default()
        self.network.connect("network-changed", self.on_network_changed)
        self.was_offline = not self.network.get_network_available()

        self.show_loading_message()
        self.refresh_data()
        GLib.timeout_add_seconds(REFRESH_INTERVAL_SECONDS, self.on_refresh_timer)

    # --- panel -------------------------------------------------------------

    def set_panel_label(self, text):
        self.indicator.set_label(text, text)

    def update_panel_from_coins(self, offline=False):
        if not self.coins:
            self.set_panel_label("Sin conexión" if offline else "…")
            return
        top = self.coins[0]
        price = top.get("current_price") or 0
        change = top.get("price_change_percentage_24h") or 0
        arrow = "▲" if change >= 0 else "▼"
        label = f"₿ {format_price(price)} {arrow}{abs(change):.1f}%"
        if offline:
            label += " ⚠"
        self.set_panel_label(label)

    # --- red / temporizadores ----------------------------------------------

    def on_network_changed(self, _monitor, available):
        if available and self.was_offline:
            self.refresh_data()
        self.was_offline = not available

    def on_refresh_timer(self):
        self.refresh_data()
        return True

    def schedule_retry(self):
        if self.retry_pending:
            return
        self.retry_pending = True

        def retry():
            self.retry_pending = False
            self.refresh_data()
            return False

        GLib.timeout_add_seconds(RETRY_INTERVAL_SECONDS, retry)

    def refresh_data(self):
        if self.fetching:
            return
        if not self.network.get_network_available():
            self.was_offline = True
            self.show_offline()
            return
        self.fetching = True
        threading.Thread(target=self.fetch_data, daemon=True).start()

    def fetch_data(self):
        try:
            response = requests.get(COINGECKO_URL, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            coins = response.json()
            GLib.idle_add(self.on_fetch_ok, coins)
        except requests.RequestException as error:
            GLib.idle_add(self.on_fetch_error, str(error))

    def on_fetch_ok(self, coins):
        self.fetching = False
        self.coins = coins
        self.last_update = datetime.now()
        self.populate_menu()
        self.update_panel_from_coins()
        return False

    def on_fetch_error(self, error_text):
        self.fetching = False
        self.schedule_retry()
        if self.coins:
            # Conservar los últimos datos; solo avisar que están desactualizados.
            self.populate_menu(stale_note="Sin conexión — reintentando…")
            self.update_panel_from_coins(offline=True)
        else:
            self.show_error_message(error_text)
        return False

    # --- menú ---------------------------------------------------------------

    def clear_menu(self):
        for child in self.menu.get_children():
            self.menu.remove(child)

    def add_note(self, text):
        item = Gtk.MenuItem(label=text)
        item.set_sensitive(False)
        self.menu.append(item)

    def show_loading_message(self):
        self.clear_menu()
        self.add_note("Cargando datos de CoinGecko…")
        self.menu.show_all()

    def show_offline(self):
        self.schedule_retry()
        if self.coins:
            self.populate_menu(stale_note="Sin conexión — se actualizará al volver internet")
            self.update_panel_from_coins(offline=True)
            return
        self.set_panel_label("Sin conexión")
        self.clear_menu()
        self.add_note("Sin conexión a internet")
        self.add_note("Se actualizará automáticamente al reconectar")
        self.menu.append(Gtk.SeparatorMenuItem())
        self.append_action_items()
        self.menu.show_all()

    def show_error_message(self, error_text):
        self.set_panel_label("Error ⚠")
        self.clear_menu()
        self.add_note(f"Error al obtener datos: {error_text}")
        self.menu.append(Gtk.SeparatorMenuItem())
        self.append_action_items()
        self.menu.show_all()

    def populate_menu(self, stale_note=None):
        self.clear_menu()

        self.add_note("Top 20 Criptomonedas (CoinGecko)")
        if stale_note:
            self.add_note(f"⚠ {stale_note}")
        elif self.last_update:
            self.add_note(f"Actualizado: {self.last_update:%H:%M}")
        self.menu.append(Gtk.SeparatorMenuItem())

        for rank, coin in enumerate(self.coins, start=1):
            symbol = coin.get("symbol", "").upper()
            name = coin.get("name", "")
            price = coin.get("current_price") or 0
            change_24h = coin.get("price_change_percentage_24h") or 0
            entry_label = (
                f"{rank:>2}. {name} ({symbol})  "
                f"{format_price(price)}  {change_24h:+.2f}%"
            )
            coin_item = Gtk.MenuItem(label=entry_label)
            coin_item.set_submenu(self.build_coin_submenu(coin))
            self.menu.append(coin_item)

        self.menu.append(Gtk.SeparatorMenuItem())
        self.append_action_items()
        self.menu.show_all()

    def build_coin_submenu(self, coin):
        submenu = Gtk.Menu()

        def detail(text):
            item = Gtk.MenuItem(label=text)
            item.set_sensitive(False)
            submenu.append(item)

        price = coin.get("current_price") or 0
        change_24h = coin.get("price_change_percentage_24h") or 0
        high = coin.get("high_24h") or 0
        low = coin.get("low_24h") or 0
        market_cap = coin.get("market_cap") or 0
        volume = coin.get("total_volume") or 0
        rank = coin.get("market_cap_rank") or "—"

        detail(f"Precio: {format_price(price)}")
        detail(f"Cambio 24 h: {change_24h:+.2f}%")
        detail(f"Máx / Mín 24 h: {format_price(high)} / {format_price(low)}")
        detail(f"Cap. de mercado: {format_big_number(market_cap)} (#{rank})")
        detail(f"Volumen 24 h: {format_big_number(volume)}")

        coin_id = coin.get("id")
        if coin_id:
            submenu.append(Gtk.SeparatorMenuItem())
            link_item = Gtk.MenuItem(label="Ver en CoinGecko…")
            url = COIN_PAGE_URL.format(coin_id=coin_id)
            link_item.connect("activate", lambda _w, u=url: self.open_url(u))
            submenu.append(link_item)

        return submenu

    def open_url(self, url):
        Gio.AppInfo.launch_default_for_uri(url, None)

    def append_action_items(self):
        refresh_item = Gtk.MenuItem(label="Actualizar ahora")
        refresh_item.connect("activate", lambda _: self.refresh_data())
        self.menu.append(refresh_item)

        quit_item = Gtk.MenuItem(label="Salir")
        quit_item.connect("activate", lambda _: Gtk.main_quit())
        self.menu.append(quit_item)


def main():
    if already_running():
        print("crypto-indicator ya está en ejecución.", file=sys.stderr)
        sys.exit(0)
    CryptoIndicator()
    Gtk.main()


if __name__ == "__main__":
    main()
