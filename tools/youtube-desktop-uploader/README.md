# YouTube Desktop Uploader

Upload a video to YouTube straight from a desktop app via the YouTube Data API (OAuth).

![GUI](https://img.shields.io/badge/GUI-PySide6-41CD52) ![License](https://img.shields.io/badge/license-MIT-green)

## What it does

Handles the OAuth flow (via `client_secret.json`, never committed) and pushes a video + title/description/tags to your channel without opening a browser upload form.

## Requirements

```
pip install PySide6 google-api-python-client google-auth-oauthlib google-auth
```

## Run

```bash
python youtube-desktop-uploader.py
```

## Part of

This tool lives in the [indie-tools](../../) collection — small, single-file desktop utilities. See the [root README](../../README.md) for the full list.
