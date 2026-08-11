#!/usr/bin/env python3
# =======================================================================
# Titel:    GuideOS Videokonverter – Starter & Auswähler (PyQt6)
# Version:  2.2.0
# Autor:    Nightworker / Gemini
# =======================================================================
import sys
import os
import subprocess
import argparse
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QRadioButton, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt

CONFIG_DIR = Path.home() / ".config" / "guideos-videokonverter"
CONFIG_FILE = CONFIG_DIR / "layout.conf"
APP_DIR = Path("/usr/lib/guideos-videokonverter")


class LayoutSelectionDialog(QDialog):
    """PyQt6-Dialog zur Auswahl und zum dauerhaften Festlegen des Layouts."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GuideOS Videokonverter – Layout auswählen")
        self.setFixedSize(520, 240)

        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Infotext
        label = QLabel("<b>Bitte wähle das gewünschte Layout:</b>")
        label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(label)

        # Radio-Buttons
        self.radio_q = QRadioButton("Querformat (Optimal für Standard- und kleinere Bildschirme)")
        self.radio_h = QRadioButton("Hochformat (Für große/hohe Bildschirme)")

        layout.addWidget(self.radio_q)
        layout.addWidget(self.radio_h)

        # Aktuelle Konfiguration laden, um Vorauswahl zu treffen
        self.load_current_config()

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_cancel = QPushButton("Abbrechen")
        btn_start_once = QPushButton("Nur diesmal starten")
        btn_save_and_start = QPushButton("Als Standard speichern & Starten")
        btn_save_and_start.setDefault(True)

        btn_cancel.clicked.connect(self.reject)
        btn_start_once.clicked.connect(self.accept)
        btn_save_and_start.clicked.connect(self.save_and_accept)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_start_once)
        btn_layout.addWidget(btn_save_and_start)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def load_current_config(self):
        """Setzt den Radiobutton auf die bisherige Speicherung (falls vorhanden)."""
        if CONFIG_FILE.exists():
            try:
                if CONFIG_FILE.read_text().strip() == "h":
                    self.radio_h.setChecked(True)
                    return
            except Exception:
                pass
        self.radio_q.setChecked(True)

    def save_and_accept(self):
        """Speichert die Auswahl in der Config-Datei und schließt den Dialog."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(f"{self.get_selected_layout()}\n")
        except Exception as e:
            show_error_dialog(f"Konnte Konfiguration nicht speichern:\n{e}")
            return
        self.accept()

    def get_selected_layout(self):
        return "q" if self.radio_q.isChecked() else "h"


def show_error_dialog(message):
    """Zeigt eine Fehlermeldung via PyQt6 an."""
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle("Fehler")
    msg.setText(message)
    msg.exec()


def get_saved_layout():
    """Liest das gespeicherte Layout aus, falls die Config existiert."""
    if CONFIG_FILE.exists():
        try:
            return CONFIG_FILE.read_text().strip()
        except Exception:
            return None
    return None


def main():
    # Prüft direkt in sys.argv, ob --select oder -s vorhanden ist
    force_select = "--select" in sys.argv or "-s" in sys.argv

    # Alle eigenen Parameter rausfiltern, damit sie nicht an das Zielskript übergeben werden
    filtered_args = [arg for arg in sys.argv[1:] if arg not in ("--select", "-s")]

    selected_layout = None

    # Nur wenn --select NICHT vorhanden ist, versuchen wir den Standard zu laden
    if not force_select:
        selected_layout = get_saved_layout()

    # Falls kein Standard existiert ODER --select erzwungen wurde -> Dialog anzeigen
    if not selected_layout:
        app = QApplication(sys.argv)
        dialog = LayoutSelectionDialog()

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_layout = dialog.get_selected_layout()
        else:
            sys.exit(0)

    # -------------------------------------------------------------
    # Skript-Aufruf vorbereiten
    # -------------------------------------------------------------
    if APP_DIR.exists():
        os.chdir(APP_DIR)
    else:
        os.chdir(Path(__file__).parent)

    script_name = (
        "guideos-videokonverter-q.py"
        if selected_layout == "q"
        else "guideos-videokonverter-h.py"
    )
    script_path = Path.cwd() / script_name

    if script_path.exists():
        # Reicht nur die restlichen Argumente weiter
        cmd = [sys.executable, str(script_path)] + filtered_args
        subprocess.Popen(cmd)
        sys.exit(0)
    else:
        if not QApplication.instance():
            app = QApplication(sys.argv)
        show_error_dialog(f"Die Datei wurde nicht gefunden:\n{script_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
