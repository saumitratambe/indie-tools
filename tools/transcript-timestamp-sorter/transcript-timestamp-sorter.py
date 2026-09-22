import sys
import os
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QPlainTextEdit,
    QMessageBox,
)
from PySide6.QtCore import Qt


# Match timestamps in format HH:MM:SS
TIMESTAMP_PATTERN = re.compile(r"(\d{2}:\d{2}:\d{2})")


@dataclass
class Segment:
    order_index: int        # original order index
    timestamp: str          # "HH:MM:SS"
    seconds: int            # total seconds
    text: str               # raw text after this timestamp until next


def timestamp_to_seconds(ts: str) -> int:
    """Convert 'HH:MM:SS' to total seconds."""
    h, m, s = map(int, ts.split(":"))
    return h * 3600 + m * 60 + s


def extract_segments(raw: str) -> Tuple[List[Segment], Optional[str]]:
    """
    Extract segments from raw transcript text.

    Returns:
        segments: list of Segment
        header: text that appears before the first timestamp (if any, else None)
    """
    matches = list(TIMESTAMP_PATTERN.finditer(raw))
    segments: List[Segment] = []

    if not matches:
        return segments, raw.strip() or None

    # Header (text before first timestamp)
    first_start = matches[0].start()
    header = raw[:first_start].strip() or None

    for idx, match in enumerate(matches):
        ts = match.group(1)
        start = match.end()
        if idx + 1 < len(matches):
            end = matches[idx + 1].start()
        else:
            end = len(raw)

        seg_text = raw[start:end]
        segments.append(
            Segment(
                order_index=idx,
                timestamp=ts,
                seconds=timestamp_to_seconds(ts),
                text=seg_text,
            )
        )

    return segments, header


def normalize_segment_text(text: str) -> str:
    """
    Clean segment text:
    - Remove leading/trailing whitespace
    - Collapse internal whitespace/newlines into single spaces
    - Strip any leading timestamp if it accidentally exists in the text
    """
    # Collapse all whitespace (spaces, tabs, newlines) to single spaces
    cleaned = " ".join(text.split())

    # If text itself still starts with a timestamp like 01:05:35, remove it
    cleaned = re.sub(r'^\s*\d{2}:\d{2}:\d{2}\s*', '', cleaned)

    return cleaned


def build_output_text(
    segments: List[Segment],
    header: Optional[str],
    sort_segments: bool = True,
) -> Tuple[str, bool]:
    """
    Build normalized transcript text.

    Args:
        segments: list of Segment
        header: optional header text before first timestamp
        sort_segments: if True, sort by timestamp seconds

    Returns:
        (output_text, was_already_sorted)
    """
    if not segments:
        # Only header or empty file
        return (header.strip() if header else ""), True

    # Check if already sorted by time
    orig_seconds = [seg.seconds for seg in segments]
    sorted_seconds = sorted(orig_seconds)
    was_sorted = (orig_seconds == sorted_seconds)

    # Sort if requested
    if sort_segments and not was_sorted:
        # Stable sort by (seconds, order_index)
        segments = sorted(segments, key=lambda s: (s.seconds, s.order_index))

    lines: List[str] = []

    # Header on top if present
    if header:
        header_clean = header.strip()
        if header_clean:
            lines.append(header_clean)
            lines.append("")  # blank line after header

    prev_key = None  # To skip exact duplicates (timestamp + text)

    for seg in segments:
        text = normalize_segment_text(seg.text)
        key = (seg.timestamp, text)

        # Skip if this segment is identical to the previous one
        if key == prev_key:
            continue

        prev_key = key

        # Timestamp line
        lines.append(seg.timestamp)

        # Segment text line (if not empty)
        if text:
            lines.append(text)

        # Blank line between segments
        lines.append("")

    # Remove trailing blank lines
    while lines and not lines[-1].strip():
        lines.pop()

    return "\n".join(lines), was_sorted


class TimestampFixer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timestamp Corrector (PySide6)")
        self.resize(800, 500)
        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Title
        title_label = QLabel("Timestamp Corrector")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 20px; font-weight: 600;")
        main_layout.addWidget(title_label)

        # Input file row
        input_layout = QHBoxLayout()
        input_label = QLabel("Transcript file (.txt):")
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Select your transcript .txt file...")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_input)

        input_layout.addWidget(input_label)
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(browse_btn)
        main_layout.addLayout(input_layout)

        # Info label for output
        self.output_info_label = QLabel(
            "Output will be saved as: <input_name>_fixed.txt in the same folder."
        )
        main_layout.addWidget(self.output_info_label)

        # Buttons row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        self.fix_btn = QPushButton("Fix Timestamps")
        self.fix_btn.setEnabled(False)
        self.fix_btn.clicked.connect(self.fix_timestamps)
        btn_layout.addWidget(self.fix_btn)
        main_layout.addLayout(btn_layout)

        # Log area
        log_label = QLabel("Status / Log:")
        main_layout.addWidget(log_label)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        main_layout.addWidget(self.log_edit, stretch=1)

        # React to manual path edits
        self.input_edit.textChanged.connect(self._update_button_state)

    def _apply_styles(self):
        # Simple gradient + rounded buttons
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #141e30,
                    stop:1 #243b55
                );
                color: #f2f2f2;
                font-family: "Segoe UI", sans-serif;
                font-size: 12px;
            }
            QLineEdit {
                background: rgba(0, 0, 0, 0.25);
                border: 1px solid #4e6e8e;
                border-radius: 6px;
                padding: 4px 8px;
                color: #f2f2f2;
            }
            QPlainTextEdit {
                background: rgba(0, 0, 0, 0.35);
                border: 1px solid #4e6e8e;
                border-radius: 6px;
                padding: 6px;
                color: #eaeaea;
            }
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff7e5f,
                    stop:1 #feb47b
                );
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                color: #1b1b1b;
                font-weight: 600;
            }
            QPushButton:disabled {
                background: #555;
                color: #aaa;
            }
            QPushButton:hover:!disabled {
                filter: brightness(1.1);
            }
            QLabel {
                font-size: 12px;
            }
        """)

    def log(self, message: str):
        self.log_edit.appendPlainText(message)

    def browse_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select transcript .txt file",
            "",
            "Text Files (*.txt);;All Files (*)",
        )
        if path:
            self.input_edit.setText(path)
            # Update output label
            base, ext = os.path.splitext(path)
            out_path = f"{base}_fixed{ext or '.txt'}"
            self.output_info_label.setText(
                f"Output will be saved as: {out_path}"
            )

    def _update_button_state(self):
        path = self.input_edit.text().strip()
        self.fix_btn.setEnabled(bool(path))

    def fix_timestamps(self):
        path = self.input_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "No file", "Please select a transcript file.")
            return

        if not os.path.isfile(path):
            QMessageBox.critical(self, "File not found", f"File does not exist:\n{path}")
            return

        base, ext = os.path.splitext(path)
        if not ext:
            ext = ".txt"
        out_path = f"{base}_fixed{ext}"

        self.log_edit.clear()
        self.log(f"Input file: {path}")
        self.log(f"Output file (planned): {out_path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Read error", f"Could not read file:\n{e}")
            return

        segments, header = extract_segments(raw)
        if not segments:
            self.log("No timestamps of format HH:MM:SS were found.")
            QMessageBox.warning(
                self,
                "No timestamps",
                "No timestamps (HH:MM:SS) found in this file.",
            )
            return

        self.log(f"Found {len(segments)} timestamp segments.")
        output_text, was_sorted = build_output_text(
            segments, header, sort_segments=True
        )

        if was_sorted:
            self.log("Original timestamps were already in sorted order.")
        else:
            self.log("Detected out-of-order timestamps. Segments have been sorted by time.")

        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(output_text)
        except Exception as e:
            QMessageBox.critical(self, "Write error", f"Could not write output file:\n{e}")
            return

        self.log("✅ Done! Corrected transcript has been saved.")
        self.log(f"Saved to: {out_path}")

        QMessageBox.information(
            self,
            "Success",
            f"Timestamp correction complete.\n\nOutput saved to:\n{out_path}",
        )


def main():
    app = QApplication(sys.argv)
    w = TimestampFixer()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
