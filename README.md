# Discord AltStore source

This repository publishes an unofficial AltSource feed for the standard Discord App Store build. The updater asks [Eevee IPA Decrypter](https://t.me/eeveedecrypterbot) for the latest decrypted IPA and does not inject tweaks or make other changes.

The source works with KSign and AltStore Classic. It does not work with AltStore PAL, which requires Apple-notarized alternative distribution packages.

## Source URL

Add this URL to KSign or AltStore Classic:

```text
https://raw.githubusercontent.com/AlfaActa/discord-altstore-source/main/source.json
```

The source stays empty until the first successful update publishes an IPA release.

## Set up automatic updates

Use a dedicated Telegram account. A Telegram session grants full access to that account, even when it is stored as an encrypted GitHub secret.

1. Create an API ID and API hash at [my.telegram.org](https://my.telegram.org).
2. Install Python 3.11 or newer and GitHub CLI.
3. Install the one Python dependency:

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

The workflow checks every Tuesday at 04:17 UTC. GitHub may delay scheduled jobs. It also disables scheduled workflows in public repositories after 60 days without repository activity, so re-enable the workflow if Discord goes that long without a published update.

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

The updater verifies the bundle identifier, version, build number, archive paths, any embedded provisioning-profile permissions, size, and SHA-256 checksum. It cannot prove that Eevee's output is identical to Apple's encrypted package. Review the upstream service before installing its files.

This project is not affiliated with Discord Inc., Apple Inc., or Eevee IPA Decrypter. Discord and its assets belong to their respective owners. Public release assets may be removed after a copyright complaint.
