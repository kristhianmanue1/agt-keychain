from __future__ import annotations

import contextlib
import http.server
import io
import json
import os
import pathlib
import stat
import tempfile
import threading
import unittest
from unittest import mock

import llavero
import llavero_core as core


CANARY = "LLAVERO_CANARY_NOT_A_REAL_KEY_123"


class TestIdentifiersAndEndpoints(unittest.TestCase):
    def test_identifier_rejects_path_traversal(self):
        for value in ("../escape", "a/b", ".hidden", "", "UPPER"):
            with self.subTest(value=value), self.assertRaises(core.LlaveroError):
                core.validate_identifier(value)

    def test_endpoint_accepts_https_and_ip_loopback(self):
        self.assertEqual(
            core.validate_endpoint("https://api.example.test/v1"),
            "https://api.example.test/v1",
        )
        self.assertEqual(
            core.validate_endpoint("http://127.0.0.1:11434/v1"),
            "http://127.0.0.1:11434/v1",
        )

    def test_endpoint_rejects_remote_http_credentials_query_and_fragment(self):
        invalid = (
            "http://api.example.test/v1",
            "https://user:pass@example.test/v1",
            "https://example.test/v1?redirect=evil",
            "https://example.test/v1#fragment",
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(core.LlaveroError):
                core.validate_endpoint(value)

    def test_cli_endpoint_cannot_replace_profile_destination(self):
        profile = {"base_url": "https://api.example.test/v1"}
        with self.assertRaises(core.LlaveroError):
            llavero._resolved_endpoint("https://evil.example/v1", profile)


class TestProfiles(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.config_patch = mock.patch.object(
            core, "CONFIG_DIR", pathlib.Path(self.temporary.name) / "profiles"
        )
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)

    def test_profile_is_atomic_private_and_round_trips(self):
        profile = {
            "base_url": "https://api.example.test/v1",
            "modelo": "example-model",
            "delivery": {
                "mode": "env",
                "secret_env": "EXAMPLE_API_KEY",
                "public_env": {"EXAMPLE_MODEL": "example-model"},
            },
        }
        path = core.save_profile("example", profile)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        loaded = core.load_profile("example")
        self.assertEqual(loaded["schema"], core.PROFILE_SCHEMA)
        self.assertEqual(loaded["delivery"]["secret_env"], "EXAMPLE_API_KEY")

    def test_profile_rejects_symlink(self):
        target = pathlib.Path(self.temporary.name) / "target.json"
        target.write_text("{}", encoding="utf-8")
        core.CONFIG_DIR.mkdir(mode=0o700)
        core.profile_path("example").symlink_to(target)
        with self.assertRaises(core.LlaveroError):
            core.load_profile("example")

    def test_profile_rejects_symlinked_config_directory(self):
        real_directory = pathlib.Path(self.temporary.name) / "real"
        real_directory.mkdir()
        real_directory.chmod(0o700)
        core.CONFIG_DIR.symlink_to(real_directory, target_is_directory=True)
        with self.assertRaises(core.LlaveroError):
            core.load_profile("example")

    def test_public_environment_rejects_secret_like_and_protected_names(self):
        for name in (
            "PATH", "ANOTHER_TOKEN", "DATABASE_PASSWORD", "BASH_ENV",
            "PYTHONPATH", "NODE_OPTIONS", "DYLD_INSERT_LIBRARIES",
            "SSLKEYLOGFILE", "HTTPS_PROXY", "JAVA_TOOL_OPTIONS",
            "JDK_JAVA_OPTIONS", "PYTHONUSERBASE", "LD_AUDIT", "CLASSPATH",
            "NODE_PATH", "PERL5LIB", "RUBYLIB", "GIT_SSH_COMMAND",
            "SSH_ASKPASS",
        ):
            with self.subTest(name=name), self.assertRaises(core.LlaveroError):
                core.validate_public_environment(name, "value")

    def test_secret_environment_requires_credential_name(self):
        for name in ("PATH", "HOME", "MODEL_NAME", "PYTHONPATH"):
            with self.subTest(name=name), self.assertRaises(core.LlaveroError):
                core.validate_secret_environment_name(name)
        self.assertEqual(
            core.validate_secret_environment_name("ANTHROPIC_API_KEY"),
            "ANTHROPIC_API_KEY",
        )

    def test_atomic_replace_failure_preserves_previous_profile(self):
        original = {"modelo": "before"}
        path = core.save_profile("example", original)
        with mock.patch.object(core.os, "replace", side_effect=OSError("fixture")):
            with self.assertRaises(OSError):
                core.save_profile("example", {"modelo": "after"})
        self.assertEqual(json.loads(path.read_text())["modelo"], "before")
        self.assertEqual(list(path.parent.glob(".profile-*")), [])

    def test_generic_profile_without_schema_is_rejected(self):
        core.CONFIG_DIR.mkdir(mode=0o700)
        path = core.profile_path("example")
        path.write_text(json.dumps({
            "delivery": {
                "mode": "env",
                "secret_env": "EXAMPLE_API_KEY",
                "public_env": {},
            }
        }), encoding="utf-8")
        path.chmod(0o600)
        with self.assertRaises(core.LlaveroError):
            core.load_profile("example")


class TestEnvironmentDelivery(unittest.TestCase):
    def test_generic_profile_maps_any_consumer_variable(self):
        profile = {
            "schema": core.PROFILE_SCHEMA,
            "delivery": {
                "mode": "env",
                "secret_env": "ANTHROPIC_API_KEY",
                "public_env": {"MODEL_NAME": "example-model"},
            }
        }
        with mock.patch.dict(os.environ, {"UNRELATED_SECRET": CANARY}, clear=False):
            environment = core.build_consumer_environment(profile, "consumer-key")
        self.assertEqual(environment["ANTHROPIC_API_KEY"], "consumer-key")
        self.assertEqual(environment["MODEL_NAME"], "example-model")
        self.assertNotIn("UNRELATED_SECRET", environment)

    def test_arbitrary_lc_prefix_is_not_inherited(self):
        with mock.patch.dict(
            os.environ,
            {"LC_SECRET": CANARY, "LC_CTYPE": "C"},
            clear=True,
        ):
            environment = core.minimal_environment()
        self.assertNotIn("LC_SECRET", environment)
        self.assertEqual(environment["LC_CTYPE"], "C")

    def test_legacy_profile_keeps_skopos_adapter(self):
        profile = {
            "api": "openai",
            "base_url": "https://api.example.test/v1",
            "modelo": "example-model",
        }
        environment = core.build_consumer_environment(profile, "consumer-key")
        self.assertEqual(environment["SKOPOS_LLM_API_KEY"], "consumer-key")
        self.assertEqual(environment["SKOPOS_LLM_MODELO"], "example-model")

    def test_status_does_not_reveal_length_or_suffix(self):
        output = io.StringIO()
        with mock.patch.object(llavero, "secret_exists", return_value=True):
            with contextlib.redirect_stdout(output):
                self.assertEqual(llavero.cmd_status("example"), 0)
        rendered = output.getvalue()
        self.assertEqual(rendered, "llavero: credencial presente para 'example'\n")

    def test_presence_check_does_not_request_secret_value(self):
        completed = mock.Mock(returncode=0)
        with mock.patch.object(core, "_run_security", return_value=completed) as run:
            self.assertTrue(core.secret_exists("example"))
        self.assertNotIn("-w", run.call_args.args)

    def test_interactive_capture_requires_tty(self):
        with mock.patch.object(llavero.sys.stdin, "isatty", return_value=False):
            with mock.patch.object(llavero.getpass, "getpass") as getpass_mock:
                with self.assertRaises(core.LlaveroError):
                    llavero.cmd_store("example", None)
        getpass_mock.assert_not_called()

    def test_command_is_resolved_before_secret_is_read(self):
        with mock.patch.object(llavero, "read_secret") as read_mock:
            with self.assertRaises(core.LlaveroError):
                llavero.cmd_run("example", ["relative-consumer"])
        read_mock.assert_not_called()

    def test_cmd_run_executes_resolved_path_with_minimal_environment(self):
        profile = {
            "schema": core.PROFILE_SCHEMA,
            "delivery": {
                "mode": "env",
                "secret_env": "EXAMPLE_API_KEY",
                "public_env": {"MODEL_NAME": "fixture-model"},
            },
        }
        with mock.patch.object(llavero, "read_secret", return_value=CANARY):
            with mock.patch.object(llavero, "load_profile", return_value=profile):
                with mock.patch.object(
                    llavero.os, "execve", side_effect=RuntimeError("stop")
                ) as execute:
                    with self.assertRaisesRegex(RuntimeError, "stop"):
                        llavero.cmd_run("example", ["/bin/echo", "ok"])
        executable, arguments, environment = execute.call_args.args
        self.assertEqual(executable, "/bin/echo")
        self.assertEqual(arguments, ["/bin/echo", "ok"])
        self.assertEqual(environment["EXAMPLE_API_KEY"], CANARY)
        self.assertEqual(environment["MODEL_NAME"], "fixture-model")
        self.assertNotIn("UNRELATED_SECRET", environment)
        self.assertEqual(environment["PATH"], "/usr/bin:/bin:/usr/sbin:/sbin")

    def test_env_shebang_is_rejected_before_secret_read(self):
        with tempfile.TemporaryDirectory() as directory:
            script = pathlib.Path(directory) / "consumer"
            script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            script.chmod(0o700)
            with mock.patch.object(llavero, "load_profile", return_value={"modelo": "m"}):
                with mock.patch.object(llavero, "read_secret") as read_mock:
                    with self.assertRaises(core.LlaveroError):
                        llavero.cmd_run("example", [str(script)])
        read_mock.assert_not_called()

    def test_missing_profile_is_rejected_before_secret_read(self):
        with mock.patch.object(llavero, "load_profile", return_value={}):
            with mock.patch.object(llavero, "read_secret") as read_mock:
                with self.assertRaises(core.LlaveroError):
                    llavero.cmd_run("example", ["/bin/echo"])
        read_mock.assert_not_called()


class TestKeychainTransport(unittest.TestCase):
    def fake_security(self, directory, mode="normal"):
        fake = pathlib.Path(directory) / "fake-security"
        fake.write_text(
            f"#!{__import__('sys').executable}\n"
            "import getpass, os, sys, termios, time\n"
            f"canary = {CANARY!r}\n"
            "if any(canary in arg for arg in sys.argv): raise SystemExit(2)\n"
            "if 'LLAVERO_PARENT_SECRET' in os.environ: raise SystemExit(3)\n"
            "if os.getsid(0) != os.getpid(): raise SystemExit(4)\n"
            "with open('/dev/tty','rb',buffering=0) as tty:\n"
            "    if os.tcgetpgrp(tty.fileno()) != os.getpgrp(): raise SystemExit(5)\n"
            "    if termios.tcgetattr(tty.fileno())[3] & (termios.ECHO | termios.ECHONL): raise SystemExit(6)\n"
            + ("time.sleep(10)\n" if mode == "timeout" else "")
            + ("raise SystemExit(0)\n" if mode == "early" else "")
            + "first = getpass.getpass('password data for new item: ')\n"
            "second = getpass.getpass('retype password for new item: ')\n"
            "raise SystemExit(0 if first == second == canary else 7)\n",
            encoding="utf-8",
        )
        fake.chmod(0o700)
        return fake

    def test_canary_uses_own_controlling_tty_and_both_prompts(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = self.fake_security(directory)
            with mock.patch.object(core, "SECURITY_BIN", str(fake)), mock.patch.object(core, "read_secret", return_value=CANARY), mock.patch.dict(os.environ, {"LLAVERO_PARENT_SECRET": "must-not-inherit"}):
                self.assertTrue(core.store_secret("example", CANARY))

    def test_timeout_does_not_claim_success_or_read_back(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = self.fake_security(directory, "timeout")
            with mock.patch.object(core, "SECURITY_BIN", str(fake)), mock.patch.object(core, "_SECURITY_WRITE_TIMEOUT", 0.2), mock.patch.object(core, "read_secret") as read:
                self.assertFalse(core.store_secret("example", CANARY))
                read.assert_not_called()

    def test_zero_exit_without_capture_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = self.fake_security(directory, "early")
            with mock.patch.object(core, "SECURITY_BIN", str(fake)), mock.patch.object(core, "read_secret") as read:
                self.assertFalse(core.store_secret("example", CANARY))
                read.assert_not_called()

    def test_readback_mismatch_or_missing_is_not_success(self):
        for value in (None, "different"):
            with self.subTest(value=value), mock.patch.object(core, "_run_security_with_secret", return_value=0), mock.patch.object(core, "read_secret", return_value=value):
                self.assertFalse(core.store_secret("example", CANARY))

    def test_oversized_secret_rejected_before_process(self):
        with mock.patch.object(core.subprocess, "Popen") as process:
            with self.assertRaises(core.LlaveroError): core.store_secret("example", "x"*1025)
            process.assert_not_called()


class TestHttpPolicy(unittest.TestCase):
    def test_redirect_is_rejected_without_replaying_authorization(self):
        hits = {"redirect": 0, "target": 0}
        observed_authorization = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path == "/chat/completions":
                    hits["redirect"] += 1
                    observed_authorization.append(self.headers.get("Authorization"))
                    self.send_response(302)
                    self.send_header(
                        "Location",
                        f"http://127.0.0.1:{self.server.server_port}/target",
                    )
                    self.end_headers()
                    return
                hits["target"] += 1
                self.send_response(200)
                self.end_headers()

            def do_GET(self):
                hits["target"] += 1
                self.send_response(200)
                self.end_headers()

            def log_message(self, format, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        profile = {
            "base_url": f"http://127.0.0.1:{server.server_port}",
            "modelo": "fixture-model",
        }
        with mock.patch.object(llavero, "read_secret", return_value=CANARY):
            with mock.patch.object(llavero, "load_profile", return_value=profile):
                with mock.patch.dict(os.environ, {
                    "HTTP_PROXY": "http://127.0.0.1:1",
                    "NO_PROXY": "",
                }, clear=False):
                    with contextlib.redirect_stderr(io.StringIO()):
                        result = llavero.cmd_test("example", None, None, 2)
        self.assertEqual(result, 1)
        self.assertEqual(hits, {"redirect": 1, "target": 0})
        self.assertEqual(observed_authorization, [f"Bearer {CANARY}"])

    def test_success_requires_nonempty_model_content(self):
        class Response:
            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self, limit):
                return self.payload[:limit]

        class Opener:
            def __init__(self, payload):
                self.payload = payload

            def open(self, request, timeout):
                return Response(self.payload)

        profile = {
            "base_url": "https://api.example.test/v1",
            "modelo": "fixture-model",
        }
        invalid_documents = ({}, {"choices": []}, {"choices": [1]}, {
            "choices": [{"message": {"content": ""}}]
        }, {"choices": [{"message": {"content": "   "}}]})
        for document in invalid_documents:
            with self.subTest(document=document):
                opener = Opener(json.dumps(document).encode())
                with mock.patch.object(llavero, "read_secret", return_value=CANARY):
                    with mock.patch.object(llavero, "load_profile", return_value=profile):
                        with mock.patch.object(
                            llavero.urllib.request, "build_opener", return_value=opener
                        ):
                            with contextlib.redirect_stderr(io.StringIO()):
                                self.assertEqual(
                                    llavero.cmd_test("example", None, None, 2), 1
                                )
        valid = {"choices": [{"message": {"content": "ok"}}]}
        opener = Opener(json.dumps(valid).encode())
        with mock.patch.object(llavero, "read_secret", return_value=CANARY):
            with mock.patch.object(llavero, "load_profile", return_value=profile):
                with mock.patch.object(
                    llavero.urllib.request, "build_opener", return_value=opener
                ):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(llavero.cmd_test("example", None, None, 2), 0)

    def test_all_redirect_codes_are_denied_by_handler(self):
        handler = core.NoRedirectHandler()
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                self.assertIsNone(
                    handler.redirect_request(None, None, code, "", {}, "https://x")
                )

    def test_model_control_characters_are_rejected(self):
        profile = {"base_url": "https://api.example.test/v1"}
        for model in ("ok\nforged", "ok\u009bforged", "ok\u202eforged", "ok\u2028forged"):
            with self.subTest(model=repr(model)):
                with mock.patch.object(llavero, "load_profile", return_value=profile):
                    with mock.patch.object(llavero, "read_secret") as read_mock:
                        with self.assertRaises(core.LlaveroError):
                            llavero.cmd_test("example", None, model, 2)
                read_mock.assert_not_called()


class TestProfileJson(unittest.TestCase):
    def test_profile_rejects_secret_value_field(self):
        with self.assertRaises(core.LlaveroError):
            core._validate_profile({"secret": CANARY})


if __name__ == "__main__":
    unittest.main()
