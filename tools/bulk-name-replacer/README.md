# Bulk Name Replacer

Find-and-replace names across a novel's text file using a CSV/XLSX mapping table.

![GUI](https://img.shields.io/badge/GUI-PySide6-41CD52) ![License](https://img.shields.io/badge/license-MIT-green)

## What it does

Load a CSV or XLSX with `name` and `replacement` columns (row 1 = header), pick a `.txt` manuscript, and every occurrence of each name is swapped in one pass. Built for localizing character names at scale.

## Requirements

```
pip install PySide6 pandas openpyxl
```

## Run

```bash
python bulk-name-replacer.py
```

## Part of

This tool lives in the [indie-tools](../../) collection — small, single-file desktop utilities. See the [root README](../../README.md) for the full list.
