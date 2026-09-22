# Gemini Hindi Batch Translator

Batch-translate a folder of .txt files into conversational (GenZ-style) Hindi using the Gemini API.

![GUI](https://img.shields.io/badge/GUI-PySide6-41CD52) ![License](https://img.shields.io/badge/license-MIT-green)

## What it does

Point it at an input folder of `para1.txt, para2.txt, ...` files and an output folder. Supports multiple comma-separated Gemini API keys with round-robin failover, a model picker, and a requests-per-minute limiter to stay under quota.

## Requirements

```
pip install PySide6 google-generativeai
```

## Run

```bash
python gemini-hindi-batch-translator.py
```

## Part of

This tool lives in the [indie-tools](../../) collection — small, single-file desktop utilities. See the [root README](../../README.md) for the full list.
