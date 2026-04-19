#!/usr/bin/env python3
"""
VPS-Optimized Instagram Media Processor
========================================

A fully automated, resource-safe Instagram media downloader and processor
designed for Ubuntu 20.04 VPS environments with constrained resources
(2 CPU cores, 2 GB RAM, 40 GB SSD).

Features
--------
* Downloads **every** media item (photo, video, reel, IGTV, album) from one
  or more target Instagram users — no files are skipped.
* Resource guards that pause or gracefully exit when RAM ≥ 80 % or disk
  usage ≥ 90 %.
* Email-based Instagram challenge resolution over IMAP-SSL (port 993) and
  SMTP-STARTTLS (port 587) or SMTP-SSL (port 465) — port 25 is **never** used.
* Exponential-backoff retry logic with configurable attempt counts.
* Detailed per-file success / failure logging to a rotating log file.
* Fully configurable via environment variables — zero manual code edits
  required.

Dependencies (pip)
------------------
    instagrapi   (this repository)
    Pillow       (required by instagrapi for image handling)

All other imports are Python 3.8+ stdlib.

Usage
-----
    export IG_USERNAME="your_username"
    export IG_PASSWORD="your_password"
    export IG_TARGET_USERS="user1,user2,user3"
    python3 vps_media_processor.py
"""

from __future__ import annotations

import email as email_lib
import gc
import imaplib
import json
import logging
import os
import re
import shutil
import smtplib
import sys
import time
from email.mime.text import MIMEText
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration — all values are read from environment variables with sane
# defaults.  No manual code editing is required.
# ---------------------------------------------------------------------------

# Instagram credentials
IG_USERNAME: str = os.environ.get("IG_USERNAME", "")
IG_PASSWORD: str = os.environ.get("IG_PASSWORD", "")

# Comma-separated list of target Instagram usernames to download from
IG_TARGET_USERS: str = os.environ.get("IG_TARGET_USERS", "")

# Maximum number of media items to fetch per user (0 = all)
IG_MEDIA_LIMIT: int = int(os.environ.get("IG_MEDIA_LIMIT", "0"))

# Directory for downloaded media
DOWNLOAD_DIR: str = os.environ.get("DOWNLOAD_DIR", "./ig_downloads")

# Session persistence file
SESSION_FILE: str = os.environ.get("SESSION_FILE", "./ig_session.json")

# Logging
LOG_FILE: str = os.environ.get("LOG_FILE", "./vps_media_processor.log")
LOG_MAX_BYTES: int = int(os.environ.get("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10 MB
LOG_BACKUP_COUNT: int = int(os.environ.get("LOG_BACKUP_COUNT", "3"))
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

# Resource thresholds (percent, 0-100)
RAM_THRESHOLD: float = float(os.environ.get("RAM_THRESHOLD", "80"))
DISK_THRESHOLD: float = float(os.environ.get("DISK_THRESHOLD", "90"))
# Seconds to wait when a resource threshold is exceeded before rechecking
RESOURCE_WAIT: int = int(os.environ.get("RESOURCE_WAIT", "30"))
# Maximum consecutive resource-exceeded waits before aborting
RESOURCE_MAX_WAITS: int = int(os.environ.get("RESOURCE_MAX_WAITS", "20"))

# Retry settings
RETRY_ATTEMPTS: int = int(os.environ.get("RETRY_ATTEMPTS", "3"))
RETRY_BASE_DELAY: float = float(os.environ.get("RETRY_BASE_DELAY", "5"))

# Email challenge resolver settings — port 25 is never used.
CHALLENGE_EMAIL: str = os.environ.get("CHALLENGE_EMAIL", "")
CHALLENGE_EMAIL_PASSWORD: str = os.environ.get("CHALLENGE_EMAIL_PASSWORD", "")
CHALLENGE_IMAP_SERVER: str = os.environ.get("CHALLENGE_IMAP_SERVER", "imap.gmail.com")
CHALLENGE_IMAP_PORT: int = int(os.environ.get("CHALLENGE_IMAP_PORT", "993"))
# SMTP for optional email notifications — 587 (STARTTLS) or 465 (SSL)
SMTP_SERVER: str = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT: int = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USE_SSL: bool = os.environ.get("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes")
NOTIFY_EMAIL: str = os.environ.get("NOTIFY_EMAIL", "")

# Delay between processing individual media items (seconds) — helps avoid
# Instagram rate-limiting.
INTER_MEDIA_DELAY: float = float(os.environ.get("INTER_MEDIA_DELAY", "2"))

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def _setup_logging() -> logging.Logger:
    """Configure rotating-file + console logging and return the root logger."""
    logger = logging.getLogger("vps_media_processor")
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Rotating file handler
    fh = RotatingFileHandler(
        LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


log = _setup_logging()

# ---------------------------------------------------------------------------
# Resource monitoring helpers
# ---------------------------------------------------------------------------


def _ram_usage_percent() -> float:
    """Return current RAM usage as a percentage (0-100) using /proc/meminfo."""
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        info: Dict[str, int] = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                info[parts[0].rstrip(":")] = int(parts[1])
        total = info.get("MemTotal", 1)
        available = info.get("MemAvailable", total)
        return (1.0 - available / total) * 100.0
    except Exception:
        # Fallback: assume safe
        return 0.0


def _disk_usage_percent(path: str = "/") -> float:
    """Return disk usage percentage for the filesystem containing *path*."""
    try:
        usage = shutil.disk_usage(path)
        return (usage.used / usage.total) * 100.0
    except Exception:
        return 0.0


def check_resources(logger: logging.Logger) -> bool:
    """Return True when resource usage is within safe limits.

    If thresholds are exceeded the function sleeps in a loop (up to
    ``RESOURCE_MAX_WAITS`` iterations) and then returns False, signalling
    the caller to abort gracefully.
    """
    for attempt in range(RESOURCE_MAX_WAITS):
        ram = _ram_usage_percent()
        disk = _disk_usage_percent(DOWNLOAD_DIR)
        if ram < RAM_THRESHOLD and disk < DISK_THRESHOLD:
            return True
        logger.warning(
            "Resource threshold exceeded (RAM %.1f%% / %.1f%%, Disk %.1f%% / %.1f%%) — "
            "waiting %d s (attempt %d/%d)",
            ram, RAM_THRESHOLD, disk, DISK_THRESHOLD,
            RESOURCE_WAIT, attempt + 1, RESOURCE_MAX_WAITS,
        )
        # Free unused Python memory before waiting
        gc.collect()
        time.sleep(RESOURCE_WAIT)

    logger.error(
        "Resource limits still exceeded after %d waits — aborting gracefully.",
        RESOURCE_MAX_WAITS,
    )
    return False


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------


def retry(attempts: int = RETRY_ATTEMPTS, base_delay: float = RETRY_BASE_DELAY):
    """Decorator implementing exponential-backoff retries."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exc: Optional[Exception] = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt < attempts:
                        delay = base_delay * (2 ** (attempt - 1))
                        log.warning(
                            "Attempt %d/%d for %s failed (%s). Retrying in %.1f s …",
                            attempt, attempts, func.__name__, exc, delay,
                        )
                        time.sleep(delay)
                    else:
                        log.error(
                            "All %d attempts for %s exhausted. Last error: %s",
                            attempts, func.__name__, exc,
                        )
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Email challenge resolver (IMAP on 993 — never port 25)
# ---------------------------------------------------------------------------


def get_code_from_email(username: str) -> Optional[str]:
    """Fetch the latest Instagram verification code via IMAP-SSL.

    Connects to the configured IMAP server on the configured port (default 993).
    Port 25 is **never** used.
    """
    if not CHALLENGE_EMAIL or not CHALLENGE_EMAIL_PASSWORD:
        log.warning("Challenge email credentials not configured — cannot auto-resolve.")
        return None

    try:
        mail = imaplib.IMAP4_SSL(CHALLENGE_IMAP_SERVER, CHALLENGE_IMAP_PORT)
        mail.login(CHALLENGE_EMAIL, CHALLENGE_EMAIL_PASSWORD)
        mail.select("inbox")
        _status, data = mail.search(None, "(UNSEEN)")
        if _status != "OK":
            log.error("IMAP search failed: %s", _status)
            return None

        ids = data[0].split()
        for num in reversed(ids):
            mail.store(num, "+FLAGS", "\\Seen")
            _status, msg_data = mail.fetch(num, "(RFC822)")
            if _status != "OK":
                continue
            raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else msg_data[0]
            msg = email_lib.message_from_bytes(raw)
            payloads = msg.get_payload()
            if not isinstance(payloads, list):
                payloads = [msg]
            for payload in payloads:
                body_bytes = payload.get_payload(decode=True)
                if body_bytes is None:
                    continue
                body = body_bytes.decode(errors="replace")
                if "<div" not in body:
                    continue
                match = re.search(
                    ">([^>]*?({u})[^<]*?)<".format(u=re.escape(username)), body
                )
                if not match:
                    continue
                code_match = re.search(r">(\d{6})<", body)
                if code_match:
                    code = code_match.group(1)
                    log.info("Challenge code retrieved from email: %s", code)
                    mail.logout()
                    return code
        mail.logout()
    except Exception as exc:
        log.error("Failed to retrieve challenge code from email: %s", exc)

    return None


def challenge_code_handler(username: str, choice) -> Optional[str]:
    """Handler passed to ``Client.challenge_code_handler``."""
    # Always attempt email first; SMS requires manual interaction which
    # violates the "fully automated" constraint.
    return get_code_from_email(username)


# ---------------------------------------------------------------------------
# Optional email notification (port 587 STARTTLS or 465 SSL — never 25)
# ---------------------------------------------------------------------------


def send_notification(subject: str, body: str) -> None:
    """Send an email notification.  Uses port 587 (STARTTLS) or 465 (SSL)."""
    if not NOTIFY_EMAIL or not CHALLENGE_EMAIL or not CHALLENGE_EMAIL_PASSWORD:
        return

    if SMTP_PORT == 25:
        log.error("Port 25 is blocked — refusing to send notification on port 25.")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = CHALLENGE_EMAIL
    msg["To"] = NOTIFY_EMAIL

    try:
        if SMTP_USE_SSL or SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30)
        else:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()
        server.login(CHALLENGE_EMAIL, CHALLENGE_EMAIL_PASSWORD)
        server.sendmail(CHALLENGE_EMAIL, [NOTIFY_EMAIL], msg.as_string())
        server.quit()
        log.info("Notification email sent to %s", NOTIFY_EMAIL)
    except Exception as exc:
        log.warning("Could not send notification email: %s", exc)


# ---------------------------------------------------------------------------
# Instagram client helpers
# ---------------------------------------------------------------------------


@retry()
def create_client():
    """Create, configure, and log in the instagrapi Client."""
    from instagrapi import Client

    cl = Client()
    cl.challenge_code_handler = challenge_code_handler

    session_path = Path(SESSION_FILE)
    if session_path.exists():
        log.info("Loading existing session from %s", SESSION_FILE)
        cl.load_settings(SESSION_FILE)
        cl.login(IG_USERNAME, IG_PASSWORD)
    else:
        log.info("No session file found — performing fresh login.")
        cl.login(IG_USERNAME, IG_PASSWORD)

    cl.dump_settings(SESSION_FILE)
    log.info("Logged in as %s — session saved to %s", IG_USERNAME, SESSION_FILE)
    return cl


# ---------------------------------------------------------------------------
# Media download logic
# ---------------------------------------------------------------------------


def _media_type_label(media) -> str:
    """Return a human-readable label for the media type."""
    if media.media_type == 1:
        return "photo"
    if media.media_type == 2:
        product = getattr(media, "product_type", "") or ""
        if product == "clips":
            return "reel"
        if product == "igtv":
            return "igtv"
        return "video"
    if media.media_type == 8:
        return "album"
    return f"unknown({media.media_type})"


@retry()
def download_single_media(cl, media, folder: Path) -> List[Path]:
    """Download a single Media object and return the list of file paths."""
    paths: List[Path] = []
    if media.media_type == 1:
        paths.append(cl.photo_download(media.pk, folder))
    elif media.media_type == 2:
        paths.append(cl.video_download(media.pk, folder))
    elif media.media_type == 8:
        paths.extend(cl.album_download(media.pk, folder))
    else:
        log.warning(
            "Unsupported media type %s for pk=%s — downloading as video fallback.",
            media.media_type, media.pk,
        )
        paths.append(cl.video_download(media.pk, folder))
    return paths


def process_user(
    cl,
    username: str,
    stats: Dict[str, int],
    file_log: List[Dict],
) -> None:
    """Download every media item from *username*, updating *stats* and *file_log*."""
    log.info("=== Processing user: %s ===", username)

    # Resolve user ID
    try:
        user_id = cl.user_id_from_username(username)
    except Exception as exc:
        log.error("Could not resolve user '%s': %s", username, exc)
        stats["users_failed"] += 1
        return

    # Fetch media list
    try:
        medias = cl.user_medias(user_id, amount=IG_MEDIA_LIMIT)
    except Exception as exc:
        log.error("Could not fetch media list for '%s': %s", username, exc)
        stats["users_failed"] += 1
        return

    if not medias:
        log.info("No media found for user '%s'.", username)
        stats["users_ok"] += 1
        return

    log.info("Found %d media items for '%s'.", len(medias), username)
    user_folder = Path(DOWNLOAD_DIR) / username
    user_folder.mkdir(parents=True, exist_ok=True)

    for idx, media in enumerate(medias, start=1):
        media_label = _media_type_label(media)
        media_code = getattr(media, "code", "unknown")
        log_prefix = f"[{username}] ({idx}/{len(medias)}) pk={media.pk} type={media_label}"

        # Resource check before every download
        if not check_resources(log):
            log.error("Aborting due to resource limits while processing '%s'.", username)
            stats["aborted"] = 1
            return

        try:
            paths = download_single_media(cl, media, user_folder)
            for p in paths:
                log.info("%s  =>  SUCCESS  %s", log_prefix, p)
                file_log.append({
                    "user": username,
                    "media_pk": str(media.pk),
                    "media_code": media_code,
                    "type": media_label,
                    "path": str(p),
                    "status": "success",
                })
                stats["files_ok"] += 1
        except Exception as exc:
            log.error("%s  =>  FAILED  %s", log_prefix, exc)
            file_log.append({
                "user": username,
                "media_pk": str(media.pk),
                "media_code": media_code,
                "type": media_label,
                "path": "",
                "status": f"failed: {exc}",
            })
            stats["files_failed"] += 1

        # Rate-limit courtesy delay
        if INTER_MEDIA_DELAY > 0:
            time.sleep(INTER_MEDIA_DELAY)

    stats["users_ok"] += 1


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the complete media processing pipeline.  Returns 0 on success, 1 on error."""
    log.info("=" * 60)
    log.info("VPS Media Processor — starting")
    log.info("=" * 60)

    # --- Validate configuration -------------------------------------------------
    errors: List[str] = []
    if not IG_USERNAME:
        errors.append("IG_USERNAME environment variable is required.")
    if not IG_PASSWORD:
        errors.append("IG_PASSWORD environment variable is required.")
    if not IG_TARGET_USERS:
        errors.append("IG_TARGET_USERS environment variable is required (comma-separated usernames).")
    if errors:
        for e in errors:
            log.error(e)
        return 1

    target_users = [u.strip() for u in IG_TARGET_USERS.split(",") if u.strip()]
    if not target_users:
        log.error("No valid target users found in IG_TARGET_USERS.")
        return 1

    log.info("Target users: %s", ", ".join(target_users))
    log.info("Download directory: %s", DOWNLOAD_DIR)
    log.info("Media limit per user: %s", IG_MEDIA_LIMIT or "unlimited")

    # --- Pre-flight resource check ----------------------------------------------
    if not check_resources(log):
        log.error("Pre-flight resource check failed — exiting.")
        return 1

    # --- Ensure download directory exists ----------------------------------------
    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)

    # --- Login -------------------------------------------------------------------
    try:
        cl = create_client()
    except Exception as exc:
        log.error("Login failed: %s", exc)
        return 1

    # --- Process each target user ------------------------------------------------
    stats: Dict[str, int] = {
        "users_ok": 0,
        "users_failed": 0,
        "files_ok": 0,
        "files_failed": 0,
        "aborted": 0,
    }
    file_log: List[Dict] = []

    for username in target_users:
        if stats.get("aborted"):
            log.warning("Processing aborted due to resource constraints.")
            break
        process_user(cl, username, stats, file_log)

    # --- Write per-file manifest -------------------------------------------------
    manifest_path = Path(DOWNLOAD_DIR) / "processing_manifest.json"
    try:
        with open(manifest_path, "w") as f:
            json.dump(file_log, f, indent=2)
        log.info("File manifest written to %s", manifest_path)
    except Exception as exc:
        log.warning("Could not write manifest: %s", exc)

    # --- Summary -----------------------------------------------------------------
    log.info("=" * 60)
    log.info("Processing complete.")
    log.info(
        "  Users OK: %d | Users failed: %d", stats["users_ok"], stats["users_failed"]
    )
    log.info(
        "  Files OK: %d | Files failed: %d", stats["files_ok"], stats["files_failed"]
    )
    if stats.get("aborted"):
        log.warning("  Processing was ABORTED due to resource constraints.")
    log.info("=" * 60)

    # --- Optional completion notification ----------------------------------------
    send_notification(
        subject="VPS Media Processor — run complete",
        body=(
            f"Users OK: {stats['users_ok']}, Users failed: {stats['users_failed']}\n"
            f"Files OK: {stats['files_ok']}, Files failed: {stats['files_failed']}\n"
            f"Aborted: {'yes' if stats.get('aborted') else 'no'}\n"
        ),
    )

    return 1 if stats["files_failed"] > 0 or stats.get("aborted") else 0


if __name__ == "__main__":
    sys.exit(main())
