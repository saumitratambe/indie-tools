import re
import sys
from pathlib import Path

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

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
    QMessageBox,
    QComboBox,
    QCheckBox,
)
from PySide6.QtCore import Qt


# ---------- Helper: Extract video ID from URL or ID ----------

def extract_video_id(text: str):
    """
    Accepts:
      - Full URL: https://www.youtube.com/watch?v=VIDEO_ID
      - Short URL: https://youtu.be/VIDEO_ID
      - Just the VIDEO_ID itself
    Returns video_id or None if not found.
    """
    text = text.strip()

    # If it's a plain 11-char YouTube-like ID
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", text):
        return text

    # Look for v=VIDEO_ID in URL
    match = re.search(r"[?&]v=([0-9A-Za-z_-]{11})", text)
    if match:
        return match.group(1)

    # youtu.be short link
    match = re.search(r"youtu\.be/([0-9A-Za-z_-]{11})", text)
    if match:
        return match.group(1)

    return None


# ---------- Time formatting ----------

def format_timestamp(seconds: float) -> str:
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"


# ---------- Basic (chunk-based) transcript formatting ----------

def format_transcript_raw(chunks, include_timestamps: bool) -> str:
    lines = []
    for item in chunks:
        text = item.get("text", "").replace("\n", " ").strip()
        if not text:
            continue
        if include_timestamps:
            ts = format_timestamp(item.get("start", 0.0))
            lines.append(f"[{ts}] {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


# ---------- TTS-friendly sentence splitting & grouping ----------

def split_sentences_with_times(chunks):
    """
    Turn transcript chunks into a list of (sentence_text, start_time_seconds).
    start_time_seconds = start of the first chunk that contributes to the sentence.

    We:
      - Merge text across chunks
      - Use . ? ! as sentence terminators
      - Keep start time from the first contributing chunk for each sentence
    """
    sentences = []

    current_sentence = ""
    current_start = None

    # Regex to detect sentence-ending punctuation
    # We will treat ".", "?", "!" as ends
    for chunk in chunks:
        raw_text = chunk.get("text", "").replace("\n", " ")
        raw_text = re.sub(r"\s+", " ", raw_text).strip()

        if not raw_text:
            continue

        chunk_start = float(chunk.get("start", 0.0))

        i = 0
        while i < len(raw_text):
            ch = raw_text[i]

            # If starting a new sentence, record its start time
            if current_sentence == "" and not ch.isspace() and current_start is None:
                current_start = chunk_start

            current_sentence += ch

            # Check if this is a sentence terminator
            if ch in ".?!":
                # Look ahead: if next char is space or end-of-text, treat as end of sentence
                next_char = raw_text[i + 1] if i + 1 < len(raw_text) else ""
                if next_char in [" ", "", '"', "'"]:
                    # Sentence complete
                    sent = current_sentence.strip()
                    if sent:
                        # Ensure it ends with proper punctuation
                        if sent[-1] not in ".?!":
                            sent += "."
                        sentences.append((sent, current_start if current_start is not None else chunk_start))
                    current_sentence = ""
                    current_start = None
            i += 1

        # End of this chunk, but sentence may continue in next chunk
        # Do nothing special here; we keep current_sentence and current_start

    # If any leftover sentence without terminator, force-finish it
    leftover = current_sentence.strip()
    if leftover:
        if leftover[-1] not in ".?!":
            leftover += "."
        # Fallback start time if None
        if current_start is None:
            current_start = chunks[0].get("start", 0.0) if chunks else 0.0
        sentences.append((leftover, float(current_start)))

    return sentences


def format_transcript_tts_blocks(chunks, include_timestamps: bool) -> str:
    """
    Build TTS-friendly transcript:
      - Split into sentences
      - Group in blocks of 2 sentences
      - Prepend each block with a single timestamp (start time of first sentence)
      - Always end sentences with full stop / ? / !
    """
    if not chunks:
        return ""

    sentences = split_sentences_with_times(chunks)
    if not sentences:
        return ""

    blocks = []
    i = 0
    while i < len(sentences):
        group = sentences[i:i + 2]
        # Join the sentences with a space
        text_block = " ".join(s[0].strip() for s in group)
        # Make sure we don't accidentally break punctuation
        text_block = re.sub(r"\s+", " ", text_block).strip()

        start_time = group[0][1]  # start of first sentence in the group
        if include_timestamps:
            ts = format_timestamp(start_time)
            block_str = f"{ts}\n{text_block}"
        else:
            block_str = text_block

        blocks.append(block_str)
        i += 2

    # Separate blocks by a blank line to match your style
    return "\n\n".join(blocks)


# ---------- Main GUI Class ----------

class YouTubeTranscriptTool(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube → Transcript (TTS Friendly)")
        self.setMinimumSize(900, 550)
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        # Title label
        title_label = QLabel("YouTube to Transcript Tool (TTS Ready)")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(
            "font-size: 20px; font-weight: bold; padding: 8px;"
        )
        main_layout.addWidget(title_label)

        # URL row
        url_layout = QHBoxLayout()
        url_label = QLabel("YouTube URL / Video ID:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube link here...")
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        main_layout.addLayout(url_layout)

        # Options row 1: Language + timestamps + TTS friendly
        options_layout = QHBoxLayout()

        lang_label = QLabel("Language:")
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Auto (best available)", "auto")
        self.lang_combo.addItem("English (en)", "en")
        self.lang_combo.addItem("Hindi (hi)", "hi")

        self.timestamps_checkbox = QCheckBox("Include timestamps")
        self.timestamps_checkbox.setChecked(True)

        self.tts_friendly_checkbox = QCheckBox("TTS-friendly blocks (2 sentences)")
        self.tts_friendly_checkbox.setChecked(True)

        options_layout.addWidget(lang_label)
        options_layout.addWidget(self.lang_combo)
        options_layout.addWidget(self.timestamps_checkbox)
        options_layout.addWidget(self.tts_friendly_checkbox)
        options_layout.addStretch()

        main_layout.addLayout(options_layout)

        # Buttons row
        btn_layout = QHBoxLayout()
        self.fetch_button = QPushButton("Fetch Transcript")
        self.fetch_button.clicked.connect(self.fetch_transcript)

        self.save_button = QPushButton("Save as .txt")
        self.save_button.clicked.connect(self.save_transcript)
        self.save_button.setEnabled(False)

        btn_layout.addStretch()
        btn_layout.addWidget(self.fetch_button)
        btn_layout.addWidget(self.save_button)
        main_layout.addLayout(btn_layout)

        # Transcript box
        self.transcript_box = QTextEdit()
        self.transcript_box.setPlaceholderText("Transcript will appear here...")
        self.transcript_box.setLineWrapMode(QTextEdit.WidgetWidth)
        main_layout.addWidget(self.transcript_box)

        # Small footer
        footer = QLabel("(PySide6 + youtube-transcript-api)")
        footer.setAlignment(Qt.AlignRight)
        footer.setStyleSheet("font-size: 10px; color: gray;")
        main_layout.addWidget(footer)

        self.setLayout(main_layout)

    # ---------- Actions ----------

    def fetch_transcript(self):
        url_text = self.url_input.text().strip()
        if not url_text:
            QMessageBox.warning(self, "Input missing", "Please paste a YouTube URL or video ID.")
            return

        video_id = extract_video_id(url_text)
        if not video_id:
            QMessageBox.warning(self, "Invalid link", "Could not extract a valid video ID from the input.")
            return

        lang_choice = self.lang_combo.currentData()  # 'auto' or language code
        include_ts = self.timestamps_checkbox.isChecked()
        tts_mode = self.tts_friendly_checkbox.isChecked()

        self.fetch_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.transcript_box.clear()
        self.transcript_box.setPlainText("Fetching transcript… Please wait.")

        try:
            if lang_choice == "auto":
                chunks = YouTubeTranscriptApi.get_transcript(video_id)
            else:
                chunks = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang_choice])

            if tts_mode:
                text = format_transcript_tts_blocks(chunks, include_ts)
            else:
                text = format_transcript_raw(chunks, include_ts)

            if not text.strip():
                self.transcript_box.setPlainText("Transcript is empty or not available.")
                self.save_button.setEnabled(False)
            else:
                self.transcript_box.setPlainText(text)
                self.save_button.setEnabled(True)

        except TranscriptsDisabled:
            self.transcript_box.clear()
            QMessageBox.critical(
                self,
                "Transcripts disabled",
                "This video has transcripts disabled by the uploader."
            )
        except NoTranscriptFound:
            self.transcript_box.clear()
            QMessageBox.critical(
                self,
                "No transcript found",
                "No transcript is available for this video in the selected language."
            )
        except VideoUnavailable:
            self.transcript_box.clear()
            QMessageBox.critical(
                self,
                "Video unavailable",
                "The video is unavailable or the ID is invalid."
            )
        except Exception as e:
            self.transcript_box.clear()
            QMessageBox.critical(
                self,
                "Error",
                f"An unexpected error occurred:\n{e}"
            )
        finally:
            self.fetch_button.setEnabled(True)

    def save_transcript(self):
        text = self.transcript_box.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Nothing to save", "Transcript box is empty.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save transcript",
            "transcript.txt",
            "Text Files (*.txt);;All Files (*)",
        )
        if not file_path:
            return

        try:
            Path(file_path).write_text(text, encoding="utf-8")
            QMessageBox.information(self, "Saved", f"Transcript saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save error", f"Could not save file:\n{e}")


# ---------- Main entry ----------

def main():
    app = QApplication(sys.argv)
    window = YouTubeTranscriptTool()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
