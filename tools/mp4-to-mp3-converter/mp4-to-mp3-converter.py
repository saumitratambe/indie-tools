# mp4_to_mp3_gui.py
# Simple MP4 → MP3 converter using PySide6 + ffmpeg
# Works on Windows/Linux/macOS (needs ffmpeg installed)

import os
import sys
import shlex
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QProcess, QTimer
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFileDialog, QTextEdit, QComboBox, QMessageBox, QCheckBox
)

def guess_ffmpeg_path():
    """
    Try a few common ways to locate ffmpeg:
    1) PATH ("ffmpeg")
    2) Local folder beside the script ("./ffmpeg.exe" or "./ffmpeg")
    Returns a string path or None if not found.
    """
    candidates = ["ffmpeg"]
    here = Path(__file__).resolve().parent
    if os.name == "nt":
        candidates.append(str(here / "ffmpeg.exe"))
    else:
        candidates.append(str(here / "ffmpeg"))

    for c in candidates:
        try:
            # Check if ffmpeg is callable
            subprocess.run([c, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
            return c
        except Exception:
            continue
    return None


class ConverterUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP4 → MP3 Converter (PySide6 + ffmpeg)")
        self.setMinimumWidth(720)

        # Widgets
        self.in_label = QLabel("Input MP4:")
        self.in_edit = QLineEdit()
        self.in_browse = QPushButton("Browse…")

        self.out_label = QLabel("Output MP3:")
        self.out_edit = QLineEdit()
        self.out_browse = QPushButton("Browse…")

        self.same_folder_cb = QCheckBox("Place output next to input")
        self.same_folder_cb.setChecked(True)

        self.br_label = QLabel("Bitrate:")
        self.br_combo = QComboBox()
        self.br_combo.addItems(["96k", "128k", "160k", "192k", "256k", "320k"])
        self.br_combo.setCurrentText("96k")

        self.ffmpeg_label = QLabel("ffmpeg:")
        self.ffmpeg_edit = QLineEdit()
        self.ffmpeg_browse = QPushButton("Browse ffmpeg…")

        self.start_btn = QPushButton("Convert")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)

        self.open_folder_btn = QPushButton("Open Output Folder")
        self.open_folder_btn.setEnabled(False)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Logs will appear here…")

        # Layouts
        row1 = QHBoxLayout()
        row1.addWidget(self.in_label)
        row1.addWidget(self.in_edit, 1)
        row1.addWidget(self.in_browse)

        row2 = QHBoxLayout()
        row2.addWidget(self.out_label)
        row2.addWidget(self.out_edit, 1)
        row2.addWidget(self.out_browse)

        row3 = QHBoxLayout()
        row3.addWidget(self.br_label)
        row3.addWidget(self.br_combo)
        row3.addStretch(1)
        row3.addWidget(self.same_folder_cb)

        row4 = QHBoxLayout()
        row4.addWidget(self.ffmpeg_label)
        row4.addWidget(self.ffmpeg_edit, 1)
        row4.addWidget(self.ffmpeg_browse)

        row5 = QHBoxLayout()
        row5.addWidget(self.start_btn)
        row5.addWidget(self.cancel_btn)
        row5.addStretch(1)
        row5.addWidget(self.open_folder_btn)

        root = QVBoxLayout(self)
        root.addLayout(row1)
        root.addLayout(row2)
        root.addLayout(row3)
        root.addLayout(row4)
        root.addWidget(self.log, 1)
        root.addLayout(row5)

        # Process
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.on_proc_output)
        self.proc.readyReadStandardError.connect(self.on_proc_output)
        self.proc.finished.connect(self.on_proc_finished)

        # Signals
        self.in_browse.clicked.connect(self.pick_input)
        self.out_browse.clicked.connect(self.pick_output)
        self.same_folder_cb.stateChanged.connect(self.on_same_folder_change)
        self.ffmpeg_browse.clicked.connect(self.pick_ffmpeg)
        self.start_btn.clicked.connect(self.start_convert)
        self.cancel_btn.clicked.connect(self.cancel_convert)
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        self.in_edit.textChanged.connect(self.autofill_output_name)

        # Initialize ffmpeg path
        found = guess_ffmpeg_path()
        if found:
            self.ffmpeg_edit.setText(found)

    def append_log(self, text: str):
        self.log.append(text.rstrip())

    def pick_input(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select MP4 file", "", "MP4 Video (*.mp4);;All Files (*)")
        if path:
            self.in_edit.setText(path)

    def pick_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save MP3 as", self.suggest_output_path(), "MP3 Audio (*.mp3)")
        if path:
            if not path.lower().endswith(".mp3"):
                path += ".mp3"
            self.out_edit.setText(path)
            self.same_folder_cb.setChecked(False)

    def suggest_output_path(self):
        in_path = self.in_edit.text().strip()
        if not in_path:
            return ""
        stem = Path(in_path).stem
        parent = Path(in_path).parent
        return str(parent / f"{stem}.mp3")

    def autofill_output_name(self):
        if self.same_folder_cb.isChecked():
            self.out_edit.setText(self.suggest_output_path())

    def on_same_folder_change(self, _state):
        if self.same_folder_cb.isChecked():
            self.out_edit.setText(self.suggest_output_path())

    def pick_ffmpeg(self):
        title = "Select ffmpeg executable"
        if os.name == "nt":
            path, _ = QFileDialog.getOpenFileName(self, title, "", "Executable (ffmpeg.exe)")
        else:
            path, _ = QFileDialog.getOpenFileName(self, title, "", "All Files (*)")
        if path:
            self.ffmpeg_edit.setText(path)

    def validate_inputs(self):
        ffmpeg_path = self.ffmpeg_edit.text().strip() or "ffmpeg"
        # Verify ffmpeg is callable
        try:
            subprocess.run([ffmpeg_path, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        except Exception:
            QMessageBox.critical(self, "ffmpeg not found",
                                 "ffmpeg is not available.\n\nInstall FFmpeg and add it to PATH, "
                                 "or browse to ffmpeg.exe/ffmpeg binary.")
            return None

        in_file = self.in_edit.text().strip()
        if not in_file:
            QMessageBox.warning(self, "Missing input", "Please choose an input MP4 file.")
            return None
        if not Path(in_file).is_file():
            QMessageBox.warning(self, "Invalid input", "The selected input file does not exist.")
            return None

        out_file = self.out_edit.text().strip() or self.suggest_output_path()
        if not out_file:
            QMessageBox.warning(self, "Missing output", "Please specify an output MP3 path.")
            return None

        out_dir = Path(out_file).parent
        out_dir.mkdir(parents=True, exist_ok=True)

        bitrate = self.br_combo.currentText()

        return {
            "ffmpeg": ffmpeg_path,
            "input": in_file,
            "output": out_file,
            "bitrate": bitrate
        }

    def start_convert(self):
        cfg = self.validate_inputs()
        if not cfg:
            return

        # Build ffmpeg command
        cmd = [
            cfg["ffmpeg"],
            "-y",
            "-i", cfg["input"],
            "-vn",
            "-acodec", "libmp3lame",
            "-b:a", cfg["bitrate"],
            cfg["output"]
        ]

        self.log.clear()
        self.append_log("Starting conversion…")
        self.append_log("Command:")
        self.append_log(" ".join(shlex.quote(c) for c in cmd))

        # Disable/enable buttons appropriately
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(False)

        # Start QProcess
        # On Windows, passing a string can be safer; but we’ll pass list as well.
        self.proc.start(cmd[0], cmd[1:])
        if not self.proc.waitForStarted(3000):
            self.append_log("Failed to start ffmpeg process.")
            QMessageBox.critical(self, "Error", "Could not start ffmpeg. Check the path and try again.")
            self.start_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)

    def on_proc_output(self):
        out = bytes(self.proc.readAllStandardOutput()).decode(errors="ignore")
        if out:
            for line in out.splitlines():
                self.append_log(line)

        err = bytes(self.proc.readAllStandardError()).decode(errors="ignore")
        if err:
            for line in err.splitlines():
                self.append_log(line)

    def on_proc_finished(self, code, status):
        self.cancel_btn.setEnabled(False)
        self.start_btn.setEnabled(True)

        if code == 0:
            self.append_log("\n✅ Done!")
            self.open_folder_btn.setEnabled(True)
            # If output exists, encourage user to open
            # (No blocking dialog to keep flow smooth)
        else:
            self.append_log(f"\n⛔ ffmpeg exited with code {code}. See logs above.")

    def cancel_convert(self):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self.proc.kill()
            self.proc.waitForFinished(1000)
            self.append_log("Conversion cancelled by user.")
            self.start_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)

    def open_output_folder(self):
        out_path = self.out_edit.text().strip()
        if not out_path:
            return
        folder = str(Path(out_path).parent.resolve())
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            QMessageBox.information(self, "Open Folder", f"Folder: {folder}\n\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ConverterUI()
    w.show()
    sys.exit(app.exec())
