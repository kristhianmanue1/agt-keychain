import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import llavero
import llavero_core as core

CANARY = "FAKE_PROVIDER_TEST_KEY"
def profile():
    return {"schema": core.PROVIDER_SCHEMA, "provider": "typesafe-systemone",
            "base_url": "https://api.typesafe.ai", "modelo": "jev-1.13.0"}

def response():
    return {"model": "jev-1.13.0", "answers": {"color": {
        "type": "choice", "choice": "blue", "confidence": 0.9,
        "probabilities": {"blue": 0.95, "red": 0.05}}},
        "usage": {"input_tokens": 80, "output_tokens": 10}}

class TestProviders(unittest.TestCase):
    def test_roundtrip_and_environment(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(core, "CONFIG_DIR", Path(d)/"profiles"):
            core.save_profile("agora.dev.typesafe", profile())
            p = core.load_profile("agora.dev.typesafe")
            env = core.build_consumer_environment(p, CANARY)
            self.assertEqual(env["TYPESAFE_API_KEY"], CANARY)
            self.assertEqual(env["TYPESAFE_BASE_URL"], p["base_url"])
            self.assertEqual(env["TYPESAFE_DEFAULT_MODEL"], p["modelo"])
            self.assertNotIn("SKOPOS_LLM_API_KEY", env)
            self.assertNotIn(CANARY, core.profile_path("agora.dev.typesafe").read_text())

    def test_v2_rejects_ambiguous_delivery_and_unknown_provider(self):
        for change in ({"delivery": {}}, {"api": "openai"}, {"provider": "arbitrary"}):
            with self.subTest(change=change), self.assertRaises(core.LlaveroError):
                core._validate_profile(dict(profile(), **change))

    def test_legacy_endpoint_and_model_conflicts(self):
        for name, value in (("TYPESAFE_BASE_URL", "https://other.invalid"), ("TYPESAFE_DEFAULT_MODEL", "different")):
            p = {"schema": core.PROFILE_SCHEMA, "base_url": "https://api.typesafe.ai",
                 "modelo": "jev-1.13.0", "delivery": {"mode": "env", "secret_env": "TYPESAFE_API_KEY",
                 "public_env": {name: value}}}
            with self.subTest(name=name), self.assertRaises(core.LlaveroError):
                core.build_consumer_environment(p, CANARY)

    def call_probe(self, document):
        result = mock.MagicMock()
        result.__enter__.return_value.read.return_value = json.dumps(document).encode()
        opener = mock.Mock()
        opener.open.return_value = result
        output = io.StringIO()
        with mock.patch.object(llavero, "load_profile", return_value=profile()),              mock.patch.object(llavero, "read_secret", return_value=CANARY),              mock.patch.object(llavero.urllib.request, "build_opener", return_value=opener),              contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            status = llavero.cmd_test("agora.dev.typesafe", None, None, 5)
        self.assertEqual(opener.open.call_count, 1)
        req = opener.open.call_args.args[0]
        self.assertEqual(req.full_url, "https://api.typesafe.ai/v1/systemone")
        self.assertEqual(req.get_header("Authorization"), "Bearer "+CANARY)
        self.assertNotIn(CANARY, req.data.decode())
        self.assertNotIn("messages", json.loads(req.data))
        self.assertNotIn(CANARY, output.getvalue())
        return status, output.getvalue()

    def test_probe_positive_and_safe_metadata(self):
        code, output = self.call_probe(response())
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["usage"]["input_tokens"], 80)

    def test_probe_rejects_bad_shapes_probabilities_and_wrong_answer(self):
        bad = [{}, {"choices": []}]
        for key,value in (("choice","red"),("confidence",True),("confidence",float("nan")),
                          ("probabilities",{"blue":0.2,"red":0.2}),
                          ("probabilities",{"blue":True,"red":False})):
            r=response();r["answers"]["color"][key]=value;bad.append(r)
        r=response();r["model"]=CANARY;bad.append(r)
        r=response();r["answers"]["extra"]={};bad.append(r)
        for document in bad:
            with self.subTest(document=document):
                self.assertEqual(self.call_probe(document)[0],1)

    def test_override_and_timeout_rejected_before_read(self):
        for model,timeout in (("different",5),(None,0),(None,float("nan"))):
            with mock.patch.object(llavero,"load_profile",return_value=profile()),                  mock.patch.object(llavero,"read_secret") as read, self.assertRaises(core.LlaveroError):
                llavero.cmd_test("x",None,model,timeout)
            read.assert_not_called()

    def test_replace_requires_explicit_flag(self):
        with mock.patch.object(llavero.sys.stdin,"isatty",return_value=True),              mock.patch.object(llavero.getpass,"getpass",return_value=CANARY),              mock.patch.object(llavero,"secret_exists",return_value=True),              mock.patch.object(llavero,"store_secret",return_value=True) as store:
            with self.assertRaises(core.LlaveroError):
                llavero.cmd_store("x",None)
            store.assert_not_called()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(llavero.cmd_store("x",None,True),0)
            store.assert_called_once_with("x",CANARY,update=True)

    def test_list_does_not_read_keychain(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(core,"CONFIG_DIR",Path(d)/"profiles"),              mock.patch.object(core,"_run_security") as keychain:
            core.save_profile("agora.dev.typesafe",profile())
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(llavero.cmd_list(),0)
            self.assertEqual(json.loads(output.getvalue())["provider"],"typesafe-systemone")
            keychain.assert_not_called()

    def test_cli_creates_explicit_profile(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(core,"CONFIG_DIR",Path(d)/"profiles"),              contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(llavero.main(["perfil","agora.dev.typesafe","--provider","typesafe-systemone",
                "--base-url","https://api.typesafe.ai","--modelo","jev-1.13.0"]),0)
            self.assertEqual(core.load_profile("agora.dev.typesafe"),profile())
            self.assertEqual(llavero.main(["validar","agora.dev.typesafe"]),0)
