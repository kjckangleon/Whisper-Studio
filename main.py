import tkinter as tk
from tkinter import filedialog
from tkinterdnd2 import TkinterDnD, DND_FILES
import threading
import subprocess
import os
import re
import time

# ─────────────────── THEME ─────────────────── #
BG_DEEP    = "#0d0d14"
BG_PANEL   = "#13131f"
BG_CARD    = "#1a1a2e"
BG_DROP    = "#16213e"
ACCENT     = "#7c3aed"
ACCENT2    = "#06b6d4"
SUCCESS    = "#10b981"
ERROR      = "#ef4444"
WARN       = "#f59e0b"
CANCEL_C   = "#dc2626"
TEXT_PRI   = "#f1f5f9"
TEXT_SEC   = "#64748b"
TEXT_DIM   = "#334155"
BORDER     = "#1e293b"
MONO_FG    = "#a5f3fc"
SEG_FG     = "#818cf8"
ETA_FG     = "#34d399"

SUPPORTED  = ("*.mp4", "*.mkv", "*.mov", "*.avi", "*.mp3", "*.wav", "*.m4a", "*.flac", "*.webm")
MODELS     = ["tiny", "base", "small", "medium", "large"]
TASKS      = ["translate", "transcribe"]
FORMATS    = ["srt", "vtt", "txt", "tsv", "json"]

# Whisper segment lines:  [00:01.000 --> 00:04.000]  Hello world
RE_SEGMENT = re.compile(r"\[(\d+):(\d+\.\d+)\s*-->\s*(\d+):(\d+\.\d+)\](.*)")

# ─────────────────── RUNTIME STATE ─────────────────── #
is_processing  = False
_process       = None
_cancel_flag   = False
_start_time    = 0.0
_total_dur_sec = 0.0
_seg_count     = 0

# ─────────────────── HELPERS ─────────────────── #
def _mmss_to_sec(mm, ss):
    return int(mm) * 60 + float(ss)

def get_media_duration(path):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=10
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0

def detect_gpu():
    # CUDA
    try:
        r = subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
        if r.returncode == 0:
            return True, False, None
    except Exception:
        pass
    # Apple MPS
    try:
        r = subprocess.run(
            ["python", "-c", "import torch; print(torch.backends.mps.is_available())"],
            capture_output=True, text=True, timeout=8
        )
        if r.stdout.strip() == "True":
            return False, True, None
    except Exception:
        pass
    return False, False, (
        "⚠  No GPU detected — running on CPU.\n"
        "   Large models will be VERY slow. Consider 'tiny' or 'base' for quick tests."
    )

# ─────────────────── UI HELPERS ─────────────────── #
def set_status(text, color=TEXT_PRI):
    status_label.config(text=text, fg=color)

def set_eta(text):
    eta_label.config(text=text)

def log(text, tag="normal"):
    output_box.config(state="normal")
    output_box.insert(tk.END, text + "\n", tag)
    output_box.see(tk.END)
    output_box.config(state="disabled")

def clear_logs():
    output_box.config(state="normal")
    output_box.delete("1.0", tk.END)
    output_box.config(state="disabled")

def set_drop_state(active=False):
    color = ACCENT if active else BG_DROP
    for w in (drop_canvas, drop_inner, drop_icon_lbl, drop_text_lbl, drop_hint_lbl):
        w.config(bg=color)

def set_progress(fraction, color=ACCENT):
    fraction = max(0.0, min(1.0, fraction))
    progress_bar.config(bg=color)
    progress_bar.place(relx=0, rely=0, relwidth=fraction, relheight=1)

def finish_progress(success=True):
    if _cancel_flag:
        color = WARN
    elif success:
        color = SUCCESS
    else:
        color = ERROR
    set_progress(1.0, color)
    root.after(900,  lambda: progress_bar.place_forget())
    root.after(1000, lambda: progress_bar.config(bg=ACCENT))

def set_processing(state):
    global is_processing
    is_processing = state
    if state:
        btn_select.config(state="disabled")
        btn_cancel.config(state="normal", bg=CANCEL_C, fg=TEXT_PRI)
        set_progress(0.0)
    else:
        btn_select.config(state="normal")
        btn_cancel.config(state="disabled", bg=BG_CARD, fg=TEXT_DIM)
        set_eta("")

# ─────────────────── CANCEL ─────────────────── #
def cancel_processing():
    global _cancel_flag, _process
    if not is_processing:
        return
    _cancel_flag = True
    if _process and _process.poll() is None:
        try:
            _process.terminate()
        except Exception:
            pass
    root.after(0, set_status, "⏹  Cancelled", WARN)
    root.after(0, log, "─" * 60, "dim")
    root.after(0, log, "⏹  Cancelled by user.", "warn")

# ─────────────────── MAIN WORKER ─────────────────── #
def run_whisper(file_path):
    global is_processing, _process, _cancel_flag
    global _start_time, _total_dur_sec, _seg_count

    _cancel_flag   = False
    _start_time    = time.time()
    _total_dur_sec = 0.0
    _seg_count     = 0

    try:
        root.after(0, set_processing, True)
        root.after(0, set_status, "⏳  Processing…", WARN)
        root.after(0, clear_logs)

        # GPU detection
        root.after(0, log, "🔍  Checking hardware…", "dim")
        has_cuda, has_mps, gpu_warn = detect_gpu()
        if has_cuda:
            root.after(0, log, "✔  CUDA GPU detected — running on GPU.", "success")
        elif has_mps:
            root.after(0, log, "✔  Apple MPS detected — running on GPU.", "success")
        else:
            root.after(0, log, gpu_warn, "warn")

        # Duration probe
        _total_dur_sec = get_media_duration(file_path)
        if _total_dur_sec > 0:
            mm = int(_total_dur_sec // 60)
            ss = int(_total_dur_sec % 60)
            root.after(0, log, f"🕐  Media duration: {mm}m {ss:02d}s", "dim")
        else:
            root.after(0, log, "🕐  Duration unknown (ffprobe missing) — ETA unavailable.", "dim")

        root.after(0, log, f"📁  {os.path.basename(file_path)}", "dim")
        root.after(0, log,
            f"🤖  Model: {selected_model.get()}  │  "
            f"Task: {selected_task.get()}  │  "
            f"Format: {selected_format.get()}", "dim")
        root.after(0, log, "─" * 60, "dim")

        cmd = [
            "python", "-m", "whisper", file_path,
            "--model",         selected_model.get(),
            "--task",          selected_task.get(),
            "--output_format", selected_format.get(),
        ]

        _process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in _process.stdout:
            if _cancel_flag:
                break

            stripped = line.strip()
            if not stripped:
                continue

            m = RE_SEGMENT.match(stripped)
            if m:
                _seg_count += 1
                end_sec = _mmss_to_sec(m.group(3), m.group(4))
                text    = m.group(5).strip()

                # Format: [mm:ss] » transcript text
                end_mm = int(m.group(3))
                end_ss = int(float(m.group(4)))
                seg_display = f"  [{end_mm:02d}:{end_ss:02d}]  »  {text}"
                root.after(0, log, seg_display, "segment")

                # Progress
                if _total_dur_sec > 0:
                    frac = min(end_sec / _total_dur_sec, 0.99)
                    root.after(0, set_progress, frac)

                    elapsed = time.time() - _start_time
                    if frac > 0.02 and elapsed > 0:
                        total_est = elapsed / frac
                        remaining = max(0, total_est - elapsed)
                        rm = int(remaining // 60)
                        rs = int(remaining  % 60)
                        spd = end_sec / elapsed
                        eta_txt = (
                            f"ETA  {rm:02d}m {rs:02d}s"
                            f"   │   {frac*100:.0f}%"
                            f"   │   {spd:.1f}× realtime"
                            f"   │   {_seg_count} segs"
                        )
                        root.after(0, set_eta, eta_txt)
                else:
                    elapsed = time.time() - _start_time
                    em = int(elapsed // 60)
                    es = int(elapsed % 60)
                    root.after(0, set_eta,
                        f"Elapsed  {em:02d}m {es:02d}s   │   {_seg_count} segs")
            else:
                root.after(0, log, stripped, "normal")

        if not _cancel_flag:
            _process.wait()

        elapsed = time.time() - _start_time
        em = int(elapsed // 60)
        es = int(elapsed % 60)

        if _cancel_flag:
            root.after(0, finish_progress, False)
        elif _process.returncode == 0:
            root.after(0, set_status, f"✔  Done in {em}m {es:02d}s", SUCCESS)
            root.after(0, finish_progress, True)
            root.after(0, log, "─" * 60, "dim")
            root.after(0, log,
                f"✅  Complete!  {_seg_count} segments   │   {em}m {es:02d}s total", "success")
        else:
            root.after(0, set_status, "✖  Whisper exited with an error", ERROR)
            root.after(0, finish_progress, False)

    except FileNotFoundError:
        root.after(0, set_status, "✖  whisper not found", ERROR)
        root.after(0, finish_progress, False)
        root.after(0, log, "Run:  pip install openai-whisper", "error")
    except Exception as e:
        root.after(0, set_status, "✖  Unexpected error", ERROR)
        root.after(0, finish_progress, False)
        root.after(0, log, str(e), "error")
    finally:
        is_processing = False
        _process      = None
        root.after(0, set_processing, False)

# ─────────────────── FILE ROUTING ─────────────────── #
def process_file(file_path):
    if is_processing:
        return
    file_path = file_path.strip("{}").strip()
    if not os.path.isfile(file_path):
        set_status("✖  File not found", ERROR)
        return
    file_label.config(text=f"📄  {os.path.basename(file_path)}")
    threading.Thread(target=run_whisper, args=(file_path,), daemon=True).start()

def drop_enter(event): set_drop_state(True)
def drop_leave(event): set_drop_state(False)
def drop(event):
    set_drop_state(False)
    process_file(event.data)

def open_file():
    fp = filedialog.askopenfilename(
        filetypes=[("Video / Audio", " ".join(SUPPORTED)), ("All Files", "*.*")]
    )
    if fp:
        process_file(fp)

def copy_logs():
    root.clipboard_clear()
    root.clipboard_append(output_box.get("1.0", tk.END))
    set_status("📋  Logs copied", ACCENT2)
    root.after(2000, lambda: set_status("Ready", TEXT_SEC))

# ─────────────────── PILL SELECTOR ─────────────────── #
class PillSelector(tk.Frame):
    def __init__(self, parent, label, options, variable, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        tk.Label(self, text=label, bg=BG_PANEL, fg=TEXT_SEC,
                 font=("Courier New", 8)).pack(anchor="w", pady=(0, 4))
        row = tk.Frame(self, bg=BG_PANEL)
        row.pack(anchor="w")
        self.btns = {}
        variable.set(options[0])

        def select(opt):
            variable.set(opt)
            for o, b in self.btns.items():
                on = (o == opt)
                b.config(bg=ACCENT if on else BG_CARD,
                         fg=TEXT_PRI if on else TEXT_SEC)

        for opt in options:
            b = tk.Button(
                row, text=opt,
                bg=ACCENT if opt == options[0] else BG_CARD,
                fg=TEXT_PRI if opt == options[0] else TEXT_SEC,
                font=("Courier New", 9), relief="flat",
                padx=10, pady=4, cursor="hand2",
                command=lambda o=opt: select(o)
            )
            b.pack(side="left", padx=(0, 4))
            self.btns[opt] = b

# ═══════════════════════════════════════════════════════
#  ROOT WINDOW
# ═══════════════════════════════════════════════════════
root = TkinterDnD.Tk()
root.title("Whisper Studio")
root.geometry("880x710")
root.minsize(720, 600)
root.configure(bg=BG_DEEP)

# StringVars (must follow root creation)
selected_model  = tk.StringVar()
selected_task   = tk.StringVar()
selected_format = tk.StringVar()

# ── HEADER ── #
hdr = tk.Frame(root, bg=BG_DEEP)
hdr.pack(fill="x", padx=28, pady=(22, 4))
tk.Label(hdr, text="WHISPER", font=("Courier New", 22, "bold"),
         bg=BG_DEEP, fg=ACCENT).pack(side="left")
tk.Label(hdr, text=" STUDIO",  font=("Courier New", 22, "bold"),
         bg=BG_DEEP, fg=TEXT_PRI).pack(side="left")
tk.Label(hdr, text=" AI SUBTITLES ", font=("Courier New", 8),
         bg=ACCENT, fg=TEXT_PRI, padx=4, pady=2).pack(side="left", padx=10, pady=6)
tk.Label(hdr, text="openai/whisper", font=("Courier New", 9),
         bg=BG_DEEP, fg=TEXT_DIM).pack(side="right", pady=6)

tk.Frame(root, bg=BORDER, height=1).pack(fill="x", padx=28)

# ── CONTROLS ── #
ctrl = tk.Frame(root, bg=BG_PANEL, pady=14)
ctrl.pack(fill="x", padx=28, pady=10, ipadx=14)
PillSelector(ctrl, "MODEL",  MODELS,  selected_model ).pack(side="left", padx=14)
tk.Frame(ctrl, bg=BORDER, width=1).pack(side="left", fill="y", padx=8)
PillSelector(ctrl, "TASK",   TASKS,   selected_task  ).pack(side="left", padx=14)
tk.Frame(ctrl, bg=BORDER, width=1).pack(side="left", fill="y", padx=8)
PillSelector(ctrl, "FORMAT", FORMATS, selected_format).pack(side="left", padx=14)

# ── DROP ZONE ── #
drop_canvas = tk.Frame(root, bg=BG_DROP, height=100,
                       highlightbackground=ACCENT, highlightthickness=1)
drop_canvas.pack(fill="x", padx=28, pady=(0, 10))
drop_canvas.pack_propagate(False)

drop_inner    = tk.Frame(drop_canvas, bg=BG_DROP)
drop_inner.place(relx=0.5, rely=0.5, anchor="center")
drop_icon_lbl = tk.Label(drop_inner, text="⬇", font=("Courier New", 20),
                          bg=BG_DROP, fg=ACCENT)
drop_icon_lbl.pack()
drop_text_lbl = tk.Label(drop_inner, text="Drop a video or audio file here",
                          font=("Courier New", 11, "bold"), bg=BG_DROP, fg=TEXT_PRI)
drop_text_lbl.pack()
drop_hint_lbl = tk.Label(drop_inner, text="mp4  mkv  mov  avi  mp3  wav  m4a  flac  webm",
                          font=("Courier New", 8), bg=BG_DROP, fg=TEXT_SEC)
drop_hint_lbl.pack(pady=(2, 0))

for w in (drop_canvas, drop_inner, drop_icon_lbl, drop_text_lbl, drop_hint_lbl):
    w.drop_target_register(DND_FILES)
    w.dnd_bind("<<Drop>>",      drop)
    w.dnd_bind("<<DragEnter>>", drop_enter)
    w.dnd_bind("<<DragLeave>>", drop_leave)

# ── BUTTON BAR ── #
bar = tk.Frame(root, bg=BG_DEEP)
bar.pack(fill="x", padx=28, pady=(0, 6))

btn_select = tk.Button(
    bar, text="Select File", command=open_file,
    bg=ACCENT, fg=TEXT_PRI, font=("Courier New", 10, "bold"),
    relief="flat", padx=16, pady=7,
    activebackground="#6d28d9", activeforeground=TEXT_PRI, cursor="hand2"
)
btn_select.pack(side="left")

btn_cancel = tk.Button(
    bar, text="⏹  Cancel", command=cancel_processing,
    bg=BG_CARD, fg=TEXT_DIM, font=("Courier New", 10, "bold"),
    relief="flat", padx=14, pady=7,
    activebackground=CANCEL_C, activeforeground=TEXT_PRI,
    cursor="hand2", state="disabled"
)
btn_cancel.pack(side="left", padx=(8, 0))

file_label = tk.Label(bar, text="📄  No file selected",
                       font=("Courier New", 9), bg=BG_DEEP, fg=TEXT_SEC)
file_label.pack(side="left", padx=14)

btn_copy = tk.Button(
    bar, text="Copy Logs", command=copy_logs,
    bg=BG_CARD, fg=TEXT_SEC, font=("Courier New", 9),
    relief="flat", padx=10, pady=7,
    activebackground=BG_DROP, activeforeground=TEXT_PRI, cursor="hand2"
)
btn_copy.pack(side="right")

# ── PROGRESS + STATUS ── #
prog_row = tk.Frame(root, bg=BG_DEEP)
prog_row.pack(fill="x", padx=28, pady=(2, 0))

status_label = tk.Label(prog_row, text="Ready",
                         font=("Courier New", 9), bg=BG_DEEP, fg=TEXT_SEC,
                         width=30, anchor="w")
status_label.pack(side="left")

prog_track = tk.Frame(prog_row, bg=BG_CARD, height=4)
prog_track.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=9)

progress_bar = tk.Frame(prog_track, bg=ACCENT, height=4)
# hidden initially

# ── ETA ROW ── #
eta_row = tk.Frame(root, bg=BG_DEEP)
eta_row.pack(fill="x", padx=28, pady=(1, 4))

eta_label = tk.Label(eta_row, text="",
                      font=("Courier New", 8), bg=BG_DEEP, fg=ETA_FG, anchor="w")
eta_label.pack(side="left")

# ── CONSOLE ── #
console = tk.Frame(root, bg=BG_PANEL,
                   highlightbackground=BORDER, highlightthickness=1)
console.pack(fill="both", expand=True, padx=28, pady=(2, 16))

con_hdr = tk.Frame(console, bg=BG_CARD, height=26)
con_hdr.pack(fill="x")
con_hdr.pack_propagate(False)
tk.Label(con_hdr, text="● ● ●", font=("Courier New", 8),
         bg=BG_CARD, fg=TEXT_DIM).pack(side="left", padx=10)
tk.Label(con_hdr, text="OUTPUT / SEGMENTS",
         font=("Courier New", 8), bg=BG_CARD, fg=TEXT_SEC).pack(side="left")

output_box = tk.Text(
    console,
    bg=BG_DEEP, fg=MONO_FG,
    font=("Courier New", 9),
    relief="flat",
    insertbackground=ACCENT,
    selectbackground=ACCENT,
    wrap="word",
    state="disabled",
    padx=14, pady=10
)
sb = tk.Scrollbar(console, command=output_box.yview,
                  bg=BG_PANEL, troughcolor=BG_DEEP,
                  activebackground=ACCENT, relief="flat", width=8)
output_box.config(yscrollcommand=sb.set)
sb.pack(side="right", fill="y")
output_box.pack(fill="both", expand=True)

output_box.tag_config("normal",  foreground=MONO_FG)
output_box.tag_config("dim",     foreground=TEXT_DIM)
output_box.tag_config("success", foreground=SUCCESS)
output_box.tag_config("error",   foreground=ERROR)
output_box.tag_config("warn",    foreground=WARN)
output_box.tag_config("segment", foreground=SEG_FG)

# ── DEFAULTS + BOOT ── #
selected_model.set("medium")
selected_task.set("translate")
selected_format.set("srt")

log("Whisper Studio ready.  Drop a file or click 'Select File'.", "dim")
log("Tip: install ffmpeg for accurate progress % and ETA.", "dim")

root.mainloop()
