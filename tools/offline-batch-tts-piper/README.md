# Offline Batch TTS (Piper)

Scan a local folder of text files and batch-generate speech offline using Piper TTS.

![GUI](https://img.shields.io/badge/GUI-PySide6-41CD52) ![License](https://img.shields.io/badge/license-MIT-green)

## What it does

No cloud API, no per-character cost: this drives a local Piper TTS install to turn a folder of scripts into narration audio in one batch run.

## Requirements

```
pip install PySide6
```

**Also requires (not pip-installable):** piper (local TTS binary + voice model)

## Run

```bash
python offline-batch-tts-piper.py
```

## Part of

This tool lives in the [indie-tools](../../) collection — small, single-file desktop utilities. See the [root README](../../README.md) for the full list.
