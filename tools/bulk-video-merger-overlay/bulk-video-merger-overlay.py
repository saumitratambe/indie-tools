#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Bulk Merger — Smart Fix + Lossless + Optional Overlay (FFmpeg)
Adds overlay PNG picker, position/scale/opacity controls, 5s preview, and merge-with-overlay.
Author: Saumitra Tambe

Requirements:
  • Python 3.8+
  • FFmpeg & FFprobe in PATH or next to this script
  • NVIDIA GPU optional (auto-uses h264_nvenc when available + enabled)
"""

import os, re, sys, shlex, time, threading, subprocess, math, signal, tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "Video Bulk Merger — Smart Fix + Lossless + Overlay (FFmpeg)"
TEMP_LIST_NAME = "_concat_list.txt"

# ------------------------ Utilities ------------------------

def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]

def run_cmd(cmd):
    # keep stderr, stdout as text; preserve utf8 replacement if needed
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")

def find_bin(names):
    for n in names:
        try:
            p = subprocess.run([n, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if p.returncode == 0:
                return n
        except Exception:
            pass
    return None

FFMPEG = find_bin(["ffmpeg.exe","ffmpeg"])
FFPROBE = find_bin(["ffprobe.exe","ffprobe"])

def ffprobe_json(path):
    # flat probing (no json lib needed)
    p1 = run_cmd([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                  "-of", "default=nw=1:nk=1", path])
    try:
        duration = float(p1.stdout.strip())
    except Exception:
        duration = 0.0

    vkeys = "codec_name,width,height,r_frame_rate,pix_fmt,field_order,codec_time_base"
    p2 = run_cmd([FFPROBE, "-v", "error", "-select_streams", "v:0",
                  "-show_entries", f"stream={vkeys}",
                  "-of", "default=nw=1", path])
    vinfo = {}
    for line in p2.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            vinfo[k.strip()] = v.strip()

    akeys = "codec_name,channels,sample_rate,channel_layout,codec_time_base"
    p3 = run_cmd([FFPROBE, "-v", "error", "-select_streams", "a:0",
                  "-show_entries", f"stream={akeys}",
                  "-of", "default=nw=1", path])
    ainfo = {}
    for line in p3.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            ainfo[k.strip()] = v.strip()

    return {"duration": duration, "video": vinfo, "audio": ainfo, "has_audio": bool(ainfo)}

def rframe_rate_to_float(r):
    if not r or "/" not in r:
        return 0.0
    num, den = r.split("/", 1)
    try:
        num = float(num); den = float(den)
        if den == 0:
            return 0.0
        return num/den
    except:
        return 0.0

def parse_ffmpeg_time(line):
    m = re.search(r"time=(\d+):(\d+):(\d+)(?:\.(\d+))?", line)
    if m:
        h, m_, s, ms = m.groups()
        h = int(h); m_ = int(m_); s = int(s); ms = int(ms) if ms else 0
        return h*3600 + m_*60 + s + ms/100.0
    return None

def encoder_has_nvenc():
    out = run_cmd([FFMPEG, "-hide_banner", "-encoders"])
    return "h264_nvenc" in out.stdout

def sanitize_list_path(name):
    return name.replace("'", "'\\''")

# ------------------------ App ------------------------

class VideoMergerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1020x760")
        self.configure(bg="#0b0f14")

        # core state
        self.folder_var = tk.StringVar()
        self.output_var = tk.StringVar(value="merged_output.mp4")
        self.use_nvenc = tk.BooleanVar(value=True)
        self.preset_var = tk.StringVar(value="ultrafast")
        self.proc = None
        self.stop_flag = False
        self.files = []
        self.file_map = {}  # original -> final (reencoded or original)
        self.total_duration = 0.0
        self.baseline = None
        self.reencoded_dir = None

        # overlay state
        self.overlay_path = tk.StringVar(value="")
        self.overlay_enabled = tk.BooleanVar(value=False)
        self.overlay_position = tk.StringVar(value="top-right")  # tl, tr, bl, br, center, custom
        self.overlay_scale_pct = tk.IntVar(value=35)
        self.overlay_opacity = tk.DoubleVar(value=0.85)  # 0..1
        self.overlay_x = tk.IntVar(value=20)
        self.overlay_y = tk.IntVar(value=20)

        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#111827")
        style.configure("TLabel", background="#111827", foreground="#d1d5db", font=("Segoe UI", 10))
        style.configure("TCheckbutton", background="#111827", foreground="#d1d5db", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=6)
        style.configure("TCombobox", fieldbackground="#0b0f14", background="#0b0f14", foreground="#d1d5db")

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        # Top selectors
        top = ttk.Frame(outer, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Chunks Folder:").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.folder_var, width=58).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Button(top, text="Browse", command=self.browse_folder).grid(row=1, column=1, padx=5)

        ttk.Label(top, text="Output File:").grid(row=0, column=2, sticky="w", padx=(15,0))
        ttk.Entry(top, textvariable=self.output_var, width=38).grid(row=1, column=2, padx=5)
        ttk.Button(top, text="Pick", command=self.pick_output).grid(row=1, column=3, padx=5)

        # Options row
        opt = ttk.Frame(outer, padding=10)
        opt.pack(fill="x")
        ttk.Label(opt, text="Reencode preset:").pack(side="left")
        ttk.Combobox(opt, textvariable=self.preset_var, values=["ultrafast","superfast","veryfast","faster","fast"],
                     width=12, state="readonly").pack(side="left", padx=6)
        ttk.Checkbutton(opt, text="Use NVIDIA NVENC (if available)", variable=self.use_nvenc).pack(side="left", padx=12)

        # Overlay panel
        ov = ttk.LabelFrame(outer, text="Overlay", padding=10)
        ov.pack(fill="x", pady=(6,6))
        ttk.Checkbutton(ov, text="Enable overlay", variable=self.overlay_enabled, command=self._toggle_overlay_state).grid(row=0, column=0, sticky="w")

        ttk.Label(ov, text="Overlay PNG:").grid(row=1, column=0, sticky="w", pady=(4,0))
        ttk.Entry(ov, textvariable=self.overlay_path, width=62).grid(row=1, column=1, sticky="w", padx=5, pady=(4,0))
        ttk.Button(ov, text="Choose", command=self.pick_overlay).grid(row=1, column=2, padx=5, pady=(4,0))
        ttk.Button(ov, text="Preview 5s", command=self.preview_overlay).grid(row=1, column=3, padx=5, pady=(4,0))

        ttk.Label(ov, text="Position:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Combobox(ov, textvariable=self.overlay_position,
                     values=["top-left","top-right","bottom-left","bottom-right","center","custom"],
                     width=16, state="readonly").grid(row=2, column=1, sticky="w", padx=5, pady=4)

        ttk.Label(ov, text="Scale %:").grid(row=2, column=2, sticky="e", pady=4)
        ttk.Spinbox(ov, from_=5, to=300, textvariable=self.overlay_scale_pct, width=8).grid(row=2, column=3, sticky="w", padx=5, pady=4)

        ttk.Label(ov, text="Opacity (0-1):").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Spinbox(ov, from_=0.0, to=1.0, increment=0.05, textvariable=self.overlay_opacity, width=8).grid(row=3, column=1, sticky="w", padx=5, pady=4)

        ttk.Label(ov, text="Custom X:").grid(row=3, column=2, sticky="e", pady=4)
        ttk.Spinbox(ov, from_=-4096, to=4096, textvariable=self.overlay_x, width=8).grid(row=3, column=3, sticky="w", padx=5, pady=4)
        ttk.Label(ov, text="Custom Y:").grid(row=3, column=4, sticky="e", pady=4)
        self.ov_y_spin = ttk.Spinbox(ov, from_=-4096, to=4096, textvariable=self.overlay_y, width=8)
        self.ov_y_spin.grid(row=3, column=5, sticky="w", padx=5, pady=4)

        # Actions
        actions = ttk.Frame(outer, padding=10)
        actions.pack(fill="x")
        self.scan_btn = ttk.Button(actions, text="1) Scan Files", command=self.scan_files)
        self.scan_btn.pack(side="left")
        self.fix_btn = ttk.Button(actions, text="2) Auto-Fix (Reencode if needed)", command=self.autofix_files, state="disabled")
        self.fix_btn.pack(side="left", padx=8)
        self.merge_btn = ttk.Button(actions, text="3) Merge All", command=self.merge_all, state="disabled")
        self.merge_btn.pack(side="left", padx=8)
        self.cancel_btn = ttk.Button(actions, text="Cancel", command=self.cancel_current, state="disabled")
        self.cancel_btn.pack(side="left", padx=8)

        # Progress & status
        rightwrap = ttk.Frame(actions)
        rightwrap.pack(side="right")
        self.progress = ttk.Progressbar(rightwrap, orient="horizontal", length=360, mode="determinate")
        self.progress.pack(side="right", padx=10)
        self.status_lbl = ttk.Label(rightwrap, text="Idle")
        self.status_lbl.pack(side="right", padx=10)

        # Log
        log_frame = ttk.Frame(outer, padding=10)
        log_frame.pack(fill="both", expand=True)
        ttk.Label(log_frame, text="Log Output:").pack(anchor="w")
        self.log = tk.Text(log_frame, height=22, bg="#0b0f14", fg="#d1d5db")
        self.log.pack(fill="both", expand=True)

        self._toggle_overlay_state()

    # ---------- small helpers ----------
    def browse_folder(self):
        path = filedialog.askdirectory(title="Select folder")
        if path:
            self.folder_var.set(path)

    def pick_output(self):
        path = filedialog.asksaveasfilename(title="Select output file",
                                            defaultextension=".mp4",
                                            filetypes=[("MP4", "*.mp4"), ("All", "*.*")])
        if path:
            self.output_var.set(path)

    def pick_overlay(self):
        path = filedialog.askopenfilename(title="Select overlay PNG",
                                          filetypes=[("PNG image", "*.png"), ("All files", "*.*")])
        if path:
            self.overlay_path.set(path)

    def print_log(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.update_idletasks()

    def set_status(self, txt):
        self.status_lbl.config(text=txt)
        self.update_idletasks()

    def _toggle_overlay_state(self):
        enabled = self.overlay_enabled.get()
        # No hard disable of controls; just info/status update
        self.set_status("Overlay: ON" if enabled else "Overlay: OFF")

    # ---------- Scanning ----------
    def scan_files(self):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Please select a valid folder.")
            return

        exts = (".mp4",".mov",".mkv",".ts",".m4v")
        files = [f for f in os.listdir(folder) if f.lower().endswith(exts)]
        files.sort(key=natural_key)
        self.files = [os.path.join(folder, f) for f in files]
        self.file_map = {fp: fp for fp in self.files}
        self.total_duration = 0.0
        self.reencoded_dir = os.path.join(folder, "reencoded")
        os.makedirs(self.reencoded_dir, exist_ok=True)

        if not self.files:
            self.print_log("No video files found.")
            self.fix_btn.configure(state="disabled")
            self.merge_btn.configure(state="disabled")
            return

        self.print_log(f"Found {len(self.files)} files. Probing…")
        good_files = []
        for fp in self.files:
            meta = ffprobe_json(fp)
            self.total_duration += meta["duration"]
            if meta["duration"] <= 0.2 or not meta["video"]:
                self.print_log(f"⚠️  Corrupt or unreadable: {os.path.basename(fp)} (duration/video stream missing)")
            else:
                good_files.append((fp, meta))

        if not good_files:
            self.print_log("No usable files to merge.")
            self.fix_btn.configure(state="disabled")
            self.merge_btn.configure(state="disabled")
            return

        # Baseline from first good file
        bfp, bmeta = good_files[0]
        self.baseline = {
            "width": int(bmeta["video"].get("width", 0) or 0),
            "height": int(bmeta["video"].get("height", 0) or 0),
            "fps": rframe_rate_to_float(bmeta["video"].get("r_frame_rate","0/0")),
            "vcodec": bmeta["video"].get("codec_name",""),
            "pix_fmt": bmeta["video"].get("pix_fmt","yuv420p"),
            "has_audio": bmeta["has_audio"],
            "acodec": bmeta["audio"].get("codec_name","aac") if bmeta["has_audio"] else "aac",
            "channels": int(bmeta["audio"].get("channels","2") or 2) if bmeta["has_audio"] else 2,
            "sample_rate": int(bmeta["audio"].get("sample_rate","48000") or 48000) if bmeta["has_audio"] else 48000,
        }
        if self.baseline["fps"] <= 0:
            self.baseline["fps"] = 30.0

        size_mb = sum(os.path.getsize(fp) for fp in self.files)/ (1024*1024)
        self.print_log(f"✔️ Scan complete. Total size ~{size_mb:.2f} MB. Baseline: "
                       f'{self.baseline["width"]}x{self.baseline["height"]} @ {self.baseline["fps"]:.3f}fps, '
                       f'video={self.baseline["vcodec"]}, audio={self.baseline["acodec"]} ({self.baseline["channels"]}ch/{self.baseline["sample_rate"]}Hz)')
        self.print_log("Next: Click “Auto-Fix” to re-encode only the incompatible files, then “Merge All”.")
        self.fix_btn.configure(state="normal")
        self.merge_btn.configure(state="disabled")

    # ---------- Decide if reencode is needed ----------
    def needs_reencode(self, meta):
        b = self.baseline
        v = meta["video"]
        a = meta["audio"]

        same_res = (int(v.get("width",0) or 0) == b["width"] and int(v.get("height",0) or 0) == b["height"])
        same_fps = abs(rframe_rate_to_float(v.get("r_frame_rate","0/0")) - b["fps"]) < 0.01
        same_vc  = (v.get("codec_name","") == b["vcodec"] == "h264")
        same_pix = (v.get("pix_fmt","yuv420p") == "yuv420p")
        has_audio = meta["has_audio"]

        if not (same_res and same_fps and same_vc and same_pix):
            return True

        if has_audio != b["has_audio"]:
            return True
        if has_audio:
            if a.get("codec_name","") != "aac":
                return True
            if int(a.get("channels","0") or 0) != b["channels"]:
                return True
            if int(a.get("sample_rate","0") or 0) != b["sample_rate"]:
                return True

        if meta["duration"] <= 0.2 or not v:
            return True

        return False

    # ---------- Reencode a single file ----------
    def reencode_one(self, in_fp, out_fp):
        b = self.baseline
        use_nv = self.use_nvenc.get() and encoder_has_nvenc()
        vcodec = "h264_nvenc" if use_nv else "libx264"
        preset = self.preset_var.get()

        vf = f"scale={b['width']}:{b['height']}:flags=bicubic,fps={b['fps']}"
        base = [FFMPEG, "-hide_banner", "-y", "-i", in_fp]

        meta = ffprobe_json(in_fp)
        maps = []
        if meta["has_audio"]:
            maps = ["-map", "0:v:0", "-map", "0:a:0"]
            a_args = ["-c:a", "aac", "-b:a", "128k", "-ac", str(b["channels"]), "-ar", str(b["sample_rate"])]
        else:
            base = [FFMPEG, "-hide_banner", "-y", "-i", in_fp, "-f", "lavfi", "-t", f"{max(0.1, meta['duration']):.3f}",
                    "-i", f"anullsrc=channel_layout=stereo:sample_rate={b['sample_rate']}"]
            maps = ["-map", "0:v:0", "-map", "1:a:0"]
            a_args = ["-c:a", "aac", "-b:a", "128k", "-ac", str(b["channels"]), "-ar", str(b["sample_rate"])]

        v_args = ["-c:v", vcodec, "-pix_fmt", "yuv420p", "-preset", preset,
                  "-tune", "zerolatency", "-movflags", "+faststart",
                  "-vf", vf]

        if vcodec == "libx264":
            v_args += ["-crf", "23"]
        else:
            v_args += ["-rc", "vbr", "-cq", "23"]

        cmd = base + maps + v_args + a_args + [out_fp]
        self.print_log("Reencode: " + " ".join(shlex.quote(x) for x in cmd))
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")

        while True:
            if self.stop_flag and p.poll() is None:
                try:
                    p.send_signal(signal.SIGINT)
                except Exception:
                    pass
                time.sleep(0.5)
                if p.poll() is None:
                    p.terminate()
                break

            line = p.stderr.readline()
            if not line:
                if p.poll() is not None:
                    break
                time.sleep(0.02)
                continue

            line = line.strip()
            self.print_log(line)

        return p.returncode == 0

    # ---------- Auto-fix stage ----------
    def autofix_files(self):
        if not self.files or not self.baseline:
            messagebox.showerror("Error", "Please run Scan first.")
            return

        self.scan_btn.configure(state="disabled")
        self.fix_btn.configure(state="disabled")
        self.merge_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.stop_flag = False
        self.progress["value"] = 0
        self.progress["maximum"] = len(self.files)

        def worker():
            self.set_status("Auto-fixing…")
            fixed = 0
            for idx, src_fp in enumerate(self.files, 1):
                if self.stop_flag:
                    break
                meta = ffprobe_json(src_fp)
                need = self.needs_reencode(meta)
                if need:
                    base = os.path.splitext(os.path.basename(src_fp))[0]
                    out_fp = os.path.join(self.reencoded_dir, f"{base}__fixed.mp4")
                    ok = self.reencode_one(src_fp, out_fp)
                    if ok:
                        self.file_map[src_fp] = out_fp
                        self.print_log(f"✔️  Reencoded: {os.path.basename(src_fp)} → {os.path.basename(out_fp)}")
                        fixed += 1
                    else:
                        self.print_log(f"❌ Reencode failed for: {os.path.basename(src_fp)} — file will be skipped")
                        self.file_map[src_fp] = None
                else:
                    self.print_log(f"= OK: {os.path.basename(src_fp)} (lossless-copy compatible)")
                self.progress["value"] = idx

            final_list = [self.file_map[f] for f in self.files if self.file_map.get(f)]
            missing = [f for f in self.files if self.file_map.get(f) is None]
            if not final_list:
                self.print_log("No files available after auto-fix. Aborting.")
                self.set_status("Aborted")
                self.scan_btn.configure(state="normal")
                self.fix_btn.configure(state="normal")
                self.cancel_btn.configure(state="disabled")
                return

            self.files = final_list
            self.print_log(f"Auto-fix complete. Reencoded: {fixed}, Skipped (failed): {len(missing)}")
            self.set_status("Ready to merge")
            self.merge_btn.configure(state="normal")
            self.scan_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")
            self.stop_flag = False

        threading.Thread(target=worker, daemon=True).start()

    # ---------- Build concat list ----------
    def build_file_list(self):
        folder = os.path.dirname(self.output_var.get().strip()) or os.getcwd()
        list_path = os.path.join(folder, TEMP_LIST_NAME)
        with open(list_path, "w", encoding="utf-8") as f:
            for path in self.files:
                name = sanitize_list_path(path)
                f.write(f"file '{name}'\n")
        return list_path

    # ---------- Overlay filter helpers ----------
    def _overlay_xy(self, w, h):
        pos = self.overlay_position.get()
        x = self.overlay_x.get()
        y = self.overlay_y.get()
        # ffmpeg expressions for corners/center relative to main video W,H and overlay w,h
        if pos == "top-left":
            return "20", "20"
        if pos == "top-right":
            return "W-w-20", "20"
        if pos == "bottom-left":
            return "20", "H-h-20"
        if pos == "bottom-right":
            return "W-w-20", "H-h-20"
        if pos == "center":
            return "(W-w)/2", "(H-h)/2"
        # custom uses provided ints (still allow negatives)
        return str(x), str(y)

    def _overlay_filter_complex(self):
        # Build a filter_complex graph string for overlay with scale & opacity
        # Inputs: [0:v] main; [1:v] overlay
        # Steps on overlay: scale, force rgba, apply alpha (opacity)
        scale_pct = max(1, min(500, int(self.overlay_scale_pct.get() or 100)))
        opacity = max(0.0, min(1.0, float(self.overlay_opacity.get() or 1.0)))
        ox, oy = self._overlay_xy(None, None)

        # Scale overlay relative to its own size by percentage
        # Use eval=init so expressions are computed once.
        overlay_chain = (
            f"[1:v]scale=iw*{scale_pct}/100:ih*{scale_pct}/100:flags=lanczos,"
            f"format=rgba,colorchannelmixer=aa={opacity}[ol]"
        )
        # Place overlay
        main_chain = f"[0:v][ol]overlay=x={ox}:y={oy}:eval=init:format=auto"
        return f"{overlay_chain};{main_chain}"

    # ---------- Preview 5 seconds with overlay ----------
    def preview_overlay(self):
        if not self.overlay_enabled.get():
            messagebox.showwarning("Overlay disabled", "Enable overlay first.")
            return
        if not self.overlay_path.get() or not os.path.isfile(self.overlay_path.get()):
            messagebox.showerror("Missing overlay", "Please choose a valid PNG overlay.")
            return
        if not self.files:
            messagebox.showerror("No videos", "Scan (and Auto-Fix if needed) before preview.")
            return

        # take the first processed file for quick preview
        src = self.files[0]
        tmpdir = tempfile.gettempdir()
        prev_path = os.path.join(tmpdir, "overlay_preview_5s.mp4")

        use_nv = self.use_nvenc.get() and encoder_has_nvenc()
        vcodec = "h264_nvenc" if use_nv else "libx264"
        preset = self.preset_var.get()

        fc = self._overlay_filter_complex()
        cmd = [FFMPEG, "-hide_banner", "-y",
               "-i", src, "-i", self.overlay_path.get(),
               "-filter_complex", fc,
               "-t", "5",
               "-c:v", vcodec, "-preset", preset, "-pix_fmt", "yuv420p",
               "-movflags", "+faststart",
               "-an",  # fast preview without audio
               prev_path]

        self.print_log("Preview: " + " ".join(shlex.quote(x) for x in cmd))
        self.set_status("Making 5s preview…")
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        while True:
            line = p.stderr.readline()
            if not line:
                if p.poll() is not None:
                    break
                time.sleep(0.02); continue
            self.print_log(line.strip())

        if p.returncode == 0:
            self.print_log(f"🎬 Preview ready: {prev_path}")
            self.set_status("Opening preview…")
            try:
                if sys.platform.startswith("win"):
                    os.startfile(prev_path)  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", prev_path])
                else:
                    subprocess.Popen(["xdg-open", prev_path])
            except Exception as e:
                self.print_log(f"Could not auto-open preview: {e}")
                messagebox.showinfo("Preview saved", f"Preview saved at:\n{prev_path}")
        else:
            self.print_log("❌ Preview failed")
            messagebox.showerror("Error", "Failed to create overlay preview.")
        self.set_status("Idle")

    # ---------- Merge ----------
    def merge_all(self):
        if not self.files:
            messagebox.showerror("Error", "No files to merge.")
            return
        outpath = self.output_var.get().strip()
        if not outpath:
            messagebox.showerror("Error", "Please choose an output file.")
            return

        list_path = self.build_file_list()
        self.scan_btn.configure(state="disabled")
        self.fix_btn.configure(state="disabled")
        self.merge_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.stop_flag = False

        # total duration for progress
        self.total_duration = 0.0
        for fp in self.files:
            self.total_duration += ffprobe_json(fp)["duration"]
        if self.total_duration <= 0:
            self.total_duration = 1.0

        self.progress["value"] = 0
        self.progress["maximum"] = 100.0

        def worker():
            if self.overlay_enabled.get():
                # One-pass concat (as input) + overlay (filter) → re-encode video (NVENC/libx264), copy audio
                self.set_status("Merging with overlay (re-encode video)…")
                use_nv = self.use_nvenc.get() and encoder_has_nvenc()
                vcodec = "h264_nvenc" if use_nv else "libx264"
                preset = self.preset_var.get()

                fc = self._overlay_filter_complex()
                cmd = [FFMPEG, "-hide_banner", "-y",
                       "-fflags", "+genpts", "-f", "concat", "-safe", "0", "-i", list_path,
                       "-i", self.overlay_path.get(),
                       "-filter_complex", fc,
                       "-c:v", vcodec, "-preset", preset, "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                       "-c:a", "copy",  # fast path if all AAC
                       outpath]
            else:
                # pure lossless stream-copy
                self.set_status("Merging (lossless copy)…")
                cmd = [FFMPEG, "-hide_banner", "-y", "-fflags", "+genpts", "-f", "concat", "-safe", "0",
                       "-i", list_path, "-c", "copy", outpath]

            self.print_log("Merge: " + " ".join(shlex.quote(x) for x in cmd))
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")

            last_t = 0.0
            while True:
                if self.stop_flag and self.proc.poll() is None:
                    try:
                        self.proc.send_signal(signal.SIGINT)
                    except Exception:
                        pass
                    time.sleep(0.5)
                    if self.proc.poll() is None:
                        self.proc.terminate()
                    break

                line = self.proc.stderr.readline()
                if not line:
                    if self.proc.poll() is not None:
                        break
                    time.sleep(0.02)
                    continue
                s = line.strip()
                self.print_log(s)
                t = parse_ffmpeg_time(s)
                if t is not None:
                    pct = max(0.0, min(100.0, (t / self.total_duration) * 100.0))
                    self.progress["value"] = pct
                    last_t = t

            rc = self.proc.returncode
            try:
                os.remove(list_path)
            except Exception:
                pass

            if rc == 0:
                self.print_log("🎉 Merge completed successfully!")
                self.set_status("Done")
                messagebox.showinfo("Success", "All videos merged successfully!")
            else:
                self.print_log("❌ FFmpeg merge failed!")
                self.set_status("Failed")
                messagebox.showerror("Error", "Failed to merge videos.")

            self.scan_btn.configure(state="normal")
            self.fix_btn.configure(state="normal")
            self.merge_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")
            self.stop_flag = False

        threading.Thread(target=worker, daemon=True).start()

    # ---------- Cancel ----------
    def cancel_current(self):
        if self.proc and self.proc.poll() is None:
            self.stop_flag = True
            self.print_log("Cancel requested… sending SIGINT to FFmpeg.")
        else:
            self.stop_flag = True
            self.print_log("Cancel requested…")

# ------------------------ Main ------------------------

if __name__ == "__main__":
    if not FFMPEG or not FFPROBE:
        try:
            tk.Tk().withdraw()
            messagebox.showerror("FFmpeg/FFprobe Missing",
                                 "FFmpeg or FFprobe not found.\nInstall them or place binaries next to this script.")
        except Exception:
            print("FFmpeg/FFprobe not found. Install them or place binaries next to this script.", file=sys.stderr)
        sys.exit(1)
    app = VideoMergerApp()
    app.mainloop()
