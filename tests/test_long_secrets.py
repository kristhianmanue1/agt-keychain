"""Claves largas: pipe sin argv/env; canarios reales sólo por opt-in."""
import os
import subprocess
import unittest
import uuid
from unittest.mock import patch
import llavero_core as core

class LongSecretTests(unittest.TestCase):
    def test_pipe_has_exact_hex_and_single_command(self):
        secret = ('canary \" \\ ; $() ' * 20)
        with patch.object(core.subprocess, 'run') as run, patch.object(core, 'read_secret', return_value=secret):
            run.return_value.returncode = 0
            self.assertTrue(core.store_secret('test.long', secret, update=False))
            args, kwargs = run.call_args
            self.assertEqual(args[0], [core.SECURITY_BIN, '-i', '-q'])
            self.assertNotIn(secret, repr(args))
            self.assertNotIn(secret, repr(kwargs['env']))
            self.assertEqual(kwargs['input'], 'add-generic-password -s llavero -a test.long -X ' + secret.encode().hex() + '\n')
            self.assertNotIn('-U', kwargs['input'])

    def test_timeout_or_nonzero_never_reports_success(self):
        for failure in (subprocess.TimeoutExpired('security', 30), None):
            with patch.object(core.subprocess, 'run', side_effect=failure) as run, patch.object(core, 'read_secret') as read:
                run.return_value.returncode = 1
                self.assertFalse(core.store_secret('test.long', 'x' * 192))
                read.assert_not_called()

    def test_byte_limit_precedes_process(self):
        with patch.object(core.subprocess, 'run') as run:
            with self.assertRaises(core.LlaveroError):
                core.store_secret('test.long', 'á' * 513)
            run.assert_not_called()

    def test_ambiguous_long_values_rejected_before_mutation(self):
        for value in ('á' * 256, 'x' * 192 + '\t'):
            with patch.object(core.subprocess, 'run') as run:
                with self.assertRaises(core.LlaveroError):
                    core.store_secret('test.long', value)
                run.assert_not_called()

    @unittest.skipUnless(os.environ.get('LLAVERO_KEYCHAIN_INTEGRATION') == '1', 'real Keychain opt-in')
    def test_real_boundary_roundtrip_and_replace(self):
        for secret in ('x' * 128, 'x' * 129, 'x' * 192, 'x' * 512, 'x' * 1024):
            identity = 'llavero-long-test-' + uuid.uuid4().hex
            try:
                self.assertTrue(core.store_secret(identity, secret, update=False))
                self.assertTrue(core.read_secret(identity) == secret, 'roundtrip mismatch')
                self.assertFalse(core.store_secret(identity, 'y' * 192, update=False))
                self.assertTrue(core.read_secret(identity) == secret, 'duplicate changed value')
                self.assertTrue(core.store_secret(identity, 'y' * 192, update=True))
                self.assertTrue(core.read_secret(identity) == 'y' * 192, 'replacement mismatch')
            finally:
                if core.secret_exists(identity):
                    self.assertTrue(core.delete_secret(identity))
                self.assertFalse(core.secret_exists(identity))
