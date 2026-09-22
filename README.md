<div align="center">

# indie-tools

**A collection of small, single-file desktop utilities for video, audio, text and transcript workflows.**

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
![Tools](https://img.shields.io/badge/tools-19-blue)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

---

## About

Each tool here is a standalone Python script with its own small GUI (Tkinter or PySide6) — built to solve one specific, repetitive task (merge these videos, translate these files, sort these timestamps). None of them depend on each other, so you only need to install what a given tool asks for.

They're grouped in one repository instead of split into 19 tiny repos so they stay easy to browse, search and maintain in one place. Each tool keeps its own `README.md` and `requirements.txt` inside `tools/<name>/`.

## Tools

| Tool | What it does | GUI |
|---|---|---|
| [Batch Image Strip Cropper](tools/batch-image-strip-cropper/) | Preview a folder of images, auto-match a reference credit strip, and bulk delete or crop it out. | tkinter |
| [Bulk MP3 Merger](tools/bulk-mp3-merger/) | Batch-merge folders of MP3 files into single tracks via FFmpeg, with a simple desktop UI. | tkinter |
| [Bulk Name Replacer](tools/bulk-name-replacer/) | Find-and-replace names across a novel's text file using a CSV/XLSX mapping table. | PySide6 |
| [Bulk Video Merger & Overlay](tools/bulk-video-merger-overlay/) | Batch-merge videos and burn in overlays (watermark/logo/text) via FFmpeg. | tkinter |
| [Chapter Image Batch Downloader](tools/chapter-image-batch-downloader/) | Scrape and download chapter image sets from a manga/manhwa/comic reader page. | tkinter |
| [Gemini Hindi Batch Translator](tools/gemini-hindi-batch-translator/) | Batch-translate a folder of .txt files into conversational (GenZ-style) Hindi using the Gemini API. | PySide6 |
| [Gemini Hinglish → Hindi Converter](tools/gemini-hinglish-to-hindi-converter/) | Convert Hinglish (Latin-script Hindi) text into proper Devanagari Hindi via Gemini 1.5 Flash. | PySide6 |
| [Hinglish → Devanagari Transliterator](tools/hinglish-to-devanagari-transliterator/) | Offline, dictionary-based transliteration of Hinglish names into Devanagari — no API calls. | PySide6 |
| [Lossless Video Splitter](tools/lossless-video-splitter/) | Split a video at chosen timestamps with zero re-encoding, via FFmpeg stream copy. | tkinter |
| [MP4 Integrity Checker & Merger](tools/mp4-integrity-checker-merger/) | Scan a folder of MP4s for corruption/concat-incompatibility, then merge the safe ones without re-encoding. | tkinter |
| [MP4 to MP3 Converter](tools/mp4-to-mp3-converter/) | Batch-convert MP4 videos to MP3 audio via FFmpeg, with a Qt desktop UI. | PySide6 |
| [Offline Batch TTS (Piper)](tools/offline-batch-tts-piper/) | Scan a local folder of text files and batch-generate speech offline using Piper TTS. | PySide6 |
| [Timestamped Script Splitter](tools/timestamped-script-splitter/) | Split a long narration/subtitle script into chunks without ever cutting inside a timestamp. | PySide6 |
| [Transcript Timestamp Sorter](tools/transcript-timestamp-sorter/) | Detect and re-sort/correct `HH:MM:SS` timestamps in a transcript file. | PySide6 |
| [Transcript to LosslessCut CSV](tools/transcript-to-losslesscut-csv/) | Convert a timestamped transcript into a LosslessCut-compatible chapter/segment CSV. | tkinter |
| [Video Merger with YouTube Chapters](tools/video-merger-youtube-chapters/) | Merge multiple video files into one and auto-generate a YouTube chapters timestamp list. | tkinter |
| [Video Scene Frame Extractor](tools/video-scene-frame-extractor/) | Detect scene changes in a video and export one representative frame per scene. | PySide6 |
| [YouTube Desktop Uploader](tools/youtube-desktop-uploader/) | Upload a video to YouTube straight from a desktop app via the YouTube Data API (OAuth). | PySide6 |
| [YouTube Transcript Downloader](tools/youtube-transcript-downloader/) | Fetch a YouTube video's transcript and save it in a TTS-friendly text format. | PySide6 |


## Using a tool

```bash
git clone https://github.com/<your-username>/indie-tools.git
cd indie-tools/tools/<tool-name>
pip install -r requirements.txt
python <tool-name>.py
```

Some tools also need an external binary on your PATH (FFmpeg, Piper) or an API key (Gemini, YouTube Data API) — check that tool's own README for specifics.

## License

MIT — see [LICENSE](LICENSE). Free to use, modify and redistribute.
