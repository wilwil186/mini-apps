#!/usr/bin/env python3
import gi

gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as AppIndicator
except (ValueError, ImportError):
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator

from gi.repository import Gtk, GLib
import requests
import threading

APP_ID = "crypto-top20-indicator"
INDICATOR_ICON = "utilities-system-monitor-symbolic"
COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&order=market_cap_desc&per_page=20&page=1&sparkline=false"
)
REFRESH_INTERVAL_SECONDS = 120
REQUEST_TIMEOUT_SECONDS = 10


class CryptoIndicator:
    def __init__(self):
        self.indicator = AppIndicator.Indicator.new(
            APP_ID,
            INDICATOR_ICON,
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_title("Top 20 Cripto")

        self.menu = Gtk.Menu()
        self.indicator.set_menu(self.menu)

        self.show_loading_message()
        self.refresh_data()
        GLib.timeout_add_seconds(REFRESH_INTERVAL_SECONDS, self.on_refresh_timer)

    def clear_menu(self):
        for child in self.menu.get_children():
            self.menu.remove(child)

    def show_loading_message(self):
        self.clear_menu()
        loading_item = Gtk.MenuItem(label="Cargando datos de CoinGecko...")
        loading_item.set_sensitive(False)
        self.menu.append(loading_item)
        self.menu.show_all()

    def on_refresh_timer(self):
        self.refresh_data()
        return True

    def refresh_data(self):
        threading.Thread(target=self.fetch_data, daemon=True).start()

    def fetch_data(self):
        try:
            response = requests.get(COINGECKO_URL, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            coins = response.json()
            GLib.idle_add(self.populate_menu, coins)
        except requests.RequestException as error:
            GLib.idle_add(self.show_error_message, str(error))

    def populate_menu(self, coins):
        self.clear_menu()

        title_item = Gtk.MenuItem(label="Top 20 Criptomonedas (CoinGecko)")
        title_item.set_sensitive(False)
        self.menu.append(title_item)
        self.menu.append(Gtk.SeparatorMenuItem())

        for rank, coin in enumerate(coins, start=1):
            symbol = coin.get("symbol", "").upper()
            name = coin.get("name", "")
            price = coin.get("current_price") or 0
            change_24h = coin.get("price_change_percentage_24h") or 0
            entry_label = (
                f"{rank:>2}. {name} ({symbol})  ${price:,.2f}  {change_24h:+.2f}%"
            )
            coin_item = Gtk.MenuItem(label=entry_label)
            coin_item.set_sensitive(False)
            self.menu.append(coin_item)

        self.menu.append(Gtk.SeparatorMenuItem())
        self.append_action_items()
        self.menu.show_all()
        return False

    def show_error_message(self, error_text):
        self.clear_menu()
        error_item = Gtk.MenuItem(label=f"Error al obtener datos: {error_text}")
        error_item.set_sensitive(False)
        self.menu.append(error_item)
        self.menu.append(Gtk.SeparatorMenuItem())
        self.append_action_items()
        self.menu.show_all()
        return False

    def append_action_items(self):
        refresh_item = Gtk.MenuItem(label="Actualizar ahora")
        refresh_item.connect("activate", lambda _: self.refresh_data())
        self.menu.append(refresh_item)

        quit_item = Gtk.MenuItem(label="Salir")
        quit_item.connect("activate", lambda _: Gtk.main_quit())
        self.menu.append(quit_item)


def main():
    CryptoIndicator()
    Gtk.main()


if __name__ == "__main__":
    main()
