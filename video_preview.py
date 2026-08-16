#!/usr/bin/env python3
# =======================================================================
# Titel:     Video Schnittbereich Vorschau (PyQt6 - FFmpeg Engine)
# =======================================================================
import sys
import os
import subprocess
import threading

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton,
    QDialogButtonBox, QScrollArea, QRadioButton, QButtonGroup,
    QApplication, QMainWindow
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QImage, QPixmap


class ThreadSignals(QObject):
    pixmap_ready = pyqtSignal(QPixmap)


class VideoPreviewDialog(QDialog):
    def __init__(self, parent=None, video_path=""):
        super().__init__(parent)
        self.setWindowTitle("Schnittbereich wählen")
        self.setModal(True)

        self.video_path = os.path.abspath(video_path)
        self.duration = self.get_duration()
        self.start_time = 0.0
        self.end_time = self.duration
        self.is_updating = False

        # Threading Signal verbinden
        self.signals = ThreadSignals()
        self.signals.pixmap_ready.connect(self._set_image)

        # 1. Das exakte Seitenverhältnis (Aspect Ratio) des Videos ermitteln
        self.video_aspect_ratio = self.get_video_aspect_ratio()

        # Wir steuern die Qualität über die Ziel-Höhe.
        self.current_target_height = 720

        # UI initialisieren
        self.setup_ui()

        # Erstes Vorschaubild laden
        self.trigger_preview_update()

    def setup_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setSpacing(10)
        vbox.setContentsMargins(12, 12, 12, 12)

        # 1. Auswahl-Leiste (Vorschauqualität)
        button_hbox = QHBoxLayout()
        button_hbox.setSpacing(15)

        lbl_qual = QLabel("Vorschauqualität (Höhe):", self)
        button_hbox.addWidget(lbl_qual)

        self.res_group = QButtonGroup(self)

        self.radio_small = QRadioButton("Klein (360p)", self)
        self.res_group.addButton(self.radio_small, 360)
        button_hbox.addWidget(self.radio_small)

        self.radio_med = QRadioButton("Mittel (720p)", self)
        self.radio_med.setChecked(True)
        self.res_group.addButton(self.radio_med, 720)
        button_hbox.addWidget(self.radio_med)

        self.radio_large = QRadioButton("Groß (1080p)", self)
        self.res_group.addButton(self.radio_large, 1080)
        button_hbox.addWidget(self.radio_large)

        button_hbox.addStretch()
        self.res_group.idToggled.connect(self.on_res_toggled)

        vbox.addLayout(button_hbox)

        # 2. ScrolledWindow / ScrollArea für das Bild
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)

        self.image = QLabel(self)
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidget(self.image)

        # Fenstergröße dynamisch basierend auf dem Seitenverhältnis berechnen
        self.update_window_dimensions()
        vbox.addWidget(self.scroll, stretch=1)

        # 3. Zeit-Label
        self.time_label = QLabel("<b>Position: 00:00:00.00</b>", self)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(self.time_label)

        # 4. Slider (Skaliert in Millisekunden für Präzision)
        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(0, int(self.duration * 1000))
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self.on_slider_moved)
        vbox.addWidget(self.slider)

        # 5. Buttons In/Out
        hbox = QHBoxLayout()
        hbox.setSpacing(10)

        self.btn_in = QPushButton("Start hier (In)", self)
        self.btn_in.clicked.connect(self.set_in_point)
        hbox.addWidget(self.btn_in, stretch=1)

        self.btn_out = QPushButton("Ende hier (Out)", self)
        self.btn_out.clicked.connect(self.set_out_point)
        hbox.addWidget(self.btn_out, stretch=1)

        vbox.addLayout(hbox)

        # 6. Status-Label
        self.status_label = QLabel(f"Bereich: 00:00:00.00 bis {self.format_time(self.duration)}", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(self.status_label)

        # 7. Dialog Standard-Buttons (Abbrechen / Übernehmen)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok, self
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Übernehmen")
        self.button_box.rejected.connect(self.reject)
        self.button_box.accepted.connect(self.accept)
        vbox.addWidget(self.button_box)

    def get_video_aspect_ratio(self):
        """Ermittelt die echten Pixel-Dimensionen und errechnet das Seitenverhältnis (W/H)."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x",
            self.video_path
        ]
        try:
            output = subprocess.check_output(cmd).decode().strip()
            dimensions = output.split('\n')[0]
            width, height = map(int, dimensions.split('x'))
            return width / height
        except Exception as e:
            print(f"Fehler bei der Seitenverhältnis-Ermittlung: {e}")
            return 16.0 / 9.0  # Fallback auf Standard-Querformat

    def update_window_dimensions(self):
        """Berechnet die optimalen Maße für das Widget und passt das Fenster an."""
        calculated_width = int(self.current_target_height * self.video_aspect_ratio)
        calculated_height = self.current_target_height

        max_widget_height = 800
        if calculated_height > max_widget_height:
            scale_factor = max_widget_height / calculated_height
            widget_width = int(calculated_width * scale_factor)
            widget_height = max_widget_height
        else:
            widget_width = calculated_width
            widget_height = calculated_height

        # Setze die Mindestgröße für die Scroll-Area
        self.scroll.setMinimumSize(widget_width, widget_height)

    def on_res_toggled(self, height_id, checked):
        if checked:
            self.current_target_height = height_id
            self.update_window_dimensions()

            # Layout anpassen
            self.adjustSize()
            self.trigger_preview_update()

    def trigger_preview_update(self):
        seconds = self.slider.value() / 1000.0
        if not self.is_updating:
            threading.Thread(target=self.update_preview, args=(seconds,), daemon=True).start()

    def get_duration(self):
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", self.video_path
        ]
        try:
            return float(subprocess.check_output(cmd).decode().strip())
        except Exception as e:
            print(f"Fehler beim Ermitteln der Dauer: {e}")
            return 0.0

    def format_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:05.2f}"

    def on_slider_moved(self, value):
        seconds = value / 1000.0
        self.time_label.setText(f"<b>Position: {self.format_time(seconds)}</b>")
        self.trigger_preview_update()

    def update_preview(self, seconds):
        self.is_updating = True

        video_filter = f"scale=-1:{self.current_target_height}"

        cmd = [
            "ffmpeg", "-ss", str(seconds), "-i", self.video_path, "-frames:v", "1",
            "-vf", video_filter, "-f", "image2pipe", "-vcodec", "mjpeg", "-"
        ]

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            output, _ = proc.communicate()
            if output:
                img = QImage.fromData(output)
                pix = QPixmap.fromImage(img)
                self.signals.pixmap_ready.emit(pix)
        except Exception as e:
            print(f"Preview Error: {e}")
        finally:
            self.is_updating = False

    def _set_image(self, pixmap):
        self.image.setPixmap(pixmap)

    def set_in_point(self):
        self.start_time = self.slider.value() / 1000.0
        if self.start_time > self.end_time:
            self.end_time = self.duration
        self.update_status()

    def set_out_point(self):
        self.end_time = self.slider.value() / 1000.0
        if self.end_time < self.start_time:
            self.start_time = 0.0
        self.update_status()

    def update_status(self):
        self.status_label.setText(
            f"Bereich: {self.format_time(self.start_time)} bis {self.format_time(self.end_time)}"
        )

    def get_range(self):
        return self.start_time, self.end_time


# Standalone Test
if __name__ == "__main__":
    video_file = sys.argv[1] if len(sys.argv) > 1 else "Garten.mp4"

    app = QApplication(sys.argv)
    main_win = QMainWindow()
    main_win.setWindowTitle("Hauptfenster (Test)")
    main_win.resize(300, 100)

    btn = QPushButton("Dialog öffnen", main_win)

    def open_dialog():
        dialog = VideoPreviewDialog(main_win, video_file)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            start, end = dialog.get_range()
            print(f"Gewählter Bereich: {start:.2f}s bis {end:.2f}s")

    btn.clicked.connect(open_dialog)
    main_win.setCentralWidget(btn)
    main_win.show()

    sys.exit(app.exec())
