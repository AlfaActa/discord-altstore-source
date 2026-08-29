#!/usr/bin/env python3
"""Fetch a Discord IPA from Eevee and update an AltSource feed."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import hashlib
import json
import os
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


APP_STORE_ID = "985746746"
BOT_USERNAME = "eeveedecrypterbot"
BUNDLE_ID = "com.hammerandchisel.discord"
DEFAULT_REPOSITORY = "AlfaActa/discord-altstore-source"
MAX_IPA_SIZE = 2 * 1024**3
MAX_PLIST_SIZE = 4 * 1024**2
TELEGRAM_TIMEOUT_SECONDS = 45 * 60


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class IpaMetadata:
    version: str
    build: str
    min_os: str | None
    size: int
    sha256: str
    entitlements: tuple[str, ...]
    privacy: dict[str, str]


def _required_string(info: dict[str, Any], key: str) -> str:
    value = info.get(key)
    if not isinstance(value, str) or not value.strip():
        raise UpdateError(f"IPA Info.plist is missing {key}")
    value = value.strip()
    if any(character in value for character in "\r\n\0"):
        raise UpdateError(f"IPA {key} contains a control character")
    return value


def _safe_zip_name(name: str) -> bool:
    if not name or "\\" in name:
        return False
    path = PurePosixPath(name)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and not (path.parts and path.parts[0].endswith(":"))
    )


def _profile_entitlements(data: bytes) -> set[str]:
    start = data.find(b"<?xml")
    end = data.rfind(b"</plist>")
    if start < 0 or end < start:
        raise UpdateError("Cannot read an embedded provisioning profile")
    try:
        profile = plistlib.loads(data[start : end + len(b"</plist>")])
    except (plistlib.InvalidFileException, ValueError) as exc:
        raise UpdateError("Cannot read an embedded provisioning profile") from exc
    entitlements = profile.get("Entitlements") if isinstance(profile, dict) else None
    if not isinstance(entitlements, dict):
        raise UpdateError("Embedded provisioning profile has no entitlements")
    ignored = {
        "application-identifier",
        "com.app.developer.team-identifier",
        "com.apple.developer.team-identifier",
    }
    return {key for key in entitlements if isinstance(key, str) and key not in ignored}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_ipa(path: Path) -> IpaMetadata:
    if not path.is_file():
        raise UpdateError(f"IPA not found: {path}")

    size = path.stat().st_size
    if size >= MAX_IPA_SIZE:
        raise UpdateError("IPA must be smaller than GitHub's 2 GiB release limit")

    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if not entries or len(names) != len(set(names)):
                raise UpdateError("IPA contains duplicate or missing ZIP entries")
            if any(not _safe_zip_name(entry.filename) for entry in entries):
                raise UpdateError("IPA contains an unsafe ZIP path")
            if any(stat.S_ISLNK(entry.external_attr >> 16) for entry in entries):
                raise UpdateError("IPA contains a symbolic link")

            app_bundles = {
                "/".join(PurePosixPath(entry.filename).parts[:2])
                for entry in entries
                if len(PurePosixPath(entry.filename).parts) >= 2
                and PurePosixPath(entry.filename).parts[0] == "Payload"
                and PurePosixPath(entry.filename).parts[1].endswith(".app")
            }
            if len(app_bundles) != 1:
                raise UpdateError("IPA must contain exactly one direct Payload/*.app bundle")

            plist_entries = [
                entry
                for entry in entries
                if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist", entry.filename)
            ]
            if len(plist_entries) != 1:
                raise UpdateError("IPA must contain exactly one Payload/*.app/Info.plist")
            if plist_entries[0].file_size > MAX_PLIST_SIZE:
                raise UpdateError("IPA Info.plist is unexpectedly large")

            info = plistlib.loads(archive.read(plist_entries[0]))
            app_root = plist_entries[0].filename.rsplit("/", 1)[0] + "/"
            profile_entries = [
                entry
                for entry in entries
                if entry.filename.startswith(app_root) and entry.filename.endswith("embedded.mobileprovision")
            ]
            if not profile_entries:
                raise UpdateError("IPA has no embedded provisioning profile for AltStore permissions")
            entitlements: set[str] = set()
            for entry in profile_entries:
                if entry.file_size > MAX_PLIST_SIZE:
                    raise UpdateError("Embedded provisioning profile is unexpectedly large")
                entitlements.update(_profile_entitlements(archive.read(entry)))
    except (zipfile.BadZipFile, plistlib.InvalidFileException, ValueError) as exc:
        raise UpdateError("IPA is not a valid app archive") from exc

    if not isinstance(info, dict):
        raise UpdateError("IPA Info.plist is invalid")
    if _required_string(info, "CFBundleIdentifier") != BUNDLE_ID:
        raise UpdateError(f"IPA bundle identifier must be {BUNDLE_ID}")

    min_os = info.get("MinimumOSVersion")
    if min_os is not None and not isinstance(min_os, str):
        raise UpdateError("IPA MinimumOSVersion must be a string")

    privacy = {
        key: value
        for key, value in info.items()
        if isinstance(key, str)
        and re.fullmatch(r"NS.+UsageDescription.*", key)
        and isinstance(value, str)
    }
    invalid_privacy = [
        key
        for key in info
        if isinstance(key, str)
        and re.fullmatch(r"NS.+UsageDescription.*", key)
        and not isinstance(info[key], str)
    ]
    if invalid_privacy:
        raise UpdateError("IPA contains a non-string privacy usage description")

    return IpaMetadata(
        version=_required_string(info, "CFBundleShortVersionString"),
        build=_required_string(info, "CFBundleVersion"),
        min_os=min_os,
        size=size,
        sha256=_sha256(path),
        entitlements=tuple(sorted(entitlements)),
        privacy=dict(sorted(privacy.items())),
    )


def validate_app_store_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or host != "apps.apple.com":
        raise UpdateError("App URL must be an https://apps.apple.com URL")
    match = re.search(r"/id(\d+)(?:[/?]|$)", parsed.path + ("?" + parsed.query if parsed.query else ""))
    if not match or match.group(1) != APP_STORE_ID:
        raise UpdateError("App URL must point to Discord's App Store listing")
    return value


def fetch_apple_metadata() -> dict[str, Any]:
    request = urllib.request.Request(
        f"https://itunes.apple.com/lookup?id={APP_STORE_ID}&country=us",
        headers={"User-Agent": "discord-altstore-source/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
        result = payload.get("results", [])[0]
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError, IndexError, KeyError) as exc:
        print(f"warning: could not refresh App Store metadata: {exc}", file=sys.stderr)
        return {}


def _load_source(path: Path) -> dict[str, Any]:
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UpdateError(f"Cannot read source file: {path}") from exc
    if not isinstance(source, dict):
        raise UpdateError("source.json must contain an object")
    apps = source.get("apps")
    if (
        not isinstance(apps, list)
        or len(apps) != 1
        or not isinstance(apps[0], dict)
        or apps[0].get("bundleIdentifier") != BUNDLE_ID
    ):
        raise UpdateError("source.json must contain exactly the Discord app")
    if not isinstance(apps[0].get("versions"), list):
        raise UpdateError("source.json versions must be an array")
    return source


def update_source(
    path: Path,
    metadata: IpaMetadata,
    download_url: str,
    apple: dict[str, Any] | None = None,
) -> bool:
    source = _load_source(path)
    app = source["apps"][0]
    versions = app["versions"]
    apple = apple or {}
    release_date = datetime.now(timezone.utc).date().isoformat()
    if apple.get("version") == metadata.version and isinstance(apple.get("currentVersionReleaseDate"), str):
        release_date = apple["currentVersionReleaseDate"]

    version: dict[str, Any] = {
        "version": metadata.version,
        "buildVersion": metadata.build,
        "date": release_date,
        "localizedDescription": "Decrypted App Store build. This project adds no tweaks.",
        "downloadURL": download_url,
        "size": metadata.size,
        "sha256": metadata.sha256,
    }
    if metadata.min_os:
        version["minOSVersion"] = metadata.min_os
    duplicate = next(
        (
            item
            for item in versions
            if isinstance(item, dict)
            and item.get("version") == metadata.version
            and item.get("buildVersion") == metadata.build
        ),
        None,
    )
    if duplicate is not None and duplicate.get("sha256") not in (None, metadata.sha256):
        raise UpdateError("Published version and build have a different SHA-256 checksum")
    changed = duplicate != version
    if duplicate is None:
        versions.insert(0, version)
    elif changed:
        duplicate.clear()
        duplicate.update(version)
    if duplicate is not None and versions[0] is not duplicate:
        versions.remove(duplicate)
        versions.insert(0, duplicate)
        changed = True

    if isinstance(apple.get("trackName"), str):
        app["name"] = apple["trackName"]
    if isinstance(apple.get("artistName"), str):
        app["developerName"] = apple["artistName"]
    if isinstance(apple.get("artworkUrl512"), str):
        app["iconURL"] = apple["artworkUrl512"]
        source["iconURL"] = apple["artworkUrl512"]

    permissions = {
        "entitlements": list(metadata.entitlements),
        "privacy": metadata.privacy,
    }
    changed = changed or app.get("appPermissions") != permissions
    app["appPermissions"] = permissions

    app.update(
        {
            "version": metadata.version,
            "versionDate": release_date,
            "size": metadata.size,
            "downloadURL": download_url,
        }
    )
    if metadata.min_os:
        app["minOSVersion"] = metadata.min_os

    rendered = json.dumps(source, indent=2, ensure_ascii=False) + "\n"
    changed = changed or path.read_text(encoding="utf-8") != rendered
    if changed:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(path)
    return changed


def is_expected_ipa_message(message: Any, bot_id: int, after_id: int) -> bool:
    file = getattr(message, "file", None)
    name = getattr(file, "name", "") or ""
    return bool(
        getattr(message, "id", 0) > after_id
        and getattr(message, "sender_id", None) == bot_id
        and getattr(message, "chat_id", None) == bot_id
        and not getattr(message, "out", False)
        and getattr(message, "fwd_from", None) is None
        and getattr(message, "document", None) is not None
        and name.casefold().endswith(".ipa")
    )


def _telegram_settings() -> tuple[int, str, str]:
    missing = [
        name
        for name in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION")
        if not os.environ.get(name)
    ]
    if missing:
        raise UpdateError(f"Missing Telegram environment variables: {', '.join(missing)}")
    try:
        api_id = int(os.environ["TELEGRAM_API_ID"])
    except ValueError as exc:
        raise UpdateError("TELEGRAM_API_ID must be an integer") from exc
    return api_id, os.environ["TELEGRAM_API_HASH"], os.environ["TELEGRAM_SESSION"]


def _expected_bot_id() -> int:
    try:
        return int(os.environ["EEVEE_BOT_ID"])
    except KeyError as exc:
        raise UpdateError("Missing EEVEE_BOT_ID repository variable") from exc
    except ValueError as exc:
        raise UpdateError("EEVEE_BOT_ID must be an integer") from exc


async def download_from_eevee(app_url: str, destination: Path) -> Path:
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError as exc:
        raise UpdateError("Install dependencies with: python -m pip install -r requirements.txt") from exc

    api_id, api_hash, session = _telegram_settings()
    client = TelegramClient(StringSession(session), api_id, api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise UpdateError("TELEGRAM_SESSION is no longer authorized")
        bot = await client.get_entity(BOT_USERNAME)
        username = (getattr(bot, "username", "") or "").casefold()
        if not getattr(bot, "bot", False) or username != BOT_USERNAME or bot.id != _expected_bot_id():
            raise UpdateError("Telegram resolved an unexpected Eevee bot identity")

        sent = await client.send_message(bot, app_url)
        deadline = time.monotonic() + TELEGRAM_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            async for message in client.iter_messages(bot, min_id=sent.id, reverse=True):
                if not is_expected_ipa_message(message, bot.id, sent.id):
                    continue
                remote_size = getattr(getattr(message, "file", None), "size", None)
                if remote_size is not None and remote_size >= MAX_IPA_SIZE:
                    raise UpdateError("Eevee returned an IPA at or above GitHub's 2 GiB limit")
                destination.unlink(missing_ok=True)
                remaining = deadline - time.monotonic()
                downloaded = await asyncio.wait_for(
                    client.download_media(message, file=str(destination)),
                    timeout=max(1, remaining),
                )
                if not downloaded:
                    raise UpdateError("Telegram did not download the IPA")
                return Path(downloaded)
            await asyncio.sleep(10)
    finally:
        await client.disconnect()

    raise UpdateError("Eevee did not return a direct IPA document within 45 minutes")


def _set_github_secret(repository: str, name: str, value: str) -> None:
    result = subprocess.run(
        ["gh", "secret", "set", name, "--repo", repository],
        input=value,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise UpdateError(result.stderr.strip() or f"Could not set GitHub secret {name}")


def _set_github_variable(repository: str, name: str, value: str) -> None:
    result = subprocess.run(
        ["gh", "variable", "set", name, "--repo", repository],
        input=value,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise UpdateError(result.stderr.strip() or f"Could not set GitHub variable {name}")


async def authenticate(repository: str) -> None:
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError as exc:
        raise UpdateError("Install dependencies with: python -m pip install -r requirements.txt") from exc

    raw_api_id = os.environ.get("TELEGRAM_API_ID") or input("Telegram API ID: ").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH") or getpass.getpass("Telegram API hash: ").strip()
    try:
        api_id = int(raw_api_id)
    except ValueError as exc:
        raise UpdateError("Telegram API ID must be an integer") from exc
    if not api_hash:
        raise UpdateError("Telegram API hash is required")

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()
    try:
        me = await client.get_me()
        if getattr(me, "bot", False):
            raise UpdateError("Authenticate a dedicated Telegram user account, not a bot account")
        bot = await client.get_entity(BOT_USERNAME)
        username = (getattr(bot, "username", "") or "").casefold()
        if not getattr(bot, "bot", False) or username != BOT_USERNAME:
            raise UpdateError("Telegram resolved an unexpected Eevee bot identity")
        session = client.session.save()
    finally:
        await client.disconnect()

    _set_github_secret(repository, "TELEGRAM_API_ID", str(api_id))
    _set_github_secret(repository, "TELEGRAM_API_HASH", api_hash)
    _set_github_secret(repository, "TELEGRAM_SESSION", session)
    _set_github_variable(repository, "EEVEE_BOT_ID", str(bot.id))
    print(f"Saved Telegram secrets and the Eevee bot ID to {repository}.")


def _github_output(values: dict[str, str]) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as handle:
            for key, value in values.items():
                handle.write(f"{key}={value}\n")
    else:
        print(json.dumps(values, indent=2))


def run_update(args: argparse.Namespace) -> None:
    app_url = validate_app_store_url(args.app_store_url)
    source_path = Path(args.source).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.ipa:
        downloaded = Path(args.ipa).resolve()
    else:
        downloaded = asyncio.run(download_from_eevee(app_url, output_dir / "telegram-download.ipa"))

    metadata = inspect_ipa(downloaded)
    safe_version = re.sub(r"[^A-Za-z0-9._-]", "_", metadata.version)
    safe_build = re.sub(r"[^A-Za-z0-9._-]", "_", metadata.build)
    tag = f"discord-v{safe_version}-b{safe_build}"
    asset_name = f"Discord_{safe_version}_{safe_build}.ipa"
    asset_path = output_dir / asset_name
    repository = os.environ.get("GITHUB_REPOSITORY", args.repository)
    download_url = f"https://github.com/{repository}/releases/download/{tag}/{asset_name}"

    if downloaded != asset_path:
        shutil.copy2(downloaded, asset_path)
    apple = fetch_apple_metadata()
    changed = update_source(source_path, metadata, download_url, apple)
    _github_output(
        {
            "changed": str(changed).lower(),
            "version": metadata.version,
            "build": metadata.build,
            "tag": tag,
            "asset_name": asset_name,
            "asset_path": asset_path.as_posix(),
            "sha256": metadata.sha256,
        }
    )
    status = "Prepared" if changed else "Verified"
    print(f"{status} Discord {metadata.version} ({metadata.build}).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    auth = subparsers.add_parser("auth", help="create a Telegram session and store repository secrets")
    auth.add_argument("--repository", default=DEFAULT_REPOSITORY)

    update = subparsers.add_parser("update", help="download an IPA and update source.json")
    update.add_argument("app_store_url")
    update.add_argument("--ipa", help="use a local IPA instead of Telegram")
    update.add_argument("--source", default="source.json")
    update.add_argument("--output-dir", default="dist")
    update.add_argument("--repository", default=DEFAULT_REPOSITORY)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "auth":
            asyncio.run(authenticate(args.repository))
        else:
            run_update(args)
        return 0
    except (UpdateError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
