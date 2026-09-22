# Name: name_replacer_gui.py
# Requirements (install once):
#   pip install PySide6 pandas openpyxl
#
# What it does:
# - Load a CSV/XLSX that has headers in row 1: "name" and "replacement".
# - Starts processing from row 2 automatically (skips header).
# - Lets you pick a novel .txt file.
# - Replaces whole words safely, sorting by longer names first.
# - Shows a live log table and progress.
# - Saves:
#     <novel>_replaced.txt  (the processed text)
#     replacement_log.xlsx  (Old/New/Replacements)
#
# Notes:
# - CSV/XLSX reading is case-insensitive for headers ("name", "replacement").
# - If those headers are missing, it will fallback to first two columns.

import os
import re
import sys
import traceback
import pandas as pd

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QMessageBox,
    QLabel, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox
)

class ReplaceWorker(QThread):
    progress = Signal(int)                       # 0..100
    row_done = Signal(str, str, int)             # old, new, count
    finished_ok = Signal(str, str)               # out_text_path, log_path
    failed = Signal(str)                         # error message

    def __init__(self, map_path: str, text_path: str, parent=None):
        super().__init__(parent)
        self.map_path = map_path
        self.text_path = text_path

    def _read_mapping(self, path: str) -> pd.DataFrame:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".csv":
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
        elif ext in (".xlsx", ".xls"):
            # openpyxl handles .xlsx
            df = pd.read_excel(path, engine="openpyxl")
            # Make sure strings not become NaN for empty cells later
            df = df.fillna("")
        else:
            raise ValueError("Please select a .csv or .xlsx file.")

        # Normalize column names (case-insensitive)
        cols = [str(c).strip() for c in df.columns]
        lower_map = {c.lower(): c for c in cols}

        name_col = lower_map.get("name")
        repl_col = lower_map.get("replacement")

        # Fallback if headers not found: use first two columns
        if name_col is None or repl_col is None:
            if df.shape[1] < 2:
                raise ValueError("Mapping must have at least two columns (name, replacement).")
            name_col = df.columns[0]
            repl_col = df.columns[1]

        # Ensure strings; skip header by slicing from row 2 conceptually (but since
        # we rely on headers, simply use all rows and ignore empties)
        df = df[[name_col, repl_col]].copy()
        df.columns = ["From", "To"]
        # Drop rows where both are empty
        df = df[~((df["From"].astype(str).str.strip() == "") & (df["To"].astype(str).str.strip() == ""))]

        # IMPORTANT: we "continue replacement from row 2" means we just respect the header
        # row and process all actual data rows below. If the user accidentally repeated
        # headers inside the data, this guard removes them:
        df = df[df["From"].astype(str).str.lower() != "name"]
        df = df[df["To"].astype(str).str.lower() != "replacement"]

        # Strip whitespace
        df["From"] = df["From"].astype(str).str.strip()
        df["To"] = df["To"].astype(str).str.strip()

        # Remove empty "From" or "To"
        df = df[(df["From"] != "") & (df["To"] != "")]

        # Sort by length of "From" descending to avoid partial overlaps
        df = df.sort_values(by="From", key=lambda s: s.astype(str).str.len(), ascending=False).reset_index(drop=True)
        return df

    def run(self):
        try:
            if not os.path.exists(self.map_path):
                raise FileNotFoundError(f"Mapping file not found:\n{self.map_path}")
            if not os.path.exists(self.text_path):
                raise FileNotFoundError(f"Text file not found:\n{self.text_path}")

            # Load text
            with open(self.text_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Load mapping
            df = self._read_mapping(self.map_path)
            total = len(df)
            if total == 0:
                raise ValueError("No valid rows found in mapping (after header).")

            # Replacement loop
            replacement_log = []
            for i, row in df.iterrows():
                old = str(row["From"])
                new = str(row["To"])

                # Whole-word regex (avoid replacing inside other words)
                # Use word boundaries; re.escape for safety
                pattern = r"\b{}\b".format(re.escape(old))
                matches = re.findall(pattern, content)
                count = len(matches)

                if count > 0:
                    content = re.sub(pattern, new, content)
                    replacement_log.append({"Old": old, "New": new, "Replacements": count})
                    self.row_done.emit(old, new, count)

                # Progress
                pct = int(((i + 1) / total) * 100)
                self.progress.emit(pct)

            # Save outputs next to input text
            base_dir = os.path.dirname(self.text_path)
            base_name = os.path.splitext(os.path.basename(self.text_path))[0]
            out_text = os.path.join(base_dir, f"{base_name}_replaced.txt")
            with open(out_text, "w", encoding="utf-8") as f:
                f.write(content)

            # Save log
            log_path = os.path.join(base_dir, "replacement_log.xlsx")
            pd.DataFrame(replacement_log).to_excel(log_path, index=False)

            self.finished_ok.emit(out_text, log_path)

        except Exception as e:
            tb = traceback.format_exc()
            self.failed.emit(f"{e}\n\n{tb}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Name Replacement GUI — PySide6")
        self.setMinimumWidth(900)

        # Inputs
        self.map_edit = QLineEdit()
        self.map_btn = QPushButton("Browse…")
        self.map_btn.clicked.connect(self.browse_map)

        self.text_edit = QLineEdit()
        self.text_btn = QPushButton("Browse…")
        self.text_btn.clicked.connect(self.browse_text)

        # Action buttons
        self.start_btn = QPushButton("Start Replacement")
        self.start_btn.clicked.connect(self.start_replacement)
        self.start_btn.setEnabled(False)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        # Log table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Old", "New", "Replacements"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        # Paths group
        map_row = QHBoxLayout()
        map_row.addWidget(QLabel("Mapping (CSV/XLSX) — headers in row 1: name, replacement"))
        map_row.addStretch()

        map_pick = QHBoxLayout()
        map_pick.addWidget(self.map_edit)
        map_pick.addWidget(self.map_btn)

        text_row = QHBoxLayout()
        text_row.addWidget(QLabel("Novel .txt file"))
        text_row.addStretch()

        text_pick = QHBoxLayout()
        text_pick.addWidget(self.text_edit)
        text_pick.addWidget(self.text_btn)

        ip_group = QGroupBox("Inputs")
        ip_layout = QVBoxLayout()
        ip_layout.addLayout(map_row)
        ip_layout.addLayout(map_pick)
        ip_layout.addSpacing(8)
        ip_layout.addLayout(text_row)
        ip_layout.addLayout(text_pick)
        ip_group.setLayout(ip_layout)

        # Controls group
        ctrl_group = QGroupBox("Run")
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(self.start_btn)
        ctrl_layout.addWidget(self.progress)
        ctrl_group.setLayout(ctrl_layout)

        # Log group
        log_group = QGroupBox("Replacement Log (live)")
        log_layout = QVBoxLayout()
        log_layout.addWidget(self.table)
        log_group.setLayout(log_layout)

        # Main layout
        root = QWidget()
        v = QVBoxLayout(root)
        v.addWidget(ip_group)
        v.addWidget(ctrl_group)
        v.addWidget(log_group)
        self.setCentralWidget(root)

        # Wire edits to enable Start when ready
        self.map_edit.textChanged.connect(self._maybe_enable_start)
        self.text_edit.textChanged.connect(self._maybe_enable_start)

        self.worker = None

    def browse_map(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select mapping file", "", "Mapping Files (*.csv *.xlsx *.xls);;All Files (*)"
        )
        if path:
            self.map_edit.setText(path)

    def browse_text(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select novel text file", "", "Text Files (*.txt);;All Files (*)"
        )
        if path:
            self.text_edit.setText(path)

    def _maybe_enable_start(self):
        self.start_btn.setEnabled(bool(self.map_edit.text().strip()) and bool(self.text_edit.text().strip()))

    def start_replacement(self):
        self.table.setRowCount(0)
        self.progress.setValue(0)

        map_path = self.map_edit.text().strip()
        text_path = self.text_edit.text().strip()

        if not os.path.exists(map_path):
            QMessageBox.warning(self, "Missing file", "Please select a valid mapping file (.csv or .xlsx).")
            return
        if not os.path.exists(text_path):
            QMessageBox.warning(self, "Missing file", "Please select a valid novel .txt file.")
            return

        self.start_btn.setEnabled(False)

        self.worker = ReplaceWorker(map_path, text_path)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.row_done.connect(self._on_row_done)
        self.worker.finished_ok.connect(self._on_finished_ok)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_row_done(self, old: str, new: str, count: int):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(old))
        self.table.setItem(r, 1, QTableWidgetItem(new))
        self.table.setItem(r, 2, QTableWidgetItem(str(count)))

    def _on_finished_ok(self, out_text_path: str, log_path: str):
        self.start_btn.setEnabled(True)
        self.progress.setValue(100)
        QMessageBox.information(
            self,
            "Done",
            f"Replacement complete!\n\nSaved:\n• {out_text_path}\n• {log_path}"
        )

    def _on_failed(self, message: str):
        self.start_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Something went wrong:\n\n{message}")

def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
