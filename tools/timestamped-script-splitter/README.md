# Timestamped Script Splitter

Split a long narration/subtitle script into chunks without ever cutting inside a timestamp.

![GUI](https://img.shields.io/badge/GUI-PySide6-41CD52) ![License](https://img.shields.io/badge/license-MIT-green)

## What it does

Detects timestamp lines and only splits between them, so downstream tools (TTS, subtitle sync) never receive a broken time-code.

## Requirements

```
pip install PySide6
```

## Run

```bash
python timestamped-script-splitter.py
```

## Part of

This tool lives in the [indie-tools](../../) collection — small, single-file desktop utilities. See the [root README](../../README.md) for the full list.
