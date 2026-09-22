import sys
import time
import re
import subprocess
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFileDialog,
    QProgressBar, QLineEdit, QComboBox, QMessageBox
)
from PySide6.QtCore import QThread, Signal, QTimer

# ================= CONFIG =================
MAX_CHUNK_CHARS = 2400
WATCH_INTERVAL_MS = 60000

# ================= WORKER =================
class TTSWorker(QThread):
    log = Signal(str)
    progress = Signal(int)
    finished = Signal()

    def __init__(self, piper_path, output_root, voice_id):
        super().__init__()
        self.piper_path = Path(piper_path)
        self.output_root = Path(output_root)
        self.voice_id = voice_id
        
        self.running = True
        self.processed_files = set()
        
        # Determine model paths based on the selected ID
        # We assume the .onnx and .json are in the SAME folder as piper.exe
        self.piper_dir = self.piper_path.parent
        self.model_file = self.piper_dir / f"{voice_id}.onnx"
        self.config_file = self.piper_dir / f"{voice_id}.onnx.json"

    def stop(self):
        self.running = False

    def validate_voice(self):
        """Checks if the selected voice files exist"""
        if not self.model_file.exists():
            self.log.emit(f"❌ Model not found: {self.model_file.name}")
            return False
        if not self.config_file.exists():
            self.log.emit(f"❌ Config not found: {self.config_file.name}")
            return False
        
        self.log.emit(f"🗣️ Voice loaded: {self.voice_id}")
        return True

    def tts_file(self, script_path: Path):
        audio_dir = self.output_root / "audio"
        audio_dir.mkdir(exist_ok=True)

        name = script_path.stem
        match = re.match(r"(Part)(\d+)", name, re.IGNORECASE)
        if match:
            prefix = match.group(1)
            number = int(match.group(2))
            formatted_name = f"{prefix}{number:02d}"
        else:
            formatted_name = name

        audio_path = audio_dir / f"{formatted_name}.mp3"

        if script_path.stem in self.processed_files:
            return True

        if audio_path.exists():
            self.processed_files.add(script_path.stem)
            return True

        text = script_path.read_text(encoding="utf-8").strip()
        if not text:
            return False

        chunks = [text[i:i+MAX_CHUNK_CHARS] for i in range(0, len(text), MAX_CHUNK_CHARS)]
        temp_wavs = []
        self.log.emit(f"📝 Processing: {script_path.name} ({len(chunks)} chunks)...")

        for i, chunk in enumerate(chunks):
            if not self.running:
                break
            
            temp_out = audio_dir / f"_temp_chunk_{i}.wav"
            temp_wavs.append(temp_out)

            tries = 0
            success = False
            
            while tries < 3 and self.running:
                try:
                    cmd = [
                        str(self.piper_path),
                        "-m", str(self.model_file),
                        "-c", str(self.config_file),
                        "-f", str(temp_out)
                    ]
                    
                    proc = subprocess.run(
                        cmd,
                        input=chunk.encode('utf-8'),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE
                    )
                    
                    if proc.returncode == 0 and temp_out.exists():
                        success = True
                        break
                    else:
                        raise RuntimeError(proc.stderr.decode())
                        
                except Exception as e:
                    self.log.emit(f"⚠️ Chunk {i+1} failed (try {tries+1}): {str(e)}")
                    tries += 1
                    time.sleep(1)

            if not success:
                self.log.emit(f"❌ Chunk {i+1} failed permanently.")
                return False

        # Merge Chunks
        try:
            list_file = audio_dir / "merge_list.txt"
            with open(list_file, 'w') as f:
                for w in temp_wavs:
                    f.write(f"file '{w.name}'\n")
            
            merge_cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c:a", "libmp3lame", "-q:a", "2",
                str(audio_path)
            ]
            
            subprocess.run(merge_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            for w in temp_wavs:
                if w.exists(): w.unlink()
            if list_file.exists(): list_file.unlink()

            if audio_path.exists():
                self.log.emit(f"✅ Saved: {audio_path.name}")
                self.processed_files.add(script_path.stem)
                return True
            else:
                raise RuntimeError("Merge failed")
                
        except Exception as e:
            self.log.emit(f"❌ Merge error: {str(e)}")
            return False

    def scan_and_process(self):
        perfect_dir = self.output_root / "perfect"
        if not perfect_dir.exists():
            return 0

        scripts = sorted(perfect_dir.glob("*.txt"))
        new_scripts = [s for s in scripts if s.stem not in self.processed_files]

        if not new_scripts:
            return 0

        count = 0
        for script in new_scripts:
            if not self.running:
                break
            if self.tts_file(script):
                count += 1
        
        return count

    def run(self):
        self.log.emit("🚀 Initializing Local Piper Engine...")
        
        if not self.piper_path.exists():
            self.log.emit("❌ Piper binary not found!")
            self.finished.emit()
            return

        if not self.validate_voice():
            self.finished.emit()
            return

        self.log.emit("👀 Scanning for new scripts...")
        self.scan_and_process()
        self.finished.emit()

# ================= GUI =================
class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Piper TTS – Local Folder Scanner")
        self.resize(720, 650)
        layout = QVBoxLayout(self)

        # Piper Binary Selection
        self.picker_layout = QHBoxLayout()
        self.piper_input = QLineEdit()
        self.piper_input.setPlaceholderText("Select piper.exe")
        self.picker_btn = QPushButton("Browse Piper")
        self.picker_layout.addWidget(self.piper_input)
        self.picker_layout.addWidget(self.picker_btn)
        layout.addLayout(self.picker_layout)

        # Voice Selection (Dynamic)
        layout.addWidget(QLabel("Available Voices (Detected from Piper Folder):"))
        self.voice_combo = QComboBox()
        self.voice_combo.addItem("-- Select Piper.exe first --", "")
        layout.addWidget(self.voice_combo)
        
        self.refresh_btn = QPushButton("🔄 Refresh Voice List")
        self.refresh_btn.clicked.connect(self.scan_voices)
        layout.addWidget(self.refresh_btn)

        # Folder Selection
        btns = QHBoxLayout()
        self.pick_btn = QPushButton("Select Root Folder")
        self.start_btn = QPushButton("Start Generation")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)

        btns.addWidget(self.pick_btn)
        btns.addWidget(self.start_btn)
        btns.addWidget(self.stop_btn)
        layout.addLayout(btns)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)

        self.log_output = QTextEdit(readOnly=True)
        self.log_output.setFontPointSize(10)
        layout.addWidget(self.log_output)

        self.output_root = None
        self.worker = None
        self.timer = None

        self.picker_btn.clicked.connect(self.browse_piper)
        self.pick_btn.clicked.connect(self.pick_folder)
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)

    def browse_piper(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Piper Binary", "", "Executables (*.exe);;All Files (*)")
        if file_path:
            self.piper_input.setText(file_path)
            self.scan_voices() # Automatically scan when file is picked

    def scan_voices(self):
        piper_exe = self.piper_input.text()
        if not piper_exe:
            return

        piper_dir = Path(piper_exe).parent
        self.log_output.append(f"🔍 Scanning folder: {piper_dir}")
        
        current_selection = self.voice_combo.currentData()
        self.voice_combo.clear()
        
        found_voices = []
        
        # Look for .onnx files in the same folder as piper.exe
        onnx_files = list(piper_dir.glob("*.onnx"))
        
        if not onnx_files:
            self.voice_combo.addItem("❌ No .onnx voices found in this folder", "")
            self.log_output.append("⚠️ Please place your .onnx and .json files in the same folder as piper.exe")
            return

        for file in onnx_files:
            # Expected format: en_US-danny-medium.onnx -> ID: en_US-danny-medium
            voice_id = file.stem 
            # Friendly name cleanup
            friendly_name = voice_id.replace("_", " ").title()
            
            # Check if config exists
            config_file = file.with_suffix(".onnx.json")
            if config_file.exists():
                found_voices.append((friendly_name, voice_id))
            else:
                self.log_output.append(f"⚠️ Skipping {file.name} (Missing .json config)")

        if not found_voices:
            self.voice_combo.addItem("❌ No valid voice pairs (.onnx + .json) found", "")
            return

        for name, vid in sorted(found_voices):
            self.voice_combo.addItem(name, vid)

        self.log_output.emit(f"✅ Found {len(found_voices)} voices.")
        
        # Try to restore previous selection if still valid
        if current_selection:
            index = self.voice_combo.findData(current_selection)
            if index != -1:
                self.voice_combo.setCurrentIndex(index)

    def pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self)
        if folder:
            self.output_root = folder
            (Path(folder) / "perfect").mkdir(exist_ok=True)
            (Path(folder) / "audio").mkdir(exist_ok=True)
            self.log_output.append(f"📁 Working Directory: {folder}")
            self.log_output.append("💡 Place your .txt scripts in the 'perfect' subfolder.")

    def start(self):
        if not self.output_root or not self.piper_input.text():
            QMessageBox.warning(self, "Error", "Please select Folder and Piper Binary first.")
            return

        voice_id = self.voice_combo.currentData()
        if not voice_id:
            QMessageBox.warning(self, "Error", "Please select a valid voice from the list.")
            return

        self.worker = TTSWorker(
            Path(self.piper_input.text()),
            self.output_root,
            voice_id
        )

        self.worker.log.connect(self.log_output.append)
        self.worker.finished.connect(self.start_watch)

        self.worker.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.pick_btn.setEnabled(False)
        self.voice_combo.setEnabled(False)
        self.refresh_btn.setEnabled(False)

    def start_watch(self):
        self.log_output.append("👀 Watching folder for new scripts (every 60s)...")
        self.timer = QTimer()
        self.timer.timeout.connect(self.check)
        self.timer.start(WATCH_INTERVAL_MS)
        
        self.pick_btn.setEnabled(True)
        self.voice_combo.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.start_btn.setEnabled(False) 
        self.stop_btn.setEnabled(True)

    def check(self):
        if self.worker:
            count = self.worker.scan_and_process()
            if count:
                self.log_output.append(f"✅ Processed {count} new file(s)")

    def stop(self):
        if self.worker:
            self.worker.stop()
        if self.timer:
            self.timer.stop()

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pick_btn.setEnabled(True)
        self.voice_combo.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.log_output.append("🛑 Stopped.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = App()
    w.show()
    sys.exit(app.exec())