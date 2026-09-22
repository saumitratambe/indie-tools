import os
import re
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QFileDialog,
    QVBoxLayout, QLineEdit, QLabel, QMessageBox
)


# ----------- Helper: Check if line is timestamp --------------
def is_timestamp(line: str) -> bool:
    return bool(re.match(r"^\d{2}:\d{2}:\d{2}$", line.strip()))


# ----------- Main Split Logic --------------------------------
def split_text_file(input_file, output_folder, parts):
    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Collect all timestamp indexes
    timestamps = []
    for i, line in enumerate(lines):
        if is_timestamp(line):
            timestamps.append(i)

    if len(timestamps) < parts:
        raise ValueError("Not enough timestamps to make parts.")

    # Decide splitting points
    split_points = []
    for i in range(1, parts):
        index = int((len(timestamps) / parts) * i)
        split_points.append(timestamps[index])

    split_points.append(len(lines))

    # Make chunks
    start = 0
    for idx, end in enumerate(split_points):
        chunk_lines = lines[start:end]
        out_path = os.path.join(output_folder, f"part_{idx+1}.txt")

        with open(out_path, "w", encoding="utf-8") as out:
            out.writelines(chunk_lines)

        start = end


# ---------------- GUI ------------------
class SplitterGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Text Splitter (Timestamp Safe)")

        layout = QVBoxLayout()

        # Input file
        self.in_label = QLabel("Input Text File:")
        self.in_path = QLineEdit()
        self.in_btn = QPushButton("Browse Input")
        self.in_btn.clicked.connect(self.pick_input)

        # Output folder
        self.out_label = QLabel("Output Folder:")
        self.out_path = QLineEdit()
        self.out_btn = QPushButton("Browse Output")
        self.out_btn.clicked.connect(self.pick_output)

        # Parts
        self.parts_label = QLabel("How many parts?")
        self.parts_edit = QLineEdit()
        self.parts_edit.setPlaceholderText("Enter number")

        # Start button
        self.start_btn = QPushButton("Split Now")
        self.start_btn.clicked.connect(self.start_split)

        # Add widgets
        layout.addWidget(self.in_label)
        layout.addWidget(self.in_path)
        layout.addWidget(self.in_btn)

        layout.addWidget(self.out_label)
        layout.addWidget(self.out_path)
        layout.addWidget(self.out_btn)

        layout.addWidget(self.parts_label)
        layout.addWidget(self.parts_edit)

        layout.addWidget(self.start_btn)

        self.setLayout(layout)

    def pick_input(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose Text File", "", "Text Files (*.txt)")
        if path:
            self.in_path.setText(path)

    def pick_output(self):
        path = QFileDialog.getExistingDirectory(self, "Choose Output Folder")
        if path:
            self.out_path.setText(path)

    def start_split(self):
        input_file = self.in_path.text().strip()
        output_folder = self.out_path.text().strip()
        parts = self.parts_edit.text().strip()

        if not input_file or not output_folder or not parts:
            QMessageBox.warning(self, "Error", "Please fill all fields!")
            return

        try:
            parts = int(parts)
            split_text_file(input_file, output_folder, parts)
            QMessageBox.information(self, "Done", "Splitting completed!")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


if __name__ == "__main__":
    app = QApplication([])
    gui = SplitterGUI()
    gui.show()
    app.exec()