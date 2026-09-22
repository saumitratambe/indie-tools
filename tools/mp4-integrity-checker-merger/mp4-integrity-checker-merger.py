# file: mp4-integrity-checker-merger.py
# Purpose: Check MP4s for corruption + concat-compatibility (no re-encode) and merge safely.
# Author: Saumitra Tambe
# Usage: python mp4-integrity-checker-merger.py

import os, sys, json, re, subprocess, threading, time, tempfile, shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "MP4 Checker + Lossless Merger"
COLS = ("file", "duration", "vcodec", "acodec", "res", "fps", "issues")
BAD_DIRNAME = "_bad_mp4"
OUT_DIRNAME = "_merge_out"

def natural_key(s: str):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]

def which(cmd):
    from shutil import which as _which
    return _which(cmd)

def require_ffmpeg():
    if not which("ffmpeg") or not which("ffprobe"):
        messagebox.showerror("FFmpeg not found", "ffmpeg/ffprobe not found in PATH.\nInstall FFmpeg and restart.")
        return False
    return True

def run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def ffprobe_json(path):
    cmd = ["ffprobe","-v","error","-show_format","-show_streams","-print_format","json",path]
    p = run(cmd)
    if p.returncode != 0:
        return None, p.stderr.strip()
    try:
        return json.loads(p.stdout), ""
    except Exception as e:
        return None, str(e)

def to_float_fps(frac: str):
    if not frac or frac == "0/0": return 0.0
    if "/" in frac:
        num, den = frac.split("/", 1)
        try:
            num, den = float(num), float(den)
            return 0.0 if den == 0 else num/den
        except:
            return 0.0
    try:
        return float(frac)
    except:
        return 0.0

def inspect_file(path):
    """Return dict with metadata + issues list."""
    info = {
        "file": os.path.basename(path),
        "path": path,
        "duration": 0.0,
        "vcodec": "",
        "acodec": "",
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "pix_fmt": "",
        "asr": 0,
        "ach": 0,
        "issues": []
    }

    meta, err = ffprobe_json(path)
    if meta is None:
        info["issues"].append(f"ffprobe error: {err or 'unknown'}")
        return info

    # duration
    try:
        d = float(meta.get("format", {}).get("duration", 0.0) or 0.0)
    except:
        d = 0.0
    info["duration"] = d
    if d <= 0.01:
        info["issues"].append("duration<=0")

    # streams
    v = None; a = None
    for s in meta.get("streams", []):
        if s.get("codec_type") == "video" and v is None:
            v = s
        if s.get("codec_type") == "audio" and a is None:
            a = s

    if not v:
        info["issues"].append("no video stream")
    else:
        info["vcodec"] = v.get("codec_name","")
        info["width"] = int(v.get("width",0) or 0)
        info["height"] = int(v.get("height",0) or 0)
        info["pix_fmt"] = v.get("pix_fmt","") or ""
        fps = to_float_fps(v.get("avg_frame_rate") or v.get("r_frame_rate") or "")
        info["fps"] = round(fps, 3)
        if info["width"]<=0 or info["height"]<=0:
            info["issues"].append("invalid resolution")

    if not a:
        # audio is optional for concat, but many pipelines expect it; we won't flag as fatal.
        info["acodec"] = ""
        info["asr"] = 0
        info["ach"] = 0
    else:
        info["acodec"] = a.get("codec_name","")
        info["asr"] = int(a.get("sample_rate", "0") or 0)
        info["ach"] = int((a.get("channels", 0) or 0))

    # corruption check: ffmpeg parse errors
    # (Note: this does NOT re-encode; it just decodes to /dev/null)
    cmd = ["ffmpeg","-v","error","-xerror","-i",path,"-f","null","-"]
    p = run(cmd)
    if p.returncode != 0 or ("Error" in p.stderr or "Invalid data" in p.stderr or "moov" in p.stderr.lower()):
        # Collect only the first few error lines for brevity
        lines = [ln.strip() for ln in p.stderr.splitlines() if ln.strip()]
        err_lines = []
        for ln in lines:
            if ("error" in ln.lower()) or ("invalid" in ln.lower()) or ("moov" in ln.lower()):
                err_lines.append(ln)
            if len(err_lines) >= 3:
                break
        if not err_lines and p.returncode != 0:
            err_lines = [f"ffmpeg returned {p.returncode}"]
        info["issues"].append("corrupt: " + " | ".join(err_lines))

    return info

def summarize(info):
    res = f"{info['width']}x{info['height']}" if info['width'] and info['height'] else ""
    return [
        info["file"],
        f"{info['duration']:.2f}s" if info['duration'] else "",
        info["vcodec"] or "",
        info["acodec"] or "",
        res,
        f"{info['fps']:.3f}" if info['fps'] else "",
        "; ".join(info["issues"])
    ]

def compatible(a, b):
    """Check concat-compatibility a vs b (video+audio container params)."""
    same = (
        a["vcodec"] == b["vcodec"] and
        a["width"]  == b["width"] and
        a["height"] == b["height"] and
        a["pix_fmt"]== b["pix_fmt"] and
        round(a["fps"],3) == round(b["fps"],3)
    )
    # Audio tolerated if both absent; else must match
    if a["acodec"] or b["acodec"]:
        same = same and (
            a["acodec"] == b["acodec"] and
            a["asr"] == b["asr"] and
            a["ach"] == b["ach"]
        )
    return same

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x580")
        self.minsize(960, 520)
        self._style()
        self.folder = ""
        self.rows = []  # list of info dicts
        self.compat_ref = None

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")

        self.dir_var = tk.StringVar()
        ttk.Label(top, text="Folder:").pack(side="left")
        ttk.Entry(top, textvariable=self.dir_var, width=80).pack(side="left", padx=6)
        ttk.Button(top, text="Browse", command=self.browse).pack(side="left")
        self.btn_scan = ttk.Button(top, text="Scan MP4s", command=self.scan)
        self.btn_scan.pack(side="left", padx=6)

        ttk.Button(top, text="Export Bad List", command=self.export_bad).pack(side="left")
        ttk.Button(top, text="Move Bad to _bad_mp4", command=self.move_bad).pack(side="left")
        ttk.Button(top, text="Merge (lossless)", command=self.merge).pack(side="left", padx=(12,0))

        self.status = tk.StringVar(value="Ready.")
        ttk.Label(self, textvariable=self.status, anchor="w", padding=8).pack(fill="x")

        self.tree = ttk.Treeview(self, columns=COLS, show="headings", height=20)
        for c, w in zip(COLS, (360, 90, 90, 90, 90, 70, 400)):
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, width=w, stretch=(c in ("file","issues")))
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0,8))

        # Scrollbars
        ysb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=ysb.set)
        ysb.place(in_=self.tree, relx=1.0, rely=0, relheight=1.0, x=-1)

        # tag styles
        self.tree.tag_configure("bad", foreground="#b91c1c")      # red
        self.tree.tag_configure("warn", foreground="#b45309")     # amber
        self.tree.tag_configure("ok", foreground="#065f46")       # teal

    def _style(self):
        # Simple dark-ish ttk styling
        style = ttk.Style(self)
        try:
            self.tk.call("source", "sun-valley.tcl")
            style.theme_use("sun-valley-dark")
        except:
            pass
        style.configure("Treeview", rowheight=24)
        style.configure("TButton", padding=6)

    def browse(self):
        d = filedialog.askdirectory(title="Select folder with MP4s")
        if d:
            self.dir_var.set(d)

    def set_status(self, txt):
        self.status.set(txt)
        self.update_idletasks()

    def scan(self):
        if not require_ffmpeg(): return
        folder = self.dir_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Pick a folder", "Select a valid folder.")
            return

        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        self.compat_ref = None

        files = [f for f in os.listdir(folder) if f.lower().endswith(".mp4")]
        files.sort(key=natural_key)
        if not files:
            messagebox.showinfo("No MP4s", "No .mp4 files found in this folder.")
            return

        def work():
            bad_count = 0
            self.set_status(f"Scanning {len(files)} files…")
            for i, name in enumerate(files, 1):
                path = os.path.join(folder, name)
                info = inspect_file(path)
                self.rows.append(info)

                # establish reference
                if (self.compat_ref is None) and not info["issues"]:
                    self.compat_ref = info

                tag = "ok"
                if info["issues"]:
                    tag = "bad"; bad_count += 1
                elif self.compat_ref and not compatible(self.compat_ref, info):
                    tag = "warn"
                    info["issues"].append("incompatible with first good file")

                self.tree.insert("", "end", values=summarize(info), tags=(tag,))
                self.set_status(f"Scanning… {i}/{len(files)}")

            self.set_status(f"Done. {len(files)} files, {bad_count} corrupt; "
                            f"{sum('incompatible' in ';'.join(r['issues']) for r in self.rows)} incompatible.")

        threading.Thread(target=work, daemon=True).start()

    def bad_list(self):
        return [r for r in self.rows if r["issues"] and ("corrupt" in ";".join(r["issues"]) or "duration<=0" in r["issues"] or "no video stream" in r["issues"])]

    def incompatible_list(self):
        return [r for r in self.rows if ("incompatible" in ";".join(r["issues"]))]

    def export_bad(self):
        if not self.rows:
            messagebox.showinfo("Nothing scanned", "Scan first.")
            return
        bad = self.bad_list()
        inc = self.incompatible_list()

        if not bad and not inc:
            messagebox.showinfo("Clean", "No corrupt or incompatible files.")
            return

        save = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="bad_mp4_list.txt")
        if not save: return

        with open(save, "w", encoding="utf-8") as f:
            f.write("### CORRUPT/INVALID FILES ###\n")
            for r in bad:
                f.write(f"{r['path']}\n")
            f.write("\n### INCOMPATIBLE (won't merge losslessly) ###\n")
            for r in inc:
                f.write(f"{r['path']}\n")
        messagebox.showinfo("Exported", f"Saved list:\n{save}")

    def move_bad(self):
        if not self.rows:
            messagebox.showinfo("Nothing scanned", "Scan first.")
            return
        folder = self.dir_var.get().strip()
        bad = self.bad_list()
        if not bad:
            messagebox.showinfo("No corrupt files", "Nothing to move.")
            return

        bad_dir = os.path.join(folder, BAD_DIRNAME)
        os.makedirs(bad_dir, exist_ok=True)
        moved = 0
        for r in bad:
            src = r["path"]
            dst = os.path.join(bad_dir, os.path.basename(src))
            try:
                shutil.move(src, dst)
                moved += 1
            except Exception as e:
                print("move failed:", e)
        messagebox.showinfo("Done", f"Moved {moved} file(s) to {BAD_DIRNAME}.")

        # Refresh view
        self.scan()

    def merge(self):
        if not require_ffmpeg(): return
        if not self.rows:
            messagebox.showinfo("Nothing scanned", "Scan first.")
            return

        good = [r for r in self.rows if not r["issues"]]
        if not good:
            messagebox.showwarning("No good files", "No corruption-free files found to merge.")
            return

        # Filter to only those compatible (exact match) with the first good file
        ref = good[0]
        merge_list = [r for r in good if compatible(ref, r)]

        if len(merge_list) < 2:
            messagebox.showwarning("Need 2+ files", "Less than 2 compatible files to merge losslessly.")
            return

        # Confirm ordering and create concat list
        # (Use current folder order which is natural-sorted already)
        out_dir = os.path.join(self.dir_var.get().strip(), OUT_DIRNAME)
        os.makedirs(out_dir, exist_ok=True)
        out_path = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            initialdir=out_dir,
            initialfile="merged_lossless.mp4",
            title="Save merged output"
        )
        if not out_path:
            return

        # Create concat file
        concat_txt = os.path.join(tempfile.gettempdir(), f"concat_{int(time.time())}.txt")
        with open(concat_txt, "w", encoding="utf-8") as f:
            for r in merge_list:
                # Use absolute safe paths
                f.write(f"file '{r['path'].replace('\\', '/')}'\n")
        # Run ffmpeg concat demuxer
        # -safe 0 to allow absolute paths; -c copy to avoid re-encode
        cmd = [
            "ffmpeg","-hide_banner","-y",
            "-f","concat","-safe","0","-i",concat_txt,
            "-c","copy",
            out_path
        ]
        self.set_status("Merging… this can take a while (no re-encode).")
        p = run(cmd)
        try:
            os.remove(concat_txt)
        except:
            pass

        if p.returncode == 0:
            messagebox.showinfo("Merged", f"Success:\n{out_path}")
            self.set_status("Merge complete.")
        else:
            # Common reasons: subtle parameter mismatch between clips despite passing our checks.
            # Show stderr head to help debug.
            err = "\n".join(p.stderr.splitlines()[-15:])
            messagebox.showerror("Merge failed",
                                 "ffmpeg concat failed. Likely parameter mismatch.\n\n"
                                 "Tip: Re-export the mismatching clips uniformly or re-encode once.\n\n"
                                 f"ffmpeg says (tail):\n{err}")
            self.set_status("Merge failed.")

if __name__ == "__main__":
    app = App()
    app.mainloop()
