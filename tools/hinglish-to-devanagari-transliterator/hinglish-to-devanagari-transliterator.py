import sys
import re
from typing import List, Dict

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QPlainTextEdit,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt

# ------------------------------------------------------------
# 1. NameMapping "Library" – extend this dictionary as you like
#    Keys must be lowercase Hinglish, values are Hindi (Devanagari)
# ------------------------------------------------------------
NAME_MAP: Dict[str, str] = {
    # Pronouns
    "main": "मैं",
    "mai": "मैं",
    "me": "मैं",  # context dependent, but handy
    "tum": "तुम",
    "tu": "तू",
    "aap": "आप",
    "hum": "हम",
    "ham": "हम",
    "humlog": "हमलोग",
    "humlogon": "हमलोगों",
    "humara": "हमारा",
    "hamara": "हमारा",
    "hamari": "हमारी",
    "hamare": "हमारे",
    "mera": "मेरा",
    "meri": "मेरी",
    "mere": "मेरे",
    "tera": "तेरा",
    "teri": "तेरी",
    "tere": "तेरे",
    "ye": "ये",
    "yaha": "यहाँ",
    "yahan": "यहाँ",
    "waha": "वहाँ",
    "wahan": "वहाँ",
    "vo": "वो",
    "woh": "वो",
    "yeh": "यह",
    "yahi": "यहीं",
    "vahi": "वहीं",
    "koi": "कोई",
    "sab": "सब",
    "kuch": "कुछ",

    # Question words
    "kya": "क्या",
    "kyu": "क्यों",
    "kyun": "क्यों",
    "kaise": "कैसे",
    "kab": "कब",
    "kahan": "कहाँ",
    "kahaan": "कहाँ",
    "kaun": "कौन",

    # Time words
    "aaj": "आज",
    "kal": "कल",
    "parso": "परसों",
    "abhi": "अभी",
    "baad": "बाद",
    "pehle": "पहले",
    "hamesha": "हमेशा",

    # Yes / No / fillers
    "haan": "हाँ",
    "han": "हाँ",
    "ha": "हाँ",
    "nahi": "नहीं",
    "nahiin": "नहीं",
    "nahin": "नहीं",
    "acha": "अच्छा",
    "accha": "अच्छा",
    "achha": "अच्छा",
    "achi": "अच्छी",
    "achhi": "अच्छी",
    "theek": "ठीक",
    "thik": "ठीक",
    "bilkul": "बिलकुल",
    "shayad": "शायद",

    # Common verbs
    "karna": "करना",
    "karta": "करता",
    "kartaa": "करता",
    "kartii": "करती",
    "karti": "करती",
    "karunga": "करूँगा",
    "karungi": "करूँगी",
    "aana": "आना",
    "aata": "आता",
    "aati": "आती",
    "jaana": "जाना",
    "jaata": "जाता",
    "jaati": "जाती",
    "hona": "होना",
    "hu": "हूँ",
    "hun": "हूँ",
    "hoon": "हूँ",
    "hai": "है",
    "hain": "हैं",
    "tha": "था",
    "thi": "थी",
    "the": "थे",
    "rha": "रहा",
    "raha": "रहा",
    "rhi": "रही",
    "rahi": "रही",
    "rhe": "रहे",
    "rahe": "रहे",

    # Emotions / common words
    "khushi": "खुशी",
    "dukhi": "दुखी",
    "dard": "दर्द",
    "pyar": "प्यार",
    "pyaar": "प्यार",
    "mohabbat": "मोहब्बत",
    "zindagi": "ज़िंदगी",
    "jaan": "जान",
    "dost": "दोस्त",
    "dosti": "दोस्ती",

    # Family words
    "maa": "माँ",
    "ma": "माँ",
    "mom": "मॉम",
    "papa": "पापा",
    "pappa": "पप्पा",
    "baba": "बाबा",
    "bhai": "भाई",
    "behen": "बहन",
    "didi": "दीदी",
    "beta": "बेटा",
    "beti": "बेटी",
    "chacha": "चाचा",
    "mama": "मामा",

    # Daily life
    "ghar": "घर",
    "kam": "काम",
    "kaam": "काम",
    "office": "ऑफिस",
    "school": "स्कूल",
    "college": "कॉलेज",
    "market": "मार्केट",
    "bazaar": "बाज़ार",
    "khana": "खाना",
    "pina": "पीना",
    "paani": "पानी",
    "pani": "पानी",
    "roti": "रोटी",
    "sabzi": "सब्ज़ी",
    "chai": "चाय",
    "coffee": "कॉफी",

    # Money
    "paisa": "पैसा",
    "paise": "पैसे",
    "rupya": "रुपया",
    "rupaya": "रुपया",
    "rupaye": "रुपये",

    # Modern life (apps / things)
    "mobile": "मोबाइल",
    "phone": "फोन",
    "video": "वीडियो",
    "audio": "ऑडियो",
    "game": "गेम",
    "laptop": "लैपटॉप",
    "computer": "कम्प्यूटर",
    "website": "वेबसाइट",
    "youtube": "यूट्यूब",
    "yt": "वाइटी",
    "instagram": "इंस्टाग्राम",
    "insta": "इंस्टा",
    "facebook": "फेसबुक",
    "whatsapp": "व्हाट्सऐप",
    "telegram": "टेलीग्राम",

    # Common English loanwords
    "doctor": "डॉक्टर",
    "engineer": "इंजीनियर",
    "teacher": "टीचर",
    "student": "स्टूडेंट",
    "police": "पुलिस",
    "hotel": "होटल",
    "bus": "बस",
    "train": "ट्रेन",
    "car": "कार",
    "truck": "ट्रक",
    "auto": "ऑटो",

    # Some common Indian names (you can extend easily)
    "arjun": "अर्जुन",
    "rohan": "रोहन",
    "akhil": "अखिल",
    "akash": "आकाश",
    "akshay": "अक्षय",
    "rahul": "राहुल",
    "sahil": "साहिल",
    "aanchal": "आंचल",
    "anjali": "अंजली",
    "priya": "प्रिया",
    "rani": "रानी",
    "mujin": "मूजिन",  # from your recap use-case
    # add more character names from your stories here…
}


# ------------------------------------------------------------
# 2. Core transliteration engine (phonetic, fallback for unknown words)
# ------------------------------------------------------------

# Independent vowels (word-start)
INDEPENDENT_VOWELS: Dict[str, str] = {
    "aa": "आ",
    "ai": "ऐ",
    "au": "औ",
    "ee": "ई",
    "ii": "ई",
    "oo": "ऊ",
    "uu": "ऊ",
    "ri": "ऋ",
    "a": "अ",
    "i": "इ",
    "u": "उ",
    "e": "ए",
    "o": "ओ",
}

# Matras (vowel sign after a consonant)
MATRA_MAP: Dict[str, str] = {
    "aa": "ा",
    "ai": "ै",
    "au": "ौ",
    "ee": "ी",
    "ii": "ी",
    "oo": "ू",
    "uu": "ू",
    "ri": "ृ",
    "a": "ा",   # treat 'a' as long-aa to keep spoken feel close to Hinglish
    "i": "ि",
    "u": "ु",
    "e": "े",
    "o": "ो",
}

# Consonant mapping (simple Hindi-style; not splitting dental/retroflex)
CONSONANTS: Dict[str, str] = {
    "ksh": "क्ष",
    "chh": "छ",
    "tch": "च",

    "kh": "ख",
    "gh": "घ",
    "ch": "च",
    "jh": "झ",
    "th": "थ",
    "dh": "ध",
    "ph": "फ",
    "bh": "भ",
    "sh": "श",

    "gn": "ज्ञ",
    "gy": "ज्ञ",
    "tr": "त्र",
    "kr": "क्र",
    "pr": "प्र",
    "gr": "ग्र",

    "k": "क",
    "g": "ग",
    "c": "क",
    "j": "ज",
    "t": "त",
    "d": "द",
    "n": "न",
    "p": "प",
    "b": "ब",
    "m": "म",
    "y": "य",
    "r": "र",
    "l": "ल",
    "v": "व",
    "w": "व",
    "s": "स",
    "h": "ह",
    "f": "फ",
    "z": "ज़",
    "q": "क़",
    "x": "क्स",
}

CONSONANT_KEYS: List[str] = sorted(CONSONANTS.keys(), key=len, reverse=True)
VOWEL_KEYS: List[str] = sorted(INDEPENDENT_VOWELS.keys(), key=len, reverse=True)


def contains_devanagari(text: str) -> bool:
    """Check if text already has Hindi characters."""
    return any('\u0900' <= ch <= '\u097F' for ch in text)


def transliterate_word(word: str) -> str:
    """
    Transliterate a single Hinglish word to Hindi.
    Steps:
      1. Use NAME_MAP if we have exact mapping.
      2. If already Devanagari, return as-is.
      3. Otherwise use phonetic fallback (consonant + vowel matra rules).
    """
    if not word:
        return word

    # If already Hindi, don't touch
    if contains_devanagari(word):
        return word

    lower = word.lower()

    # 1) Direct name mapping (handles pronunciation-sensitive words)
    if lower in NAME_MAP:
        return NAME_MAP[lower]

    # 2) Phonetic transliteration
    result_chars: List[str] = []
    i = 0
    last_was_consonant = False

    while i < len(lower):
        ch = lower[i]

        # If non-alphabetic (number, punctuation), keep original char directly
        if not ch.isalpha():
            result_chars.append(word[i])
            last_was_consonant = False
            i += 1
            continue

        segment = lower[i:]
        handled = False

        # Try consonant clusters first (kh, chh, etc.)
        for key in CONSONANT_KEYS:
            if segment.startswith(key):
                dev = CONSONANTS[key]
                result_chars.append(dev)
                last_was_consonant = True
                i += len(key)
                handled = True
                break

        if handled:
            continue

        # Try vowels
        for key in VOWEL_KEYS:
            if segment.startswith(key):
                if last_was_consonant and result_chars:
                    # Add matra to previous character
                    matra = MATRA_MAP.get(key, "")
                    if matra:
                        result_chars[-1] = result_chars[-1] + matra
                else:
                    # Independent vowel
                    result_chars.append(INDEPENDENT_VOWELS[key])
                last_was_consonant = False
                i += len(key)
                handled = True
                break

        if handled:
            continue

        # Fallback: keep the original character (so unknown letters stay readable)
        result_chars.append(word[i])
        last_was_consonant = False
        i += 1

    return "".join(result_chars)


def transliterate_text(text: str) -> str:
    """
    Transliterate a full text.
    - Splits on A–Z groups.
    - Only pure alphabetic tokens are transliterated.
    - Timestamps (00:00:05), numbers, punctuation stay untouched.
    """
    parts = re.split(r'([A-Za-z]+)', text)
    out_parts: List[str] = []

    for part in parts:
        if not part:
            continue
        if re.fullmatch(r"[A-Za-z]+", part):
            out_parts.append(transliterate_word(part))
        else:
            out_parts.append(part)

    return "".join(out_parts)


# ------------------------------------------------------------
# 3. PySide6 GUI Application
# ------------------------------------------------------------

class TransliteratorApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Hinglish → Hindi Transliterator (NameMapping + Phonetic)")
        self.resize(900, 600)

        self.input_path = ""
        self.output_path = ""

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)

        # --- Input / Output selectors ---
        path_layout_in = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Input .txt file path...")
        btn_in = QPushButton("Select Input .txt")
        btn_in.clicked.connect(self.select_input_file)
        path_layout_in.addWidget(QLabel("Input:"))
        path_layout_in.addWidget(self.input_edit)
        path_layout_in.addWidget(btn_in)

        path_layout_out = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Output .txt file path...")
        btn_out = QPushButton("Select Output .txt")
        btn_out.clicked.connect(self.select_output_file)
        path_layout_out.addWidget(QLabel("Output:"))
        path_layout_out.addWidget(self.output_edit)
        path_layout_out.addWidget(btn_out)

        # --- Convert button ---
        btn_convert = QPushButton("Convert & Save")
        btn_convert.setFixedHeight(40)
        btn_convert.clicked.connect(self.convert_file)

        # --- Preview box ---
        self.preview_box = QPlainTextEdit()
        self.preview_box.setReadOnly(True)
        self.preview_box.setPlaceholderText(
            "After conversion, first few lines of the Hindi output will appear here..."
        )

        # --- Log box ---
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(130)
        self.log_box.setPlaceholderText("Log messages...")

        main_layout.addLayout(path_layout_in)
        main_layout.addLayout(path_layout_out)
        main_layout.addWidget(btn_convert)
        main_layout.addWidget(QLabel("Preview (Hindi output snippet):"))
        main_layout.addWidget(self.preview_box)
        main_layout.addWidget(QLabel("Log:"))
        main_layout.addWidget(self.log_box)

    # ---------- Utility: logging ----------
    def log(self, message: str) -> None:
        self.log_box.appendPlainText(message)
        # Auto-scroll to bottom
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ---------- File dialogs ----------
    def select_input_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Input Text File",
            "",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if path:
            self.input_path = path
            self.input_edit.setText(path)
            self.log(f"Selected input file: {path}")

    def select_output_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Output Text File",
            "",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if path:
            self.output_path = path
            self.output_edit.setText(path)
            self.log(f"Selected output file: {path}")

    # ---------- Main conversion ----------
    def convert_file(self):
        self.input_path = self.input_edit.text().strip()
        self.output_path = self.output_edit.text().strip()

        if not self.input_path:
            QMessageBox.warning(self, "Missing Input", "Please select an input .txt file.")
            return

        if not self.output_path:
            QMessageBox.warning(self, "Missing Output", "Please select an output .txt file.")
            return

        try:
            self.log(f"Reading input file: {self.input_path}")
            with open(self.input_path, "r", encoding="utf-8", errors="ignore") as f_in:
                input_text = f_in.read()
        except Exception as e:
            self.log(f"ERROR reading input: {e}")
            QMessageBox.critical(self, "Error", f"Failed to read input file:\n{e}")
            return

        try:
            self.log("Starting transliteration (Hinglish → Hindi)...")
            output_text = transliterate_text(input_text)
        except Exception as e:
            self.log(f"ERROR during transliteration: {e}")
            QMessageBox.critical(self, "Error", f"Transliteration failed:\n{e}")
            return

        try:
            self.log(f"Writing output file: {self.output_path}")
            with open(self.output_path, "w", encoding="utf-8") as f_out:
                f_out.write(output_text)
        except Exception as e:
            self.log(f"ERROR writing output: {e}")
            QMessageBox.critical(self, "Error", f"Failed to write output file:\n{e}")
            return

        # Show preview (first ~40 lines)
        lines = output_text.splitlines()
        preview_lines = "\n".join(lines[:40])
        self.preview_box.setPlainText(preview_lines)

        self.log("Conversion finished successfully ✔")
        QMessageBox.information(
            self,
            "Done",
            "Transliteration completed successfully!\nOutput saved to:\n" + self.output_path,
        )


# ------------------------------------------------------------
# 4. Entry point
# ------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TransliteratorApp()
    window.show()
    sys.exit(app.exec())
