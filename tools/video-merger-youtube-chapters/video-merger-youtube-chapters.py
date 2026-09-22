#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VideoBulkMerger - Merge many video chunks losslessly using FFmpeg.
Features:
  • GUI (Tkinter)
  • "Starts From...!" numeric field to set chapter numbering start
  • Merge videos (ffmpeg concat, copy codec)
  • Auto-generate a YouTube-ready description file with clickable timestamps
    saved automatically into the same folder as the merged output.
Requirements:
  • Python 3.8+
  • FFmpeg & FFprobe installed (on PATH or next to the script)
"""

import os
import re
import sys
import time
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "Video Bulk Merger — Lossless (FFmpeg)"
TEMP_LIST_NAME = "_concat_list.txt"


def natural_key(s: str):
    """Sort files naturally (1,2,10 instead of 1,10,2)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]


def find_executable(names):
    for name in names:
        try:
            subprocess.run([name, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return name
        except Exception:
            continue
    return None


def find_ffmpeg():
    return find_executable(["ffmpeg.exe", "ffmpeg"])


def find_ffprobe():
    return find_executable(["ffprobe.exe", "ffprobe"])


def get_video_duration(ffprobe_path, filepath):
    """Return video duration in seconds (float)."""
    try:
        proc = subprocess.run(
            [ffprobe_path, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", filepath],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        out = proc.stdout.strip()
        return float(out) if out else 0.0
    except Exception:
        return 0.0


def format_time(seconds):
    """Return H:MM:SS with zero-padded minutes/seconds and zero-padded hours (HH:MM:SS)."""
    # use gmtime so it's absolute rather than local time zone
    return time.strftime('%H:%M:%S', time.gmtime(int(seconds)))


class VideoMergerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("640x460")
        self.resizable(False, False)

        self.ffmpeg_path = find_ffmpeg()
        self.ffprobe_path = find_ffprobe()
        if not self.ffmpeg_path or not self.ffprobe_path:
            messagebox.showerror("Error", "FFmpeg or FFprobe not found! Please install them or place them next to this script.")
            self.destroy()
            return

        self.files = []
        self.output_path = ""
        self.start_number = tk.IntVar(value=1)

        self._build_ui()

    def _build_ui(self):
        frame_top = ttk.Frame(self, padding=10)
        frame_top.pack(fill="x")

        btn_add = ttk.Button(frame_top, text="Add Videos", command=self.add_files)
        btn_add.pack(side="left", padx=6)
        btn_clear = ttk.Button(frame_top, text="Clear", command=self.clear_files)
        btn_clear.pack(side="left")
        btn_merge = ttk.Button(frame_top, text="Merge", command=self.start_merge)
        btn_merge.pack(side="right", padx=6)

        ttk.Label(frame_top, text="Starts From...!").pack(side="left", padx=(12, 4))
        entry_start = ttk.Entry(frame_top, textvariable=self.start_number, width=6)
        entry_start.pack(side="left")

        lbl_hint = ttk.Label(frame_top, text="(Chapters auto-created in merged-video folder)")
        lbl_hint.pack(side="left", padx=10)

        self.file_list = tk.Listbox(self, selectmode=tk.SINGLE, height=14)
        self.file_list.pack(fill="both", expand=True, padx=12, pady=10)

        frame_bottom = ttk.Frame(self, padding=10)
        frame_bottom.pack(fill="x")

        btn_desc = ttk.Button(frame_bottom, text="Generate YouTube Description Now", command=self.create_description)
        btn_desc.pack(side="left")

        lbl_after = ttk.Label(frame_bottom, text="Description auto-created after successful merge")
        lbl_after.pack(side="right")

        self.status = ttk.Label(self, text="Ready.", relief="sunken", anchor="w")
        self.status.pack(side="bottom", fill="x")

    def add_files(self):
        paths = filedialog.askopenfilenames(title="Select video chunks", filetypes=[("Video Files", "*.*")])
        if paths:
            for p in sorted(paths, key=natural_key):
                if p not in self.files:
                    self.files.append(p)
                    self.file_list.insert("end", os.path.basename(p))

    def clear_files(self):
        self.files.clear()
        self.file_list.delete(0, "end")

    def start_merge(self):
        if not self.files:
            messagebox.showwarning("Warning", "No files selected.")
            return

        output = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4", "*.mp4"), ("MKV", "*.mkv"), ("MOV", "*.mov")])
        if not output:
            return
        self.output_path = output

        # run merge in background thread to keep UI responsive
        threading.Thread(target=self.merge_videos, daemon=True).start()

    def merge_videos(self):
        try:
            self.status.config(text="Preparing concat list...")
            # write concat list in ffmpeg expected format
            with open(TEMP_LIST_NAME, "w", encoding="utf-8") as f:
                for path in self.files:
                    # escape single quotes by replacing ' with '"'"' as ffmpeg concat input expects simple quoting
                    safe_path = path.replace("'", "'\"'\"'")
                    f.write(f"file '{safe_path}'\n")

            self.status.config(text="Merging videos with ffmpeg (copying streams)...")
            cmd = [self.ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", TEMP_LIST_NAME, "-c", "copy", self.output_path]
            subprocess.run(cmd, check=True)

            try:
                os.remove(TEMP_LIST_NAME)
            except Exception:
                pass

            self.status.config(text="Merge completed successfully.")
            messagebox.showinfo("Done", f"Video merged successfully to:\n{self.output_path}")

            # auto-generate YouTube description into same folder as output
            self.create_description(auto=True)

        except subprocess.CalledProcessError as e:
            self.status.config(text="Merge failed.")
            messagebox.showerror("Error", f"Merge failed — see console output.\n\n{e}")
        except Exception as e:
            self.status.config(text="Error occurred.")
            messagebox.showerror("Error", str(e))

    def create_description(self, auto=False):
        """
        Create a YouTube-ready description with clickable timestamps saved
        into the same folder as the merged output (if present), otherwise cwd.
        If auto=True, show only an info popup on success (no extra dialogs).
        """
        if not self.files:
            messagebox.showwarning("Warning", "No videos loaded.")
            return

        # Determine save folder (same as merged output if provided)
        save_folder = os.path.dirname(self.output_path) if self.output_path else os.getcwd()
        base_name = (os.path.splitext(os.path.basename(self.output_path))[0]
                     if self.output_path else "merged_video")
        description_filename = f"{base_name}_description.txt"
        save_path = os.path.join(save_folder, description_filename)

        start_from = self.start_number.get()
        lines = []

        # Optional header/title for description
        lines.append(f"{base_name}")
        lines.append("")
        lines.append("Chapters:")
        total_seconds = 0.0

        for idx_offset, filepath in enumerate(self.files):
            chapter_number = start_from + idx_offset
            # get duration of this clip to compute running timestamp
            dur = get_video_duration(self.ffprobe_path, filepath)
            timestamp = format_time(total_seconds)  # cumulative starting point for this chapter
            # YouTube clickable timestamps are lines starting with timestamp e.g. 00:00:00 Chapter 1
            title = os.path.splitext(os.path.basename(filepath))[0]
            lines.append(f"{timestamp} Chapter {chapter_number} — {title}")
            total_seconds += dur

        # Optionally add final total duration line
        if total_seconds > 0:
            lines.append("")
            lines.append(f"Total Duration: {format_time(total_seconds)}")

        # Extra spacing then example description body (user can edit later)
        lines.append("")
        lines.append("Description:")
        lines.append("Add any video description, links, credits, and hashtags here.")
        lines.append("")
        lines.append("#chapters")

        # write file
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.status.config(text=f"Description saved to {save_path}")
            if not auto:
                messagebox.showinfo("YouTube Description", f"Description saved to:\n{save_path}")
            else:
                # when auto-called after merge, just a small popup informing user
                messagebox.showinfo("YouTube Description", f"Description auto-saved to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save description:\n{e}")
            self.status.config(text="Failed to save description.")


if __name__ == "__main__":
    app = VideoMergerApp()
    app.mainloop()