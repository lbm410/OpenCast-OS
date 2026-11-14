"""Source bundles are deterministic and contain only selected project assets."""

import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import netcast_source as source


class SourceBundleTests(unittest.TestCase):
    def test_deterministic_source_only_bundle_has_root_entry_and_local_assets(self):
        for kind, routes in (("probe", source.ASSETS), ("shell", source.SHELL_ASSETS)):
            first, report = source.build_source(kind)
            second, _ = source.build_source(kind)
            self.assertEqual(first, second)
            self.assertFalse(report["installable"])
            with zipfile.ZipFile(io.BytesIO(first)) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(set(archive.namelist()), {v[0] for v in routes.values()})
                self.assertIn("index.html", archive.namelist())
                self.assertNotIn(".git/config", archive.namelist())
                self.assertNotIn("assets/landscape.jpg", archive.namelist())

    def test_unlisted_files_are_excluded_and_symlink_asset_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text("test")
            (root / "private.txt").write_text("must not enter archive")
            with patch.object(source, "ROOT", root), patch.object(source, "ASSETS", {"/": ("index.html", "text/html")}):
                data, _ = source.build_source("probe")
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    self.assertEqual(archive.namelist(), ["index.html"])
                (root / "index.html").unlink()
                (root / "index.html").symlink_to(root / "private.txt")
                with self.assertRaises(OSError):
                    source.build_source("probe")


if __name__ == "__main__":
    unittest.main()
