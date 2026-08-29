# Discord AltStore source

[![Update source](https://img.shields.io/github/actions/workflow/status/AlfaActa/discord-altstore-source/update-source.yml?style=flat-square&label=update%20source&color=5865F2)](https://github.com/AlfaActa/discord-altstore-source/actions/workflows/update-source.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-5865F2?style=flat-square)](LICENSE) [![Discord versions](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FAlfaActa%2Fdiscord-altstore-source%2Fmain%2Fsource.json&query=%24.apps%5B0%5D.versions.length&label=Discord%20versions&color=5865F2&style=flat-square)](source.json) [![Downloads](https://img.shields.io/github/downloads/AlfaActa/discord-altstore-source/total?style=flat-square&logo=github&color=5865F2)](https://github.com/AlfaActa/discord-altstore-source/releases)

[![Last version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FAlfaActa%2Fdiscord-altstore-source%2Fmain%2Fsource.json&query=%24.apps%5B0%5D.versions%5B0%5D.version&label=last%20version&color=5865F2&style=flat-square)](source.json) [![Last release](https://img.shields.io/github/release-date/AlfaActa/discord-altstore-source?style=flat-square&label=last%20release&color=5865F2)](https://github.com/AlfaActa/discord-altstore-source/releases) [![Stars](https://img.shields.io/github/stars/AlfaActa/discord-altstore-source?style=flat-square&color=5865F2)](https://github.com/AlfaActa/discord-altstore-source/stargazers)

This repository publishes an unofficial AltSource feed for the standard Discord App Store build. The updater asks [Eevee IPA Decrypter](https://t.me/eeveedecrypterbot) for the latest decrypted IPA and does not inject tweaks or make other changes.

The source works with KSign and AltStore Classic. It does not work with AltStore PAL, which requires Apple-notarized alternative distribution packages.

The feed uses the standard AltSource format. It may also be useful to people searching for Discord with SideStore, Scarlet, ESign, Feather, GBox, Sideloadly, or TrollStore, although those apps are not tested here.

The current Discord IPA is a universal build for iPhone and iPad, so the same source works on iOS and iPadOS. The feed keeps separate App Store screenshot sets for both device families. Installation still depends on the signing app and the minimum OS version listed in each release.

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

The lightweight scheduler checks every 15 minutes from Wednesday through Friday, chooses one pseudorandom day and UTC 15-minute slot for that ISO week, and dispatches the actual updater only at that slot. The updater itself runs once, not on all three days. Manual dispatch runs immediately. GitHub may delay scheduled jobs. It also disables scheduled workflows in public repositories after 60 days without repository activity, so re-enable the workflow if Discord goes that long without a published update.

## Run locally

To ask Eevee for the IPA and update the local source:

```powershell
python updater.py update "https://apps.apple.com/us/app/discord-talk-play-hang-out/id985746746"
```

To use an IPA you already downloaded:

```powershell
python updater.py update "https://apps.apple.com/us/app/discord-talk-play-hang-out/id985746746" --ipa "C:\path\to\Discord.ipa"
```

Run the checks with:

```powershell
python -m unittest -v
```

## Trust and legal notice

The updater verifies the bundle identifier, version, build number, archive paths, size, and SHA-256 checksum. It reads entitlements from an embedded provisioning profile when one exists, and from the Mach-O code signatures of the app and its extensions when possible. Each source entry includes the App Store's iPhone and iPad screenshots and its What's New text when Apple provides them. It cannot prove that Eevee's output is identical to Apple's encrypted package. Review the upstream service before installing its files.

This project is not affiliated with Discord Inc., Apple Inc., or Eevee IPA Decrypter. Discord and its assets belong to their respective owners. Public release assets may be removed after a copyright complaint.
