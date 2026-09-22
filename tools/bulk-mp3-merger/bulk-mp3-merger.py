#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MP3BulkMerger - Merge hundreds of MP3 chunks losslessly using FFmpeg.
Author: Saumitra Tambe
"""

import os
import re
import sys
import shlex
import time
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "MP3 Bulk Merger — Lossless (FFmpeg)"
TEMP_LIST_NAME = "_concat_list.txt"

def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]

def find_ffmpeg():
    candidates = ["ffmpeg.exe", "ffmpeg"]
    for c in candidates:
        try:
            subprocess.run([c, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return c
        except:
            continue
    return None

FFMPEG = find_ffmpeg()


class MP3MergerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("800x600")
        self.configure(bg="#0b0f14")
        self.folder_var = tk.StringVar()
        self.output_var = tk.StringVar(value="merged_output.mp3")
        self.proc = None
        self.stop_flag = False
        self.files = []
        self._build_ui()

    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#111827")
        style.configure("TLabel", background="#111827", foreground="#d1d5db", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=6)

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        # Folder select
        top = ttk.Frame(outer, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="MP3 Chunks Folder:").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.folder_var, width=60).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(top, text="Browse", command=self.browse_folder).grid(row=1, column=1, padx=5)

        # Output file
        ttk.Label(top, text="Output File:").grid(row=0, column=2, sticky="w", padx=(15,0))
        ttk.Entry(top, textvariable=self.output_var, width=30).grid(row=1, column=2, padx=5)
        ttk.Button(top, text="Pick", command=self.pick_output).grid(row=1, column=3, padx=5)

        # Buttons
        actions = ttk.Frame(outer, padding=10)
        actions.pack(fill="x")
        self.scan_btn = ttk.Button(actions, text="Scan Files", command=self.scan_files)
        self.scan_btn.pack(side="left")
        self.merge_btn = ttk.Button(actions, text="Merge All", command=self.merge_all, state="disabled")
        self.merge_btn.pack(side="left", padx=8)
        self.cancel_btn = ttk.Button(actions, text="Cancel", command=self.cancel_merge, state="disabled")
        self.cancel_btn.pack(side="left", padx=8)

        # Log window
        log_frame = ttk.Frame(outer, padding=10)
        log_frame.pack(fill="both", expand=True)
        ttk.Label(log_frame, text="Log Output:").pack(anchor="w")
        self.log = tk.Text(log_frame, height=20, bg="#0b0f14", fg="#d1d5db")
        self.log.pack(fill="both", expand=True)

    def browse_folder(self):
        path = filedialog.askdirectory(title="Select folder")
        if path:
            self.folder_var.set(path)

    def pick_output(self):
        path = filedialog.asksaveasfilename(
            title="Select output MP3 file",
            defaultextension=".mp3",
            filetypes=[("MP3", "*.mp3")]
        )
        if path:
            self.output_var.set(path)

    def print_log(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.update_idletasks()

    def scan_files(self):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Please select a valid folder.")
            return

        self.files = [f for f in os.listdir(folder) if f.lower().endswith(".mp3")]
        self.files.sort(key=natural_key)

        if not self.files:
            self.print_log("No MP3 files found.")
            self.merge_btn.configure(state="disabled")
            return

        size = sum(os.path.getsize(os.path.join(folder, f)) for f in self.files) / (1024 * 1024)
        self.print_log(f"Found {len(self.files)} MP3 files, total size {size:.2f} MB")
        self.merge_btn.configure(state="normal")

    def build_list_file(self, folder):
        list_path = os.path.join(folder, TEMP_LIST_NAME)
        with open(list_path, "w", encoding="utf-8") as f:
            for name in self.files:
                safe = name.replace("'", "'\\''")
                f.write(f"file '{safe}'\n")
        return list_path

    def merge_all(self):
        folder = self.folder_var.get().strip()
        outpath = self.output_var.get().strip()

        if not self.files:
            messagebox.showerror("Error", "No files to merge.")
            return

        list_path = self.build_list_file(folder)

        # MP3 concat (lossless)
        cmd = [
            FFMPEG, "-hide_banner", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            outpath
        ]

        self.scan_btn.configure(state="disabled")
        self.merge_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.stop_flag = False

        def worker():
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            while True:
                if self.stop_flag and self.proc.poll() is None:
                    self.proc.terminate()
                    break

                line = self.proc.stderr.readline()
                if not line:
                    if self.proc.poll() is not None:
                        break
                    time.sleep(0.02)
                    continue

                self.print_log(line.strip())

            if self.proc.returncode == 0:
                self.print_log("Merge completed successfully!")
                messagebox.showinfo("Success", "All MP3 files merged successfully!")
            else:
                self.print_log("FFmpeg merge failed!")
                messagebox.showerror("Error", "Failed to merge MP3 files.")

            try:
                os.remove(list_path)
            except:
                pass

            self.scan_btn.configure(state="normal")
            self.merge_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")
            self.stop_flag = False

        threading.Thread(target=worker, daemon=True).start()

    def cancel_merge(self):
        if self.proc and self.proc.poll() is None:
            self.stop_flag = True
            self.print_log("Cancel requested, stopping FFmpeg...")


if __name__ == "__main__":
    if not FFMPEG:
        tk.messagebox.showerror(
            "FFmpeg Missing",
            "FFmpeg not found. Install it or place ffmpeg.exe next to this script."
        )
        sys.exit(1)

    app = MP3MergerApp()
    app.mainloop()
