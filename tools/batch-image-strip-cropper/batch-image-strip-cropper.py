# Credit/Strip Remover & Editor — Preview + Select + Delete/Crop (Dark UI)
# Requirements: Pillow (PIL)
#   pip install pillow
#
# Features:
# - Preview matched images in a list with per-row checkboxes.
# - Select All / Unselect All, Delete Selected.
# - Upload a Reference Image (auto-read dimensions), then:
#     Mode = Delete  OR  Crop Top/Bottom  OR  Deep Search (experimental strip removal).
# - Backup originals instead of permanent delete.
# - Filters: Dimensions ± tolerance, optional file size window, subfolder scan.
#
# Note:
# - Deep Search uses PIL-only scoring (ImageChops difference). It’s slow on very large images,
#   but works without OpenCV. Keep tolerance tight when possible.
#
# Author: Saumitra Tambe

import os
import shutil
import threading
from dataclasses import dataclass
from typing import List, Tuple, Optional

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageChops

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# --------------------- helpers ---------------------
def human_size(n):
    for unit in ["B","KB","MB","GB"]:
        if n < 1024.0:
            return f"{n:.0f}{unit}"
        n /= 1024.0
    return f"{n:.1f}TB"

def safe_mkdir(p):
    os.makedirs(p, exist_ok=True)
    return p

def load_image_safely(path):
    try:
        im = Image.open(path)
        im.load()
        return im
    except Exception:
        return None

def diff_score(imgA, imgB) -> float:
    """
    Return a small score for 'more similar' images.
    Uses ImageChops.difference and average pixel magnitude.
    """
    if imgA.size != imgB.size:
        imgB = imgB.resize(imgA.size, Image.LANCZOS)
    d = ImageChops.difference(imgA.convert("RGB"), imgB.convert("RGB"))
    # quick score from histogram: sum of channel values
    hist = d.histogram()
    # Weighted luma-ish sum; simple approach
    s = 0
    # hist has 256*3 bins for RGB
    for i, count in enumerate(hist):
        val = (i % 256)
        s += val * count
    # Normalize by total pixels
    return s / (imgA.size[0] * imgA.size[1] * 3 + 1)

@dataclass
class MatchRow:
    path: str
    info: str
    selected: bool = True

# --------------------- main app ---------------------
class App:
    def __init__(self, root):
        self.root = root
        root.title("Credit / Strip Remover — Preview & Select")
        root.geometry("1080x720")
        root.minsize(980, 660)

        # --- state ---
        self.folder = tk.StringVar(value="")
        self.recurse = tk.BooleanVar(value=True)

        self.width = tk.IntVar(value=1080)
        self.height = tk.IntVar(value=1800)
        self.tolerance = tk.IntVar(value=0)

        self.use_filesize = tk.BooleanVar(value=False)
        self.size_kb = tk.DoubleVar(value=200.0)
        self.size_tolerance_pct = tk.IntVar(value=20)

        self.move_to_backup = tk.BooleanVar(value=True)
        self.edit_mode = tk.StringVar(value="delete")  # delete | crop_top | crop_bottom | deep_search

        # Reference image
        self.ref_path = tk.StringVar(value="")
        self.ref_w = tk.IntVar(value=0)
        self.ref_h = tk.IntVar(value=0)

        # UI state
        self.status = tk.StringVar(value="Pick your root folder and click Preview.")
        self.matches: List[MatchRow] = []
        self.preview_thumb = None  # keep reference to avoid GC

        self._init_style()
        self._build_ui()

    def _init_style(self):

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
            style.configure("TSpinbox", fieldbackground="#ffffff", foreground="#000000", insertcolor="#e6e6e6")


        except Exception:
            pass
        DARK_BG = "#111315"
        MID_BG  = "#1a1d21"
        FG      = "#e6e6e6"
        SUB_FG  = "#B4C477"
        ENTRY_BG = "#fabbf4"
        ENTRY_FG = "#f36d6d"

        style.configure(".", background=DARK_BG, foreground=FG)
        style.configure("TLabelframe", background=DARK_BG, foreground=FG)
        style.configure("TLabelframe.Label", background=DARK_BG, foreground=FG, font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background=DARK_BG, foreground=FG)
        style.configure("Sub.TLabel", background=DARK_BG, foreground=SUB_FG)
        style.configure("TButton", padding=8)
        style.configure("TEntry", fieldbackground=ENTRY_BG, foreground=ENTRY_FG)
        style.configure("Treeview", background=MID_BG, fieldbackground=MID_BG, foreground=FG)
        style.configure("Treeview.Heading", background="#2b2e34", foreground=FG)

        self.root.configure(bg=DARK_BG)

    def _build_ui(self):
        pad = {"padx": 10, "pady": 8}

        top = ttk.Frame(self.root); top.pack(fill="x", **pad)
        ttk.Label(top, text="Root folder (contains all chapters):").pack(side="left")
        ttk.Entry(top, textvariable=self.folder, width=60).pack(side="left", padx=8)
        ttk.Button(top, text="Browse…", command=self.pick_folder).pack(side="left", padx=(0,8))
        ttk.Checkbutton(top, text="Scan subfolders", variable=self.recurse).pack(side="left")

        # Filters
        filters = ttk.LabelFrame(self.root, text="Match Filters"); filters.pack(fill="x", **pad)
        rowA = ttk.Frame(filters); rowA.pack(fill="x", pady=4)
        ttk.Label(rowA, text="Width:").pack(side="left")
        ttk.Spinbox(rowA, from_=1, to=20000, textvariable=self.width, width=8).pack(side="left", padx=6)
        ttk.Label(rowA, text="Height:").pack(side="left")
        ttk.Spinbox(rowA, from_=1, to=20000, textvariable=self.height, width=8).pack(side="left", padx=6)
        ttk.Label(rowA, text="Tolerance (±px):").pack(side="left")
        ttk.Spinbox(rowA, from_=0, to=1000, textvariable=self.tolerance, width=8).pack(side="left", padx=6)
        ttk.Checkbutton(rowA, text="Also filter by file size", variable=self.use_filesize).pack(side="left", padx=10)
        ttk.Label(rowA, text="≈ Size (KB):").pack(side="left")
        ttk.Spinbox(rowA, from_=1, to=999999, increment=0.1, textvariable=self.size_kb, width=10).pack(side="left", padx=6)
        ttk.Label(rowA, text="Tolerance (±%):").pack(side="left")
        ttk.Spinbox(rowA, from_=1, to=90, textvariable=self.size_tolerance_pct, width=8).pack(side="left", padx=6)

        # Reference & action mode
        ref = ttk.LabelFrame(self.root, text="Reference & Action"); ref.pack(fill="x", **pad)
        rowB = ttk.Frame(ref); rowB.pack(fill="x", pady=4)
        ttk.Label(rowB, text="Reference image (optional):").pack(side="left")
        ttk.Entry(rowB, textvariable=self.ref_path, width=50).pack(side="left", padx=8)
        ttk.Button(rowB, text="Upload…", command=self.pick_ref).pack(side="left")
        ttk.Label(rowB, text="Ref WxH:").pack(side="left", padx=(12,4))
        ttk.Label(rowB, textvariable=tk.StringVar(value=" ")).pack_forget()  # spacer
        self.ref_dim_label = ttk.Label(rowB, text=f"{self.ref_w.get()}x{self.ref_h.get()}", style="Sub.TLabel")
        self.ref_dim_label.pack(side="left")

        rowC = ttk.Frame(ref); rowC.pack(fill="x", pady=4)
        ttk.Label(rowC, text="Mode:").pack(side="left")
        ttk.Radiobutton(rowC, text="Delete (classic)", value="delete", variable=self.edit_mode).pack(side="left", padx=4)
        ttk.Radiobutton(rowC, text="Crop Top (remove strip)", value="crop_top", variable=self.edit_mode).pack(side="left", padx=4)
        ttk.Radiobutton(rowC, text="Crop Bottom", value="crop_bottom", variable=self.edit_mode).pack(side="left", padx=4)
        ttk.Radiobutton(rowC, text="Deep Search (auto-remove matching band)", value="deep_search", variable=self.edit_mode).pack(side="left", padx=4)

        rowD = ttk.Frame(ref); rowD.pack(fill="x", pady=4)
        ttk.Checkbutton(rowD, text="Move to Backup instead of permanent delete/overwrite", variable=self.move_to_backup).pack(side="left")

        # Buttons
        actions = ttk.Frame(self.root); actions.pack(fill="x", **pad)
        ttk.Button(actions, text="🧐 Preview", command=self.preview).pack(side="left")
        ttk.Button(actions, text="Select All", command=self.select_all).pack(side="left", padx=6)
        ttk.Button(actions, text="Unselect All", command=self.unselect_all).pack(side="left")
        ttk.Button(actions, text="🗑️ Apply to Selected", command=self.apply_selected).pack(side="left", padx=10)

        # Status
        ttk.Label(self.root, textvariable=self.status, style="Sub.TLabel").pack(anchor="w", padx=12, pady=(0,4))

        # Split: list + preview
        split = ttk.Frame(self.root); split.pack(fill="both", expand=True, **pad)

        # List with checkboxes simulated (column 'Sel' toggles on click)
        self.tree = ttk.Treeview(split, columns=("sel","file","info"), show="headings", height=16)
        self.tree.heading("sel", text="Sel")
        self.tree.heading("file", text="File")
        self.tree.heading("info", text="Details")
        self.tree.column("sel", width=50, anchor="center")
        self.tree.column("file", width=640)
        self.tree.column("info", width=180)
        self.tree.bind("<Button-1>", self._tree_click)       # toggle selection by clicking "Sel" column
        self.tree.bind("<<TreeviewSelect>>", self._on_select) # update preview
        self.tree.pack(side="left", fill="both", expand=True)

        side = ttk.Frame(split, width=320); side.pack(side="left", fill="y")
        ttk.Label(side, text="Preview", style="TLabelframe.Label").pack(anchor="w", pady=(0,6))
        self.preview_canvas = tk.Canvas(side, width=300, height=420, bg="#1a1d21", highlightthickness=0)
        self.preview_canvas.pack(fill="both", expand=False)

    # ------------------- pickers -------------------
    def pick_folder(self):
        p = filedialog.askdirectory(title="Select the ROOT folder that contains all chapters")
        if p:
            self.folder.set(p)

    def pick_ref(self):
        p = filedialog.askopenfilename(title="Select reference image", filetypes=[("Images","*.png;*.jpg;*.jpeg;*.webp;*.bmp")])
        if p:
            self.ref_path.set(p)
            im = load_image_safely(p)
            if im:
                self.ref_w.set(im.width); self.ref_h.set(im.height)
                self.ref_dim_label.config(text=f"{im.width}x{im.height}")
            else:
                self.ref_w.set(0); self.ref_h.set(0)
                self.ref_dim_label.config(text="0x0")

    # ------------------- scanning -------------------
    def walk_files(self, base):
        if self.recurse.get():
            for dirpath, _, files in os.walk(base):
                for f in files:
                    if os.path.splitext(f.lower())[1] in SUPPORTED_EXTS:
                        yield os.path.join(dirpath, f)
        else:
            for f in os.listdir(base):
                full = os.path.join(base, f)
                if os.path.isfile(full) and os.path.splitext(f.lower())[1] in SUPPORTED_EXTS:
                    yield full

    def file_matches(self, fpath) -> Tuple[bool,str]:
        # Dimensions
        im = load_image_safely(fpath)
        if not im:
            return False, ""
        w,h = im.size
        tol = self.tolerance.get()
        ok_dim = (self.width.get()-tol <= w <= self.width.get()+tol
                  and self.height.get()-tol <= h <= self.height.get()+tol)
        if not ok_dim:
            return False, ""
        # Optional size window
        info = f"{w}x{h}"
        try:
            size = os.path.getsize(fpath)
            info = f"{w}x{h}, {human_size(size)}"
            if self.use_filesize.get():
                target = int(self.size_kb.get()*1024)
                pct = max(1, int(self.size_tolerance_pct.get()))
                low = target*(100-pct)//100
                high = target*(100+pct)//100
                if not (low <= size <= high):
                    return False, ""
        except OSError:
            pass
        return True, info

    def preview(self):
        base = self.folder.get().strip()
        if not base or not os.path.isdir(base):
            messagebox.showerror("Error", "Please select a valid root folder.")
            return
        self.status.set("Scanning…")
        self.tree.delete(*self.tree.get_children())
        self.matches.clear()

        def task():
            total = 0
            found = 0
            for f in self.walk_files(base):
                total += 1
                ok, info = self.file_matches(f)
                if ok:
                    self.matches.append(MatchRow(f, info, True))
                    found += 1
            # Fill table
            for row in self.matches:
                self.tree.insert("", "end", values=("✓" if row.selected else "", row.path, row.info))
            self.status.set(f"Found {found} match(es) out of {total} image(s).")
        threading.Thread(target=task, daemon=True).start()

    # ------------------- selection -------------------
    def select_all(self):
        for i, iid in enumerate(self.tree.get_children()):
            self.matches[i].selected = True
            self.tree.set(iid, "sel", "✓")

    def unselect_all(self):
        for i, iid in enumerate(self.tree.get_children()):
            self.matches[i].selected = False
            self.tree.set(iid, "sel", "")

    def _tree_click(self, event):
        # toggle checkbox when click in 'Sel' column
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        if col != "#1":  # "sel" column
            return
        rowid = self.tree.identify_row(event.y)
        if not rowid:
            return
        index = self.tree.index(rowid)
        self.matches[index].selected = not self.matches[index].selected
        self.tree.set(rowid, "sel", "✓" if self.matches[index].selected else "")

    def _on_select(self, _):
        sel = self.tree.selection()
        if not sel:
            self._show_preview(None)
            return
        rowid = sel[0]
        index = self.tree.index(rowid)
        path = self.matches[index].path
        self._show_preview(path)

    # ------------------- preview image -------------------
    def _show_preview(self, path: Optional[str]):
        self.preview_canvas.delete("all")
        if not path:
            return
        im = load_image_safely(path)
        if not im:
            return
        # Fit into canvas
        cw = int(self.preview_canvas.winfo_width() or 300)
        ch = int(self.preview_canvas.winfo_height() or 420)
        im2 = im.copy()
        im2.thumbnail((cw, ch), Image.LANCZOS)
        self.preview_thumb = ImageTk.PhotoImage(im2)
        self.preview_canvas.create_image(cw//2, ch//2, image=self.preview_thumb)

    # ------------------- actions -------------------
    def apply_selected(self):
        selected = [r for r in self.matches if r.selected]
        if not selected:
            messagebox.showinfo("Nothing selected", "Select files first.")
            return

        mode = self.edit_mode.get()
        if mode == "delete":
            if not messagebox.askyesno("Confirm", f"Apply DELETE to {len(selected)} file(s)?"):
                return
        else:
            if not messagebox.askyesno("Confirm", f"Apply '{mode}' to {len(selected)} file(s)? (Edits overwrite unless backup enabled)"):
                return

        def task():
            backup_base = None
            if self.move_to_backup.get():
                backup_base = safe_mkdir(os.path.join(self.folder.get(), "_Backup_Edit"))

            done = 0
            for row in selected:
                try:
                    if mode == "delete":
                        self._do_delete(row.path, backup_base)
                    elif mode == "crop_top":
                        self._do_crop_fixed(row.path, top=True)
                    elif mode == "crop_bottom":
                        self._do_crop_fixed(row.path, top=False)
                    elif mode == "deep_search":
                        self._do_deep_search_remove(row.path)
                    done += 1
                except Exception as e:
                    print("Failed:", row.path, e)

            self.status.set(f"Applied '{mode}' to {done} file(s).")
            self.preview()  # refresh list

        threading.Thread(target=task, daemon=True).start()

    def _do_delete(self, fpath, backup_base):
        if backup_base:
            rel = os.path.relpath(fpath, self.folder.get())
            dst = os.path.join(backup_base, rel)
            safe_mkdir(os.path.dirname(dst))
            shutil.move(fpath, dst)
        else:
            os.remove(fpath)

    def _ref_strip_height(self) -> int:
        # Use reference height if provided, else 0 (no-op)
        rh = int(self.ref_h.get() or 0)
        return max(0, rh)

    def _do_crop_fixed(self, fpath, top=True):
        """
        Remove a fixed-height band (reference height if set) from top or bottom, and save (stitch).
        If no reference height, nothing happens.
        """
        rh = self._ref_strip_height()
        if rh <= 0:
            return  # no reference; skip
        im = load_image_safely(fpath)
        if not im: return
        w,h = im.size
        if rh >= h:
            return  # can't crop more than or equal to full height
        # Backup if requested
        if self.move_to_backup.get():
            backup_base = safe_mkdir(os.path.join(self.folder.get(), "_Backup_Edit"))
            rel = os.path.relpath(fpath, self.folder.get())
            dst = os.path.join(backup_base, rel)
            safe_mkdir(os.path.dirname(dst))
            shutil.copy2(fpath, dst)
        # Crop
        if top:
            box = (0, rh, w, h)    # remove top strip
        else:
            box = (0, 0, w, h-rh)  # remove bottom strip
        out = im.crop(box)
        out.save(fpath)

    def _do_deep_search_remove(self, fpath):
        """
        Experimental: find the band of height ref_h that best matches reference anywhere in the image,
        then remove that band (crop out and stitch).
        """
        rh = self._ref_strip_height()
        if rh <= 0:
            return
        ref_path = self.ref_path.get().strip()
        ref = load_image_safely(ref_path)
        if not ref:
            return

        im = load_image_safely(fpath)
        if not im:
            return
        W,H = im.size
        if rh >= H:
            return

        # Make a resized reference width to the target image width (keeps band height rh)
        ref_band = ref.resize((W, rh), Image.LANCZOS)

        # Slide a window of height rh from y=0..H-rh, compute diff score, pick min
        best_y = None
        best_score = None
        step = max(1, rh // 6)  # step for speed; smaller = more accurate
        for y in range(0, H - rh + 1, step):
            band = im.crop((0, y, W, y+rh))
            s = diff_score(band, ref_band)
            if best_score is None or s < best_score:
                best_score = s
                best_y = y

        # Refine around best_y with step=1 within ±rh range
        if best_y is not None:
            y0 = max(0, best_y - rh)
            y1 = min(H - rh, best_y + rh)
            for y in range(y0, y1+1):
                band = im.crop((0, y, W, y+rh))
                s = diff_score(band, ref_band)
                if s < best_score:
                    best_score = s
                    best_y = y

        if best_y is None:
            return

        # Backup if requested
        if self.move_to_backup.get():
            backup_base = safe_mkdir(os.path.join(self.folder.get(), "_Backup_Edit"))
            rel = os.path.relpath(fpath, self.folder.get())
            dst = os.path.join(backup_base, rel)
            safe_mkdir(os.path.dirname(dst))
            shutil.copy2(fpath, dst)

        # Stitch: im[0:best_y] + im[best_y+rh:H]
        top = im.crop((0, 0, W, best_y))
        bottom = im.crop((0, best_y + rh, W, H))
        new_h = top.height + bottom.height
        out = Image.new("RGB", (W, new_h))
        out.paste(top, (0,0))
        out.paste(bottom, (0, top.height))
        out.save(fpath)

def main():
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
