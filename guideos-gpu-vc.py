#!/home/m/venv/bin/python3
# =======================================================================
# Titel: GuideOS-Videokonverter (komplett, GPU, Drag & Drop)
# Version: 1.2 (CustomTkinter Final, Dark Mode, Fixes)
# Autor: Nightworker / Umstellung: Gemini
# Datum: 2025-12-12
# Beschreibung: GUI zur Konvertierung von Videos mit GPU-Unterstützung
# Läuft mit CustomTkinter (für Dark Mode), tkinterdnd2, ffmpeg/ffprobe
# Lizenz: MIT
# ======================================================================

import os
import shutil
import subprocess
import threading
import re
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
# >>> CUSTOMTKINTER-IMPORTS <<<
import customtkinter as ctk
from tkinter import ttk

# Drag & Drop support
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
except Exception as e:
    tk.Tk().withdraw()
    messagebox.showerror(
        "Fehlendes Modul",
        "Das Modul 'tkinterdnd2' ist nicht installiert oder konnte nicht geladen werden.\n\n"
        "Installiere es mit:\n\n  python3 -m pip install --user tkinterdnd2 customtkinter\n\n"
        "und starte das Skript dann erneut."
    )
    raise SystemExit from e

# -------------------- Hilfsfunktionen (UNVERÄNDERT) --------------------
def which_bin(name):
    return shutil.which(name) is not None

def detect_gpu_short():
    """Kurze GPU-Bezeichnung: NVIDIA, AMD, INTEL, CPU"""
    try:
        out = subprocess.getoutput(r"lspci | grep -i 'vga\|3d' || true")
    except Exception:
        return "CPU"
    s = out.lower()
    if "nvidia" in s:
        return "NVIDIA"
    if "amd" in s or "ati" in s:
        return "AMD"
    if "intel" in s:
        return "INTEL"
    return "CPU"

def probe_duration_seconds(path: Path):
    """Gibt Dauer in Sekunden zurück (float) oder None, mittels ffprobe."""
    if not which_bin("ffprobe"):
        return None
    try:
        out = subprocess.check_output([
            "ffprobe","-v","error","-show_entries","format=duration",
            "-of","default=noprint_wrappers=1:nokey=1", str(path)
        ], stderr=subprocess.DEVNULL).decode().strip()
        return float(out) if out else None
    except Exception:
        return None

def calculate_bitrate_for_target_size(filepath, target_size_mb, audio_bitrate_kbps=192):
    """Berechnet Videobitrate in kbit/s um auf Zielgröße zu kommen."""
    dur = probe_duration_seconds(Path(filepath))
    if not dur or dur <= 0:
        return None
    # Gesamtbitrate in kbit/s: (MB * 8192) / seconds
    total_kbps = (target_size_mb * 8192) / dur
    video_kbps = max(total_kbps - audio_bitrate_kbps, 300)  # mind. 300 kbit/s
    return int(video_kbps)

def make_unique_path(path: Path) -> Path:
    """Wenn path existiert, hänge _converted oder (1),(2) etc. an."""
    if not path.exists():
        return path
    parent = path.parent
    stem = path.stem
    suffix = path.suffix
    new_stem = f"{stem}_converted"
    candidate = parent / f"{new_stem}{suffix}"
    if not candidate.exists():
        return candidate
    i = 1
    while True:
        candidate = parent / f"{new_stem}({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1

# regex für time=HH:MM:SS.ms (ffmpeg-Ausgabe)
time_re = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")

# -------------------- GUI (CUSTOMTKINTER INITIALISIERUNG) --------------------
# 1. CustomTkinter Setup vor Fenstererstellung
ctk.set_appearance_mode("System") # Automatische Systemerkennung (Light/Dark)
ctk.set_default_color_theme("blue")

# 2. Hauptfenster mit TkinterDnD.Tk()
app = TkinterDnD.Tk()
app.title("GuideOS-Videokonverter")
app.geometry("980x620")

# FIX: Setze den Root-Hintergrund manuell auf die CustomTkinter-Farbe
current_mode = ctk.get_appearance_mode().lower()
is_dark = ctk.DarkDetect.isDark() if current_mode == "system" else (current_mode == "dark")

if is_dark:
    root_bg_color = "#2b2b2b"
else:
    root_bg_color = "#ededed"
app.configure(bg=root_bg_color)
# Ende FIX

# 3. Frames (ctk.CTkFrame)
left_frame = ctk.CTkFrame(app)
left_frame.pack(side="left", fill="y", padx=14, pady=12)
right_frame = ctk.CTkFrame(app)
right_frame.pack(side="right", fill="both", expand=True, padx=14, pady=12)

# GPU
ctk.CTkLabel(left_frame, text="Erkannte Grafikkarte:").pack(anchor="w")
gpu_var = tk.StringVar(value=detect_gpu_short())
gpu_entry = ctk.CTkEntry(
    left_frame,
    textvariable=gpu_var,
    state="readonly",
    width=240,
)
gpu_entry.pack(anchor="w", pady=(2,8))

# --- Benutzer-Auswahl CPU/GPU-Modus ---
ctk.CTkLabel(left_frame, text="GPU / CPU Auswahl:").pack(anchor="w")
gpu_select_var = tk.StringVar(value="Automatisch (empfohlen)")
gpu_select_cb = ctk.CTkComboBox(
    left_frame,
    variable=gpu_select_var,
    state="readonly",
    width=240,
    values=[
        "Automatisch (empfohlen)",
        "NVIDIA",
        "AMD",
        "Intel",
        "CPU"
    ]
)
gpu_select_cb.pack(anchor="w", pady=(2,8))

# --- Dateiverwaltung Buttons (oben) ---
selected_files = []

btn_files = ctk.CTkButton(left_frame, text="Dateien auswählen")
btn_files.pack(anchor="w", fill="x", pady=3)
btn_remove = ctk.CTkButton(left_frame, text="Ausgewählte entfernen")
btn_remove.pack(anchor="w", fill="x", pady=3)
btn_browse_target = ctk.CTkButton(left_frame, text="Zielverzeichnis wählen")
btn_browse_target.pack(anchor="w", fill="x", pady=3)

ttk.Separator(left_frame, orient="horizontal").pack(fill="x", pady=(8,10))

# Einstellungen Frame
opts = ctk.CTkFrame(left_frame)
opts.pack(anchor="w", pady=(0,8))

# Upscale dropdown
ctk.CTkLabel(opts, text="Upscaling:").grid(row=0, column=0, sticky="w")
upscale_var = tk.StringVar(value="Original")
upscale_cb = ctk.CTkComboBox(opts, variable=upscale_var,
    values=["Original","720p (1280x720)","1080p (1920x1080)","1440p (2560x1440)","2160p (3840x2160)"],
    width=160, state="readonly")
upscale_cb.grid(row=0, column=1, padx=(8,0), pady=(0,6), sticky="w")

# Audio
ctk.CTkLabel(opts, text="Audioformat:").grid(row=1, column=0, sticky="w")
audio_var = tk.StringVar(value="AAC")
audio_cb = ctk.CTkComboBox(opts, variable=audio_var, values=["AAC","PCM","FLAC (mkv)"], width=160, state="readonly")
audio_cb.grid(row=1, column=1, padx=(8,0), pady=(2,6), sticky="w")

# Video
ctk.CTkLabel(opts, text="Videoformat:").grid(row=2, column=0, sticky="w")
video_var = tk.StringVar(value="H.264")
video_cb = ctk.CTkComboBox(opts, variable=video_var, values=["H.264","H.265","AV1","Nur Audio ändern"], width=160, state="readonly")
video_cb.grid(row=2, column=1, padx=(8,0), pady=(2,6), sticky="w")

# Qualität
ctk.CTkLabel(opts, text="Qualität:").grid(row=3, column=0, sticky="w")
quality_var = tk.StringVar(value="CQ (Qualitätsbasiert)")
quality_cb = ctk.CTkComboBox(opts, variable=quality_var,
    values=["CQ (Qualitätsbasiert)","Bitrate (kbit/s)","Zieldateigröße (MB)"],
    width=160, state="readonly")
quality_cb.grid(row=3, column=1, padx=(8,0), pady=(2,4), sticky="w")

ctk.CTkLabel(opts, text="Wert:").grid(row=4, column=0, sticky="w")
quality_value_var = tk.StringVar(value="23")
quality_entry = ctk.CTkEntry(opts, textvariable=quality_value_var, width=80)
quality_entry.grid(row=4, column=1, sticky="w", padx=(8,0), pady=(2,8))

def on_quality_change(event=None):
    mode = quality_var.get()
    if mode.startswith("CQ"):
        quality_value_var.set("23")
    elif "Bitrate" in mode:
        quality_value_var.set("5000")
    else:
        quality_value_var.set("700")
quality_cb.bind("<<ComboboxSelected>>", on_quality_change)
on_quality_change()

# Zielordner entry
ctk.CTkLabel(opts, text="Zielordner (leer → converted_<datum>):").grid(row=5, column=0, columnspan=2, sticky="w", pady=(6,2))
target_dir_var = tk.StringVar(value="")
target_entry = ctk.CTkEntry(opts, textvariable=target_dir_var, width=240)
target_entry.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0,6))

# Checkbox "Im Quellverzeichnis speichern"
save_in_source_var = tk.BooleanVar(value=False)
save_in_source_cb = ctk.CTkCheckBox(opts, text="Im Quellverzeichnis speichern", variable=save_in_source_var)
save_in_source_cb.grid(row=7, column=0, columnspan=2, sticky="w", pady=(0,8))

# --- Right side: listbox, progress, log ---
list_frame = ctk.CTkFrame(right_frame)
list_frame.pack(fill="both", expand=False, padx=(6,6), pady=(6,6))

# FIX: Setze Farben für tk.Listbox und tk.Text manuell basierend auf dem Modus
if is_dark:
    list_bg = "#2b2b2b"         # Hintergrundfarbe des CTkFrame/Root (für nahtlosen Übergang)
    list_fg = "#ffffff"
    select_bg = "#1f6aa5"
else:
    list_bg = "#ffffff"
    list_fg = "#000000"
    select_bg = "#3a7ebf"

# Listbox (manuell gestylt)
listbox = tk.Listbox(
    list_frame,
    selectmode="extended",
    height=12,
    borderwidth=0,
    bg=list_bg,
    fg=list_fg,
    selectbackground=select_bg
)
listbox.pack(side="left", fill="both", expand=True, padx=(6,0), pady=6)
scroll = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
scroll.pack(side="right", fill="y")
listbox.config(yscrollcommand=scroll.set)

# Drag & Drop (unverändert)
def update_listbox():
    listbox.delete(0, tk.END)
    for f in selected_files:
        listbox.insert(tk.END, Path(f).name)

def on_drop(event):
    try:
        files = app.tk.splitlist(event.data)
    except Exception:
        files = [event.data]
    added = 0
    for f in files:
        p = Path(f)
        if not p.exists():
            continue
        if any(part.startswith('.') for part in p.parts):
            continue
        if str(p) not in selected_files and p.suffix.lower() in [".mp4",".mkv",".mov",".avi",".m4v",".mpg",".mpeg",".webm"]:
            selected_files.append(str(p))
            added += 1
    if added:
        update_listbox()

listbox.drop_target_register(DND_FILES)
listbox.dnd_bind('<<Drop>>', on_drop)

# Progress bars
prog_container = ctk.CTkFrame(right_frame)
prog_container.pack(fill="x", padx=6, pady=(6,4))
ctk.CTkLabel(prog_container, text="Aktueller Dateifortschritt:").pack(anchor="w")

file_progress = ctk.CTkProgressBar(prog_container, orientation="horizontal", mode="determinate")
file_progress.pack(fill="x", pady=(4,6))
file_progress.set(0)

ctk.CTkLabel(prog_container, text="Gesamtfortschritt:").pack(anchor="w")
total_progress = ctk.CTkProgressBar(prog_container, orientation="horizontal", mode="determinate")
total_progress.pack(fill="x", pady=(4,6))
total_progress.set(0)

# Log (manuell gestylt)
log_frame = ctk.CTkFrame(right_frame)
log_frame.pack(fill="both", expand=True, padx=6, pady=(6,6))
ctk.CTkLabel(log_frame, text="ffmpeg-Ausgabe (live):").pack(anchor="w")

log_text = tk.Text(
    log_frame,
    height=10,
    wrap="word",
    bg=list_bg,
    fg=list_fg
)
log_text.pack(side="left", fill="both", expand=True, pady=(4,0))
log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=log_text.yview)
log_scroll.pack(side="right", fill="y")
log_text.config(yscrollcommand=log_scroll.set)

# bottom: start / cancel
bottom_left = ctk.CTkFrame(left_frame)
bottom_left.pack(side="bottom", fill="x", pady=8)
start_btn = ctk.CTkButton(bottom_left, text="Konvertierung starten")
start_btn.pack(side="right", padx=6)
cancel_btn = ctk.CTkButton(bottom_left, text="Abbrechen", state="disabled", fg_color="firebrick4")
cancel_btn.pack(side="right")

# -------------------- Dialog-Funktionen --------------------
def select_files_action():
    files = filedialog.askopenfilenames(title="Videodateien auswählen",
                                         filetypes=[("Videos", "*.mp4 *.mov *.mkv *.avi *.m4v *.mpg *.mpeg *.webm")],
                                         initialdir=str(Path.home()))
    if not files:
        return
    for f in files:
        p = Path(f)
        if any(part.startswith('.') for part in p.parts):
            continue
        if f not in selected_files:
            selected_files.append(f)
    update_listbox()

def remove_selected_action():
    sel = list(listbox.curselection())
    if not sel:
        return
    for idx in sorted(sel, reverse=True):
        try:
            del selected_files[idx]
        except IndexError:
            pass
    update_listbox()

# FIX: Neue, robuste Funktion zur Zielverzeichnis-Auswahl (System-Dialog)
def browse_target_dir_action():
    directory = filedialog.askdirectory(
        title="Zielverzeichnis wählen",
        initialdir=target_dir_var.get() or str(Path.home()),
        mustexist=False
    )
    if directory:
        target_dir_var.set(directory)

# -------------------- ffmpeg-Argumenterzeugung (UNVERÄNDERT) --------------------
def build_ffmpeg_args(infile: str, outfile: str):
    sel = gpu_select_var.get()
    if sel == "Automatisch (empfohlen)":
        gpu = gpu_var.get().upper()
    else:
        gpu = sel.upper()

    vchoice = video_var.get()
    achoice = audio_var.get()
    qmode = quality_var.get()
    qval = quality_value_var.get().strip()
    upscale = upscale_var.get()

    # Select encoder names depending on GPU
    if gpu == "NVIDIA":
        h264, h265, av1 = "h264_nvenc", "hevc_nvenc", "av1_nvenc"
        hw_flags = []
    elif gpu == "AMD":
        h264, h265, av1 = "h264_amf", "hevc_amf", "av1_amf"
        hw_flags = ["-hwaccel","vaapi","-hwaccel_output_format","vaapi"]
    elif gpu == "INTEL":
        h264, h265, av1 = "h264_vaapi", "hevc_vaapi", "av1_vaapi"
        hw_flags = ["-hwaccel","vaapi","-hwaccel_output_format","vaapi","-vaapi_device","/dev/dri/renderD128"]
    else:
        h264, h265, av1 = "libx264", "libx265", "libaom-av1"
        hw_flags = []

    args = []
    if hw_flags:
        args += hw_flags

    args += ["-i", infile]

    if vchoice == "Nur Audio ändern":
        args += ["-c:v", "copy"]
        if achoice == "AAC":
            args += ["-c:a", "aac", "-b:a", "192k"]
        elif achoice == "PCM":
            args += ["-c:a", "pcm_s16le"]
        elif achoice == "FLAC (mkv)":
            args += ["-c:a", "flac"]
        else:
            args += ["-c:a", "copy"]
    else:
        codec = h264 if vchoice=="H.264" else (h265 if vchoice=="H.265" else av1)
        if qmode.startswith("CQ"):
            try:
                qn = int(qval)
            except Exception:
                qn = 23
            if "nvenc" in codec or "amf" in codec or "vaapi" in codec:
                args += ["-c:v", codec, "-rc", "vbr", "-cq", str(qn), "-preset", "p5"]
            else:
                args += ["-c:v", codec, "-crf", str(qn), "-preset", "medium"]
        elif "Bitrate" in qmode:
            try:
                kb = int(float(qval))
            except Exception:
                kb = 5000
            args += ["-c:v", codec, "-b:v", f"{kb}k", "-preset", "p4"]
        else:
            try:
                mb = float(qval)
            except Exception:
                mb = 700.0
            video_kbps = calculate_bitrate_for_target_size(infile, mb, audio_bitrate_kbps=192)
            if not video_kbps:
                video_kbps = 5000
            args += ["-c:v", codec, "-b:v", f"{video_kbps}k", "-preset", "p4"]

        if achoice == "AAC":
            args += ["-c:a", "aac", "-b:a", "192k"]
        elif achoice == "PCM":
            args += ["-c:a", "pcm_s16le"]
        elif achoice == "FLAC (mkv)":
            args += ["-c:a", "flac"]
        else:
            args += ["-c:a", "copy"]

    if upscale.startswith("720p"):
        args += ["-vf", "scale=1280:720:flags=lanczos"]
    elif upscale.startswith("1080p"):
        args += ["-vf", "scale=1920:1080:flags=lanczos"]
    elif upscale.startswith("1440p"):
        args += ["-vf", "scale=2560:1440:flags=lanczos"]
    elif upscale.startswith("2160p"):
        args += ["-vf", "scale=3840:2160:flags=lanczos"]

    return args

# -------------------- Conversion Thread (UNVERÄNDERT) --------------------
current_proc = None
stop_event = threading.Event()

def append_log(text: str):
    log_text.insert(tk.END, text)
    log_text.see(tk.END)

def conversion_thread():
    global current_proc
    stop_event.clear()

    if not selected_files:
        messagebox.showwarning("Keine Dateien", "Bitte zuerst mindestens eine Datei auswählen.")
        start_btn.configure(state="normal")
        cancel_btn.configure(state="disabled")
        return

    if not which_bin("ffmpeg"):
        messagebox.showerror("ffmpeg fehlt", "ffmpeg wurde nicht gefunden. Bitte installieren: sudo apt install ffmpeg")
        start_btn.configure(state="normal")
        cancel_btn.configure(state="disabled")
        return

    chosen_target = target_dir_var.get().strip()
    target_provided = bool(chosen_target)

    outdir_candidate = None
    if target_provided:
        try:
            outdir_candidate = Path(chosen_target).expanduser()
            outdir_candidate.mkdir(parents=True, exist_ok=True)
        except Exception:
            outdir_candidate = None

    total = len(selected_files)
    append_log(f"Starte Konvertierung: {total} Dateien (gewähltes Ziel: {chosen_target or '[auto: converted_<datum>]'})\n\n")

    file_progress.set(0)
    total_progress.set(0)
    app.update_idletasks()

    for idx, infile in enumerate(list(selected_files), start=1):
        if stop_event.is_set():
            append_log("Abbruch angefragt — stoppe.\n")
            break

        in_path = Path(infile)
        base = in_path.stem

        ext = ".mp4"
        if audio_var.get() == "PCM" and video_var.get() == "Nur Audio ändern":
            ext = ".mp4"
        elif audio_var.get() == "FLAC (mkv)":
            ext = ".mkv"

        if save_in_source_var.get():
            file_outdir = in_path.parent
        else:
            if outdir_candidate:
                file_outdir = outdir_candidate
            else:
                if target_provided:
                    try:
                        maybe = Path(chosen_target).expanduser()
                        maybe.mkdir(parents=True, exist_ok=True)
                        file_outdir = maybe
                    except Exception:
                        file_outdir = in_path.parent
                else:
                    first_parent = Path(selected_files[0]).parent
                    file_outdir = first_parent / f"converted_{datetime.now().strftime('%Y-%m-%d')}"
                    file_outdir.mkdir(parents=True, exist_ok=True)

        try:
            file_outdir.mkdir(parents=True, exist_ok=True)
        except Exception:
            file_outdir = in_path.parent

        tentative = file_outdir / (base + ext)

        if file_outdir.resolve() == in_path.parent.resolve():
            outpath = make_unique_path(tentative)
        else:
            outpath = tentative
            if outpath.exists():
                outpath = make_unique_path(outpath)

        if video_var.get() == "Nur Audio ändern" and audio_var.get() == "PCM":
            if outpath.suffix.lower() == ".mp4":
                outpath = outpath.with_suffix(".mp4")
        if video_var.get() == "Nur Audio ändern" and audio_var.get() == "FLAC (mkv)":
            if outpath.suffix.lower() != ".mkv":
                outpath = outpath.with_suffix(".mkv")

        append_log(f"--- Datei {idx}/{total}: {in_path.name} → {outpath} ---\n")
        duration = probe_duration_seconds(in_path) or 1.0

        args = build_ffmpeg_args(str(in_path), str(outpath)) + ["-y", str(outpath)]
        append_log("ffmpeg " + " ".join(args) + "\n")

        try:
            current_proc = subprocess.Popen(["ffmpeg"] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)
        except Exception as e:
            append_log(f"Fehler beim Starten von ffmpeg: {e}\n")
            continue

        file_progress.set(0)
        total_progress.set(((idx-1)/total))
        app.update_idletasks()

        last_pct = 0
        for line in current_proc.stdout:
            append_log(line)
            m = time_re.search(line)
            if m:
                hh, mm, ss = int(m.group(1)), int(m.group(2)), float(m.group(3))
                secs = hh*3600 + mm*60 + ss
                pct = (secs / duration) if duration > 0 else 0
                pct = max(0.0, min(1.0, pct))

                last_pct = pct
                file_progress.set(pct)

                overall = ((idx-1)/total) + (pct/total)
                total_progress.set(overall)
                app.update_idletasks()
            if stop_event.is_set():
                try:
                    current_proc.terminate()
                except Exception:
                    pass
                break

        try:
            current_proc.wait(timeout=2)
        except Exception:
            pass

        file_progress.set(1.0 if not stop_event.is_set() else file_progress.get())
        total_progress.set((idx/total))
        append_log(f"Fertig: {outpath.name}\n\n")
        current_proc = None

    append_log("Konvertierung beendet.\n")
    start_btn.configure(state="normal")
    cancel_btn.configure(state="disabled")

# -------------------- Button Handlers --------------------
def start_conversion_action():
    if not selected_files:
        messagebox.showwarning("Keine Dateien", "Bitte wähle zuerst Videodateien aus.")
        return
    start_btn.configure(state="disabled")
    cancel_btn.configure(state="normal")
    log_text.delete(1.0, tk.END)
    threading.Thread(target=conversion_thread, daemon=True).start()

def cancel_conversion_action():
    stop_event.set()
    if current_proc:
        try:
            current_proc.terminate()
        except Exception:
            pass
    cancel_btn.configure(state="disabled")
    append_log("Abbruch angefragt — bitte warten...\n")

# -------------------- Bind UI --------------------
btn_files.configure(command=select_files_action)
btn_remove.configure(command=remove_selected_action)
# FIX: Verwendet die neue, funktionierende Aktion
btn_browse_target.configure(command=browse_target_dir_action)
start_btn.configure(command=start_conversion_action)
cancel_btn.configure(command=cancel_conversion_action)

def on_listbox_double(event):
    sel = listbox.curselection()
    if not sel:
        return
    idx = sel[0]
    messagebox.showinfo("Pfad", selected_files[idx])
listbox.bind("<Double-Button-1>", on_listbox_double)
listbox.bind("<Delete>", lambda e: remove_selected_action())

# initial log
append_log("GuideOS-Videokonverter\nHinweis: ffmpeg und ffprobe müssen installiert sein.\nWähle Dateien, überprüfe Einstellungen und klicke 'Konvertierung starten'.\n\n")

# start GUI
app.mainloop()
