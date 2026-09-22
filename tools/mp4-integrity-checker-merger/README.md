# MP4 Integrity Checker & Merger

Scan a folder of MP4s for corruption/concat-incompatibility, then merge the safe ones without re-encoding.

![GUI](https://img.shields.io/badge/GUI-Tkinter-3776AB) ![License](https://img.shields.io/badge/license-MIT-green)

## What it does

Runs each file through FFmpeg to flag corrupt or codec-mismatched MP4s before merging, so a single bad file doesn't silently break a long concat job.

## Requirements

```
# no pip packages needed — standard library only
```

**Also requires (not pip-installable):** ffmpeg

## Run

```bash
python mp4-integrity-checker-merger.py
```

## Part of

This tool lives in the [indie-tools](../../) collection — small, single-file desktop utilities. See the [root README](../../README.md) for the full list.
