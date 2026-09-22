#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Features implemented (per user selection):
1 Drag & Drop video (requires tkinterdnd2 if available; falls back to Browse)
2 Browse button
3 Auto display duration
4 Manual split time (HH:MM:SS)
5 Auto-Half Split
6 Timeline slider
7 Step buttons (+1s, +5s, +10s, +30s)
8 Lossless split using -c copy
10 Output folder selection
11 Auto file naming (input_part1.mp4 / input_part2.mp4)
12 Live FFmpeg log console
13 Status Indicators (Processing / Done / Error)
15 Remember last used output folder
18 GPU Acceleration toggle (NVENC auto-detect for re-encode step only)
21 Corruption check before processing
22 Detect & auto-fix VFR (convert to CFR) if needed
23 Auto-rename outputs if file exists

Python stdlib only (Tkinter). Optional: 'tkinterdnd2' for drag & drop.
Requires ffmpeg/ffprobe installed (PATH or local folder).
"""

import os
import sys
import json
import math
import queue
import shutil
import threading
import subprocess
from pathlib import Path
from tkinter import Tk, StringVar, BooleanVar, DoubleVar, IntVar, Text, END, DISABLED, NORMAL
from tkinter import ttk, filedialog, messagebox

APP_NAME = "Video Splitter"
SETTINGS_DIR = Path(os.environ.get("APPDATA", Path.home()/"AppData"/"Roaming")) / "Saumitra" / "VideoSplit"
SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

COMMON_FFMPEG_PATHS = [
    Path(__file__).parent / "ffmpeg.exe",
    Path(__file__).parent / "ffmpeg",
    Path("C:/ffmpeg/bin/ffmpeg.exe"),
    Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
    Path("C:/Program Files (x86)/ffmpeg/bin/ffmpeg.exe"),
]
COMMON_FFPROBE_PATHS = [
    Path(__file__).parent / "ffprobe.exe",
    Path(__file__).parent / "ffprobe",
    Path("C:/ffmpeg/bin/ffprobe.exe"),
    Path("C:/Program Files/ffmpeg/bin/ffprobe.exe"),
    Path("C:/Program Files (x86)/ffmpeg/bin/ffprobe.exe"),
]

def which(tool):
    p = shutil.which(tool)
    return Path(p) if p else None

def find_ffmpeg():
    # local/common
    for p in COMMON_FFMPEG_PATHS:
        if p.exists():
            return str(p)
    # PATH
    p = which("ffmpeg")
    return str(p) if p else None

def find_ffprobe():
    for p in COMMON_FFPROBE_PATHS:
        if p.exists():
            return str(p)
    p = which("ffprobe")
    return str(p) if p else None

FFMPEG = find_ffmpeg()
FFPROBE = find_ffprobe()

def load_settings():
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_settings(data: dict):
    try:
        SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

def seconds_to_hhmmss(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def hhmmss_to_seconds(text: str) -> float:
    text = text.strip()
    if text.isdigit():
        return float(text)
    parts = text.split(":")
    parts = [p.strip() for p in parts if p.strip() != ""]
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h = 0
        m, s = parts
    elif len(parts) == 1:
        h = 0; m = 0; s = parts[0]
    else:
        raise ValueError("Invalid time format")
    return int(h)*3600 + int(m)*60 + float(s)

def run_cmd_stream(cmd, log_callback):
    """Run a subprocess and stream stderr to log_callback; return exit code."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    for line in proc.stdout:
        if log_callback:
            log_callback(line.rstrip("\n"))
    proc.wait()
    return proc.returncode

def probe_duration(path: Path) -> float:
    if not FFPROBE:
        raise RuntimeError("ffprobe not found")
    cmd = [FFPROBE, "-v", "error", "-show_entries", "format=duration",
           "-of", "default=nokey=1:noprint_wrappers=1", str(path)]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True)
        return float(out.strip())
    except Exception as e:
        raise RuntimeError(f"Failed to read duration: {e}")

def probe_vfr(path: Path):
    """Return tuple (is_vfr: bool, avg_fps: float or None)"""
    if not FFPROBE:
        return (False, None)
    try:
        # Get avg_frame_rate & r_frame_rate
        cmd = [FFPROBE, "-v", "error", "-select_streams", "v:0",
               "-show_entries", "stream=avg_frame_rate,r_frame_rate",
               "-of", "default=nokey=1:noprint_wrappers=1", str(path)]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True).strip().splitlines()
        if len(out) >= 2:
            avg_str = out[0].strip()
            r_str = out[1].strip()
            def frac_to_float(fr):
                if fr in ("0/0", "N/A", ""):
                    return None
                if "/" in fr:
                    a,b = fr.split("/",1)
                    b = float(b) if float(b)!=0 else 1.0
                    return float(a)/float(b)
                return float(fr)
            avg = frac_to_float(avg_str)
            r = frac_to_float(r_str)
            # Heuristic: if avg fps deviates significantly from r_frame_rate (keyframe time base), consider VFR
            is_vfr = (avg is None) or (r is None) or (abs(avg - r) > 0.01)
            return (bool(is_vfr), avg if avg else r)
    except Exception:
        pass
    return (False, None)

def check_corruption(path: Path, log_callback=None) -> bool:
    """Return True if file seems OK, False if errors encountered."""
    if not FFMPEG:
        return True  # cannot check; assume ok
    cmd = [FFMPEG, "-v", "error", "-i", str(path), "-f", "null", "-"]
    try:
        code = run_cmd_stream(cmd, log_callback)
        return code == 0
    except Exception:
        return False

def ensure_unique(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    i = 1
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1

class LogConsole:
    def __init__(self, text_widget: Text):
        self.text = text_widget
        self.text.configure(state=DISABLED)
    def write(self, line: str):
        self.text.configure(state=NORMAL)
        self.text.insert(END, line + "\n")
        self.text.see(END)
        self.text.configure(state=DISABLED)
    def clear(self):
        self.text.configure(state=NORMAL)
        self.text.delete("1.0", END)
        self.text.configure(state=DISABLED)

class App(Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} — Theme A")
        self.geometry("1050x650")
        self.minsize(980, 620)
        self.configure(bg="#0d0f13")  # dark matte

        # Style (Dark Pro)
        style = ttk.Style(self)
        try:
            self.call("tk", "scaling", 1.1)
        except Exception:
            pass
        style.theme_use("clam")
        style.configure(".", background="#0d0f13", foreground="#e6f1ff", fieldbackground="#141823")
        style.configure("TLabel", background="#0d0f13", foreground="#cfe3ff")
        style.configure("TEntry", fieldbackground="#11141b", foreground="#e6f1ff", bordercolor="#1f2a3a")
        style.configure("TButton", background="#132033", foreground="#d8ecff", focusthickness=3, focuscolor="#1d2b40")
        style.map("TButton", background=[("active", "#1a2942")])
        style.configure("TScale", background="#0d0f13")
        style.configure("TLabelframe", background="#0d0f13", foreground="#9dc2ff")
        style.configure("TLabelframe.Label", background="#0d0f13", foreground="#9dc2ff")

        # State
        self.settings = load_settings()
        self.input_path = StringVar(value="")
        self.output_dir = StringVar(value=self.settings.get("last_output_dir", str(Path.home() / "Videos")))
        self.duration_s = DoubleVar(value=0.0)
        self.split_time = StringVar(value="00:00:00")
        self.slider_val = DoubleVar(value=0.0)
        self.gpu_enabled = BooleanVar(value=True)
        self.status_text = StringVar(value="Idle")
        self.status_color = StringVar(value="#728bad")

        # Header
        header = ttk.Frame(self, padding=(16, 12, 16, 8))
        header.pack(side="top", fill="x")
        title = ttk.Label(header, text="Video Splitter — Dark Pro", font=("Segoe UI", 16, "bold"))
        title.pack(side="left")
        ffstat = ttk.Label(header, text=f"FFmpeg: {'Found' if FFMPEG else 'Missing'} | FFprobe: {'Found' if FFPROBE else 'Missing'}", foreground="#7ed0ff")
        ffstat.pack(side="right")

        # Top controls row
        top = ttk.Frame(self, padding=(16, 8))
        top.pack(side="top", fill="x")

        # Drag & Drop / Browse
        self.file_btn = ttk.Button(top, text="Browse Video…", command=self.browse_file)
        self.file_btn.grid(row=0, column=0, padx=(0,8), pady=6, sticky="w")

        self.file_entry = ttk.Entry(top, textvariable=self.input_path, width=70)
        self.file_entry.grid(row=0, column=1, padx=6, pady=6, sticky="we")
        top.columnconfigure(1, weight=1)

        # Try to enable drag & drop if tkinterdnd2 available
        self._dnd_enabled = False
        try:
            import tkinterdnd2  # type: ignore
            self._dnd_enabled = True
            self.dnd = tkinterdnd2.TkinterDnD.Tk()  # noqa: F841 (to ensure package initializes)
        except Exception:
            # Show hint if not present
            hint = ttk.Label(top, text="(Tip: Install 'tkinterdnd2' for drag & drop)", foreground="#6b86a8")
            hint.grid(row=0, column=2, padx=6, sticky="e")

        if self._dnd_enabled:
            # Bind drop event to entry only if DnD available
            def handle_drop(event):
                path = event.data.strip().strip("{}")
                if os.path.isfile(path):
                    self.set_input_file(path)
            try:
                self.file_entry.drop_target_register("DND_Files")
                self.file_entry.dnd_bind("<<Drop>>", handle_drop)
            except Exception:
                pass

        # Duration label
        self.duration_label = ttk.Label(top, text="Duration: 00:00:00")
        self.duration_label.grid(row=1, column=0, padx=(0,8), pady=6, sticky="w")

        # Output folder selector
        out_row = ttk.Frame(self, padding=(16,4))
        out_row.pack(side="top", fill="x")
        ttk.Label(out_row, text="Output Folder:").pack(side="left")
        self.out_entry = ttk.Entry(out_row, textvariable=self.output_dir, width=70)
        self.out_entry.pack(side="left", padx=8, fill="x", expand=True)
        ttk.Button(out_row, text="Change…", command=self.choose_output_dir).pack(side="left", padx=6)

        # Controls
        controls = ttk.Frame(self, padding=(16, 8))
        controls.pack(side="top", fill="x")

        ttk.Label(controls, text="Split Time (HH:MM:SS or seconds):").grid(row=0, column=0, sticky="w")
        self.split_entry = ttk.Entry(controls, textvariable=self.split_time, width=16)
        self.split_entry.grid(row=0, column=1, padx=8, sticky="w")

        # Step buttons
        step_frame = ttk.Frame(controls)
        step_frame.grid(row=0, column=2, padx=4, sticky="w")
        for label, inc in [("+1s",1), ("+5s",5), ("+10s",10), ("+30s",30)]:
            ttk.Button(step_frame, text=label, command=lambda inc=inc: self.bump_time(inc)).pack(side="left", padx=2)

        # Slider
        self.slider = ttk.Scale(controls, from_=0, to=0, variable=self.slider_val, command=self.slider_changed, length=420)
        self.slider.grid(row=1, column=0, columnspan=3, pady=10, sticky="we")

        # Action buttons
        action_row = ttk.Frame(self, padding=(16,4))
        action_row.pack(side="top", fill="x")

        self.split_btn = ttk.Button(action_row, text="Split at Time", command=self.on_split_clicked)
        self.split_btn.pack(side="left", padx=(0,10))

        self.auto_half_btn = ttk.Button(action_row, text="Auto-Half Split", command=self.on_auto_half)
        self.auto_half_btn.pack(side="left", padx=(0,10))

        self.gpu_chk = ttk.Checkbutton(action_row, text="GPU Mode (NVENC for CFR fix)", variable=self.gpu_enabled)
        self.gpu_chk.pack(side="left")

        # Status
        self.status_lbl = ttk.Label(action_row, textvariable=self.status_text, foreground=self.status_color.get())
        self.status_lbl.pack(side="right")

        # Log console
        log_frame = ttk.LabelFrame(self, text="Live Log Console", padding=(12,8))
        log_frame.pack(side="top", fill="both", expand=True, padx=16, pady=(8,16))
        self.log_widget = Text(log_frame, height=16, bg="#0b0f14", fg="#d7e6ff", insertbackground="#d7e6ff",
                               relief="flat", wrap="word")
        self.log_widget.pack(side="left", fill="both", expand=True)
        self.console = LogConsole(self.log_widget)

        # Footer tip
        tip = ttk.Label(self, text="Tip: Use HH:MM:SS format | Outputs are auto-renamed to avoid overwrite | VFR is auto-fixed (CFR) only when necessary.", foreground="#7898bd")
        tip.pack(side="bottom", pady=(0,10))

        # Bindings
        self.split_entry.bind("<Return>", lambda e: self.sync_time_from_entry())
        self.bind("<Control-o>", lambda e: self.browse_file())
        self.bind("<Control-q>", lambda e: self.quit())

        # Update status colors
        self.after(100, self.refresh_status_color)

    # --- UI helpers ---
    def set_input_file(self, path: str):
        self.input_path.set(path)
        self.console.clear()
        if not os.path.isfile(path):
            return
        # Duration
        try:
            dur = probe_duration(Path(path))
            self.duration_s.set(dur)
            self.duration_label.config(text=f"Duration: {seconds_to_hhmmss(dur)}")
            self.slider.configure(to=dur)
            # set default split mid-way
            self.slider_val.set(dur/2)
            self.split_time.set(seconds_to_hhmmss(dur/2))
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not read duration.\n\n{e}")

    def browse_file(self):
        ftypes = [("Video files", "*.mp4 *.mkv *.mov *.webm *.m4v"), ("All files", "*.*")]
        path = filedialog.askopenfilename(title="Choose a video", filetypes=ftypes)
        if path:
            self.set_input_file(path)

    def choose_output_dir(self):
        d = filedialog.askdirectory(initialdir=self.output_dir.get() or str(Path.home()))
        if d:
            self.output_dir.set(d)
            self.settings["last_output_dir"] = d
            save_settings(self.settings)

    def bump_time(self, inc: int):
        try:
            cur = hhmmss_to_seconds(self.split_time.get())
        except Exception:
            cur = self.slider_val.get()
        cur += inc
        cur = min(max(cur, 0), max(0, self.duration_s.get()-0.01))
        self.split_time.set(seconds_to_hhmmss(cur))
        self.slider_val.set(cur)

    def slider_changed(self, val):
        try:
            v = float(val)
            self.split_time.set(seconds_to_hhmmss(v))
        except Exception:
            pass

    def sync_time_from_entry(self):
        try:
            v = hhmmss_to_seconds(self.split_time.get())
            v = min(max(v, 0), max(0, self.duration_s.get()-0.01))
            self.slider_val.set(v)
        except Exception:
            pass

    def set_status(self, text: str, color="#9dc2ff"):
        self.status_text.set(text)
        self.status_color.set(color)
        self.refresh_status_color()

    def refresh_status_color(self):
        self.status_lbl.configure(foreground=self.status_color.get())
        self.after(400, self.refresh_status_color)

    # --- Core actions ---
    def on_auto_half(self):
        dur = self.duration_s.get()
        if dur <= 0:
            messagebox.showwarning(APP_NAME, "Please select a valid video first.")
            return
        self.split_time.set(seconds_to_hhmmss(dur/2))
        self.slider_val.set(dur/2)
        self.on_split_clicked()

    def on_split_clicked(self):
        in_path = Path(self.input_path.get())
        if not in_path.exists():
            messagebox.showwarning(APP_NAME, "Please choose a valid input video.")
            return
        out_dir = Path(self.output_dir.get() or ".")
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Cannot access output folder:\n{e}")
            return

        try:
            split_point = hhmmss_to_seconds(self.split_time.get())
        except Exception:
            messagebox.showwarning(APP_NAME, "Invalid split time. Use HH:MM:SS or seconds.")
            return

        if split_point <= 0 or split_point >= self.duration_s.get():
            messagebox.showwarning(APP_NAME, "Split time must be within the video duration (not start or end).")
            return

        # Run in worker thread
        t = threading.Thread(target=self._do_split_worker, args=(in_path, out_dir, split_point), daemon=True)
        t.start()

    def _do_split_worker(self, in_path: Path, out_dir: Path, split_point: float):
        self.split_btn.configure(state=DISABLED); self.auto_half_btn.configure(state=DISABLED)
        self.set_status("Checking input…", "#86b3ff")
        self.console.clear()

        # 21) Corruption check
        ok = check_corruption(in_path, self.console.write)
        if not ok:
            self.set_status("Error: Input has decode errors", "#ff6b6b")
            messagebox.showerror(APP_NAME, "Input video seems corrupted. See log for details.")
            self.split_btn.configure(state=NORMAL); self.auto_half_btn.configure(state=NORMAL)
            return

        # 22) Detect VFR & optional CFR fix
        is_vfr, fps_guess = probe_vfr(in_path)
        temp_source = in_path
        if is_vfr:
            self.set_status("Detected VFR → creating CFR temp", "#e8b35c")
            if not FFMPEG:
                self.set_status("FFmpeg missing", "#ff6b6b")
                messagebox.showerror(APP_NAME, "FFmpeg not found. Cannot convert VFR→CFR.")
                self.split_btn.configure(state=NORMAL); self.auto_half_btn.configure(state=NORMAL)
                return
            # FPS to use
            fps = fps_guess or 30.0
            fps = max(1.0, round(fps))
            # Choose encoder
            use_nvenc = False
            if self.gpu_enabled.get():
                use_nvenc = self._nvenc_available()
            vcodec = "h264_nvenc" if use_nvenc else "libx264"

            temp_source = out_dir / f"{in_path.stem}_CFR_temp.mp4"
            temp_source = ensure_unique(temp_source)
            cmd = [FFMPEG, "-y", "-i", str(in_path),
                   "-map", "0:v:0", "-map", "0:a?",  # keep first video + optional audio
                   "-c:v", vcodec, "-preset", "fast",
                   "-r", str(int(fps)),
                   "-vsync", "cfr",
                   "-c:a", "aac", "-b:a", "192k",
                   str(temp_source)]
            self.console.write(f"[CFR] {' '.join(cmd)}")
            code = run_cmd_stream(cmd, self.console.write)
            if code != 0 or not temp_source.exists():
                self.set_status("CFR conversion failed", "#ff6b6b")
                messagebox.showerror(APP_NAME, "Failed to convert VFR→CFR. See logs.")
                self.split_btn.configure(state=NORMAL); self.auto_half_btn.configure(state=NORMAL)
                return
        else:
            self.console.write("[Info] Source appears CFR. Skipping CFR step.")

        # 8, 11, 23) Prepare outputs (auto rename if exists)
        base = in_path.stem
        p1 = ensure_unique(out_dir / f"{base}_part1.mp4")
        p2 = ensure_unique(out_dir / f"{base}_part2.mp4")

        # Part 1: start→split_point (copy)
        self.set_status("Cutting Part 1…", "#86e7a5")
        if not FFMPEG:
            self.set_status("FFmpeg missing", "#ff6b6b")
            messagebox.showerror(APP_NAME, "FFmpeg not found.")
            self.split_btn.configure(state=NORMAL); self.auto_half_btn.configure(state=NORMAL)
            return
        cmd1 = [FFMPEG, "-y", "-i", str(temp_source), "-to", str(split_point), "-c", "copy", str(p1)]
        self.console.write(" ".join(cmd1))
        code1 = run_cmd_stream(cmd1, self.console.write)

        # Part 2: split_point→end (copy). Use -ss before -i for faster seek.
        self.set_status("Cutting Part 2…", "#86e7a5")
        cmd2 = [FFMPEG, "-y", "-ss", str(split_point), "-i", str(temp_source), "-c", "copy", str(p2)]
        self.console.write(" ".join(cmd2))
        code2 = run_cmd_stream(cmd2, self.console.write)

        # Clean temp
        if temp_source != in_path:
            try:
                temp_source.unlink(missing_ok=True)
            except Exception:
                pass

        if code1 == 0 and code2 == 0 and p1.exists() and p2.exists():
            self.set_status("Done ✔", "#8ff0b3")
            self.console.write(f"[OK] Saved:\n - {p1}\n - {p2}")
            # remember output dir
            self.settings["last_output_dir"] = str(out_dir)
            save_settings(self.settings)
            messagebox.showinfo(APP_NAME, f"Split complete:\n\n{p1.name}\n{p2.name}")
        else:
            self.set_status("Error during split", "#ff6b6b")
            messagebox.showerror(APP_NAME, "One or both parts failed. Check log.")

        self.split_btn.configure(state=NORMAL); self.auto_half_btn.configure(state=NORMAL)

    def _nvenc_available(self) -> bool:
        if not FFMPEG:
            return False
        try:
            out = subprocess.check_output([FFMPEG, "-hide_banner", "-encoders"], stderr=subprocess.STDOUT, universal_newlines=True)
            return ("h264_nvenc" in out) or ("hevc_nvenc" in out)
        except Exception:
            return False

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
