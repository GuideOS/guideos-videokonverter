#!/home/markus/venv/bin/python3
# =======================================================================
# Titel: GuideOS-Videokonverter (komplett, helles Thema, GPU, Drag & Drop)
# Version: 1.1 (mit manueller GPU/CPU Auswahl)
# Autor: Nightworker
# Datum: 2025-11-16
# Beschreibung: GUI zur Konvertierung von Videos mit GPU-Unterstützung
# Läuft mit Standard-Python (tkinter, tkinterdnd2) + ffmpeg/ffprobe
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
from tkinter import ttk, filedialog, messagebox, simpledialog

# Drag & Drop support
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
except Exception as e:
    tk.Tk().withdraw()
    messagebox.showerror(
        "Fehlendes Modul",
        "Das Modul 'tkinterdnd2' ist nicht installiert oder konnte nicht geladen werden.\n\n"
        "Installiere es mit:\n\n  python3 -m pip install --user tkinterdnd2\n\n"
        "und starte das Skript dann erneut."
    )
    raise SystemExit from e

# >>> DESIGN_START
# -------------------- Design / Farben --------------------
BG = "#1e1e1e"
FIELD = "#2a2a2a"
FIELD2 = "#3d3b3b"
FIELD3 = "#595959"
TEXT = "#ffffff"
ACCENT = "#3a3a3a"
PROG = "#4b9e8c"
# >>> DESIGN_END

# -------------------- Hilfsfunktionen --------------------
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

# -------------------- GUI --------------------
app = TkinterDnD.Tk()  # Drag&Drop-fähiges Fenster
app.title("GuideOS-Videokonverter")
app.geometry("980x620")
app.configure(bg=BG)

style = ttk.Style()
try:
    style.theme_use("clam")  # unterstützt Farben am besten
except Exception:
    pass

# Hintergrund generell
app.configure(bg=BG)

style.configure("TFrame", background=BG)
style.configure("TLabel", background=BG, foreground=TEXT)

# Buttons
style.configure(
    "TButton",
    background=FIELD2,
    foreground=TEXT,
    borderwidth=0,
    focusthickness=3,
    focuscolor=ACCENT
)

# Hover-Fix für Buttons
style.map(
    "TButton",
    background=[("active", FIELD3)],
    foreground=[("active", TEXT)]
)

# Combobox
style.configure(
    "TCombobox",
    fieldbackground=FIELD,
    background=FIELD,
    foreground=TEXT,
    arrowcolor=TEXT
)

# Listenfeld im Dropdown weißer Text + dunkler Hintergrund
style.map(
    "TCombobox",
    fieldbackground=[("readonly", FIELD)],
    foreground=[("readonly", TEXT)]
)

# Progressbar
style.configure(
    "Horizontal.TProgressbar",
    troughcolor=FIELD,
    background=PROG
)


# Frames
left_frame = tk.Frame(app, bg=BG)
left_frame.pack(side="left", fill="y", padx=14, pady=12)
right_frame = tk.Frame(app, bg=BG)
right_frame.pack(side="right", fill="both", expand=True, padx=14, pady=12)

# GPU
tk.Label(left_frame, text="Erkannte Grafikkarte:", bg=BG, fg=TEXT).pack(anchor="w")
gpu_var = tk.StringVar(value=detect_gpu_short())
gpu_entry = tk.Entry(left_frame, textvariable=gpu_var, state="readonly", width=36,
                     disabledbackground=FIELD, disabledforeground=TEXT)
gpu_entry.pack(anchor="w", pady=(2,8))

# --- NEU: Benutzer-Auswahl CPU/GPU-Modus (unter der erk. GPU) ---
tk.Label(left_frame, text="GPU / CPU Auswahl:", bg=BG, fg=TEXT).pack(anchor="w")

gpu_select_var = tk.StringVar(value="Automatisch (empfohlen)")
gpu_select_cb = ttk.Combobox(
    left_frame,
    textvariable=gpu_select_var,
    state="readonly",
    width=36,
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

btn_files = ttk.Button(left_frame, text="Dateien auswählen")
btn_files.pack(anchor="w", fill="x", pady=3)
btn_remove = ttk.Button(left_frame, text="Ausgewählte entfernen")
btn_remove.pack(anchor="w", fill="x", pady=3)
btn_browse_target = ttk.Button(left_frame, text="Zielverzeichnis wählen")
btn_browse_target.pack(anchor="w", fill="x", pady=3)

ttk.Separator(left_frame, orient="horizontal").pack(fill="x", pady=(8,10))

# Einstellungen
opts = tk.Frame(left_frame, bg=BG)
opts.pack(anchor="w", pady=(0,8))

# Upscale dropdown
tk.Label(opts, text="Upscaling:", bg=BG, fg=TEXT).grid(row=0, column=0, sticky="w")
upscale_var = tk.StringVar(value="Original")
upscale_cb = ttk.Combobox(opts, textvariable=upscale_var,
    values=["Original","720p (1280x720)","1080p (1920x1080)","1440p (2560x1440)","2160p (3840x2160)"],
    width=28, state="readonly")
upscale_cb.grid(row=0, column=1, padx=(8,0), pady=(0,6), sticky="w")

# Audio
tk.Label(opts, text="Audioformat:", bg=BG, fg=TEXT).grid(row=1, column=0, sticky="w")
audio_var = tk.StringVar(value="AAC")
audio_cb = ttk.Combobox(opts, textvariable=audio_var, values=["AAC","PCM","FLAC (mkv)"], width=28, state="readonly")
audio_cb.grid(row=1, column=1, padx=(8,0), pady=(2,6), sticky="w")

# Video
tk.Label(opts, text="Videoformat:", bg=BG, fg=TEXT).grid(row=2, column=0, sticky="w")
video_var = tk.StringVar(value="H.264")
video_cb = ttk.Combobox(opts, textvariable=video_var, values=["H.264","H.265","AV1","Nur Audio ändern"], width=28, state="readonly")
video_cb.grid(row=2, column=1, padx=(8,0), pady=(2,6), sticky="w")

# Qualität
tk.Label(opts, text="Qualität:", bg=BG, fg=TEXT).grid(row=3, column=0, sticky="w")
quality_var = tk.StringVar(value="CQ (Qualitätsbasiert)")
quality_cb = ttk.Combobox(opts, textvariable=quality_var,
    values=["CQ (Qualitätsbasiert)","Bitrate (kbit/s)","Zieldateigröße (MB)"],
    width=28, state="readonly")
quality_cb.grid(row=3, column=1, padx=(8,0), pady=(2,4), sticky="w")

tk.Label(opts, text="Wert:", bg=BG, fg=TEXT).grid(row=4, column=0, sticky="w")
quality_value_var = tk.StringVar(value="23")  # default CQ=23
quality_entry = ttk.Entry(opts, textvariable=quality_value_var, width=10)
quality_entry.grid(row=4, column=1, sticky="w", padx=(8,0), pady=(2,8))

def on_quality_change(event=None):
    mode = quality_var.get()
    # set sensible defaults when user switches mode
    if mode.startswith("CQ"):
        quality_value_var.set("23")
    elif "Bitrate" in mode:
        quality_value_var.set("5000")
    else:
        quality_value_var.set("700")
quality_cb.bind("<<ComboboxSelected>>", on_quality_change)
on_quality_change()

# Zielordner entry
tk.Label(opts, text="Zielordner (leer → converted_<datum>):", bg=BG, fg=TEXT).grid(row=5, column=0, columnspan=2, sticky="w", pady=(6,2))
target_dir_var = tk.StringVar(value="")
target_entry = ttk.Entry(opts, textvariable=target_dir_var, width=36)
target_entry.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0,6))

# Checkbox "Im Quellverzeichnis speichern"
save_in_source_var = tk.BooleanVar(value=False)
save_in_source_cb = ttk.Checkbutton(opts, text="Im Quellverzeichnis speichern", variable=save_in_source_var)
save_in_source_cb.grid(row=7, column=0, columnspan=2, sticky="w", pady=(0,8))

# --- Right side: listbox, progress, log ---
list_frame = tk.Frame(right_frame, bg=FIELD, bd=1, relief="solid")
list_frame.pack(fill="both", expand=False, padx=(6,6), pady=(6,6))
listbox = tk.Listbox(list_frame, bg=FIELD2, fg=TEXT, selectmode="extended", height=12, borderwidth=0)
listbox.pack(side="left", fill="both", expand=True, padx=(6,0), pady=6)
scroll = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
scroll.pack(side="right", fill="y")
listbox.config(yscrollcommand=scroll.set)

# ✅ Drag & Drop aktivieren
def update_listbox():
    listbox.delete(0, tk.END)
    for f in selected_files:
        listbox.insert(tk.END, Path(f).name)

def on_drop(event):
    # event.data kann mehrere Dateinamen enthalten; splitlist handhabt das korrekt
    try:
        files = app.tk.splitlist(event.data)
    except Exception:
        files = [event.data]
    added = 0
    for f in files:
        p = Path(f)
        # akzeptiere nur existierende Dateien und keine versteckten Pfadteile
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
prog_container = tk.Frame(right_frame, bg=BG)
prog_container.pack(fill="x", padx=6, pady=(6,4))
tk.Label(prog_container, text="Aktueller Dateifortschritt:", bg=BG, fg=TEXT).pack(anchor="w")
file_progress = ttk.Progressbar(prog_container, style="Horizontal.TProgressbar", orient="horizontal", length=640, mode="determinate")
file_progress.pack(fill="x", pady=(4,6))
tk.Label(prog_container, text="Gesamtfortschritt:", bg=BG, fg=TEXT).pack(anchor="w")
total_progress = ttk.Progressbar(prog_container, style="Horizontal.TProgressbar", orient="horizontal", length=640, mode="determinate")
total_progress.pack(fill="x", pady=(4,6))

# Log
log_frame = tk.Frame(right_frame, bg=BG)
log_frame.pack(fill="both", expand=True, padx=6, pady=(6,6))
tk.Label(log_frame, text="ffmpeg-Ausgabe (live):", bg=BG, fg=TEXT).pack(anchor="w")
log_text = tk.Text(log_frame, height=10, bg=FIELD2, fg=TEXT, wrap="word")
log_text.pack(fill="both", expand=True, pady=(4,0))
log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=log_text.yview)
log_scroll.pack(side="right", fill="y")
log_text.config(yscrollcommand=log_scroll.set)

# bottom: start / cancel
bottom_left = tk.Frame(left_frame, bg=BG)
bottom_left.pack(side="bottom", fill="x", pady=8)
start_btn = ttk.Button(bottom_left, text="Konvertierung starten")
start_btn.pack(side="right", padx=6)
cancel_btn = ttk.Button(bottom_left, text="Abbrechen", state="disabled")
cancel_btn.pack(side="right")

# -------------------- Dialog-Funktionen (Datei-Auswahl etc.) --------------------
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

# custom folder browser that hides dot-folders and allows new folder creation
def browse_target_dir_custom():
    top = tk.Toplevel(app)
    top.title("Zielverzeichnis wählen")
    top.geometry("520x420")
    top.configure(bg=BG)
    top.transient(app)
    top.grab_set()

    tk.Label(top, text="Wähle Zielverzeichnis (versteckte Ordner ausgeblendet):", bg=BG).pack(anchor="w", padx=8, pady=6)
    frame = tk.Frame(top, bg=BG)
    frame.pack(fill="both", expand=True, padx=8, pady=6)

    tree = ttk.Treeview(frame)
    tree.pack(side="left", fill="both", expand=True)
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    vsb.pack(side="right", fill="y")
    tree.configure(yscrollcommand=vsb.set)
    nodes = {}

    def insert_node(parent, p: Path):
        try:
            for item in sorted(p.iterdir()):
                if item.name.startswith("."):
                    continue
                if item.is_dir():
                    node = tree.insert(parent, "end", text=item.name, values=(str(item),))
                    # dummy child, damit das [+] Symbol erscheint
                    tree.insert(node, "end", text="dummy")
                    nodes[node] = item
        except PermissionError:
            pass

    def on_open(event):
        node = tree.focus()
        if node in nodes:
            children = tree.get_children(node)
            for child in children:
                if tree.item(child, "text") == "dummy":
                    tree.delete(child)
            insert_node(node, nodes[node])

    # Basis-Ebene: Home und Root
    home = Path.home()
    root_node = tree.insert("", "end", text=home.name, values=(str(home),))
    nodes[root_node] = home
    insert_node(root_node, home)

    try:
        rootpath = Path("/")
        rnode = tree.insert("", "end", text="/", values=("/",))
        nodes[rnode] = rootpath
        insert_node(rnode, rootpath)
    except Exception:
        pass

    tree.bind("<<TreeviewOpen>>", on_open)

    btn_frame = tk.Frame(top, bg=BG)
    btn_frame.pack(fill="x", padx=8, pady=6)

    def new_folder():
        node = tree.focus()
        if not node or node not in nodes:
            messagebox.showwarning("Kein Ordner", "Bitte zuerst einen Ordner wählen, in dem der neue Ordner erstellt werden soll.")
            return
        parent_path = nodes[node]
        name = simpledialog.askstring("Neuer Ordner", "Name des neuen Ordners:", parent=top)
        if not name:
            return
        if name.startswith("."):
            messagebox.showwarning("Ungültig", "Name darf nicht mit Punkt beginnen.")
            return
        newp = parent_path / name
        try:
            newp.mkdir(exist_ok=False)
        except Exception as e:
            messagebox.showerror("Fehler", f"Ordner konnte nicht erstellt werden: {e}")
            return
        # Einfügen in Tree
        new_node = tree.insert(node, "end", text=newp.name, values=(str(newp),))
        nodes[new_node] = newp
        tree.see(new_node)
        tree.selection_set(new_node)

    def ok():
        node = tree.focus()
        if node in nodes:
            target_dir_var.set(str(nodes[node]))
        top.destroy()

    def cancel():
        top.destroy()

    ttk.Button(btn_frame, text="Neuer Ordner", command=new_folder).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(btn_frame, text="Abbrechen", command=cancel).pack(side="right", padx=4)

# -------------------- ffmpeg-Argumenterzeugung (GPU-aware) --------------------
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

    # audio (default or for full conversion)
    # For "Nur Audio ändern" we still set audio below in that branch
    if vchoice == "Nur Audio ändern":
        # Video unverändert kopieren
        args += ["-c:v", "copy"]
        # Audio neu kodieren
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
            # hardware encoders often support -cq / -rc vbr; fallback to crf for software
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
        else:  # Zielgröße
            try:
                mb = float(qval)
            except Exception:
                mb = 700.0
            video_kbps = calculate_bitrate_for_target_size(infile, mb, audio_bitrate_kbps=192)
            if not video_kbps:
                video_kbps = 5000
            args += ["-c:v", codec, "-b:v", f"{video_kbps}k", "-preset", "p4"]

        # audio codec for full conversion
        if achoice == "AAC":
            args += ["-c:a", "aac", "-b:a", "192k"]
        elif achoice == "PCM":
            args += ["-c:a", "pcm_s16le"]
        elif achoice == "FLAC (mkv)":
            args += ["-c:a", "flac"]
        else:
            args += ["-c:a", "copy"]

    # Upscale mapping
    if upscale.startswith("720p"):
        args += ["-vf", "scale=1280:720:flags=lanczos"]
    elif upscale.startswith("1080p"):
        args += ["-vf", "scale=1920:1080:flags=lanczos"]
    elif upscale.startswith("1440p"):
        args += ["-vf", "scale=2560:1440:flags=lanczos"]
    elif upscale.startswith("2160p"):
        args += ["-vf", "scale=3840:2160:flags=lanczos"]

    # overwrite output will be appended by caller
    return args

# -------------------- Conversion Thread --------------------
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
        start_btn.config(state="normal")
        cancel_btn.config(state="disabled")
        return

    if not which_bin("ffmpeg"):
        messagebox.showerror("ffmpeg fehlt", "ffmpeg wurde nicht gefunden. Bitte installieren: sudo apt install ffmpeg")
        start_btn.config(state="normal")
        cancel_btn.config(state="disabled")
        return

    # PREPARE: compute chosen output base directory (do not decide per-file yet)
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
    file_progress['value'] = 0
    total_progress['value'] = 0
    app.update_idletasks()

    for idx, infile in enumerate(list(selected_files), start=1):
        if stop_event.is_set():
            append_log("Abbruch angefragt — stoppe.\n")
            break

        in_path = Path(infile)
        base = in_path.stem

        # choose extension default and special cases
        ext = ".mp4"
        if audio_var.get() == "PCM" and video_var.get() == "Nur Audio ändern":
            # produce container that supports pcm (mp4)
            ext = ".mp4"
        elif audio_var.get() == "FLAC (mkv)":
            ext = ".mkv"

        # Determine outdir
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

        # Safety ensure directory exists
        try:
            file_outdir.mkdir(parents=True, exist_ok=True)
        except Exception:
            file_outdir = in_path.parent

        tentative = file_outdir / (base + ext)

        # If saving in same dir as source -> ensure renamed to avoid overwrite
        if file_outdir.resolve() == in_path.parent.resolve():
            outpath = make_unique_path(tentative)
        else:
            outpath = tentative
            if outpath.exists():
                outpath = make_unique_path(outpath)

        # Special adjustments: ensure .mkv for PCM / FLAC in audio-only mode
        if video_var.get() == "Nur Audio ändern" and audio_var.get() == "PCM":
            if outpath.suffix.lower() == ".mp4":
                outpath = outpath.with_suffix(".mp4")
        if video_var.get() == "Nur Audio ändern" and audio_var.get() == "FLAC (mkv)":
            if outpath.suffix.lower() != ".mkv":
                outpath = outpath.with_suffix(".mkv")

        append_log(f"--- Datei {idx}/{total}: {in_path.name} → {outpath} ---\n")
        duration = probe_duration_seconds(in_path) or 1.0

        # Build args and run ffmpeg
        args = build_ffmpeg_args(str(in_path), str(outpath)) + ["-y", str(outpath)]
        append_log("ffmpeg " + " ".join(args) + "\n")

        try:
            current_proc = subprocess.Popen(["ffmpeg"] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)
        except Exception as e:
            append_log(f"Fehler beim Starten von ffmpeg: {e}\n")
            continue

        file_progress['value'] = 0
        total_progress['value'] = int(((idx-1)/total) * 100)
        app.update_idletasks()

        last_pct = 0
        for line in current_proc.stdout:
            append_log(line)
            m = time_re.search(line)
            if m:
                hh, mm, ss = int(m.group(1)), int(m.group(2)), float(m.group(3))
                secs = hh*3600 + mm*60 + ss
                pct = int((secs / duration) * 100) if duration > 0 else 0
                pct = max(0, min(100, pct))
                last_pct = pct
                file_progress['value'] = pct
                overall = int(((idx-1)/total)*100 + (pct/total))
                total_progress['value'] = overall
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

        file_progress['value'] = 100 if not stop_event.is_set() else file_progress['value']
        total_progress['value'] = int((idx/total)*100)
        append_log(f"Fertig: {outpath.name}\n\n")
        current_proc = None

    append_log("Konvertierung beendet.\n")
    start_btn.config(state="normal")
    cancel_btn.config(state="disabled")

# -------------------- Button Handlers --------------------
def start_conversion_action():
    if not selected_files:
        messagebox.showwarning("Keine Dateien", "Bitte wähle zuerst Videodateien aus.")
        return
    start_btn.config(state="disabled")
    cancel_btn.config(state="normal")
    log_text.delete(1.0, tk.END)
    threading.Thread(target=conversion_thread, daemon=True).start()

def cancel_conversion_action():
    stop_event.set()
    if current_proc:
        try:
            current_proc.terminate()
        except Exception:
            pass
    cancel_btn.config(state="disabled")
    append_log("Abbruch angefragt — bitte warten...\n")

# -------------------- Bind UI --------------------
btn_files.config(command=select_files_action)
btn_remove.config(command=remove_selected_action)
btn_browse_target.config(command=browse_target_dir_custom)
start_btn.config(command=start_conversion_action)
cancel_btn.config(command=cancel_conversion_action)

# double click show full path
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
