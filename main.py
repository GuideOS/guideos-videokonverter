#!/usr/bin/env python3
# =======================================================================
# Titel:     Linux Video Enkoder (Dynamic Layout Engine)
# Version:   1.2.2
# Autor:     Nightworker / Gemini
# =======================================================================
import sys
import os
sys.dont_write_bytecode = True
import shutil
import subprocess
import threading
import re
import argparse
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox,
    QListWidget, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QIcon

# Layout-Module importieren
import layout_h
import layout_q

try:
    from video_preview import VideoPreviewDialog
except ImportError:
    VideoPreviewDialog = None

# Pfade für den Starter-Aufruf definieren
APP_DIR = Path("/usr/lib/guideos-videokonverter")


# -------------------- Hilfsfunktionen --------------------
def which_bin(name):
    return shutil.which(name) is not None


def detect_gpu_short():
    try:
        res = subprocess.run(["lspci"], capture_output=True, text=True, check=False)
        s = res.stdout.lower()
        if "nvidia" in s:
            return "NVIDIA"
        if "amd" in s or "ati" in s:
            return "AMD"
        if "intel" in s:
            return "INTEL"
    except Exception:
        pass
    return "CPU"


def probe_duration_seconds(path: Path):
    if not which_bin("ffprobe"):
        return None
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path.resolve())
        ], stderr=subprocess.DEVNULL).decode().strip()
        return float(out) if out else None
    except Exception:
        return None


def calculate_bitrate_for_target_size(filepath, target_size_mb, audio_bitrate_kbps=192):
    dur = probe_duration_seconds(Path(filepath))
    if not dur or dur <= 0:
        return None
    total_kbps = (target_size_mb * 8192) / dur
    return int(max(total_kbps - audio_bitrate_kbps, 300))


def make_unique_path(path: Path) -> Path:
    path = path.resolve()
    if not path.exists():
        return path
    parent, stem, suffix = path.parent, path.stem, path.suffix
    candidate = parent / f"{stem}_converted{suffix}"
    if not candidate.exists():
        return candidate
    i = 1
    while True:
        candidate = parent / f"{stem}_converted({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def sanitize_time_str(time_str: str, default: str = "00:00:00") -> str:
    time_str = time_str.strip()
    if re.match(r"^(\d{2}:)?\d{2}:\d{2}(\.\d+)?$", time_str) or re.match(r"^\d+(\.\d+)?$", time_str):
        return time_str
    return default


def sanitize_int(val_str: str, default: int = 0) -> int:
    try:
        return abs(int(re.sub(r"[^\d]", "", val_str)))
    except ValueError:
        return default


time_re = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
_encoder_cache = {}


def is_encoder_available(encoder: str) -> bool:
    if encoder in _encoder_cache:
        return _encoder_cache[encoder]
    try:
        out = subprocess.check_output(["ffmpeg", "-hide_banner", "-encoders"]).decode()
        res = encoder in out
        _encoder_cache[encoder] = res
        return res
    except Exception:
        return False


_ENCODER_MAP = {
    "H.264": {"NVIDIA": ["h264_nvenc"], "AMD": ["h264_vaapi"], "INTEL": ["h264_vaapi"], "CPU": ["libx264"]},
    "H.265": {"NVIDIA": ["hevc_nvenc"], "AMD": ["hevc_vaapi"], "INTEL": ["hevc_vaapi"], "CPU": ["libx265"]},
    "VP9":   {"NVIDIA": [], "AMD": ["vp9_vaapi"], "INTEL": ["vp9_vaapi"], "CPU": ["libvpx-vp9"]},
    "AV1":   {"NVIDIA": ["av1_nvenc"], "AMD": ["av1_vaapi"], "INTEL": ["av1_vaapi"], "CPU": ["libsvtav1"]},
}


def _select_encoder(fmt, mode):
    candidates = _ENCODER_MAP.get(fmt, {}).get(mode, [])
    for enc in candidates:
        if is_encoder_available(enc):
            return enc
    return {"H.264": "libx264", "H.265": "libx265", "VP9": "libvpx-vp9", "AV1": "libsvtav1"}.get(fmt, "libx264")


def _codec_quality_args(codec, qmode, qval_raw, preset, infile, force_cbr=False):
    args = ["-c:v", codec]
    p_map = {"ultrafast": "p1", "superfast": "p2", "veryfast": "p3", "faster": "p4", "fast": "p5", "medium": "p6", "slow": "p7"}
    p = p_map.get(preset, "p5") if "nvenc" in codec else preset

    if "CQ" in qmode:
        qn = str(sanitize_int(qval_raw, default=23))
        if "nvenc" in codec:
            args += ["-rc", "vbr", "-cq", qn, "-preset", p]
        elif "vaapi" in codec:
            args += ["-rc_mode", "CQP", "-qp", qn]
        elif "libvpx-vp9" in codec:
            args += ["-crf", qn, "-b:v", "0"]
        else:
            args += ["-crf", qn, "-preset", p]
    elif "Bitrate" in qmode:
        kbps = str(sanitize_int(qval_raw, default=5000))
        args += ["-b:v", f"{kbps}k"]
        if force_cbr:
            if "nvenc" in codec:
                args += ["-rc", "cbr", "-preset", p]
            elif "vaapi" in codec:
                args += ["-rc_mode", "CBR"]
            else:
                args += ["-minrate", f"{kbps}k", "-maxrate", f"{kbps}k", "-bufsize", f"{int(kbps)*2}k"]
                if "libvpx-vp9" not in codec:
                    args += ["-preset", p]
        else:
            if "nvenc" in codec:
                args += ["-rc", "vbr", "-preset", p]
            elif "vaapi" in codec:
                args += ["-rc_mode", "VBR"]
            elif "libvpx-vp9" not in codec:
                args += ["-preset", p]
    else:
        target_mb = sanitize_int(qval_raw, default=700)
        vkbps = calculate_bitrate_for_target_size(infile, target_mb) or 5000
        args += ["-b:v", f"{vkbps}k"]
        if "libvpx-vp9" not in codec:
            args += ["-preset", p]
    return args


# -------------------- Drag & Drop Widget --------------------
class FileListWidget(QListWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if os.path.exists(file_path) and file_path not in self.parent_window.selected_files:
                    self.parent_window.selected_files.append(file_path)
                    self.addItem(os.path.basename(file_path))
            event.acceptProposedAction()


# -------------------- Worker Signals --------------------
class ConversionSignals(QObject):
    log_signal = pyqtSignal(str)
    file_label_signal = pyqtSignal(str)
    file_progress_signal = pyqtSignal(float)
    total_progress_signal = pyqtSignal(float)
    finished_signal = pyqtSignal()


# -------------------- Main Window --------------------
class VideoConverterWindow(QMainWindow):
    def __init__(self, layout_type="h"):
        super().__init__()
        self.setWindowTitle("GuideOS Videokonverter")
        self.layout_type = layout_type

        self.detect_gpu_short = detect_gpu_short
        self.FileListWidget = FileListWidget

        self.selected_files = []
        self.current_proc = None
        self.stop_event = threading.Event()
        self.signals = ConversionSignals()

        self.signals.log_signal.connect(self._safe_append_log)
        self.signals.file_label_signal.connect(self._safe_set_file_label)
        self.signals.file_progress_signal.connect(self._safe_set_file_progress)
        self.signals.total_progress_signal.connect(self._safe_set_total_progress)
        self.signals.finished_signal.connect(self._on_conversion_finished)

        # Dynamic Layout Loader
        if self.layout_type == "q":
            self.resize(800, 410)
            layout_q.build_ui_querformat(self)
        else:
            self.resize(870, 810)
            layout_h.build_ui_hochformat(self)

        self._apply_styles()
        self.on_quality_mode_changed(0)

    def _apply_styles(self):
        self.setStyleSheet("""
            #btn-start { background-color: #27ae60; color: white; border-radius: 4px; padding: 6px; font-weight: bold; }
            #btn-start:hover { background-color: #2ecc71; }
            #btn-exit { background-color: #c0392b; color: white; border-radius: 4px; padding: 6px; font-weight: bold; }
            #btn-exit:hover { background-color: #e74c3c; }
            .prog-label { font-weight: bold; margin-top: 5px; }
        """)

    def change_layout(self):
        """Ruft das Starter-Skript mit --select auf, um den Layout-Auswahldialog zu öffnen."""
        # Sucht zuerst im Systempfad, ansonsten im aktuellen Ordner
        starter_script = APP_DIR / "guideos-videokonverter-start.py"
        if not starter_script.exists():
            starter_script = Path(__file__).parent / "guideos-videokonverter-start.py"

        if starter_script.exists():
            subprocess.Popen([sys.executable, str(starter_script), "--select"])
            self.close()
        else:
            QMessageBox.critical(
                self,
                "Fehler",
                f"Das Starter-Skript konnte nicht gefunden werden unter:\n{starter_script}"
            )

    def open_help_dialog(self):
        possible_paths = [Path(__file__).parent / "hilfe.html", Path("/usr/lib/guideos-videokonverter/hilfe.html")]
        help_text = next((p.read_text(encoding="utf-8") for p in possible_paths if p.exists()), "<b>Fehler:</b> hilfe.html nicht gefunden.")

        msg = QMessageBox(self)
        msg.setWindowTitle("Hilfe & Skriptbeschreibung")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(help_text)
        msg.exec()

    # --- Actions / Handlers ---
    def _check_codec_hardware_support(self, *args):
        codec = self.video_combo.currentText() or ""
        gpu_sel = self.gpu_combo.currentText() or ""
        gpu = detect_gpu_short() if "Automatisch" in gpu_sel else gpu_sel.upper()

        warning_text = ""
        if "VP9" in codec and "NVIDIA" in gpu:
            warning_text = "⚠️ <b>Hinweis (VP9):</b> NVIDIA bietet kein HW-Encoding für VP9."
        elif "AV1" in codec and "NVIDIA" in gpu:
            warning_text = "💡 <b>Hinweis (AV1):</b> HW-Encoding benötigt eine RTX 40xx+."

        self.hw_warning_label.setText(f'<span style="color: #d35400;"><small>{warning_text}</small></span>' if warning_text else "")

    def on_format_changed(self, index):
        container = self.format_combo.currentText() or ""
        self.video_combo.blockSignals(True)
        self.video_combo.clear()

        valid_codecs = ["VP9", "AV1", "Nur Audio ändern"] if "WebM" in container else ["H.264", "H.265", "VP9", "AV1", "Nur Audio ändern"]
        self.video_combo.addItems(valid_codecs)
        self.video_combo.blockSignals(False)

        if "WebM" in container and hasattr(self, 'audio_combo'):
            self.audio_combo.setCurrentIndex(1)

    def on_audio_format_changed(self, index):
        is_copy = "Original kopieren" in self.audio_combo.currentText()
        self.volume_spin.setEnabled(not is_copy)

    def on_quality_mode_changed(self, index):
        m = self.quality_combo.currentText()
        if "Bitrate" in m:
            if hasattr(self, 'mode_stack'):
                self.mode_stack.setCurrentIndex(1)
            self.quality_label.setText("kbit/s:")
            self.quality_entry.setText("5000")
        else:
            if hasattr(self, 'mode_stack'):
                self.mode_stack.setCurrentIndex(0)
            self.quality_label.setText("CRF (0-51):" if "CQ" in m else "MB:")
            self.quality_entry.setText("23" if "CQ" in m else "700")

    def on_select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Videos wählen", "", "Video Files (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv)")
        for f in files:
            if f not in self.selected_files:
                self.selected_files.append(f)
                self.file_list.addItem(Path(f).name)

    def on_remove_selected(self):
        for item in self.file_list.selectedItems():
            row = self.file_list.row(item)
            del self.selected_files[row]
            self.file_list.takeItem(row)

    def on_browse_target(self):
        folder = QFileDialog.getExistingDirectory(self, "Ziel wählen")
        if folder:
            self.target_entry.setText(folder)

    def on_open_preview(self):
        if not self.selected_files or not VideoPreviewDialog:
            return
        dialog = VideoPreviewDialog(self, self.selected_files[0])
        if dialog.exec() == VideoPreviewDialog.DialogCode.Accepted:
            s, e = dialog.get_range()
            self.start_entry.setText(f"{int(s//3600):02d}:{int((s%3600)//60):02d}:{s%60:05.2f}")
            self.duration_limit_entry.setText(f"{max(0.0, e - s):.2f}")

    def on_reset_all(self):
        self.selected_files.clear()
        self.file_list.clear()
        self.file_progress.setValue(0)
        self.total_progress.setValue(0)
        self.log_view.clear()
        self.start_entry.setText("00:00:00")
        self.duration_limit_entry.setText("0")

    # --- FFmpeg & Execution ---
    def build_ffmpeg_args(self, infile, outfile):
        sel_text = self.gpu_combo.currentText()
        hw_mode = "CPU" if "Software" in sel_text else detect_gpu_short().upper()
        vchoice, achoice = self.video_combo.currentText(), self.audio_combo.currentText()
        qmode, qval_raw = self.quality_combo.currentText(), self.quality_entry.text()

        args = []
        if self.keep_rotation_chk.isChecked():
            args += ["-noautorotate"]

        start_time = sanitize_time_str(self.start_entry.text(), "00:00:00")
        if start_time != "00:00:00":
            args += ["-ss", start_time]

        args += ["-i", str(Path(infile).resolve())]

        if vchoice == "Nur Audio ändern":
            args += ["-c:v", "copy"]
        else:
            fmt = "H.264" if "H.264" in vchoice else ("H.265" if "H.265" in vchoice else ("VP9" if "VP9" in vchoice else "AV1"))
            codec = _select_encoder(fmt, hw_mode)
            args += _codec_quality_args(codec, qmode, qval_raw, self.preset_combo.currentText(), infile)

        if "Original kopieren" in achoice:
            args += ["-c:a", "copy"]
        else:
            args += ["-c:a", "aac"]

        return args

    def _safe_append_log(self, text):
        self.log_view.append(text)

    def _safe_set_file_label(self, text):
        self.file_label.setText(text)

    def _safe_set_file_progress(self, val):
        self.file_progress.setValue(int(val * 100))

    def _safe_set_total_progress(self, val):
        self.total_progress.setValue(int(val * 100))

    def _on_conversion_finished(self):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def start_conversion(self):
        if not self.selected_files:
            return
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.stop_event.clear()
        threading.Thread(target=self.run_conversion, daemon=True).start()

    def cancel_conversion(self):
        self.stop_event.set()
        if self.current_proc:
            self.current_proc.terminate()

    def run_conversion(self):
        total = len(self.selected_files)
        for idx, infile in enumerate(list(self.selected_files), 1):
            if self.stop_event.is_set():
                break
            in_p = Path(infile).resolve()
            self.signals.file_label_signal.emit(f"Fortschritt: {in_p.name}")
            out_dir = in_p.parent / "converted"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_p = make_unique_path(out_dir / f"{in_p.stem}.mp4")

            cmd = ["ffmpeg"] + self.build_ffmpeg_args(str(in_p), str(out_p)) + ["-y", str(out_p)]
            self.signals.log_signal.emit(f"\nSTART: {in_p.name}\n")
            try:
                self.current_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                for line in self.current_proc.stdout:
                    self.signals.log_signal.emit(line.strip())
                self.current_proc.wait()
            except Exception as e:
                self.signals.log_signal.emit(f"FEHLER: {e}\n")

        self.signals.log_signal.emit("\nFERTIG.\n")
        self.signals.file_label_signal.emit("Konvertierung abgeschlossen")
        self.signals.finished_signal.emit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--layout",
        choices=["h", "q"],
        default="h",
        help="Layout auswählen: 'h' (Hochformat) oder 'q' (Querformat)"
    )
    args = parser.parse_args()

    os.environ["QT_QPA_PLATFORM_APP_ID"] = "guideos-videokonverter"
    app = QApplication(sys.argv)

    icon_path = "/usr/share/pixmaps/guideos-videokonverter.png"
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = VideoConverterWindow(layout_type=args.layout)
    window.show()
    sys.exit(app.exec())
