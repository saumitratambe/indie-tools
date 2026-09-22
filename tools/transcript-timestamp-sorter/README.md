# Transcript Timestamp Sorter

Detect and re-sort/correct `HH:MM:SS` timestamps in a transcript file.

![GUI](https://img.shields.io/badge/GUI-PySide6-41CD52) ![License](https://img.shields.io/badge/license-MIT-green)

## What it does

Fixes out-of-order or malformed timestamp lines in a transcript so it can be fed into editing or captioning tools that expect strictly increasing time-codes.

## Requirements

```
pip install PySide6
```

## Run

```bash
python transcript-timestamp-sorter.py
```

## Part of

This tool lives in the [indie-tools](../../) collection — small, single-file desktop utilities. See the [root README](../../README.md) for the full list.
