import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import launcher


class BrowserArtifacts(unittest.TestCase):
    def test_owned_png_and_invalid_paths_or_payloads(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(launcher, 'RUNS_DIR', Path(directory)/'runs'):
            run = '12345678-1234-1234-1234-123456789abc'
            name = '1788856000000-1234abcd.png'
            folder = launcher.RUNS_DIR/run/'browser'
            folder.mkdir(parents=True)
            file = folder/name
            png = b'\x89PNG\r\n\x1a\nfixture'
            file.write_bytes(png)
            self.assertEqual(launcher.read_browser_artifact(run, name), png)
            for owner, filename in [('../outside', name), (run, '../private.png'), (run, 'secret.txt')]:
                with self.assertRaises(ValueError): launcher.read_browser_artifact(owner, filename)
            file.write_bytes(b'not a png')
            with self.assertRaises(ValueError): launcher.read_browser_artifact(run, name)
            file.unlink()
            outside = Path(directory)/'outside.png'
            outside.write_bytes(png)
            file.symlink_to(outside)
            with self.assertRaises(OSError): launcher.read_browser_artifact(run, name)
            file.unlink()
            os.mkfifo(file)
            with self.assertRaises(ValueError): launcher.read_browser_artifact(run, name)
            file.unlink()
            folder.rmdir()
            folder.symlink_to(directory)
            with self.assertRaises(ValueError): launcher.read_browser_artifact(run, name)
