"""Opt-in: real CLI with disposable Keychain entry, no provider or user keys."""
import errno
import os
import pathlib
import pty
import secrets
import select
import subprocess
import sys
import termios
import time
import unittest
import uuid
import llavero_core as core

@unittest.skipUnless(os.environ.get('LLAVERO_KEYCHAIN_INTEGRATION')=='1','requires explicit disposable Keychain test')
class KeychainLiveTests(unittest.TestCase):
    def test_cli_has_two_hidden_prompts_and_roundtrip(self):
        identity='llavero-test-'+uuid.uuid4().hex
        secret='SYNTHETIC_'+secrets.token_hex(24)
        self.assertFalse(core.secret_exists(identity))
        master,slave=pty.openpty();attrs=termios.tcgetattr(slave);attrs[3]&=~(termios.ECHO|termios.ECHONL);termios.tcsetattr(slave,termios.TCSANOW,attrs)
        child=None;seen=b'';pending=b'';answered=0
        prompts=[f"Credencial para '{identity}' (entrada oculta): ".encode(),b'Repite para confirmar: ']
        try:
            command=[sys.executable,'-I','-c',core._SECURITY_TTY_HELPER,sys.executable,str(pathlib.Path(core.__file__).with_name('llavero.py')),'guardar',identity]
            child=subprocess.Popen(command,stdin=slave,stdout=slave,stderr=slave,start_new_session=True,env=core.minimal_environment(),close_fds=True)
            os.close(slave);slave=-1;deadline=time.monotonic()+40
            while True:
                self.assertLess(time.monotonic(),deadline,'CLI deadline exceeded')
                ready,_,_=select.select([master],[],[],0.1)
                if ready:
                    try:block=os.read(master,4096)
                    except OSError as exc:
                        if exc.errno!=errno.EIO:raise
                        block=b''
                    seen+=block;pending+=block
                    if answered<2 and prompts[answered] in pending:
                        core._write_all(master,secret.encode()+b'\n');answered+=1;pending=b''
                    if not block and child.poll() is not None:break
                elif child.poll() is not None:break
            self.assertEqual(child.wait(),0)
            self.assertEqual(answered,2)
            self.assertTrue(secret.encode() not in seen,'secret echoed')
            self.assertTrue(b'password data for new item' not in seen,'native prompt escaped')
            self.assertTrue(b'retype password for new item' not in seen,'native confirmation escaped')
            self.assertTrue(b'llavero: credencial guardada' in seen)
            self.assertTrue(core.read_secret(identity)==secret,'roundtrip mismatch')
        finally:
            if child is not None and child.poll() is None:child.kill();child.wait()
            if slave>=0:os.close(slave)
            os.close(master)
            if core.secret_exists(identity):self.assertTrue(core.delete_secret(identity),'temporary entry cleanup failed')
            self.assertFalse(core.secret_exists(identity),'temporary entry remains')
