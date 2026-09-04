# Discord AltStore Source

<p><a href="https://github.com/AlfaActa/discord-altstore-source/actions/workflows/update-source.yml"><img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FAlfaActa%2Fdiscord-altstore-source%2Fmain%2Fbadge.json&amp;style=flat-square&amp;cacheSeconds=300" alt="Update Source"></a>&nbsp;&nbsp; <a href="source.json"><img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FAlfaActa%2Fdiscord-altstore-source%2Fmain%2Fsource.json&amp;query=%24.apps%5B0%5D.versions.length&amp;label=Discord%20Versions&amp;labelColor=5865F2&amp;color=4F545C&amp;style=flat-square" alt="Discord Versions"></a>&nbsp;&nbsp; <a href="source.json"><img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FAlfaActa%2Fdiscord-altstore-source%2Fmain%2Fsource.json&amp;query=%24.apps%5B0%5D.versions%5B0%5D.version&amp;label=Last%20Version&amp;labelColor=5865F2&amp;color=4F545C&amp;style=flat-square" alt="Last Version"></a>&nbsp;&nbsp; <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-4F545C?style=flat-square&amp;labelColor=5865F2" alt="License: MIT"></a>&nbsp;&nbsp; <a href="https://github.com/AlfaActa/discord-altstore-source/releases"><img src="https://img.shields.io/github/downloads/AlfaActa/discord-altstore-source/total?style=flat-square&amp;logo=github&amp;label=Downloads&amp;labelColor=5865F2&amp;color=4F545C" alt="Downloads"></a>&nbsp;&nbsp; <a href="https://github.com/AlfaActa/discord-altstore-source/releases"><img src="https://img.shields.io/github/release-date/AlfaActa/discord-altstore-source?style=flat-square&amp;label=Last%20Release%20Date&amp;labelColor=5865F2&amp;color=4F545C" alt="Last Release Date"></a></p>

This repository publishes an unofficial AltSource feed for the standard Discord App Store build. The updater asks [Eevee IPA Decrypter](https://t.me/eeveedecrypterbot) for the latest decrypted IPA and does not inject tweaks or make other changes.

The source works with KSign and AltStore Classic. It does not work with AltStore PAL, which requires Apple-notarized alternative distribution packages.

The feed uses the standard AltSource format. It may also be useful to people searching for Discord with SideStore, Scarlet, ESign, Feather, GBox, Sideloadly, or TrollStore, although those apps are not tested here.

## Source URL

Add this URL to KSign or AltStore Classic:

```text
https://raw.githubusercontent.com/AlfaActa/discord-altstore-source/main/source.json
```

The feed is populated automatically after the first successful update publishes an IPA release.

## Set up automatic updates

Use a dedicated Telegram account. A Telegram session grants full access to that account, even when it is stored as an encrypted GitHub secret.

1. Create an API ID and API hash at [my.telegram.org](https://my.telegram.org).
2. Install Python 3.11 or newer and GitHub CLI.
3. Install the Python dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Sign in to the dedicated Telegram account and store its repository secrets:

   ```powershell
   python updater.py auth
   ```

   The command asks for the API ID, API hash, phone number, login code, and optional two-step verification password. It sends `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and `TELEGRAM_SESSION` directly to GitHub without printing their values. It also records Eevee's numeric bot ID as `EEVEE_BOT_ID` so the workflow does not rely on the username alone.

5. Start the first update:

   ```powershell
   gh workflow run update-source.yml --repo AlfaActa/discord-altstore-source
   ```

The lightweight scheduler checks every 15 minutes on Friday, chooses one pseudorandom UTC 15-minute slot for that ISO week, and dispatches the actual updater at that slot or the first later Friday check if GitHub delays a scheduled run. A daily guard allows only one updater dispatch. The updater itself runs once. Manual dispatch runs immediately. GitHub may delay scheduled jobs. It also disables scheduled workflows in public repositories after 60 days without repository activity, so re-enable the workflow if Discord goes that long without a published update.

## Run locally

To ask Eevee for the IPA and update the local source:

```powershell
python updater.py update "https://apps.apple.com/us/app/discord-talk-play-hang-out/id985746746"
```

To use an IPA you already downloaded:

```powershell
python updater.py update "https://apps.apple.com/us/app/discord-talk-play-hang-out/id985746746" --ipa "C:\path\to\Discord.ipa"
```

## Trust and legal notice

The updater verifies the bundle identifier, version, build number, archive paths, size, and SHA-256 checksum. It reads entitlements from an embedded provisioning profile when one exists, and from the Mach-O code signatures of the app and its extensions when possible. It cannot prove that Eevee's output is identical to Apple's encrypted package. Review the upstream service before installing its files.

This project is not affiliated with Discord Inc., Apple Inc., or Eevee IPA Decrypter. Discord and its assets belong to their respective owners.
