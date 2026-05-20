import os
import random
import io
import requests
from requests.auth import HTTPBasicAuth
from pydub import AudioSegment
from mutagen.easyid3 import EasyID3
from mutagen import MutagenError
from dotenv import load_dotenv

# ─── Config ─────────────────────────────────────────────────────────────
load_dotenv("clipbot.env")

WEBHOOK_URL = os.environ["WEBHOOK_URL"]
NEXTCLOUD_USER = os.environ["NEXTCLOUD_USERNAME"]
NEXTCLOUD_PASS = os.environ["NEXTCLOUD_APP_PASSWORD"]
SUBMISSION_URL = os.environ["SUBMISSION_URL"]
NEXTCLOUD_URL = os.environ["NEXTCLOUD_URL"]

SUBMISSIONS_REMOTE_PATH = "ClipBotLibrary"
CLIPS_PATH = "clips"
CLIP_LENGTH_MS = 10000
FADE_MS = 1000
MAX_FILE_SIZE_BYTES = 30 * 1024 * 1024  # 30 MB
# ────────────────────────────────────────────────────────────────────────

WEBDAV_BASE = f"{NEXTCLOUD_URL}/remote.php/dav/files/{NEXTCLOUD_USER}"
AUTH = HTTPBasicAuth(NEXTCLOUD_USER, NEXTCLOUD_PASS)


def list_remote_files(path):
    """List files in a Nextcloud folder via WebDAV.
    Returns list of dicts: {'name': ..., 'size': ..., 'is_dir': ...}"""
    import xml.etree.ElementTree as ET
    from urllib.parse import unquote

    url = f"{WEBDAV_BASE}/{path}"
    response = requests.request("PROPFIND", url, auth=AUTH, headers={"Depth": "1"})
    response.raise_for_status()

    ns = {"d": "DAV:"}
    root = ET.fromstring(response.content)

    items = []
    for resp in root.findall("d:response", ns):
        href = resp.find("d:href", ns).text
        name = unquote(href.rstrip("/").split("/")[-1])
        resourcetype = resp.find(".//d:resourcetype", ns)
        is_dir = resourcetype is not None and resourcetype.find("d:collection", ns) is not None

        size_elem = resp.find(".//d:getcontentlength", ns)
        size = int(size_elem.text) if size_elem is not None and size_elem.text else 0

        # Skip the folder itself (it shows up in PROPFIND results)
        if is_dir and name == path.rstrip("/").split("/")[-1]:
            continue

        items.append({"name": name, "size": size, "is_dir": is_dir})
    return items


def delete_remote(remote_path):
    """Delete a file from Nextcloud via WebDAV."""
    url = f"{WEBDAV_BASE}/{remote_path}"
    response = requests.delete(url, auth=AUTH)
    response.raise_for_status()


def download_remote(remote_path):
    """Download a file from Nextcloud, return bytes."""
    url = f"{WEBDAV_BASE}/{remote_path}"
    response = requests.get(url, auth=AUTH)
    response.raise_for_status()
    return response.content


def cleanup_oversize_files():
    """Scan the submissions folder and delete anything over MAX_FILE_SIZE_BYTES."""
    print("Scanning submissions folder for oversize files...")
    items = list_remote_files(SUBMISSIONS_REMOTE_PATH)
    deleted = []
    for item in items:
        if item["is_dir"]:
            continue
        if item["size"] > MAX_FILE_SIZE_BYTES:
            size_mb = item["size"] / 1024 / 1024
            print(f"  Deleting {item['name']} ({size_mb:.1f} MB, over 30 MB limit)")
            try:
                delete_remote(f"{SUBMISSIONS_REMOTE_PATH}/{item['name']}")
                deleted.append(item["name"])
            except Exception as e:
                print(f"    Failed to delete: {e}")
    if deleted:
        print(f"Deleted {len(deleted)} oversize file(s).")
    else:
        print("No oversize files found.")
    return deleted


def parse_filename(filename):
    """'Marc_Evanstein~Adagio_Cantabile.mp3' → ('Marc Evanstein', 'Adagio Cantabile')"""
    name = os.path.splitext(filename)[0]
    if "~" not in name:
        return None, None
    artist, title = name.split("~", 1)
    return artist.replace("_", " ").strip(), title.replace("_", " ").strip()


def get_artist_and_title(mp3_bytes, filename):
    artist, title = parse_filename(filename)
    if artist and title:
        return artist, title

    try:
        tags = EasyID3(io.BytesIO(mp3_bytes))
        artist = tags.get("artist", [None])[0]
        title = tags.get("title", [None])[0]
        if artist and title:
            return artist, title
    except MutagenError:
        pass

    return "Unknown Artist", os.path.splitext(filename)[0].replace("_", " ")


def format_timestamp(ms):
    total_seconds = ms // 1000
    return f"{total_seconds // 60}:{total_seconds % 60:02d}"


def slugify(text):
    return "".join(c if c.isalnum() else "_" for c in text)


def pick_random_clip():
    """Pick a random mp3 from the Nextcloud submissions folder, clip it, return metadata."""
    items = list_remote_files(SUBMISSIONS_REMOTE_PATH)
    mp3_files = [
        item["name"] for item in items
        if not item["is_dir"] and item["name"].lower().endswith(".mp3")
    ]
    if not mp3_files:
        raise RuntimeError("No mp3 files found in submissions folder")

    filename = random.choice(mp3_files)
    print(f"Selected: {filename}")

    mp3_bytes = download_remote(f"{SUBMISSIONS_REMOTE_PATH}/{filename}")
    audio = AudioSegment.from_file(io.BytesIO(mp3_bytes))

    if len(audio) < CLIP_LENGTH_MS:
        print(f"  Too short ({len(audio)}ms), picking another")
        return pick_random_clip()

    artist, title = get_artist_and_title(mp3_bytes, filename)

    start_ms = random.randint(0, len(audio) - CLIP_LENGTH_MS)
    end_ms = start_ms + CLIP_LENGTH_MS
    clip = audio[start_ms:end_ms].fade_in(FADE_MS).fade_out(FADE_MS)

    os.makedirs(CLIPS_PATH, exist_ok=True)
    start_seconds = start_ms // 1000
    end_seconds = end_ms // 1000
    clip_filename = f"{slugify(artist)}_{slugify(title)}_{start_seconds}-{end_seconds}.mp3"
    clip_path = os.path.join(CLIPS_PATH, clip_filename)
    clip.export(clip_path, format="mp3")

    return (
        clip_path,
        title,
        artist,
        format_timestamp(start_ms),
        format_timestamp(end_ms),
    )


def post_snippet():
    clip_path, title, artist, start_str, end_str = pick_random_clip()
    message = (
        f"Happy Snippet Saturday! Today's snippet is {start_str}-{end_str} "
        f"from **{title}** by **{artist}**! What do you notice? Anything that stands out? "
        f"That moves or surprises you? Or did I randomly select a really stupid clip this week?"
        f"Remember, the most important thing in any discussion is to come across as cool and aloof.\n\n"
        f"_Want your music featured? Drop an mp3 (max 30 MB) at {SUBMISSION_URL}, "
        f"named like `Artist_Name~Track_Title.mp3` (underscores for spaces, tilde between artist and title)._"
    )

    with open(clip_path, "rb") as f:
        response = requests.post(
            WEBHOOK_URL,
            data={"content": message},
            files={"file": (os.path.basename(clip_path), f, "audio/mpeg")},
        )

    response.raise_for_status()
    print(f"Posted: {title} by {artist} ({start_str}-{end_str})")


if __name__ == "__main__":
    cleanup_oversize_files()
    post_snippet()