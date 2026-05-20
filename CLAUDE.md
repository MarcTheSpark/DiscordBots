# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

ClipBot ("Snippet Saturday") is a single-shot script that picks a random user-submitted mp3 from a Nextcloud folder, cuts a random 10-second clip (with a 1s fade in/out), and posts it to a Discord channel via webhook. It is meant to be run on a schedule (e.g. cron), not as a long-running service.

The entrypoint is `ClipBot.py`.

## Commands

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync              # install dependencies into .venv
uv run ClipBot.py    # run the bot (cleans up oversize files, then posts one clip)
```

There are no tests, linter, or build step configured.

## Runtime dependencies

- **System:** `pydub` requires **ffmpeg** to be installed on the host for mp3 decoding/encoding.
- **Config:** secrets are loaded from `clipbot.env` (via `python-dotenv`). Required keys: `NEXTCLOUD_URL`, `NEXTCLOUD_USERNAME`, `NEXTCLOUD_APP_PASSWORD`, `WEBHOOK_URL`, `SUBMISSION_URL`. The script will `KeyError` on startup if any are missing.

## Architecture

`ClipBot.py` runs top-to-bottom in `__main__`: `cleanup_oversize_files()` then `post_snippet()`.

- **Nextcloud access is raw WebDAV over `requests`** (no client library). `list_remote_files` issues a `PROPFIND` and parses the XML response by hand; `download_remote`/`delete_remote` are plain GET/DELETE. All paths are relative to `WEBDAV_BASE` = `{NEXTCLOUD_URL}/remote.php/dav/files/{NEXTCLOUD_USER}`. Submissions live in the `ClipBotLibrary` folder (`SUBMISSIONS_REMOTE_PATH`).
- **Submission naming convention:** users name files `Artist_Name~Track_Title.mp3` — underscores become spaces, `~` separates artist from title (`parse_filename`). If that fails, metadata falls back to ID3 tags (`mutagen`), then to "Unknown Artist".
- **Clipping** happens in memory: the mp3 is downloaded as bytes, loaded with `pydub.AudioSegment`, and a random `CLIP_LENGTH_MS` window is exported to the local `clips/` directory before being posted. Files shorter than the clip length cause `pick_random_clip` to recurse and pick another.
- **Discord posting** is a multipart POST to the webhook URL with the clip attached as a file plus a templated message.

Tunable constants live in the `Config` block at the top of `ClipBot.py` (`CLIP_LENGTH_MS`, `MAX_FILE_SIZE_BYTES`, folder paths).

## Security note

`clipbot.env` currently contains live secrets (Nextcloud app password, Discord webhook) and is **not** listed in `.gitignore`. Do not commit it; add it to `.gitignore` if you touch credential handling.
