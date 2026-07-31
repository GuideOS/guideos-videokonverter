#!/usr/bin/env python3
# =======================================================================
# Titel:    GuideOS Videokonverter – Starter & Ersteinrichtung
# Version:  1.0.1
# Autor:    Nightworker / Gemini
# =======================================================================
import sys
import os
import subprocess
from pathlib import Path

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

CONFIG_DIR = Path.home() / ".config" / "guideos-videokonverter"
CONFIG_FILE = CONFIG_DIR / "layout.conf"
APP_DIR = Path("/usr/lib/guideos-videokonverter")


class LayoutSelectionDialog(Gtk.Dialog):
    """GTK3-Ersteinrichtungsdialog zur Auswahl des Layouts."""
    def __init__(self):
        super().__init__(
            title="Videokonverter – Ersteinrichtung",
            flags=0
        )
        self.set_default_size(480, 220)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)

        # HeaderBar für modernes Aussehen
        header_bar = Gtk.HeaderBar()
        header_bar.set_show_close_button(True)
        header_bar.set_title("GuideOS Videokonverter")
        header_bar.set_subtitle("Layout auswählen")
        self.set_titlebar(header_bar)

        content_area = self.get_content_area()
        content_area.set_spacing(12)
        content_area.set_margin_start(16)
        content_area.set_margin_end(16)
        content_area.set_margin_top(16)
        content_area.set_margin_bottom(16)

        # Infotext
        label = Gtk.Label()
        label.set_markup(
            "<b>Bitte wähle das passende Layout für deine Bildschirmauflösung:</b>"
        )
        label.set_xalign(0)
        content_area.pack_start(label, False, False, 0)

        # Radio-Buttons
        self.radio_q = Gtk.RadioButton.new_with_label(
            None,
            "Querformat (Optimal für Standard- und kleinere Bildschirme - Empfohlen)"
        )
        self.radio_h = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_q,
            "Hochformat (Für große/hohe Bildschirme mit viel vertikaler Fläche)"
        )

        content_area.pack_start(self.radio_q, False, False, 4)
        content_area.pack_start(self.radio_h, False, False, 4)

        # Aktions-Buttons unten
        self.add_button("Abbrechen", Gtk.ResponseType.CANCEL)
        btn_ok = self.add_button("Speichern & Starten", Gtk.ResponseType.OK)
        btn_ok.get_style_context().add_class("suggested-action")

        self.show_all()

    def get_selected_layout(self):
        return "q" if self.radio_q.get_active() else "h"


def show_error_dialog(message):
    """Zeigt eine Fehlermeldung via GTK an."""
    dialog = Gtk.MessageDialog(
        flags=0,
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK,
        text="Fehler beim Starten"
    )
    dialog.format_secondary_text(message)
    dialog.run()
    dialog.destroy()


def main():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Beim ersten Start: Auswahldialog anzeigen
    if not CONFIG_FILE.exists():
        dialog = LayoutSelectionDialog()
        response = dialog.run()
        selected_layout = dialog.get_selected_layout()
        dialog.destroy()

        if response == Gtk.ResponseType.OK:
            try:
                CONFIG_FILE.write_text(f"{selected_layout}\n")
            except Exception as e:
                show_error_dialog(f"Konnte Konfiguration nicht speichern:\n{e}")
                sys.exit(1)
        else:
            # Benutzer hat abgebrochen
            sys.exit(0)

    # 2. Gespeichertes Layout auslesen
    try:
        saved_layout = CONFIG_FILE.read_text().strip()
    except Exception as e:
        show_error_dialog(f"Fehler beim Lesen der Konfiguration:\n{e}")
        sys.exit(1)

    # 3. Arbeitsverzeichnis wechseln, damit Python lokale Ressourcen findet
    if APP_DIR.exists():
        os.chdir(APP_DIR)
    else:
        # Fallback auf den Ordner, in dem dieses Starter-Skript liegt
        os.chdir(Path(__file__).parent)

    # 4. Zielskript bestimmen
    script_name = (
        "guideos-videokonverter-q.py"
        if saved_layout == "q"
        else "guideos-videokonverter-h.py"
    )
    script_path = Path.cwd() / script_name

    # 5. Zielskript als unabhängigen Prozess starten und Start-Skript beenden
    if script_path.exists():
        cmd = [sys.executable, str(script_path)] + sys.argv[1:]
        # Popen startet den Prozess im Hintergrund ohne zu blockieren
        subprocess.Popen(cmd)
        # Das Starter-Skript beendet sich sofort sauber selbst
        sys.exit(0)
    else:
        show_error_dialog(f"Die Datei wurde nicht gefunden:\n{script_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
