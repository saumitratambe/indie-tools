# Lossless Video Splitter

Split a video at chosen timestamps with zero re-encoding, via FFmpeg stream copy.

![GUI](https://img.shields.io/badge/GUI-Tkinter-3776AB) ![License](https://img.shields.io/badge/license-MIT-green)

## What it does

Enter split points (or let it compute even chunks) and it cuts using FFmpeg's `-c copy`, so output quality and encoding are identical to the source — just much faster than a re-encode.

## Requirements

```
# no pip packages needed — standard library only
```

**Also requires (not pip-installable):** ffmpeg

## Run

```bash
python lossless-video-splitter.py
```

## Part of

This tool lives in the [indie-tools](../../) collection — small, single-file desktop utilities. See the [root README](../../README.md) for the full list.
