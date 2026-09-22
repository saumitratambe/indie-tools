import sys
import os

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QFileDialog,
    QProgressBar,
    QMessageBox,
)
from PySide6.QtCore import Qt

# Try to import Gemini SDK
HAS_GEMINI = True
try:
    import google.generativeai as genai
except ImportError:
    HAS_GEMINI = False


GEMINI_MODEL_NAME = "gemini-flash-lite-latest"   # "gemini-flash lite latest" equivalent


class HinglishGeminiApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hinglish → Hindi (Devanagari) via Gemini 1.5 Flash")
        self.resize(900, 550)

        self.input_path = None
        self.output_path = None

        self._build_ui()

        if not HAS_GEMINI:
            QMessageBox.critical(
                self,
                "Missing Dependency",
                "Python package 'google-generativeai' is not installed.\n\n"
                "Run this in your terminal:\n\n"
                "    pip install google-generativeai\n",
            )

    # ---------------- UI -----------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Hinglish → Hindi (Devanagari) using Gemini 1.5 Flash")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # API key row
        api_row = QHBoxLayout()
        api_label = QLabel("Gemini API Key:")
        self.api_edit = QLineEdit()
        self.api_edit.setEchoMode(QLineEdit.Password)
        self.api_edit.setPlaceholderText("Paste your Gemini API key here…")
        api_row.addWidget(api_label)
        api_row.addWidget(self.api_edit)
        layout.addLayout(api_row)

        # Input file row
        in_row = QHBoxLayout()
        self.input_label = QLabel("Input: (no file selected)")
        self.input_label.setStyleSheet("color: #555;")
        btn_input = QPushButton("Select Input .txt")
        btn_input.clicked.connect(self.choose_input_file)
        in_row.addWidget(self.input_label)
        in_row.addWidget(btn_input)
        layout.addLayout(in_row)

        # Output file row
        out_row = QHBoxLayout()
        self.output_label = QLabel("Output: (auto from input or choose)")
        self.output_label.setStyleSheet("color: #555;")
        btn_output = QPushButton("Select Output File")
        btn_output.clicked.connect(self.choose_output_file)
        out_row.addWidget(self.output_label)
        out_row.addWidget(btn_output)
        layout.addLayout(out_row)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Convert button
        btn_convert = QPushButton("Convert Hinglish → Hindi via Gemini")
        btn_convert.setStyleSheet("font-size: 14px; font-weight: bold; padding: 6px;")
        btn_convert.clicked.connect(self.convert_with_gemini)
        layout.addWidget(btn_convert)

        # Log / status box
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        layout.addWidget(self.log_box)

    def log(self, msg: str):
        self.log_box.append(msg)

    # ------------- File selection -------------

    def choose_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Input Text File",
            "",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if file_path:
            self.input_path = file_path
            self.input_label.setText(f"Input: {file_path}")
            self.log(f"Selected input file: {file_path}")

            if not self.output_path:
                base, ext = os.path.splitext(file_path)
                suggested = base + "_hindi_gemini.txt"
                self.output_path = suggested
                self.output_label.setText(f"Output: {self.output_path}")
                self.log(f"Auto output file set to: {self.output_path}")

    def choose_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Output Text File",
            self.output_path or "",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if file_path:
            self.output_path = file_path
            self.output_label.setText(f"Output: {file_path}")
            self.log(f"Selected output file: {file_path}")

    # ------------- Gemini call -------------

    def _generate_with_gemini(self, api_key: str, input_text: str) -> str:
        """
        Call Gemini to transliterate Hinglish → Hindi Devanagari,
        preserving timestamps like [00:00:00].
        """
        if not HAS_GEMINI:
            raise RuntimeError(
                "google-generativeai is not installed. "
                "Run: pip install google-generativeai"
            )

        if not api_key.strip():
            raise RuntimeError("Gemini API key is empty.")

        # Configure client
        genai.configure(api_key=api_key.strip())

        # Build prompt
        system_instructions = (
            "You are a transliteration engine for Hindi.\n"
            "Task:\n"
            " - Input text is a transcript with lines like:\n"
            "   [00:00:00] Scarlet sunset ke neeche yeh maidan ek quest hai...\n"
            " - Each line may start with a timestamp in the exact format [HH:MM:SS].\n"
            " - DO NOT edit, move, remove, or create any timestamps.\n"
            " - For each line, keep the timestamp exactly the same.\n"
            " - Only transliterate the HINGLISH (Hindi written in Latin letters)\n"
            "   into NATURAL HINDI DEVANAGARI.\n"
            " - Do NOT translate or summarise. Keep the same sentences and meaning.\n"
            " - Preserve punctuation, line breaks, and any text that is already\n"
            "   in Devanagari.\n"
            " - Return output in the SAME FORMAT as the input: same number of lines,\n"
            "   same timestamps, just Hinglish text turned into Devanagari.\n"
            "   The Word inside Brackets should also be In devanagri Cause our work will fail if any Latin later will be there in output\n"
        )

        prompt = (
            system_instructions
            + "\n\n=== INPUT START ===\n"
            + input_text
            + "\n=== INPUT END ===\n\n"
            + "Now output ONLY the converted text, no explanations,no any latin letters and words, no extra comments."
        )

        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        response = model.generate_content(prompt)
        # For standard usage, text is in response.text
        return response.text

    # ------------- Conversion flow -------------

    def convert_with_gemini(self):
        api_key = self.api_edit.text().strip()
        if not api_key:
            QMessageBox.warning(self, "No API key", "Please paste your Gemini API key.")
            return

        if not self.input_path:
            QMessageBox.warning(self, "No Input", "Please select an input .txt file.")
            return

        if not self.output_path:
            QMessageBox.warning(self, "No Output", "Please select an output file path.")
            return

        # Read entire file
        try:
            self.log("Reading input file...")
            with open(self.input_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Read Error", f"Failed to read input file:\n{e}")
            self.log(f"ERROR reading file: {e}")
            return

        if not text.strip():
            QMessageBox.warning(self, "Empty File", "Input file is empty.")
            self.log("Input file is empty, nothing to convert.")
            return

        self.progress_bar.setValue(10)
        QApplication.processEvents()

        try:
            self.log("Sending text to Gemini (this may take a bit)...")
            converted = self._generate_with_gemini(api_key, text)
        except Exception as e:
            QMessageBox.critical(self, "Gemini Error", f"Error from Gemini API:\n{e}")
            self.log(f"ERROR during Gemini call: {e}")
            return

        self.progress_bar.setValue(80)
        QApplication.processEvents()

        # Write output
        try:
            with open(self.output_path, "w", encoding="utf-8") as f_out:
                f_out.write(converted)
        except Exception as e:
            QMessageBox.critical(self, "Write Error", f"Failed to write output file:\n{e}")
            self.log(f"ERROR writing file: {e}")
            return

        self.progress_bar.setValue(100)
        self.log("✅ Conversion complete!")
        self.log(f"Saved to: {self.output_path}")
        QMessageBox.information(
            self,
            "Done",
            f"Hinglish → Hindi conversion complete via Gemini.\n\n"
            f"Output saved to:\n{self.output_path}",
        )


def main():
    app = QApplication(sys.argv)
    window = HinglishGeminiApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
