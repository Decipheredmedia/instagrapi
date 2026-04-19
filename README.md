# instagrapi

[![PyPI](https://img.shields.io/pypi/v/instagrapi)](https://pypi.org/project/instagrapi/)
[![Python](https://img.shields.io/pypi/pyversions/instagrapi)](https://pypi.org/project/instagrapi/)
[![License](https://img.shields.io/pypi/l/instagrapi)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-gh--pages-blue)](https://subzeroid.github.io/instagrapi/)

Fast and effective unofficial Instagram API wrapper for Python.

`instagrapi` combines public web and private mobile API flows, supports session persistence and challenge handling, and covers the main automation primitives for users, media, stories, direct messages, notes, locations, comments, insights, and uploads.

If you want to work with Instagrapi for business interests, prefer [HikerAPI SaaS](https://hikerapi.com/p/bkXQlaVe).
You will not need to spend weeks or even months setting it up.
The service handles millions of daily requests, provides round-the-clock support, and offers partners a special rate.
In many cases, clients first try to save money with self-hosted private API automation, then return to [HikerAPI SaaS](https://hikerapi.com/p/bkXQlaVe) after spending more time and money on accounts, proxies, and challenge handling.
It is difficult to find good accounts, good proxies, resolve challenges reliably, and keep Instagram from banning accounts.

The instagrapi project is better suited for testing and research than for running a production business.

✨ [aiograpi - Asynchronous Python library for Instagram Private API](https://github.com/subzeroid/aiograpi) ✨

Support **Python 3.10+**

`Python 3.9` remains in maintenance support through **December 31, 2026**.
This transition keeps current users stable while aligning the main supported range with modern dependency security and tooling compatibility. In particular, newer `requests` releases now target `Python 3.10+`, which is one of the reasons `Python 3.9` is now maintenance-only.

## Installation

```
pip install instagrapi
```

## Quick Start

``` python
from instagrapi import Client

cl = Client()
cl.login(ACCOUNT_USERNAME, ACCOUNT_PASSWORD)

user_id = cl.user_id_from_username(ACCOUNT_USERNAME)
medias = cl.user_medias(user_id, 20)
```

## Session Persistence

``` python
from instagrapi import Client

cl = Client()
cl.login(USERNAME, PASSWORD)
cl.dump_settings("session.json")

# reload later without entering credentials again
cl = Client()
cl.load_settings("session.json")
cl.login(USERNAME, PASSWORD)
```

If you want more explicit control over the loaded session object:

```python
from instagrapi import Client

cl = Client()
cl.set_settings(cl.load_settings("session.json"))
cl.login(USERNAME, PASSWORD)
```

### Login using a sessionid

``` python
from instagrapi import Client

cl = Client()
cl.login_by_sessionid("<your_sessionid>")
```

`login_by_sessionid()` is best treated as a lightweight compatibility path. For long-lived automation, prefer the normal
`login() -> dump_settings() -> load_settings()/set_settings()` session flow.

## Typical Tasks

### List and download another user's posts

``` python
from instagrapi import Client

cl = Client()
cl.login(USERNAME, PASSWORD)

target_id = cl.user_id_from_username("target_user")
posts = cl.user_medias(target_id, amount=10)
for media in posts:
    # download photos to the current folder
    cl.photo_download(media.pk)
```
See [examples/session_login.py](examples/session_login.py) for a standalone script demonstrating these login methods.

### Search locations by name or exact pk

```python
from instagrapi import Client

cl = Client()
cl.login(USERNAME, PASSWORD)

places = cl.location_search_name("Times Square")
place = places[0]
same_place = cl.location_search_pk(place.pk)

print(same_place.name, same_place.pk)
```

### Work with Notes

```python
from instagrapi import Client

cl = Client()
cl.login(USERNAME, PASSWORD)

notes = cl.get_notes()
print(cl.get_note_text_by_user(notes, "instagram"))

note = cl.create_note("Hello from instagrapi", audience=0)
cl.delete_note(note.id)
```

## Features

* Uses [Web API](https://subzeroid.github.io/instagrapi/usage-guide/fundamentals.html) and [Mobile API](https://subzeroid.github.io/instagrapi/usage-guide/fundamentals.html) flows where available
* Supports login by password, 2FA, and `sessionid`
* Includes email/SMS-based [challenge resolver](https://subzeroid.github.io/instagrapi/usage-guide/challenge_resolver.html) hooks
* Uploads and downloads photos, videos, albums, IGTV, reels, and stories
* Works with users, media, comments, locations, hashtags, collections, notes, direct messages, and insights
* Supports story building with mentions, hashtags, link stickers, and media stickers
* Includes helpers for current location search and notes flows

Anonymous/public web paths are best treated as opportunistic rather than guaranteed. Instagram can change or restrict them independently of the library, so production-grade workflows should prefer authenticated sessions.

## Documentation And Support

* [Documentation index](https://subzeroid.github.io/instagrapi/)
* [Getting Started](https://subzeroid.github.io/instagrapi/getting-started.html)
* [Usage Guide](https://subzeroid.github.io/instagrapi/usage-guide/fundamentals.html)
* [Interactions reference](https://subzeroid.github.io/instagrapi/usage-guide/interactions.html)
* [GitHub Discussions](https://github.com/subzeroid/instagrapi/discussions)
* [Support chat in Telegram](https://t.me/instagrapi)

For other languages, consider [instagrapi-rest](https://github.com/subzeroid/instagrapi-rest). For async Python, see [aiograpi](https://github.com/subzeroid/aiograpi).


<details>
    <summary>Additional example</summary>

```python
from instagrapi import Client
from instagrapi.types import StoryMention, StoryMedia, StoryLink, StoryHashtag

cl = Client()
cl.login(USERNAME, PASSWORD, verification_code="<2FA CODE HERE>")

media_pk = cl.media_pk_from_url('https://www.instagram.com/p/CGgDsi7JQdS/')
media_path = cl.video_download(media_pk)
subzeroid = cl.user_info_by_username('subzeroid')
hashtag = cl.hashtag_info('dhbastards')

cl.video_upload_to_story(
    media_path,
    "Credits @subzeroid",
    mentions=[StoryMention(user=subzeroid, x=0.49892962, y=0.703125, width=0.8333333333333334, height=0.125)],
    links=[StoryLink(webUri='https://github.com/subzeroid/instagrapi')],
    hashtags=[StoryHashtag(hashtag=hashtag, x=0.23, y=0.32, width=0.5, height=0.22)],
    medias=[StoryMedia(media_pk=media_pk, x=0.5, y=0.5, width=0.6, height=0.8)]
)
```
</details>

## Ecosystem And Hosted Options

If you need async Python, use [aiograpi](https://github.com/subzeroid/aiograpi).

If you need hosted infrastructure instead of maintaining accounts, proxies, and challenge handling yourself, consider:

* [HikerAPI](https://hikerapi.com/p/bkXQlaVe) for production-grade hosted Instagram API infrastructure
* [Cloqly](https://cloqly.com/register?ref=58dbf70f) for premium rotating proxies and stable automation traffic
* [DataLikers](https://datalikers.com/p/S9Lv5vBy) for Instagram MCP, Cache API, and datasets
* [LamaTok](https://lamatok.com/p/B9ScEYIQ) for TikTok API access, automation, and data workflows
* [InstaSurfBot](https://t.me/InstaSurfBot) for downloading Instagram media in Telegram
* [OSINTagramBot](https://t.me/OSINTagramBot) for Instagram OSINT in Telegram

### [HikerAPI Affiliate Program](https://hikerapi.com/help/affiliate)

Refer users to HikerAPI and earn a percentage of their API spending:

| Plan | Commission |
|------|------------|
| Start trial plan ($0.02/req) | **50%** |
| Standard ($0.001/req) | **25%** |
| Business ($0.00069/req) | **15%** |
| Ultra ($0.0006/req) | **10%** |

**Extras:** 2-level referral system, no caps, lifetime attribution

**Payouts:** USDT / USDC (TRC-20 or ERC-20), minimum 20 USDT, request anytime from the dashboard

## VPS Media Processor

`vps_media_processor.py` is a fully automated, resource-safe script that downloads every media item (photos, videos, reels, IGTV, albums) from one or more Instagram users. It is optimized for constrained VPS environments (2 CPU / 2 GB RAM / 40 GB SSD) running Ubuntu 20.04.

### Prerequisites

| Requirement | Details |
|---|---|
| **OS** | Ubuntu 20.04 LTS (64-bit) |
| **Python** | 3.9 or later (`python3 --version`) |
| **pip** | `python3 -m ensurepip --upgrade` or `sudo apt install python3-pip` |
| **virtualenv** | `sudo apt install python3-venv` (optional but recommended) |
| **System packages** | `sudo apt update && sudo apt install -y python3-dev build-essential ffmpeg` |

> **Note:** `ffmpeg` is required by `moviepy` (a transitive dependency of instagrapi) for video processing.

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/subzeroid/instagrapi.git
cd instagrapi

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install the library and its dependencies
pip install --upgrade pip
pip install .

# 4. Install Pillow (required by instagrapi for image handling)
pip install Pillow
```

All dependencies are either part of the Python 3.9+ standard library or installable via `pip`:

| Package | Purpose |
|---|---|
| `instagrapi` (this repo) | Instagram Private API wrapper |
| `Pillow` | Image processing (required by instagrapi photo uploads/downloads) |
| `requests` | HTTP client (installed automatically with instagrapi) |
| `pydantic` | Data validation (installed automatically with instagrapi) |
| `moviepy` | Video processing (installed automatically with instagrapi) |
| `pycryptodomex` | Cryptographic routines (installed automatically with instagrapi) |
| `PySocks` | SOCKS proxy support (installed automatically with instagrapi) |

### Configuration

All settings are controlled via **environment variables** — no code changes needed:

| Variable | Required | Default | Description |
|---|---|---|---|
| `IG_USERNAME` | **Yes** | — | Your Instagram username |
| `IG_PASSWORD` | **Yes** | — | Your Instagram password |
| `IG_TARGET_USERS` | **Yes** | — | Comma-separated list of Instagram usernames to download from |
| `IG_MEDIA_LIMIT` | No | `0` (all) | Max media items per user (0 = unlimited) |
| `DOWNLOAD_DIR` | No | `./ig_downloads` | Directory for downloaded files |
| `SESSION_FILE` | No | `./ig_session.json` | Path for session persistence file |
| `LOG_FILE` | No | `./vps_media_processor.log` | Path for the log file |
| `LOG_LEVEL` | No | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_MAX_BYTES` | No | `10485760` (10 MB) | Max log file size before rotation |
| `LOG_BACKUP_COUNT` | No | `3` | Number of rotated log files to keep |
| `RAM_THRESHOLD` | No | `80` | Max RAM usage percentage before pausing/aborting |
| `DISK_THRESHOLD` | No | `90` | Max disk usage percentage before pausing/aborting |
| `RESOURCE_WAIT` | No | `30` | Seconds to wait when a resource threshold is exceeded |
| `RESOURCE_MAX_WAITS` | No | `20` | Max consecutive waits before aborting |
| `RETRY_ATTEMPTS` | No | `3` | Number of retry attempts per download |
| `RETRY_BASE_DELAY` | No | `5` | Base delay (seconds) for exponential backoff |
| `INTER_MEDIA_DELAY` | No | `2` | Delay between downloads (seconds) to avoid rate limits |
| `CHALLENGE_EMAIL` | No | — | Email address for Instagram challenge resolution |
| `CHALLENGE_EMAIL_PASSWORD` | No | — | Password for the challenge email account |
| `CHALLENGE_IMAP_SERVER` | No | `imap.gmail.com` | IMAP server for reading challenge emails |
| `CHALLENGE_IMAP_PORT` | No | `993` | IMAP SSL port |
| `SMTP_SERVER` | No | `smtp.gmail.com` | SMTP server for email notifications |
| `SMTP_PORT` | No | `587` | SMTP port (587 for STARTTLS, 465 for SSL — **never 25**) |
| `SMTP_USE_SSL` | No | `false` | Use SMTP-SSL instead of STARTTLS (`true` for port 465) |
| `NOTIFY_EMAIL` | No | — | Email address to receive completion notifications |

### Usage

```bash
# Activate the virtual environment
source .venv/bin/activate

# Set required environment variables
export IG_USERNAME="your_instagram_username"
export IG_PASSWORD="your_instagram_password"
export IG_TARGET_USERS="natgeo,nasa"

# Run the script
python3 vps_media_processor.py

# Optional: limit to 10 media items per user
export IG_MEDIA_LIMIT=10
python3 vps_media_processor.py

# Optional: use a custom download directory
export DOWNLOAD_DIR="/mnt/data/ig_downloads"
python3 vps_media_processor.py
```

#### Running with challenge resolution

If your Instagram account triggers a verification challenge, configure the email resolver:

```bash
export CHALLENGE_EMAIL="myemail@gmail.com"
export CHALLENGE_EMAIL_PASSWORD="app_password_here"
export CHALLENGE_IMAP_SERVER="imap.gmail.com"
export CHALLENGE_IMAP_PORT=993
python3 vps_media_processor.py
```

> For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833) rather than your main password.

#### Running with completion notifications

```bash
export NOTIFY_EMAIL="alerts@example.com"
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT=587
python3 vps_media_processor.py
```

### Output

* **Downloaded files** are saved to `DOWNLOAD_DIR/<username>/` with one sub-folder per target user.
* **`processing_manifest.json`** is written to `DOWNLOAD_DIR/` after each run. It contains a JSON array with per-file entries:

```json
[
  {
    "user": "natgeo",
    "media_pk": "3012345678901234567",
    "media_code": "CxYz123",
    "type": "photo",
    "path": "/home/user/ig_downloads/natgeo/natgeo_3012345678901234567.jpg",
    "status": "success"
  }
]
```

* **Log file** at `LOG_FILE` contains timestamped entries for every operation.

### Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `IG_USERNAME environment variable is required` | Missing credentials | Export `IG_USERNAME`, `IG_PASSWORD`, and `IG_TARGET_USERS` before running the script. |
| `Login failed` / `ChallengeRequired` | Instagram requires verification | Configure `CHALLENGE_EMAIL` and `CHALLENGE_EMAIL_PASSWORD` for automatic email challenge resolution. |
| `Resource threshold exceeded — waiting` | RAM ≥ 80 % or disk ≥ 90 % | Free disk space, close other applications, or increase `RAM_THRESHOLD` / `DISK_THRESHOLD`. |
| `Processing was ABORTED due to resource constraints` | Thresholds exceeded for too long | Free resources and re-run. The script resumes from where it left off thanks to `overwrite=True` default. |
| `ConnectionError` / `Timeout` | Network issue | The script automatically retries up to `RETRY_ATTEMPTS` times with exponential backoff. Check your internet connection. |
| `Port 25 is blocked` | VPS blocks outbound port 25 | The script **never** uses port 25. Use `SMTP_PORT=587` (STARTTLS) or `SMTP_PORT=465` (SSL). |
| `ModuleNotFoundError: No module named 'instagrapi'` | Library not installed | Run `pip install .` from the repository root inside your virtual environment. |
| `ModuleNotFoundError: No module named 'PIL'` | Pillow not installed | Run `pip install Pillow`. |
| `ffmpeg not found` | System dependency missing | Run `sudo apt install ffmpeg`. |
| Rate-limiting / temporary bans | Too many requests | Increase `INTER_MEDIA_DELAY` (e.g., `5` or `10` seconds). Use a proxy with instagrapi's proxy settings. |
| Partial downloads after abort | Script was interrupted | Re-run the script — it picks up where it left off. Review `processing_manifest.json` for the list of completed files. |

## Contributing

[![List of contributors](https://opencollective.com/instagrapi/contributors.svg?width=890&button=0)](https://github.com/subzeroid/instagrapi/graphs/contributors)

To release, you need to call the following commands:

    python -m build
    twine upload dist/*
