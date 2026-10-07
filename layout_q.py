#!/usr/bin/env python3
# =======================================================================
# Titel:     Linux Video Enkoder (Querformat-Layout Modul)
# Version:   1.2.3
# Autor:     Nightworker / Gemini
# =======================================================================
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QCheckBox, QSpinBox, QProgressBar, QTextEdit,
    QFrame, QTabWidget, QStackedWidget
)
from PyQt6.QtGui import QIcon

# Verzeichnisstruktur ermitteln
BASE_DIR = Path(__file__).resolve().parent
ICON_DIR = BASE_DIR / "icons"


def load_png_icon(icon_name: str) -> QIcon:
    """Lädt ausschließlich PNG-Grafiken aus dem ICON_DIR.
    Gibt ein leeres QIcon zurück, falls die Datei nicht existiert oder beschädigt ist.
    """
    png_path = ICON_DIR / f"{icon_name}.png"
    if png_path.exists():
        icon = QIcon(str(png_path))
        if not icon.isNull():
            return icon
    return QIcon()


def build_ui_querformat(window):
    """Baut das Tabbed-Querformat-Layout auf."""
    central_widget = QWidget()
    window.setCentralWidget(central_widget)

    outer_vbox = QVBoxLayout(central_widget)
    outer_vbox.setContentsMargins(0, 0, 0, 0)
    outer_vbox.setSpacing(0)

    # Header Bar
    header_bar = QWidget()
    header_bar.setObjectName("headerBar")
    header_layout = QHBoxLayout(header_bar)
    header_layout.setContentsMargins(10, 5, 10, 5)

    title_lbl = QLabel("")
    title_lbl.setObjectName("headerTitle")

    # --- Hilfe-Button (ausschließlich help.png) ---
    window.help_btn = QPushButton()
    window.help_btn.setObjectName("btn-help")
    window.help_btn.setToolTip("Öffnet die Hilfedatei")

    help_icon = load_png_icon("help")
    if not help_icon.isNull():
        window.help_btn.setIcon(help_icon)
    else:
        window.help_btn.setText("Hilfe")

    window.help_btn.clicked.connect(window.open_help_dialog)

    # --- Layout-Button (ausschließlich layout.png) ---
    window.layout_toggle_btn = QPushButton()
    window.layout_toggle_btn.setObjectName("btn-layout")
    window.layout_toggle_btn.setToolTip("Wechselt das Layout")

    layout_icon = load_png_icon("layout")
    if not layout_icon.isNull():
        window.layout_toggle_btn.setIcon(layout_icon)
    else:
        window.layout_toggle_btn.setText("Layout wechseln")

    window.layout_toggle_btn.clicked.connect(window.change_layout)

    header_layout.addWidget(title_lbl)
    header_layout.addStretch()
    header_layout.addWidget(window.help_btn)
    header_layout.addWidget(window.layout_toggle_btn)
    outer_vbox.addWidget(header_bar)

    # Content
    content_widget = QWidget()
    main_hbox = QHBoxLayout(content_widget)
    main_hbox.setContentsMargins(12, 12, 12, 12)
    main_hbox.setSpacing(12)
    outer_vbox.addWidget(content_widget)

    window.notebook = QTabWidget()
    main_hbox.addWidget(window.notebook, stretch=0)

    # TAB 1: Video & GPU
    tab_video = QWidget()
    tab_video_vbox = QVBoxLayout(tab_video)
    tab_video_vbox.setContentsMargins(10, 10, 10, 10)
    tab_video_vbox.setSpacing(10)

    grid_gpu = QGridLayout()
    grid_gpu.addWidget(QLabel("Erkannte GPU:"), 0, 0)
    window.gpu_entry = QLineEdit(window.detect_gpu_short())
    window.gpu_entry.setReadOnly(True)
    grid_gpu.addWidget(window.gpu_entry, 0, 1)

    grid_gpu.addWidget(QLabel("GPU / CPU Wahl:"), 1, 0)
    window.gpu_combo = QComboBox()
    window.gpu_combo.addItems(["Automatisch (empfohlen)", "NVIDIA", "AMD", "Intel", "Software (CPU)"])
    window.gpu_combo.currentIndexChanged.connect(window._check_codec_hardware_support)
    grid_gpu.addWidget(window.gpu_combo, 1, 1)
    tab_video_vbox.addLayout(grid_gpu)

    sep1 = QFrame()
    sep1.setFrameShape(QFrame.Shape.HLine)
    tab_video_vbox.addWidget(sep1)

    grid_vopts = QGridLayout()
    grid_vopts.addWidget(QLabel("Container-Format:"), 0, 0)
    window.format_combo = QComboBox()
    window.format_combo.addItems(["MP4 (.mp4)", "Matroska (.mkv)", "WebM (.webm)"])
    window.format_combo.currentIndexChanged.connect(window.on_format_changed)
    grid_vopts.addWidget(window.format_combo, 0, 1)

    grid_vopts.addWidget(QLabel("Video-Codec:"), 1, 0)
    window.video_combo = QComboBox()
    window.video_combo.addItems(["H.264", "H.265", "VP9", "AV1", "Nur Audio ändern"])
    window.video_combo.currentIndexChanged.connect(window._check_codec_hardware_support)
    grid_vopts.addWidget(window.video_combo, 1, 1)

    grid_vopts.addWidget(QLabel("Dimension:"), 2, 0)
    window.dimension_combo = QComboBox()
    window.dimension_combo.addItems(["Original", "720p (1280x720)", "1080p (1920x1080)", "1440p (2560x1440)", "2160p (3840x2160)"])
    grid_vopts.addWidget(window.dimension_combo, 2, 1)

    grid_vopts.addWidget(QLabel("Nachschärfung (Lanczos):"), 3, 0)
    window.sharpness_combo = QComboBox()
    window.sharpness_combo.addItems(["Keine", "Leicht", "Mittel", "Stark"])
    window.sharpness_combo.setCurrentIndex(0)
    grid_vopts.addWidget(window.sharpness_combo, 3, 1)

    grid_vopts.addWidget(QLabel("Farbtiefe:"), 4, 0)
    window.bit_combo = QComboBox()
    window.bit_combo.addItems(["8-Bit (Standard)", "10-Bit (HDR/High)"])
    grid_vopts.addWidget(window.bit_combo, 4, 1)

    grid_vopts.addWidget(QLabel("Qualität Modus:"), 5, 0)
    window.quality_combo = QComboBox()
    window.quality_combo.addItems(["CQ (Qualitätsbasiert)", "Bitrate (kbit/s)", "Zieldateigröße (MB)"])
    window.quality_combo.currentIndexChanged.connect(window.on_quality_mode_changed)
    grid_vopts.addWidget(window.quality_combo, 5, 1)

    window.quality_mode_label = QLabel("Bitratenmodus:")
    grid_vopts.addWidget(window.quality_mode_label, 6, 0)

    window.mode_stack = QStackedWidget()
    window.empty_widget = QWidget()
    window.bitrate_mode_combo = QComboBox()
    window.bitrate_mode_combo.addItems(["VBR (Variable Bitrate)", "CBR (Konstante Bitrate)"])
    window.mode_stack.addWidget(window.empty_widget)
    window.mode_stack.addWidget(window.bitrate_mode_combo)
    grid_vopts.addWidget(window.mode_stack, 6, 1)

    window.quality_label = QLabel("CRF (0-51):")
    grid_vopts.addWidget(window.quality_label, 7, 0)
    window.quality_entry = QLineEdit("23")
    grid_vopts.addWidget(window.quality_entry, 7, 1)

    grid_vopts.addWidget(QLabel("Analyse-Stufe:"), 8, 0)
    window.preset_combo = QComboBox()
    window.preset_combo.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"])
    window.preset_combo.setCurrentIndex(4)
    grid_vopts.addWidget(window.preset_combo, 8, 1)

    tab_video_vbox.addLayout(grid_vopts)

    window.hw_warning_label = QLabel("")
    window.hw_warning_label.setWordWrap(True)
    tab_video_vbox.addWidget(window.hw_warning_label)
    tab_video_vbox.addStretch()

    window.notebook.addTab(tab_video, "Video & GPU")

    # TAB 2: Audio & Schnitt
    tab_audio = QWidget()
    tab_audio_vbox = QVBoxLayout(tab_audio)
    tab_audio_vbox.setContentsMargins(10, 10, 10, 10)

    grid_audio = QGridLayout()
    grid_audio.addWidget(QLabel("Audioeinstellungen:"), 0, 0)
    window.audio_combo = QComboBox()
    # Angepasste Reihenfolge für volle Kompatibilität mit layout_h.py
    window.audio_combo.addItems(["Original kopieren", "AAC", "Opus (WebM/MKV)", "PCM", "FLAC (mkv)"])
    window.audio_combo.setCurrentIndex(0)
    window.audio_combo.currentIndexChanged.connect(window.on_audio_format_changed)
    grid_audio.addWidget(window.audio_combo, 0, 1)

    grid_audio.addWidget(QLabel("Normalisierung (LUFS):"), 1, 0)
    window.volume_spin = QSpinBox()
    window.volume_spin.setRange(-30, -5)
    window.volume_spin.setValue(-16)
    window.volume_spin.setEnabled(False)
    grid_audio.addWidget(window.volume_spin, 1, 1)

    tab_audio_vbox.addLayout(grid_audio)

    sep2 = QFrame()
    sep2.setFrameShape(QFrame.Shape.HLine)
    tab_audio_vbox.addWidget(sep2)

    window.btn_preview = QPushButton("Schnittbereich festlegen (Vorschau)")
    window.btn_preview.clicked.connect(window.on_open_preview)
    tab_audio_vbox.addWidget(window.btn_preview)

    grid_time = QGridLayout()
    grid_time.addWidget(QLabel("Startzeit:"), 0, 0)
    window.start_entry = QLineEdit("00:00:00")
    grid_time.addWidget(window.start_entry, 0, 1)

    grid_time.addWidget(QLabel("Dauer (sek):"), 1, 0)
    window.duration_limit_entry = QLineEdit("0")
    grid_time.addWidget(window.duration_limit_entry, 1, 1)

    tab_audio_vbox.addLayout(grid_time)
    tab_audio_vbox.addStretch()

    window.notebook.addTab(tab_audio, "Audio & Schnitt")

    # TAB 3: Dateien & Start
    tab_export = QWidget()
    tab_export_vbox = QVBoxLayout(tab_export)
    tab_export_vbox.setContentsMargins(10, 10, 10, 10)

    window.btn_files = QPushButton("Dateien auswählen")
    window.btn_files.clicked.connect(window.on_select_files)
    tab_export_vbox.addWidget(window.btn_files)

    window.btn_remove = QPushButton("Ausgewählte entfernen")
    window.btn_remove.clicked.connect(window.on_remove_selected)
    tab_export_vbox.addWidget(window.btn_remove)

    sep3 = QFrame()
    sep3.setFrameShape(QFrame.Shape.HLine)
    tab_export_vbox.addWidget(sep3)

    tab_export_vbox.addWidget(QLabel("Zielordner (leer -> auto):"))
    window.target_entry = QLineEdit()
    tab_export_vbox.addWidget(window.target_entry)

    window.btn_target = QPushButton("Zielverzeichnis wählen")
    window.btn_target.clicked.connect(window.on_browse_target)
    tab_export_vbox.addWidget(window.btn_target)

    window.save_in_source_chk = QCheckBox("Im Quellverzeichnis speichern")
    tab_export_vbox.addWidget(window.save_in_source_chk)

    window.keep_rotation_chk = QCheckBox("Metadaten-Rotation (9:16) beibehalten")
    window.keep_rotation_chk.setChecked(True)
    tab_export_vbox.addWidget(window.keep_rotation_chk)

    sep4 = QFrame()
    sep4.setFrameShape(QFrame.Shape.HLine)
    tab_export_vbox.addWidget(sep4)

    action_grid = QGridLayout()
    window.start_btn = QPushButton("Konvertieren")
    window.start_btn.setObjectName("btn-start")
    window.start_btn.clicked.connect(window.start_conversion)
    action_grid.addWidget(window.start_btn, 0, 0)

    window.cancel_btn = QPushButton("Abbrechen")
    window.cancel_btn.setEnabled(False)
    window.cancel_btn.clicked.connect(window.cancel_conversion)
    action_grid.addWidget(window.cancel_btn, 0, 1)

    window.exit_btn = QPushButton("Programm beenden")
    window.exit_btn.setObjectName("btn-exit")
    window.exit_btn.clicked.connect(window.close)
    action_grid.addWidget(window.exit_btn, 1, 0)

    window.reset_btn = QPushButton("Reset")
    window.reset_btn.clicked.connect(window.on_reset_all)
    action_grid.addWidget(window.reset_btn, 1, 1)

    tab_export_vbox.addLayout(action_grid)
    tab_export_vbox.addStretch()

    window.notebook.addTab(tab_export, "Dateien & Start")

    # Rechte Spalte
    right_vbox = QVBoxLayout()
    main_hbox.addLayout(right_vbox, stretch=1)

    window.file_list = window.FileListWidget(window)
    right_vbox.addWidget(window.file_list, stretch=1)

    window.file_label = QLabel("Fortschritt: Keine Datei aktiv")
    window.file_label.setProperty("class", "prog-label")
    right_vbox.addWidget(window.file_label)

    window.file_progress = QProgressBar()
    window.file_progress.setRange(0, 100)
    window.file_progress.setValue(0)
    right_vbox.addWidget(window.file_progress)

    window.total_label = QLabel("Gesamtfortschritt")
    window.total_label.setProperty("class", "prog-label")
    right_vbox.addWidget(window.total_label)

    window.total_progress = QProgressBar()
    window.total_progress.setRange(0, 100)
    window.total_progress.setValue(0)
    right_vbox.addWidget(window.total_progress)

    window.log_view = QTextEdit()
    window.log_view.setReadOnly(True)
    right_vbox.addWidget(window.log_view, stretch=1)
