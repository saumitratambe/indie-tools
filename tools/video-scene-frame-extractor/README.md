# Video Scene Frame Extractor

Detect scene changes in a video and export one representative frame per scene.

![GUI](https://img.shields.io/badge/GUI-PySide6-41CD52) ![License](https://img.shields.io/badge/license-MIT-green)

## What it does

Uses OpenCV frame-diffing to find scene cuts, then extracts a frame per scene (plus a CSV log of timestamps) — handy for storyboard previews or thumbnail candidates.

## Requirements

```
pip install PySide6 opencv-python numpy
```

## Run

```bash
python video-scene-frame-extractor.py
```

## Part of

This tool lives in the [indie-tools](../../) collection — small, single-file desktop utilities. See the [root README](../../README.md) for the full list.
