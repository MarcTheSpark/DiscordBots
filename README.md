# ClipBot

A little "Snippet Saturday" bot: it grabs a random user-submitted mp3 from a
Nextcloud folder, cuts a random 10-second clip, and posts it to a Discord channel
via webhook. Meant to be run on a schedule (e.g. cron), one post per run.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- **ffmpeg** installed on the host (used by `pydub` to decode/encode mp3s).
  On Debian/Ubuntu: `sudo apt install ffmpeg`.

## Setup

Create a `clipbot.env` file (gitignored) with:

```
NEXTCLOUD_URL=https://your-nextcloud.example.com
NEXTCLOUD_USERNAME=...
NEXTCLOUD_APP_PASSWORD=...
WEBHOOK_URL=https://discord.com/api/webhooks/...
SUBMISSION_URL=https://link-people-use-to-submit-mp3s
```

Then install dependencies:

```bash
uv sync
```

## Running

```bash
uv run ClipBot.py
```

Each run deletes any submissions over 30 MB, then posts one random clip.

## Submitting music

Drop an mp3 (max 30 MB) in the Nextcloud `ClipBotLibrary` folder, named like:

```
Artist_Name~Track_Title.mp3
```

Underscores become spaces, and the `~` separates artist from title. If the name
doesn't follow that pattern, ClipBot falls back to the file's ID3 tags.
