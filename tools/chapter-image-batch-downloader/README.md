# Chapter Image Batch Downloader

Scrape and download chapter image sets from a manga/manhwa/comic reader page.

![GUI](https://img.shields.io/badge/GUI-Tkinter-3776AB) ![License](https://img.shields.io/badge/license-MIT-green)

## What it does

Give it a chapter URL, it parses the page with BeautifulSoup, finds every image in reading order (natural-sorted), and downloads them into a per-chapter folder.

## Requirements

```
pip install requests beautifulsoup4 lxml natsort
```

## Run

```bash
python chapter-image-batch-downloader.py
```

## Part of

This tool lives in the [indie-tools](../../) collection — small, single-file desktop utilities. See the [root README](../../README.md) for the full list.
