# Video Merger with YouTube Chapters

Merge multiple video files into one and auto-generate a YouTube chapters timestamp list.

![GUI](https://img.shields.io/badge/GUI-Tkinter-3776AB) ![License](https://img.shields.io/badge/license-MIT-green)

## What it does

Merges your clips in order and, since it knows each clip's duration, writes out a ready-to-paste YouTube chapters block (`00:00 Intro`, `02:14 Part 2`, ...) alongside the merged file.

## Requirements

```
# no pip packages needed — standard library only
```

**Also requires (not pip-installable):** ffmpeg

## Run

```bash
python video-merger-youtube-chapters.py
```

## Part of

This tool lives in the [indie-tools](../../) collection — small, single-file desktop utilities. See the [root README](../../README.md) for the full list.
