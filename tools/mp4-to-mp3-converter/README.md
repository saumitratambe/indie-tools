# MP4 to MP3 Converter

Batch-convert MP4 videos to MP3 audio via FFmpeg, with a Qt desktop UI.

![GUI](https://img.shields.io/badge/GUI-PySide6-41CD52) ![License](https://img.shields.io/badge/license-MIT-green)

## What it does

Drop in a batch of MP4s and get matching MP3s out, using FFmpeg under the hood through a QProcess-driven progress UI.

## Requirements

```
pip install PySide6
```

**Also requires (not pip-installable):** ffmpeg

## Run

```bash
python mp4-to-mp3-converter.py
```

## Part of

This tool lives in the [indie-tools](../../) collection — small, single-file desktop utilities. See the [root README](../../README.md) for the full list.
