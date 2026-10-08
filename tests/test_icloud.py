"""iCloud bridge tests use a fake helper; they never touch Keychain."""
import base64
import json
import pathlib
import subprocess
import unittest
from unittest import mock

import llavero
import llavero_core as core


class ICloudBridgeTests(unittest.TestCase):
    def setUp(self):
        self.path = mock.patch.object(core, "SYNC_HELPER", pathlib.Path("/usr/bin/true"))
        self.path.start()
        self.addCleanup(self.path.stop)
        self.signature = mock.patch.object(core, "_verify_sync_helper")
        self.signature.start()
        self.addCleanup(self.signature.stop)

    def test_secret_uses_stdin_and_readback(self):
        canary = "synthetic-credential"
        calls = []

        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            request = json.loads(kwargs["input"])
            if request["operation"] == "put":
                self.assertEqual(base64.b64decode(request["data"]).decode(), canary)
                return subprocess.CompletedProcess(argv, 0, '{"ok":true}', "")
            return subprocess.CompletedProcess(argv, 0, json.dumps({
                "ok": True, "found": True,
                "data": base64.b64encode(canary.encode()).decode(),
            }), "")

        with mock.patch.object(core.subprocess, "run", side_effect=fake_run):
            self.assertTrue(core.sync_store_secret("example.dev", canary))
        self.assertEqual(len(calls), 2)
        for argv, kwargs in calls:
            self.assertEqual(argv, ["/usr/bin/true"])
            self.assertNotIn(canary, str(argv))
            self.assertNotIn(canary, str(kwargs["env"]))

    def test_missing_entitlement_fails_closed(self):
        failure = subprocess.CompletedProcess(["/bin/true"], 1,
            '{"ok":false,"error":"keychain_error","status":-34018}', "")
        with mock.patch.object(core.subprocess, "run", return_value=failure):
            with self.assertRaisesRegex(core.LlaveroError, "entitlement"):
                core.sync_secret_exists("example.dev")

    def test_profile_roundtrip_is_separate_from_local_files(self):
        profile = {"schema": core.PROFILE_SCHEMA, "base_url": "https://example.org",
                   "modelo": "sample", "delivery": {"mode": "env",
                   "secret_env": "SAMPLE_API_KEY", "public_env": {}}}
        encoded = base64.b64encode(json.dumps(profile).encode()).decode()
        operations = []

        def fake_run(argv, **kwargs):
            request = json.loads(kwargs["input"])
            operations.append(request["operation"])
            if request["operation"] == "put":
                self.assertEqual(request["kind"], "profile")
                self.assertEqual(json.loads(base64.b64decode(request["data"])), profile)
                response = {"ok": True}
            else:
                response = {"ok": True, "found": True, "data": encoded}
            return subprocess.CompletedProcess(argv, 0, json.dumps(response), "")

        with mock.patch.object(core.subprocess, "run", side_effect=fake_run):
            with mock.patch.object(core, "save_profile", side_effect=AssertionError):
                core.sync_save_profile("example.dev", profile)
        self.assertEqual(operations, ["put", "get"])

    def test_icloud_mode_does_not_fall_back_to_local(self):
        with mock.patch.object(core, "sync_secret_exists", side_effect=core.LlaveroError("unavailable")):
            with mock.patch.object(llavero, "secret_exists", side_effect=AssertionError):
                with self.assertRaisesRegex(core.LlaveroError, "unavailable"):
                    llavero.cmd_status("example.dev", icloud=True)

    def test_rejected_signature_precedes_secret_transfer(self):
        with mock.patch.object(core, "_verify_sync_helper",
                               side_effect=core.LlaveroError("firma inválida")):
            with mock.patch.object(core.subprocess, "run", side_effect=AssertionError):
                with self.assertRaisesRegex(core.LlaveroError, "firma"):
                    core.sync_store_secret("example.dev", "synthetic-credential")


if __name__ == "__main__":
    unittest.main()
