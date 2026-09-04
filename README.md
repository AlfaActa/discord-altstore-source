# Discord AltStore Source

<p><a href="https://github.com/AlfaActa/discord-altstore-source/actions/workflows/update-source.yml"><img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FAlfaActa%2Fdiscord-altstore-source%2Fmain%2Fbadge.json&amp;style=flat-square&amp;cacheSeconds=300" alt="Update Source"></a>&nbsp;&nbsp; <a href="source.json"><img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FAlfaActa%2Fdiscord-altstore-source%2Fmain%2Fsource.json&amp;query=%24.apps%5B0%5D.versions.length&amp;label=Discord%20Versions&amp;labelColor=5865F2&amp;color=4F545C&amp;style=flat-square" alt="Discord Versions"></a>&nbsp;&nbsp; <a href="source.json"><img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FAlfaActa%2Fdiscord-altstore-source%2Fmain%2Fsource.json&amp;query=%24.apps%5B0%5D.versions%5B0%5D.version&amp;label=Last%20Version&amp;labelColor=5865F2&amp;color=4F545C&amp;style=flat-square" alt="Last Version"></a>&nbsp;&nbsp; <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-4F545C?style=flat-square&amp;labelColor=5865F2" alt="License: MIT"></a>&nbsp;&nbsp; <a href="https://github.com/AlfaActa/discord-altstore-source/releases"><img src="https://img.shields.io/github/downloads/AlfaActa/discord-altstore-source/total?style=flat-square&amp;logo=github&amp;label=Downloads&amp;labelColor=5865F2&amp;color=4F545C" alt="Downloads"></a>&nbsp;&nbsp; <a href="https://github.com/AlfaActa/discord-altstore-source/releases"><img src="https://img.shields.io/github/release-date/AlfaActa/discord-altstore-source?style=flat-square&amp;label=Last%20Release%20Date&amp;labelColor=5865F2&amp;color=4F545C" alt="Last Release Date"></a></p>

Unofficial AltSource feed for the standard Discord App Store IPA. The updater gets it from [Eevee IPA Decrypter](https://t.me/eeveedecrypterbot) and makes no tweaks or other changes.

Works with KSign, AltStore Classic, SideStore, Scarlet, ESign, Feather, GBox, Sideloadly, and TrollStore. AltStore PAL is not supported.

## Source URL

Add this URL to your signing app:

```text
https://raw.githubusercontent.com/AlfaActa/discord-altstore-source/main/source.json
```

## Automatic updates

Use a dedicated Telegram user account. Create an API ID and API hash at [my.telegram.org](https://my.telegram.org), then install Python 3.11+ and GitHub CLI:

```powershell
python -m pip install -r requirements.txt
```

Sign in with:

```powershell
python updater.py auth
```

The command stores `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION`, and `EEVEE_BOT_ID` through GitHub CLI.

Start the first update:

```powershell
gh workflow run update-source.yml --repo AlfaActa/discord-altstore-source
```

The scheduler checks Friday every 15 minutes, chooses one stable pseudorandom UTC quarter-hour, and dispatches the updater once at or after it. GitHub may delay scheduled runs.

## Run locally

To ask Eevee for the IPA and update the local source:

```powershell
python updater.py update "https://apps.apple.com/us/app/discord-talk-play-hang-out/id985746746"
```

To use an IPA you already downloaded:

```powershell
python updater.py update "https://apps.apple.com/us/app/discord-talk-play-hang-out/id985746746" --ipa "C:\path\to\Discord.ipa"
```

## Trust

The updater checks the bundle ID, metadata, archive safety, SHA-256, entitlements, and privacy keys. Eevee remains a third-party trust boundary. This project is not affiliated with Discord, Apple, or Eevee.
