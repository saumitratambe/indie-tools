import sys, os, pickle
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit,
    QFileDialog, QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

class YouTubeUploader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎬 YouTube Video Uploader")
        self.setGeometry(300, 200, 500, 400)
        self.setStyleSheet("""
            QWidget { background-color: #0d1117; color: white; font-family: 'Segoe UI'; }
            QPushButton { background-color: #238636; border-radius: 6px; padding: 8px; color: white; }
            QPushButton:hover { background-color: #2ea043; }
            QLineEdit, QTextEdit { background-color: #161b22; border: 1px solid #30363d; color: white; padding: 5px; border-radius: 5px; }
        """)

        layout = QVBoxLayout()

        self.api_label = QLabel("Enter Your YouTube API Key (for reference only):")
        self.api_input = QLineEdit()
        layout.addWidget(self.api_label)
        layout.addWidget(self.api_input)

        self.video_label = QLabel("Selected Video:")
        self.video_path = QLineEdit()
        self.video_path.setReadOnly(True)
        layout.addWidget(self.video_label)
        layout.addWidget(self.video_path)

        self.browse_btn = QPushButton("📂 Browse Video")
        self.browse_btn.clicked.connect(self.browse_video)
        layout.addWidget(self.browse_btn)

        self.title_label = QLabel("Video Title:")
        self.title_input = QLineEdit()
        layout.addWidget(self.title_label)
        layout.addWidget(self.title_input)

        self.desc_label = QLabel("Video Description:")
        self.desc_input = QTextEdit()
        layout.addWidget(self.desc_label)
        layout.addWidget(self.desc_input)

        self.upload_btn = QPushButton("🚀 Upload to YouTube")
        self.upload_btn.clicked.connect(self.upload_video)
        layout.addWidget(self.upload_btn)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(QLabel("🧾 Log Output:"))
        layout.addWidget(self.log)

        self.setLayout(layout)

    def browse_video(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Video File", "", "Video Files (*.mp4 *.mov *.avi)")
        if file:
            self.video_path.setText(file)

    def get_authenticated_service(self):
        creds = None
        if os.path.exists("token.pkl"):
            with open("token.pkl", "rb") as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists("client_secret.json"):
                    QMessageBox.warning(self, "Missing File", "⚠️ Please place 'client_secret.json' in this folder.")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
                creds = flow.run_local_server(port=0)
            with open("token.pkl", "wb") as token:
                pickle.dump(creds, token)
        return build("youtube", "v3", credentials=creds)

    def upload_video(self):
        video_file = self.video_path.text()
        title = self.title_input.text().strip()
        description = self.desc_input.toPlainText().strip()

        if not video_file or not os.path.exists(video_file):
            QMessageBox.warning(self, "Error", "Please select a valid video file.")
            return
        if not title:
            QMessageBox.warning(self, "Error", "Please enter a title.")
            return

        youtube = self.get_authenticated_service()
        if youtube is None:
            return

        self.log.append(f"🚀 Uploading: {video_file}\n")
        self.upload_btn.setEnabled(False)

        try:
            request_body = {
                "snippet": {"title": title, "description": description, "categoryId": "22"},
                "status": {"privacyStatus": "public"}
            }

            media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
            request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media)
            response = request.execute()

            self.log.append(f"✅ Upload complete!\nVideo ID: {response['id']}\nhttps://youtu.be/{response['id']}")
            QMessageBox.information(self, "Success", f"✅ Upload complete!\nVideo ID: {response['id']}")
        except Exception as e:
            self.log.append(f"❌ Error: {str(e)}")
        finally:
            self.upload_btn.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = YouTubeUploader()
    w.show()
    sys.exit(app.exec())