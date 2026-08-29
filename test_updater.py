import json
import os
import plistlib
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import updater


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def make_ipa(
        self,
        name="Discord",
        bundle=updater.BUNDLE_ID,
        version="342.0",
        build="70001",
        profile=True,
    ):
        path = self.root / f"{name}.ipa"
        info = {
            "CFBundleIdentifier": bundle,
            "CFBundleShortVersionString": version,
            "CFBundleVersion": build,
            "MinimumOSVersion": "16.0",
            "NSCameraUsageDescription": "Discord uses the camera for video calls.",
        }
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(f"Payload/{name}.app/Info.plist", plistlib.dumps(info, fmt=plistlib.FMT_BINARY))
            archive.writestr(f"Payload/{name}.app/{name}", b"binary")
            if profile:
                archive.writestr(
                    f"Payload/{name}.app/embedded.mobileprovision",
                    plistlib.dumps(
                        {
                            "Entitlements": {
                                "application-identifier": "TEAM.bundle",
                                "com.apple.developer.team-identifier": "TEAM",
                                "aps-environment": "production",
                            }
                        },
                        fmt=plistlib.FMT_XML,
                    ),
                )
        return path

    def make_source(self):
        path = self.root / "source.json"
        path.write_text(
            json.dumps({"name": "Discord", "apps": [{"bundleIdentifier": updater.BUNDLE_ID, "versions": []}]}),
            encoding="utf-8",
        )
        return path

    def test_inspects_binary_plist_and_hash(self):
        metadata = updater.inspect_ipa(self.make_ipa())
        self.assertEqual((metadata.version, metadata.build, metadata.min_os), ("342.0", "70001", "16.0"))
        self.assertEqual(len(metadata.sha256), 64)
        self.assertEqual(metadata.entitlements, ("aps-environment",))
        self.assertEqual(metadata.privacy["NSCameraUsageDescription"], "Discord uses the camera for video calls.")

    def test_reads_macho_signature_entitlements(self):
        entitlements = plistlib.dumps(
            {
                "application-identifier": "TEAM.bundle",
                "com.apple.security.application-groups": ["group.example"],
            },
            fmt=plistlib.FMT_XML,
        )
        entitlement_blob = struct.pack(">II", updater.CSMAGIC_ENTITLEMENTS, 8 + len(entitlements)) + entitlements
        signature = (
            struct.pack(">III", updater.CSMAGIC_EMBEDDED_SIGNATURE, 20 + len(entitlement_blob), 1)
            + struct.pack(">II", updater.CSSLOT_ENTITLEMENTS, 20)
            + entitlement_blob
        )
        header = struct.pack("<IiiIIIII", 0xFEEDFACF, 0, 0, 2, 1, 16, 0, 0)
        command = struct.pack("<IIII", updater.LC_CODE_SIGNATURE, 16, 48, len(signature))
        self.assertEqual(updater._signature_entitlements(header + command + signature), {"com.apple.security.application-groups"})

    def test_accepts_app_store_ipa_without_provisioning_profile(self):
        metadata = updater.inspect_ipa(self.make_ipa(profile=False))
        self.assertEqual(metadata.entitlements, ())

    def test_rejects_wrong_bundle_and_multiple_apps(self):
        with self.assertRaises(updater.UpdateError):
            updater.inspect_ipa(self.make_ipa(bundle="example.wrong"))

        path = self.make_ipa()
        with zipfile.ZipFile(path, "a") as archive:
            archive.writestr(
                "Payload/Other.app/Info.plist",
                plistlib.dumps(
                    {
                        "CFBundleIdentifier": updater.BUNDLE_ID,
                        "CFBundleShortVersionString": "1",
                        "CFBundleVersion": "1",
                    }
                ),
            )
        with self.assertRaises(updater.UpdateError):
            updater.inspect_ipa(path)

        hidden = self.make_ipa()
        with zipfile.ZipFile(hidden, "a") as archive:
            archive.writestr("Payload/Hidden.app/Hidden", b"binary")
        with self.assertRaises(updater.UpdateError):
            updater.inspect_ipa(hidden)

    def test_rejects_unsafe_malformed_and_oversized_archives(self):
        unsafe = self.root / "unsafe.ipa"
        with zipfile.ZipFile(unsafe, "w") as archive:
            archive.writestr("../Info.plist", b"bad")
        with self.assertRaises(updater.UpdateError):
            updater.inspect_ipa(unsafe)

        malformed = self.root / "malformed.ipa"
        malformed.write_bytes(b"not a zip")
        with self.assertRaises(updater.UpdateError):
            updater.inspect_ipa(malformed)

        valid = self.make_ipa()
        with mock.patch.object(updater, "MAX_IPA_SIZE", 1):
            with self.assertRaises(updater.UpdateError):
                updater.inspect_ipa(valid)

    def test_updates_source_newest_first_and_is_idempotent(self):
        source = self.make_source()
        first = updater.inspect_ipa(self.make_ipa(version="342.0", build="70001"))
        self.assertTrue(updater.update_source(source, first, "https://example.com/342.ipa"))
        self.assertFalse(updater.update_source(source, first, "https://example.com/342.ipa"))

        second = updater.inspect_ipa(self.make_ipa(version="343.0", build="70100"))
        self.assertTrue(updater.update_source(source, second, "https://example.com/343.ipa"))
        app = json.loads(source.read_text(encoding="utf-8"))["apps"][0]
        self.assertEqual([item["version"] for item in app["versions"]], ["343.0", "342.0"])
        self.assertEqual(app["downloadURL"], "https://example.com/343.ipa")
        self.assertEqual(app["version"], "343.0")
        self.assertEqual(app["appPermissions"]["entitlements"], ["aps-environment"])

    def test_adds_app_store_screenshots_and_release_notes(self):
        source = self.make_source()
        metadata = updater.inspect_ipa(self.make_ipa())
        apple = {
            "version": "342.0",
            "releaseNotes": "New voice features.\n\nSmaller fixes.",
            "screenshotUrls": ["https://example.com/392x696bb.png"],
            "ipadScreenshotUrls": ["https://example.com/552x414bb.png"],
        }
        updater.update_source(source, metadata, "https://example.com/342.ipa", apple)
        app = json.loads(source.read_text(encoding="utf-8"))["apps"][0]
        self.assertEqual(app["screenshots"]["iphone"][0]["width"], 392)
        self.assertEqual(app["screenshots"]["ipad"][0]["height"], 414)
        self.assertEqual(app["versions"][0]["localizedDescription"], apple["releaseNotes"])

    def test_uses_previous_release_notes_when_app_store_has_none(self):
        source = self.make_source()
        document = json.loads(source.read_text(encoding="utf-8"))
        document["apps"][0]["versions"].append(
            {"version": "341.0", "buildVersion": "70000", "localizedDescription": "Previous App Store note."}
        )
        source.write_text(json.dumps(document), encoding="utf-8")
        metadata = updater.inspect_ipa(self.make_ipa(version="342.0"))
        updater.update_source(source, metadata, "https://example.com/342.ipa", {"version": "342.0"})
        app = json.loads(source.read_text(encoding="utf-8"))["apps"][0]
        self.assertEqual(app["versions"][0]["localizedDescription"], "Previous App Store note.")

    def test_writes_multiline_github_outputs_safely(self):
        output = self.root / "github-output"
        with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}):
            updater._github_output({"release_notes": "First line\n\nSecond line", "version": "342.0"})
        lines = output.read_text(encoding="utf-8").splitlines()
        delimiter = lines[0].split("<<", 1)[1]
        self.assertEqual(lines[1:4], ["First line", "", "Second line"])
        self.assertEqual(lines[4], delimiter)
        self.assertEqual(lines[5], "version=342.0")

    def test_rejects_duplicate_version_with_different_hash(self):
        source = self.make_source()
        metadata = updater.inspect_ipa(self.make_ipa())
        updater.update_source(source, metadata, "https://example.com/Discord.ipa")
        document = json.loads(source.read_text(encoding="utf-8"))
        document["apps"][0]["versions"][0]["sha256"] = "0" * 64
        source.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(updater.UpdateError):
            updater.update_source(source, metadata, "https://example.com/Discord.ipa")

    def test_accepts_only_fresh_direct_ipa_from_expected_bot(self):
        file = SimpleNamespace(name="Discord.ipa")
        valid = SimpleNamespace(
            id=11,
            sender_id=42,
            chat_id=42,
            out=False,
            fwd_from=None,
            document=object(),
            file=file,
        )
        self.assertTrue(updater.is_expected_ipa_message(valid, 42, 10))

        for change in (
            {"id": 10},
            {"sender_id": 99},
            {"chat_id": 99},
            {"out": True},
            {"fwd_from": object()},
            {"document": None},
            {"file": SimpleNamespace(name="Discord.zip")},
        ):
            values = vars(valid) | change
            self.assertFalse(updater.is_expected_ipa_message(SimpleNamespace(**values), 42, 10))

    def test_rejects_non_discord_app_store_urls(self):
        with self.assertRaises(updater.UpdateError):
            updater.validate_app_store_url("https://example.com/id985746746")
        with self.assertRaises(updater.UpdateError):
            updater.validate_app_store_url("https://apps.apple.com/us/app/example/id123")


if __name__ == "__main__":
    unittest.main()
