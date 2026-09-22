# GenZ Hindi Translator (PySide6 + Gemini)
# ------------------------------------------------
# Features:
# - Select input folder of .txt (para1.txt, para2.txt, ...)
# - Select output folder (translated files saved with same names, UTF-8)
# - Gemini model dropdown (gemini-1.5-flash / gemini-1.5-pro)
# - Multiple API keys (comma-separated). Round-robin on failures.
# - Rate limiting control (requests per minute)
# - Skip existing outputs option
# - Live log and progress bar
#
# Setup (once): pip install PySide6 google-generativeai
#
# Run: python gemini-hindi-batch-translator.py

import os
import sys
import time
import traceback
from pathlib import Path
from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

# Google Generative AI (Gemini)
import google.generativeai as genai


GENZ_TRANSLATION_SYSTEM_PROMPT = (
    "You are a professional literary translator and creative rewriter. "
    "Your job is to translate AND adapt English web-novel paragraphs into NATURAL, "
    "story-like, engaging Hindi with a subtle Gen-Z vibe suitable for Indian audiences. "
    "CRITICAL RULES:\n"
    "1) Output language: Hindi only (no English lines), but light Gen-Z tone/slang is okay if it keeps the meaning clear.\n"
    "2) Preserve meaning, character names, places, and terminology exactly as in the source unless a place is a common generic noun.\n"
    "3) Keep paragraph boundaries: produce a single polished Hindi paragraph for each input paragraph (no bullet points, no headings, no emojis).\n"
    "4) Keep it cinematic, smooth, and readable; avoid cringe slang and avoid vulgarity.\n"
    "5) Do NOT add extra plot info, do NOT summarize; fully translate/adapt the whole content.\n"
    "6) Maintain pronouns, tense, tone, and emotions accurately; keep metaphors if present.\n"
    "7) Use standard Devanagari punctuation where natural.\n"
)

USER_INSTRUCTION_TEMPLATE = (
    "Translate & adapt the following paragraph to Hindi in a clean, cinematic, Indian Gen-Z friendly narration. "
    "Return ONLY the Hindi paragraph, nothing else.\n\n"
    "Paragraph:\n{paragraph}"
)


def chunk_text_if_needed(txt: str, max_chars: int = 18000) -> List[str]:
    """
    Gemini can handle long inputs, but this is a safety guard.
    Splits by sentences if extremely large. Most para*.txt will be fine.
    """
    if len(txt) <= max_chars:
        return [txt]
    # naive chunk by sentences/full stops to keep boundaries reasonable
    parts = []
    current = []
    size = 0
    for seg in txt.split(". "):
        s = seg + ". "
        if size + len(s) > max_chars and current:
            parts.append("".join(current).strip())
            current, size = [], 0
        current.append(s)
        size += len(s)
    if current:
        parts.append("".join(current).strip())
    return parts


class TranslatorWorker(QtCore.QThread):
    log_signal = QtCore.Signal(str)
    progress_signal = QtCore.Signal(int)
    done_signal = QtCore.Signal()

    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        model_name: str,
        api_keys: List[str],
        rpm: int,
        temperature: float,
        skip_existing: bool,
        parent=None,
    ):
        super().__init__(parent)
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.model_name = model_name
        self.api_keys = [k.strip() for k in api_keys if k.strip()]
        self.rpm = max(1, int(rpm))  # minimum 1 req/min
        self.temperature = float(temperature)
        self.skip_existing = skip_existing
        self._stop_requested = False
        self._key_index = 0

    def request_stop(self):
        self._stop_requested = True

    # ----- Gemini call -----
    def _configure_key(self, key: str):
        genai.configure(api_key=key)

    def _get_model(self):
        return genai.GenerativeModel(
            self.model_name,
            system_instruction=GENZ_TRANSLATION_SYSTEM_PROMPT
        )

    def _switch_key(self):
        if not self.api_keys:
            return
        self._key_index = (self._key_index + 1) % len(self.api_keys)
        self._configure_key(self.api_keys[self._key_index])

    def _active_key(self) -> Optional[str]:
        if not self.api_keys:
            return None
        return self.api_keys[self._key_index]

    def _sleep_for_rpm(self):
        # Simple pacing: spread calls evenly across the minute
        time.sleep(60.0 / float(self.rpm))

    def _translate_paragraph(self, text: str, max_retries_per_key: int = 2) -> str:
        """
        Attempts translation with current key; on failures, rotates keys and retries.
        """
        if not self.api_keys:
            raise RuntimeError("No API keys provided.")

        attempts = 0
        total_allowed = max_retries_per_key * len(self.api_keys)

        while attempts < total_allowed and not self._stop_requested:
            key = self._active_key()
            try:
                model = self._get_model()
                prompt = USER_INSTRUCTION_TEMPLATE.format(paragraph=text)

                # Pace to respect RPM
                self._sleep_for_rpm()

                resp = model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": self.temperature,
                        "max_output_tokens": 2048,
                    },
                )
                out = resp.text or ""
                out = out.strip()

                # Clean trivial leading artifacts (sometimes models add quotes)
                if out.startswith('"') and out.endswith('"'):
                    out = out[1:-1].strip()

                if not out:
                    raise RuntimeError("Empty response received.")

                return out

            except Exception as e:
                attempts += 1
                self.log_signal.emit(
                    f"[KEY ****{key[-6:] if key else 'NONE'}] Error: {type(e).__name__}: {e}"
                )
                # rotate key after each failure
                self._switch_key()
                # short backoff
                time.sleep(2)

        raise RuntimeError("All keys failed for this paragraph.")

    # ----- Main run loop -----
    def run(self):
        try:
            if not self.input_dir.exists():
                self.log_signal.emit("❌ Input folder does not exist.")
                return
            self.output_dir.mkdir(parents=True, exist_ok=True)

            files = sorted([p for p in self.input_dir.glob("*.txt")])
            total = len(files)
            if total == 0:
                self.log_signal.emit("No .txt files found in input.")
                return

            self._configure_key(self._active_key() or "")
            self.log_signal.emit(
                f"🚀 Starting translation | Model: {self.model_name} | Keys: {len(self.api_keys)} | RPM: {self.rpm}"
            )

            for idx, src in enumerate(files, start=1):
                if self._stop_requested:
                    self.log_signal.emit("🛑 Stop requested. Finishing current step...")
                    break

                dst = self.output_dir / src.name
                if self.skip_existing and dst.exists() and dst.stat().st_size > 0:
                    self.log_signal.emit(f"⏭️ Skipped (exists): {src.name}")
                    self.progress_signal.emit(int(idx * 100 / total))
                    continue

                try:
                    text = src.read_text(encoding="utf-8", errors="ignore").strip()
                    if not text:
                        self.log_signal.emit(f"⚠️ Empty file: {src.name} (skipped)")
                        self.progress_signal.emit(int(idx * 100 / total))
                        continue

                    parts = chunk_text_if_needed(text)
                    translated_parts = []
                    for pi, part in enumerate(parts, start=1):
                        if self._stop_requested:
                            break
                        self.log_signal.emit(f"📝 Translating {src.name} (chunk {pi}/{len(parts)})...")
                        hindi = self._translate_paragraph(part)
                        translated_parts.append(hindi)

                    if self._stop_requested:
                        break

                    final = "\n".join(translated_parts).strip()
                    dst.write_text(final, encoding="utf-8")
                    self.log_signal.emit(f"✅ Done: {src.name}")

                except Exception as e:
                    self.log_signal.emit(f"❌ Failed: {src.name} -> {e}")
                    # write partial (if any) to a .error.txt for debugging
                    try:
                        (self.output_dir / f"{src.stem}.error.txt").write_text(
                            f"Source file: {src.name}\n\nTraceback:\n{traceback.format_exc()}",
                            encoding="utf-8",
                        )
                    except Exception:
                        pass

                self.progress_signal.emit(int(idx * 100 / total))

            self.log_signal.emit("🎉 All done (or stopped).")
        finally:
            self.done_signal.emit()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GenZ Hindi Translator (Gemini)")
        self.setMinimumSize(900, 600)

        # --- Widgets ---
        self.input_edit = QtWidgets.QLineEdit()
        self.btn_browse_in = QtWidgets.QPushButton("Browse…")
        self.btn_browse_in.clicked.connect(self.choose_input)

        self.output_edit = QtWidgets.QLineEdit()
        self.btn_browse_out = QtWidgets.QPushButton("Browse…")
        self.btn_browse_out.clicked.connect(self.choose_output)

        self.model_combo = QtWidgets.QComboBox()
        # Add common Gemini text models
        self.model_combo.addItems([
            "gemma-3-4b-it",
            "gemini-flash-lite-latest",
        ])

        self.keys_edit = QtWidgets.QLineEdit()
        self.keys_edit.setPlaceholderText("Enter one or more API keys (comma-separated)")

        self.rpm_spin = QtWidgets.QSpinBox()
        self.rpm_spin.setRange(1, 300)
        self.rpm_spin.setValue(30)
        self.rpm_spin.setSuffix(" req/min")

        self.temp_spin = QtWidgets.QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 1.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(0.7)

        self.skip_check = QtWidgets.QCheckBox("Skip if output exists")
        self.skip_check.setChecked(True)

        self.start_btn = QtWidgets.QPushButton("Start")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.setEnabled(False)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("font-family: Consolas, Menlo, monospace;")

        # --- Layout ---
        form = QtWidgets.QFormLayout()
        in_row = QtWidgets.QHBoxLayout()
        in_row.addWidget(self.input_edit)
        in_row.addWidget(self.btn_browse_in)
        form.addRow("Input folder (.txt):", self._wrap(in_row))

        out_row = QtWidgets.QHBoxLayout()
        out_row.addWidget(self.output_edit)
        out_row.addWidget(self.btn_browse_out)
        form.addRow("Output folder:", self._wrap(out_row))

        model_row = QtWidgets.QHBoxLayout()
        model_row.addWidget(self.model_combo)
        form.addRow("Gemini model:", self._wrap(model_row))

        form.addRow("API keys:", self.keys_edit)

        opts_row = QtWidgets.QHBoxLayout()
        opts_row.addWidget(QtWidgets.QLabel("Rate limit:"))
        opts_row.addWidget(self.rpm_spin)
        opts_row.addSpacing(20)
        opts_row.addWidget(QtWidgets.QLabel("Temperature:"))
        opts_row.addWidget(self.temp_spin)
        opts_row.addStretch()
        opts_row.addWidget(self.skip_check)
        form.addRow("Options:", self._wrap(opts_row))

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)

        main = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel("Gen-Z Hindi Novel Rewriter (Gemini)")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        subtitle = QtWidgets.QLabel("Input: para1.txt, para2.txt … → Output: polished Hindi (Gen-Z tone, cinematic)")
        subtitle.setStyleSheet("color: #666;")
        main.addWidget(title)
        main.addWidget(subtitle)
        main.addSpacing(8)
        main.addLayout(form)
        main.addSpacing(6)
        main.addLayout(btn_row)
        main.addWidget(self.progress)
        main.addWidget(self.log_view, stretch=1)

        container = QtWidgets.QWidget()
        container.setLayout(main)
        self.setCentralWidget(container)

        # --- Signals ---
        self.start_btn.clicked.connect(self.start_translation)
        self.stop_btn.clicked.connect(self.stop_translation)

        # Worker
        self.worker: Optional[TranslatorWorker] = None

    def _wrap(self, layout: QtWidgets.QLayout) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        w.setLayout(layout)
        return w

    def choose_input(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose Input Folder")
        if d:
            self.input_edit.setText(d)

    def choose_output(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose Output Folder")
        if d:
            self.output_edit.setText(d)

    def append_log(self, msg: str):
        self.log_view.appendPlainText(msg)

    def set_progress(self, val: int):
        self.progress.setValue(val)

    def start_translation(self):
        input_dir = self.input_edit.text().strip()
        output_dir = self.output_edit.text().strip()
        model = self.model_combo.currentText().strip()
        keys_raw = self.keys_edit.text().strip()
        keys = [k.strip() for k in keys_raw.split(",") if k.strip()]
        rpm = self.rpm_spin.value()
        temperature = self.temp_spin.value()
        skip_existing = self.skip_check.isChecked()

        if not input_dir or not os.path.isdir(input_dir):
            QtWidgets.QMessageBox.warning(self, "Missing Input", "Please select a valid input folder.")
            return
        if not output_dir:
            QtWidgets.QMessageBox.warning(self, "Missing Output", "Please select an output folder.")
            return
        if not keys:
            QtWidgets.QMessageBox.warning(self, "Missing API Keys", "Enter at least one Gemini API key.")
            return

        self.log_view.clear()
        self.progress.setValue(0)
        self.append_log("Preparing…")

        self.worker = TranslatorWorker(
            input_dir=input_dir,
            output_dir=output_dir,
            model_name=model,
            api_keys=keys,
            rpm=rpm,
            temperature=temperature,
            skip_existing=skip_existing,
        )
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.set_progress)
        self.worker.done_signal.connect(self.on_done)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.append_log("Started.")
        self.worker.start()

    def stop_translation(self):
        if self.worker and self.worker.isRunning():
            self.worker.request_stop()
            self.append_log("Stop requested…")

    def on_done(self):
        self.append_log("Finished.")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.worker = None


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("GenZ Hindi Translator (Gemini)")
    win = MainWindow()
    win.resize(980, 640)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
