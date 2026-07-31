#!/usr/bin/env python3
# =======================================================================
# Titel:    GuideOS Videokonverter (GTK3 Port)
# Version:  1.1.5 (Tabbed-UI Notebook Version)
# Autor:    Nightworker / UI Refactoring: Gemini
# =======================================================================
import sys
import os
sys.dont_write_bytecode = True
import shutil
import subprocess
import threading
import re
import urllib.parse
from pathlib import Path

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
from gi.repository.GdkPixbuf import Pixbuf

# --- Import der Vorschau ---
try:
    from video_preview import VideoPreviewDialog
except ImportError:
    VideoPreviewDialog = None

# -------------------- Hilfsfunktionen & Sicherheit --------------------
def which_bin(name):
    return shutil.which(name) is not None

def detect_gpu_short():
    """Sichere GPU-Erkennung ohne Shell-Interpreter (Schutz vor Shell-Injection)."""
    try:
        res = subprocess.run(["lspci"], capture_output=True, text=True, check=False)
        s = res.stdout.lower()
        if "nvidia" in s: return "NVIDIA"
        if "amd" in s or "ati" in s: return "AMD"
        if "intel" in s: return "INTEL"
    except Exception:
        pass
    return "CPU"

def probe_duration_seconds(path: Path):
    if not which_bin("ffprobe"): return None
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path.resolve())
        ], stderr=subprocess.DEVNULL).decode().strip()
        return float(out) if out else None
    except Exception: return None

def calculate_bitrate_for_target_size(filepath, target_size_mb, audio_bitrate_kbps=192):
    dur = probe_duration_seconds(Path(filepath))
    if not dur or dur <= 0: return None
    total_kbps = (target_size_mb * 8192) / dur
    video_kbps = max(total_kbps - audio_bitrate_kbps, 300)
    return int(video_kbps)

def make_unique_path(path: Path) -> Path:
    path = path.resolve()
    if not path.exists(): return path
    parent, stem, suffix = path.parent, path.stem, path.suffix
    new_stem = f"{stem}_converted"
    candidate = parent / f"{new_stem}{suffix}"
    if not candidate.exists(): return candidate
    i = 1
    while True:
        candidate = parent / f"{new_stem}({i}){suffix}"
        if not candidate.exists(): return candidate
        i += 1

def sanitize_time_str(time_str: str, default: str = "00:00:00") -> str:
    """Prüft, ob der Zeit-String das Format HH:MM:SS oder SS(.ms) einhält."""
    time_str = time_str.strip()
    if re.match(r"^(\d{2}:)?\d{2}:\d{2}(\.\d+)?$", time_str) or re.match(r"^\d+(\.\d+)?$", time_str):
        return time_str
    return default

def sanitize_int(val_str: str, default: int = 0) -> int:
    """Extrahiert sicher Ganzzahlen aus Benutzereingaben."""
    try:
        return abs(int(re.sub(r"[^\d]", "", val_str)))
    except ValueError:
        return default

time_re = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
_encoder_cache = {}

def is_encoder_available(encoder: str) -> bool:
    if encoder in _encoder_cache: return _encoder_cache[encoder]
    try:
        cmd = ["ffmpeg", "-hide_banner", "-encoders"]
        out = subprocess.check_output(cmd).decode()
        res = encoder in out
        _encoder_cache[encoder] = res
        return res
    except: return False

_ENCODER_MAP = {
    "H.264": {"NVIDIA": ["h264_nvenc"], "AMD": ["h264_vaapi"], "INTEL": ["h264_vaapi"], "CPU": ["libx264"]},
    "H.265": {"NVIDIA": ["hevc_nvenc"], "AMD": ["hevc_vaapi"], "INTEL": ["hevc_vaapi"], "CPU": ["libx265"]},
    "VP9":   {"NVIDIA": [], "AMD": ["vp9_vaapi"], "INTEL": ["vp9_vaapi"], "CPU": ["libvpx-vp9"]},
    "AV1":   {"NVIDIA": ["av1_nvenc"], "AMD": ["av1_vaapi"], "INTEL": ["av1_vaapi"], "CPU": ["libsvtav1"]},
}

def _select_encoder(fmt, mode):
    candidates = _ENCODER_MAP.get(fmt, {}).get(mode, [])
    for enc in candidates:
        if is_encoder_available(enc): return enc
    return {"H.264":"libx264", "H.265":"libx265", "VP9":"libvpx-vp9", "AV1":"libsvtav1"}.get(fmt, "libx264")

def _codec_quality_args(codec, qmode, qval_raw, preset, infile):
    args = ["-c:v", codec]

    if "nvenc" in codec:
        p_map = {"ultrafast":"p1","superfast":"p2","veryfast":"p3","faster":"p4","fast":"p5","medium":"p6","slow":"p7"}
        p = p_map.get(preset, "p4")
    elif "libsvtav1" in codec:
        svt_map = {
            "ultrafast": "12", "superfast": "11", "veryfast": "10",
            "faster": "8", "fast": "7", "medium": "6",
            "slow": "4", "slower": "3", "veryslow": "2"
        }
        p = svt_map.get(preset, "6")
    else:
        p = preset

    if "CQ" in qmode:
        qn = str(sanitize_int(qval_raw, default=23))
        if "nvenc" in codec: args += ["-rc", "vbr", "-cq", qn, "-preset", p]
        elif "vaapi" in codec: args += ["-rc_mode", "CQP", "-qp", qn]
        elif "libvpx-vp9" in codec: args += ["-crf", qn, "-b:v", "0"]
        else: args += ["-crf", qn, "-preset", p]
    elif "Bitrate" in qmode:
        kbps = str(sanitize_int(qval_raw, default=5000))
        args += ["-b:v", f"{kbps}k"]
        if "libvpx-vp9" not in codec: args += ["-preset", p]
    else:
        target_mb = sanitize_int(qval_raw, default=700)
        vkbps = calculate_bitrate_for_target_size(infile, target_mb) or 5000
        args += ["-b:v", f"{vkbps}k"]
        if "libvpx-vp9" not in codec: args += ["-preset", p]
    return args

# -------------------- Hauptklasse --------------------

class VideoConverterWindow(Gtk.Window):
    def __init__(self):
        super().__init__()
        # Sehr kompakte, feste Startgröße für moderne Displays:
        self.set_default_size(860, 520)

        # --- Pfad zum Logo ---
        logo_file = Path(__file__).parent / "guideos-logo.png"

        # --- HeaderBar Setup ---
        header_bar = Gtk.HeaderBar()
        header_bar.set_show_close_button(True)

        # Logo zentriert einfügen (falls Datei existiert)
        if logo_file.exists():
            try:
                # Hier die Höhe/Breite deines tatsächlichen Logos anpassen:
                pixbuf = Pixbuf.new_from_file_at_scale(str(logo_file), width=-1, height=36, preserve_aspect_ratio=True)
                header_logo = Gtk.Image.new_from_pixbuf(pixbuf)

                # Platziert dein Logo mittig in der HeaderBar
                header_bar.set_custom_title(header_logo)
            except Exception as e:
                print(f"Konnte Logo nicht laden: {e}")
        else:
            # Falls kein Logo da ist, Fallback auf Text-Titel
            header_bar.set_title("GuideOS Videokonverter")

        # ---------------------------------------------------------
        # NEU: Button zum Wechseln ins Hochformat-Layout (rechts)
        # ---------------------------------------------------------
        btn_layout = Gtk.Button()
        icon_layout = Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        btn_layout.set_image(icon_layout)
        btn_layout.set_tooltip_text("Zum Hochformat-Layout wechseln")
        btn_layout.connect("clicked", self.on_switch_layout)
        header_bar.pack_end(btn_layout)
        # ---------------------------------------------------------

        self.set_titlebar(header_bar)

        self.selected_files = []
        self.current_proc = None
        self.stop_event = threading.Event()

        # --- CSS / Theme Styling inkl. Farbiger HeaderBar ---
        HEADER_BG_COLOR = "#2c3e50"

        css_style = f"""
            #btn-start {{ background-image: none; background-color: #27ae60; color: white; text-shadow: none; }}
            #btn-start:hover {{ background-color: #2ecc71; }}
            #btn-exit {{ background-image: none; background-color: #c0392b; color: white; text-shadow: none; }}
            #btn-exit:hover {{ background-color: #e74c3c; }}
            .prog-label {{ font-weight: bold; margin-top: 5px; }}

            headerbar {{
                background-image: none;
                background-color: {HEADER_BG_COLOR};
                border-color: {HEADER_BG_COLOR};
                min-height: 50px;
            }}

            headerbar .title, headerbar .subtitle {{
                color: #ffffff;
            }}
            headerbar button {{
                color: #ffffff;
            }}
        """

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css_style.encode('utf-8'))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        main_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        main_hbox.set_margin_start(12); main_hbox.set_margin_end(12)
        main_hbox.set_margin_top(12); main_hbox.set_margin_bottom(12)
        self.add(main_hbox)

        # --- Linke Seite: Tabs (Gtk.Notebook) ---
        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)
        main_hbox.pack_start(self.notebook, False, False, 0)

        # ================= TAB 1: Video & Codecs =================
        tab_video = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        tab_video.set_margin_start(10); tab_video.set_margin_end(10)
        tab_video.set_margin_top(10); tab_video.set_margin_bottom(10)

        grid_gpu = Gtk.Grid(column_spacing=10, row_spacing=6)
        tab_video.pack_start(grid_gpu, False, False, 0)

        grid_gpu.attach(Gtk.Label(label="Erkannte GPU:", xalign=0), 0, 0, 1, 1)
        self.gpu_entry = Gtk.Entry(editable=False, text=detect_gpu_short())
        grid_gpu.attach(self.gpu_entry, 1, 0, 1, 1)

        grid_gpu.attach(Gtk.Label(label="GPU / CPU Wahl:", xalign=0), 0, 1, 1, 1)
        self.gpu_combo = self._create_wayland_ready_combo(["Automatisch (empfohlen)", "NVIDIA", "AMD", "Intel", "Software (CPU)"])
        self.gpu_combo.connect("changed", self._check_codec_hardware_support)
        grid_gpu.attach(self.gpu_combo, 1, 1, 1, 1)

        tab_video.pack_start(Gtk.Separator(), False, False, 2)

        grid_vopts = Gtk.Grid(column_spacing=10, row_spacing=6)
        tab_video.pack_start(grid_vopts, False, False, 0)

        grid_vopts.attach(Gtk.Label(label="Container-Format:", xalign=0), 0, 0, 1, 1)
        self.format_combo = self._create_wayland_ready_combo(["MP4 (.mp4)", "Matroska (.mkv)", "WebM (.webm)"])
        self.format_combo.connect("changed", self.on_format_changed)
        grid_vopts.attach(self.format_combo, 1, 0, 1, 1)

        grid_vopts.attach(Gtk.Label(label="Video-Codec:", xalign=0), 0, 1, 1, 1)
        self.video_combo = self._create_wayland_ready_combo(["H.264", "H.265", "VP9", "AV1", "Nur Audio ändern"])
        self.video_combo.connect("changed", self._check_codec_hardware_support)
        grid_vopts.attach(self.video_combo, 1, 1, 1, 1)

        grid_vopts.attach(Gtk.Label(label="Dimension:", xalign=0), 0, 2, 1, 1)
        self.dimension_combo = self._create_wayland_ready_combo(["Original", "720p (1280x720)", "1080p (1920x1080)", "1440p (2560x1440)", "2160p (3840x2160)"])
        grid_vopts.attach(self.dimension_combo, 1, 2, 1, 1)

        grid_vopts.attach(Gtk.Label(label="Farbtiefe:", xalign=0), 0, 3, 1, 1)
        self.bit_combo = self._create_wayland_ready_combo(["8-Bit (Standard)", "10-Bit (HDR/High)"])
        grid_vopts.attach(self.bit_combo, 1, 3, 1, 1)

        grid_vopts.attach(Gtk.Label(label="Qualität Modus:", xalign=0), 0, 4, 1, 1)
        self.quality_combo = self._create_wayland_ready_combo(["CQ (Qualitätsbasiert)","Bitrate (kbit/s)","Zieldateigröße (MB)"])
        self.quality_combo.connect("changed", self.on_quality_mode_changed)
        grid_vopts.attach(self.quality_combo, 1, 4, 1, 1)

        self.quality_label = Gtk.Label(label="CRF Wert (0-51):", xalign=0)
        grid_vopts.attach(self.quality_label, 0, 5, 1, 1)
        self.quality_entry = Gtk.Entry(text="23")
        grid_vopts.attach(self.quality_entry, 1, 5, 1, 1)

        grid_vopts.attach(Gtk.Label(label="Analyse-Stufe:", xalign=0), 0, 6, 1, 1)
        self.preset_combo = self._create_wayland_ready_combo(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"], active_idx=5)
        grid_vopts.attach(self.preset_combo, 1, 6, 1, 1)

        self.hw_warning_label = Gtk.Label(xalign=0)
        self.hw_warning_label.set_line_wrap(True)
        tab_video.pack_start(self.hw_warning_label, False, False, 0)

        self.notebook.append_page(tab_video, Gtk.Label(label="Video & GPU"))

        # ================= TAB 2: Audio & Schnitt =================
        tab_audio = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        tab_audio.set_margin_start(10); tab_audio.set_margin_end(10)
        tab_audio.set_margin_top(10); tab_audio.set_margin_bottom(10)

        grid_audio = Gtk.Grid(column_spacing=10, row_spacing=8)
        tab_audio.pack_start(grid_audio, False, False, 0)

        grid_audio.attach(Gtk.Label(label="Audioformat:", xalign=0), 0, 0, 1, 1)
        self.audio_combo = self._create_wayland_ready_combo(["Opus (WebM/MKV)", "AAC", "PCM", "FLAC (mkv)"], active_idx=1)
        grid_audio.attach(self.audio_combo, 1, 0, 1, 1)

        norm_label = Gtk.Label(label="Normalisierung (LUFS):", xalign=0)
        grid_audio.attach(norm_label, 0, 1, 1, 1)
        self.volume_spin = Gtk.SpinButton.new_with_range(-30, -5, 1)
        self.volume_spin.set_value(-16)
        grid_audio.attach(self.volume_spin, 1, 1, 1, 1)

        self.audio_copy_chk = Gtk.CheckButton(label="Audio kopieren (Kein Filter)")
        self.audio_copy_chk.connect("toggled", self.on_audio_copy_toggled)
        grid_audio.attach(self.audio_copy_chk, 1, 2, 1, 1)

        tab_audio.pack_start(Gtk.Separator(), False, False, 5)

        self.btn_preview = Gtk.Button(label="Schnittbereich festlegen (Vorschau)")
        self.btn_preview.connect("clicked", self.on_open_preview)
        tab_audio.pack_start(self.btn_preview, False, False, 0)

        grid_time = Gtk.Grid(column_spacing=10, row_spacing=6)
        tab_audio.pack_start(grid_time, False, False, 0)
        grid_time.attach(Gtk.Label(label="Startzeit:", xalign=0), 0, 0, 1, 1)
        self.start_entry = Gtk.Entry(text="00:00:00")
        grid_time.attach(self.start_entry, 1, 0, 1, 1)

        grid_time.attach(Gtk.Label(label="Dauer (sek):", xalign=0), 0, 1, 1, 1)
        self.duration_limit_entry = Gtk.Entry(text="0")
        grid_time.attach(self.duration_limit_entry, 1, 1, 1, 1)

        self.notebook.append_page(tab_audio, Gtk.Label(label="Audio & Schnitt"))

        # ================= TAB 3: Pfade & Export =================
        tab_export = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        tab_export.set_margin_start(10); tab_export.set_margin_end(10)
        tab_export.set_margin_top(10); tab_export.set_margin_bottom(10)

        self.btn_files = Gtk.Button(label="Dateien auswählen")
        self.btn_files.connect("clicked", self.on_select_files)
        tab_export.pack_start(self.btn_files, False, False, 0)

        self.btn_remove = Gtk.Button(label="Ausgewählte aus Liste entfernen")
        self.btn_remove.connect("clicked", self.on_remove_selected)
        tab_export.pack_start(self.btn_remove, False, False, 0)

        tab_export.pack_start(Gtk.Separator(), False, False, 2)

        tab_export.pack_start(Gtk.Label(label="Zielordner (leer -> auto/converted):", xalign=0), False, False, 0)
        self.target_entry = Gtk.Entry()
        tab_export.pack_start(self.target_entry, False, False, 0)

        self.btn_target = Gtk.Button(label="Zielverzeichnis suchen")
        self.btn_target.connect("clicked", self.on_browse_target)
        tab_export.pack_start(self.btn_target, False, False, 0)

        self.save_in_source_chk = Gtk.CheckButton(label="Im Quellverzeichnis speichern")
        tab_export.pack_start(self.save_in_source_chk, False, False, 0)

        self.keep_rotation_chk = Gtk.CheckButton(label="Metadaten-Rotation (9:16) beibehalten")
        self.keep_rotation_chk.set_active(True)
        tab_export.pack_start(self.keep_rotation_chk, False, False, 0)

        tab_export.pack_start(Gtk.Separator(), False, False, 2)

        action_grid = Gtk.Grid(column_spacing=6, row_spacing=6)
        action_grid.set_column_homogeneous(True)
        tab_export.pack_start(action_grid, False, False, 0)

        self.start_btn = Gtk.Button(label="Konvertieren")
        self.start_btn.set_name("btn-start")
        self.start_btn.connect("clicked", self.start_conversion)
        action_grid.attach(self.start_btn, 0, 0, 1, 1)

        self.cancel_btn = Gtk.Button(label="Abbrechen", sensitive=False)
        self.cancel_btn.connect("clicked", self.cancel_conversion)
        action_grid.attach(self.cancel_btn, 1, 0, 1, 1)

        self.exit_btn = Gtk.Button(label="Programm beenden")
        self.exit_btn.set_name("btn-exit")
        self.exit_btn.connect("clicked", lambda w: self.close())
        action_grid.attach(self.exit_btn, 0, 1, 1, 1)

        self.reset_btn = Gtk.Button(label="Reset")
        self.reset_btn.connect("clicked", self.on_reset_all)
        action_grid.attach(self.reset_btn, 1, 1, 1, 1)

        self.notebook.append_page(tab_export, Gtk.Label(label="Dateien & Start"))

        # --- Rechte Spalte (Dateiliste + Log) ---
        right_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_hbox.pack_start(right_vbox, True, True, 0)

        self.liststore = Gtk.ListStore(str)
        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.append_column(Gtk.TreeViewColumn("Ausgewählte Dateien", Gtk.CellRendererText(), text=0))
        self.treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        self.treeview.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.treeview.drag_dest_add_uri_targets()
        self.treeview.connect("drag-data-received", self.on_drag_data_received)

        scroll_tree = Gtk.ScrolledWindow(min_content_height=110)
        scroll_tree.add(self.treeview)
        right_vbox.pack_start(scroll_tree, True, True, 0)

        self.file_label = Gtk.Label(label="Fortschritt: Keine Datei aktiv", xalign=0)
        self.file_label.get_style_context().add_class("prog-label")
        right_vbox.pack_start(self.file_label, False, False, 0)
        self.file_progress = Gtk.ProgressBar()
        right_vbox.pack_start(self.file_progress, False, False, 0)

        self.total_label = Gtk.Label(label="Gesamtfortschritt", xalign=0)
        self.total_label.get_style_context().add_class("prog-label")
        right_vbox.pack_start(self.total_label, False, False, 0)
        self.total_progress = Gtk.ProgressBar()
        right_vbox.pack_start(self.total_progress, False, False, 0)

        self.log_view = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD)
        scroll_log = Gtk.ScrolledWindow(min_content_height=130)
        scroll_log.add(self.log_view)
        right_vbox.pack_start(scroll_log, True, True, 0)

        self.show_all()

    def on_switch_layout(self, widget):
        """Speichert 'h' in der Config, startet guideos-videokonverter-h.py und schließt dieses Fenster."""
        script_dir = Path(__file__).parent
        target_script = script_dir / "guideos-videokonverter-h.py"

        # Pfad zur layout.conf im Home-Verzeichnis
        config_file = Path.home() / ".config" / "guideos-videokonverter" / "layout.conf"

        try:
            # 1. Config auf 'h' (Hochformat) aktualisieren
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text("h\n")

            # 2. Hochformat-Skript direkt starten
            if target_script.exists():
                subprocess.Popen([sys.executable, str(target_script)])
                self.close()
            else:
                self.append_log(f"\n[Fehler] Hochformat-Skript nicht gefunden: {target_script.name}\n")
        except Exception as e:
            self.append_log(f"\n[Fehler] Fehler beim Layout-Wechsel: {e}\n")

    def _create_wayland_ready_combo(self, items, active_idx=0):
        combo = Gtk.ComboBoxText()
        combo.set_property("popup-fixed-width", True)
        combo.set_wrap_width(1)
        for item in items:
            combo.append_text(item)
        combo.set_active(active_idx)
        return combo

    def _check_codec_hardware_support(self, *args):
        codec = self.video_combo.get_active_text() or ""
        gpu_sel = self.gpu_combo.get_active_text() or ""

        detected_gpu = detect_gpu_short()
        gpu = detected_gpu if "Automatisch" in gpu_sel else gpu_sel.upper()

        warning_text = ""

        if "VP9" in codec and "NVIDIA" in gpu:
            warning_text = (
                "⚠️ <b>VP9:</b> NVIDIA unterstützt kein HW-Encoding für VP9.\n"
                "Bitte auf <b>Software (CPU)</b> umstellen."
            )
        elif "VP9" in codec and "AMD" in gpu:
            warning_text = (
                "⚠️ <b>VP9:</b> AMD unterstützt kein HW-Encoding für VP9.\n"
                "Bitte auf <b>Software (CPU)</b> umstellen."
            )
        elif "AV1" in codec and "NVIDIA" in gpu:
            warning_text = (
                "💡 <b>AV1:</b> Benötigt eine <b>RTX 40xx+</b>.\n"
                "Sonst bitte <b>Software (CPU)</b> nutzen."
            )
        elif "AV1" in codec and "AMD" in gpu:
            warning_text = (
                "💡 <b>AV1:</b> Benötigt eine <b>Radeon RX 7000+</b>.\n"
                "Sonst bitte <b>Software (CPU)</b> nutzen."
            )
        elif "AV1" in codec and "INTEL" in gpu:
            warning_text = (
                "💡 <b>AV1:</b> Benötigt eine <b>Intel Arc</b> GPU.\n"
                "Sonst bitte <b>Software (CPU)</b> nutzen."
            )

        if warning_text:
            self.hw_warning_label.set_markup(f'<span foreground="#d35400"><small>{warning_text}</small></span>')
        else:
            self.hw_warning_label.set_markup("")

    def _update_video_codecs_for_container(self):
        container = self.format_combo.get_active_text() or ""
        current_codec = self.video_combo.get_active_text() or ""

        self.video_combo.remove_all()

        if "WebM" in container:
            valid_codecs = ["VP9", "AV1", "Nur Audio ändern"]
            for c in valid_codecs:
                self.video_combo.append_text(c)
            if current_codec in valid_codecs:
                self.video_combo.set_active(valid_codecs.index(current_codec))
            else:
                self.video_combo.set_active(0)
        else:
            all_codecs = ["H.264", "H.265", "VP9", "AV1", "Nur Audio ändern"]
            for c in all_codecs:
                self.video_combo.append_text(c)
            if current_codec in all_codecs:
                self.video_combo.set_active(all_codecs.index(current_codec))
            else:
                self.video_combo.set_active(0)

        self._check_codec_hardware_support()

    def on_format_changed(self, combo):
        fmt = combo.get_active_text()
        self._update_video_codecs_for_container()

        if fmt and "WebM" in fmt:
            self.audio_combo.set_active(0)
        elif fmt and ("MP4" in fmt or "Matroska" in fmt):
            if self.audio_combo.get_active() == 0:
                self.audio_combo.set_active(1)

    def on_audio_copy_toggled(self, btn):
        active = btn.get_active()
        self.audio_combo.set_sensitive(not active)
        self.volume_spin.set_sensitive(not active)

    def on_drag_data_received(self, widget, context, x, y, selection, info, time):
        uris = selection.get_uris()
        for uri in uris:
            path = urllib.parse.unquote(uri.replace('file://', ''))
            if os.path.exists(path) and path not in self.selected_files:
                self.selected_files.append(path)
                self.liststore.append([os.path.basename(path)])
        context.finish(True, False, time)

    def on_reset_all(self, btn):
        self.selected_files.clear(); self.liststore.clear()
        self.file_progress.set_fraction(0); self.total_progress.set_fraction(0)
        self.file_label.set_text("Fortschritt: Keine Datei aktiv")
        self.log_view.get_buffer().set_text("")
        self.start_entry.set_text("00:00:00")
        self.duration_limit_entry.set_text("0")
        self.gpu_combo.set_active(0)
        self.format_combo.set_active(0)
        self._update_video_codecs_for_container()
        self.dimension_combo.set_active(0)
        self.audio_combo.set_active(1)
        self.video_combo.set_active(0)
        self.bit_combo.set_active(0)
        self.quality_combo.set_active(0)
        self.preset_combo.set_active(5)
        self.volume_spin.set_value(-16)
        self.audio_copy_chk.set_active(False)
        self.quality_entry.set_text("23")
        self.target_entry.set_text("")
        self.save_in_source_chk.set_active(False)
        self.keep_rotation_chk.set_active(True)
        self._check_codec_hardware_support()

    def on_quality_mode_changed(self, combo):
        m = combo.get_active_text()
        if not m: return
        if "CQ" in m: self.quality_label.set_text("CRF (0-51):"); self.quality_entry.set_text("23")
        elif "Bitrate" in m: self.quality_label.set_text("kbit/s:"); self.quality_entry.set_text("5000")
        else: self.quality_label.set_text("MB:"); self.quality_entry.set_text("700")

    def on_select_files(self, btn):
        dialog = Gtk.FileChooserDialog(title="Videos wählen", parent=self, action=Gtk.FileChooserAction.OPEN,
                                      buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dialog.set_select_multiple(True)
        if dialog.run() == Gtk.ResponseType.OK:
            for f in dialog.get_filenames():
                if f not in self.selected_files:
                    self.selected_files.append(f); self.liststore.append([Path(f).name])
        dialog.destroy()

    def on_remove_selected(self, btn):
        model, paths = self.treeview.get_selection().get_selected_rows()
        for p in reversed(paths):
            idx = p.get_indices()[0]
            del self.selected_files[idx]
            model.remove(model.get_iter(p))

    def on_browse_target(self, btn):
        dialog = Gtk.FileChooserDialog(title="Ziel wählen", parent=self, action=Gtk.FileChooserAction.SELECT_FOLDER,
                                      buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        if dialog.run() == Gtk.ResponseType.OK: self.target_entry.set_text(dialog.get_filename())
        dialog.destroy()

    def on_open_preview(self, btn):
        if not self.selected_files or not VideoPreviewDialog: return
        dialog = VideoPreviewDialog(self, self.selected_files[0])
        if dialog.run() == Gtk.ResponseType.OK:
            s, e = dialog.get_range()
            self.start_entry.set_text(f"{int(s//3600):02d}:{int((s%3600)//60):02d}:{s%60:05.2f}")
            self.duration_limit_entry.set_text(f"{e-s:.2f}")
        dialog.destroy()

    def build_ffmpeg_args(self, infile, outfile):
        sel_text = self.gpu_combo.get_active_text()
        keep_rotation = self.keep_rotation_chk.get_active()
        container_choice = self.format_combo.get_active_text()
        is_webm = "WebM" in container_choice

        if "NVIDIA" in sel_text: hw_mode = "NVIDIA"
        elif "AMD" in sel_text: hw_mode = "AMD"
        elif "Intel" in sel_text: hw_mode = "INTEL"
        elif "Software" in sel_text: hw_mode = "CPU"
        else: hw_mode = detect_gpu_short().upper()

        vchoice, achoice = self.video_combo.get_active_text(), self.audio_combo.get_active_text()
        qmode, qval_raw = self.quality_combo.get_active_text(), self.quality_entry.get_text()
        upscale = self.dimension_combo.get_active_text()
        preset = self.preset_combo.get_active_text()
        audio_copy = self.audio_copy_chk.get_active()
        target_lufs = int(self.volume_spin.get_value())
        is_10bit = "10-Bit" in self.bit_combo.get_active_text()

        if is_webm:
            if vchoice not in ["VP9", "AV1"]:
                vchoice = "VP9"
            audio_copy = False

        args = []

        if keep_rotation:
            args += ["-noautorotate"]

        if vchoice != "Nur Audio ändern" and hw_mode != "CPU":
            if "NVIDIA" in hw_mode:
                args += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
            elif "INTEL" in hw_mode or "AMD" in hw_mode:
                args += ["-hwaccel", "vaapi", "-hwaccel_output_format", "vaapi", "-hwaccel_device", "/dev/dri/renderD128"]

        start_time = sanitize_time_str(self.start_entry.get_text(), "00:00:00")
        if start_time != "00:00:00":
            args += ["-ss", start_time]

        args += ["-i", str(Path(infile).resolve())]

        # --- KORREKTUR FÜR DIE DAUER (Limit) ---
        # Statt int parsen wir Float, um Dezimalstellen (wie "10.00") sicher zu verarbeiten.
        raw_dur = self.duration_limit_entry.get_text().strip().replace(',', '.')
        try:
            dur_float = float(raw_dur)
            if dur_float > 0:
                args += ["-t", f"{dur_float:.2f}"]
        except ValueError:
            pass
        # --------------------------------------

        if vchoice == "Nur Audio ändern":
            args += ["-c:v", "copy"]
        else:
            if "H.264" in vchoice: fmt = "H.264"
            elif "H.265" in vchoice: fmt = "H.265"
            elif "VP9" in vchoice: fmt = "VP9"
            else: fmt = "AV1"

            codec = _select_encoder(fmt, hw_mode)
            args += _codec_quality_args(codec, qmode, qval_raw, preset, infile)

            if is_10bit and "vaapi" not in codec and "nvenc" not in codec:
                 args += ["-pix_fmt", "yuv420p10le"]
            elif not is_10bit and "vaapi" not in codec and "nvenc" not in codec:
                 args += ["-pix_fmt", "yuv420p"]

            # --- FILTER & DIMENSIONS LOGIK ---
            res_map = {"720p": "1280", "1080p": "1920", "1440p": "2560", "2160p": "3840"}
            target_w = next((v for k, v in res_map.items() if k in upscale), None)

            if "nvenc" in codec:
                if target_w:
                    args += ["-vf", f"scale_cuda={target_w}:-1"]
            elif "vaapi" in codec:
                vfmt = "p010le" if is_10bit else "nv12"
                if target_w:
                    args += ["-vf", f"scale_vaapi={target_w}:-2,format=vaapi|{vfmt}"]
                else:
                    args += ["-vf", f"format=vaapi|{vfmt}"]
            elif target_w:
                args += ["-vf", f"scale={target_w}:-2:flags=lanczos"]

        if keep_rotation:
            args += ["-metadata:s:v:0", "rotate=90"]

        if audio_copy:
            args += ["-c:a", "copy"]
        else:
            a_codec_map = {
                "Opus (WebM/MKV)": "libopus",
                "AAC": "aac",
                "PCM": "pcm_s16le",
                "FLAC (mkv)": "flac"
            }
            if is_webm:
                a_codec = "libopus"
            else:
                a_codec = a_codec_map.get(achoice, "aac")

            args += ["-c:a", a_codec]

            audio_filters = []
            if achoice == "PCM" or vchoice in ["AV1", "VP9"] or is_webm:
                args += ["-ar", "48000"]
                audio_filters.append("aresample=48000")

            audio_filters.append(f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11")
            args += ["-af", ",".join(audio_filters)]

        return args

    def append_log(self, text):
        GLib.idle_add(self._safe_append_log, text)

    def _safe_append_log(self, text):
        buf = self.log_view.get_buffer()
        buf.insert(buf.get_end_iter(), text)
        self.log_view.scroll_to_mark(buf.create_mark(None, buf.get_end_iter(), False), 0.0, True, 0.0, 1.0)

    def start_conversion(self, btn):
        if not self.selected_files: return
        self.start_btn.set_sensitive(False); self.cancel_btn.set_sensitive(True)
        self.stop_event.clear()
        threading.Thread(target=self.run_conversion, daemon=True).start()

    def cancel_conversion(self, btn):
        self.stop_event.set()
        if self.current_proc: self.current_proc.terminate()

    def run_conversion(self):
        total = len(self.selected_files)
        container_choice = self.format_combo.get_active_text()
        audio_format = self.audio_combo.get_active_text()

        for idx, infile in enumerate(list(self.selected_files), 1):
            if self.stop_event.is_set(): break
            in_p = Path(infile).resolve()
            GLib.idle_add(self.file_label.set_text, f"Fortschritt: {in_p.name}")

            if container_choice and "WebM" in container_choice:
                ext = ".webm"
            elif audio_format and "FLAC" in audio_format:
                ext = ".mkv"
            elif container_choice and "MP4" in container_choice:
                ext = ".mp4"
            else:
                ext = ".mkv"

            target_val = self.target_entry.get_text().strip()
            if self.save_in_source_chk.get_active():
                out_dir = in_p.parent
            elif target_val:
                out_dir = Path(target_val).resolve()
            else:
                out_dir = in_p.parent / "converted"

            out_dir.mkdir(parents=True, exist_ok=True)
            out_p = make_unique_path(out_dir / (in_p.stem + ext))

            dur_str = sanitize_time_str(self.duration_limit_entry.get_text(), "0")
            dur = float(dur_str) if dur_str != "0" else (probe_duration_seconds(in_p) or 1.0)

            cmd = ["ffmpeg"] + self.build_ffmpeg_args(str(in_p), str(out_p)) + ["-y", str(out_p)]

            self.append_log(f"\nSTART: {in_p.name}\n")
            try:
                self.current_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                for line in self.current_proc.stdout:
                    self.append_log(line)
                    m = time_re.search(line)
                    if m:
                        pct = min(1.0, (int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))) / dur)
                        GLib.idle_add(self.file_progress.set_fraction, pct)
                        GLib.idle_add(self.total_progress.set_fraction, (idx-1+pct)/total)

                return_code = self.current_proc.wait()

                if return_code != 0 and not self.stop_event.is_set():
                    vchoice = self.video_combo.get_active_text()
                    gpu_choice = self.gpu_combo.get_active_text()

                    if ("VP9" in vchoice or "AV1" in vchoice) and "Software" not in gpu_choice:
                        codec_name = "VP9" if "VP9" in vchoice else "AV1"
                        self.append_log(
                            "\n" + "="*60 + "\n"
                            f"⚠️ HINWEIS / ENCODER-FEHLER ({codec_name}):\n"
                            f"Das Encodieren ist fehlgeschlagen. Der Codec {codec_name} wird auf deiner GPU\n"
                            "eventuell nicht hardwareseitig zum Enkodieren unterstützt.\n\n"
                            "💡 LÖSUNG: Bitte stelle die 'GPU / CPU Auswahl' auf der ersten Seite auf\n"
                            "'Software (CPU)' um und starte die Konvertierung erneut.\n"
                            + "="*60 + "\n\n"
                        )

            except Exception as e:
                self.append_log(f"FEHLER: {e}\n")

        self.append_log("\nFERTIG.\n")
        GLib.idle_add(self.file_label.set_text, "Konvertierung abgeschlossen")
        GLib.idle_add(self.start_btn.set_sensitive, True)
        GLib.idle_add(self.cancel_btn.set_sensitive, False)

if __name__ == "__main__":
    win = VideoConverterWindow()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
