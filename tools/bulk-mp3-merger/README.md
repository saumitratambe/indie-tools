# Bulk MP3 Merger

Batch-merge folders of MP3 files into single tracks via FFmpeg, with a simple desktop UI.

![GUI](https://img.shields.io/badge/GUI-Tkinter-3776AB) ![License](https://img.shields.io/badge/license-MIT-green)

## What it does

Pick a parent folder; each subfolder of MP3s gets merged, in order, into one output file. Uses FFmpeg's concat mode so there's no re-encode quality loss.

## Requirements

```
# no pip packages needed — standard library only
```

**Also requires (not pip-installable):** ffmpeg

## Run

```bash
python bulk-mp3-merger.py
```

## Part of

This tool lives in the [indie-tools](../../) collection — small, single-file desktop utilities. See the [root README](../../README.md) for the full list.
