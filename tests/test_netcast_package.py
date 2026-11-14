"""Synthetic portal layouts and hostile ZIP boundaries; no TV or extraction."""
import contextlib
import io
import json
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

from tools import netcast_package as package

APP = "1234567890"


def portal(icons=False):
    files = {APP + "/" + name: ("source " + name).encode() for name in package.SOURCE_ASSETS}
    files[APP + "/manifest.xml"] = b"NCGFILE_HEADER" + b"opaque"
    files[APP + "/developer.test"] = b"1"
    if icons:
        for number in range(4):
            files[APP + "/icon" + str(number) + ".png"] = b"icon"
    return files


def zipped(files, compression=zipfile.ZIP_STORED):
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=compression) as archive:
        for name, content in (files.items() if isinstance(files, dict) else files):
            archive.writestr(name, content)
    return result.getvalue()


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "package.zip"

    def inspect(self, files=None, data=None, source=None):
        self.path.write_bytes(data if data is not None else zipped(portal() if files is None else files))
        return package.inspect_package(self.path, source)

    def reject(self, code, files=None, data=None):
        with self.assertRaises(package.PackageError) as caught:
            self.inspect(files, data)
        self.assertEqual(caught.exception.code, code)
        self.assertNotIn(APP, str(caught.exception))

    def test_original_and_fixed_portal_layouts_with_optional_icons(self):
        for icons, expected in ((True, 12), (False, 8)):
            files = {APP + "/": b"", APP + "/assets/": b"", **portal(icons)}
            report = self.inspect(files)
            self.assertEqual(report["entries"], expected + 2)
            self.assertEqual(report["file_count"], expected)
            self.assertTrue(report["structurally_valid"])
            self.assertFalse(report["entry_in_manifest_verified"])
            self.assertFalse(report["entitlement_verified"])
            self.assertNotIn(APP, json.dumps(report))
            self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["package.zip"])

    def test_observed_modify_nested_package_has_specific_diagnostic(self):
        old = portal(True)
        files = {APP + "/" + name: value for name, value in old.items()}
        files[APP + "/manifest.xml"] = b"NCGFILE_HEADERnew"
        files[APP + "/developer.test"] = b"1"
        self.reject("nested_app_root", files)

    def test_required_root_entry_metadata_and_signature(self):
        for missing, code in (("index.html", "missing_root_entry"), ("manifest.xml", "missing_portal_metadata"), ("developer.test", "missing_portal_metadata")):
            files = portal(); del files[APP + "/" + missing]
            self.reject(code, files)
        files = portal(); files[APP + "/index.html"] = b""
        self.reject("empty_root_entry", files)
        files = portal(); files[APP + "/manifest.xml"] = b"<manifest>private</manifest>"
        self.reject("manifest_signature", files)

    def test_ambiguous_roots_include_unrelated_empty_directories(self):
        for extra in ("999/index.html", "999/", "index.html", "__MACOSX/"):
            self.reject("ambiguous_app_root", {**portal(), extra: b""})
        self.reject("ambiguous_app_root", {name.replace(APP, "app"): value for name, value in portal().items()})

    def test_unsafe_paths(self):
        for name in ("/absolute", "../bad", APP + "/../bad", APP + "/./bad", APP + "//bad", APP + "/bad\\x", "C:/bad", APP + "/bad\nname", APP + "/bad\u202ename", APP + "/bad.", APP + "/bad "):
            with self.subTest(name=repr(name)):
                self.reject("unsafe_path", {**portal(), name: b""})
        # ZipInfo truncates a NUL on construction; inject one into a real member name.
        self.reject("unsafe_path", data=zipped({**portal(), APP + "/badXname": b""}).replace(b"badXname", b"bad\x00name"))

    def test_duplicate_case_unicode_and_file_directory_collisions(self):
        for names in ((APP + "/index.html", APP + "/index.html"), (APP + "/a", APP + "/A"), (APP + "/caf\u00e9", APP + "/cafe\u0301"), (APP + "/collision", APP + "/collision/")):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                self.reject("duplicate_path", data=zipped(list(portal().items()) + [(name, b"") for name in names]))
        self.reject("path_conflict", {**portal(), APP + "/parent": b"x", APP + "/parent/file": b"x"})

    def test_symlink_device_and_directory_payload_rejected(self):
        for mode in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR):
            entry = zipfile.ZipInfo(APP + "/special")
            entry.create_system = 3
            entry.external_attr = (mode | 0o600) << 16
            self.reject("nonregular_entry", data=zipped(list(portal().items()) + [(entry, b"target")]))
        self.reject("nonregular_entry", {**portal(), APP + "/directory/": b"payload"})

    def test_encrypted_flag_and_unsupported_compression_rejected(self):
        data = bytearray(zipped(portal()))
        for signature, delta in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
            at = data.index(signature) + delta
            struct.pack_into("<H", data, at, struct.unpack_from("<H", data, at)[0] | 1)
        self.reject("encrypted_zip_entry", data=data)
        self.reject("unsupported_compression", data=zipped(portal(), zipfile.ZIP_BZIP2))

    def test_file_ratio_total_and_metadata_budgets(self):
        self.reject("member_bounds", {**portal(), APP + "/large": b"a" * (package.MAX_FILE + 1)})
        self.reject("member_bounds", data=zipped({**portal(), APP + "/ratio": b"a" * 100000}, zipfile.ZIP_DEFLATED))
        with patch.object(package, "MAX_EXPANDED", 10):
            self.reject("expanded_bounds", portal())
        self.reject("metadata_bounds", {APP + "/item" + str(i): b"x" for i in range(101)})
        with patch.object(package, "MAX_ZIP", 100):
            self.reject("zip_file_bounds", portal())

    def test_corruption_and_malformed_archive_rejected(self):
        data = zipped(portal())
        self.reject("invalid_zip", data=data[:-3])
        self.reject("invalid_zip", data=data + b"extra")
        self.reject("invalid_zip", data=data.replace(b"source shell.js", b"broken shell.js", 1))
        damaged = bytearray(data)
        struct.pack_into("<H", damaged, len(damaged) - 22 + 10, 1)
        struct.pack_into("<H", damaged, len(damaged) - 22 + 8, 1)
        self.reject("invalid_zip", data=damaged)

    def test_source_comparison_reports_changed_missing_and_hashes(self):
        source = self.root / "source.zip"
        original = portal()
        source.write_bytes(zipped({name[len(APP) + 1:]: value for name, value in original.items() if name[len(APP) + 1:] in package.SOURCE_ASSETS}))
        report = self.inspect(original, source=source)
        self.assertTrue(report["source_comparison"]["matches"])
        self.assertEqual(len(report["source_comparison"]["matching"]), 6)
        changed = dict(original)
        changed[APP + "/shell.js"] = b"different"
        del changed[APP + "/style.css"]
        report = self.inspect(changed, source=source)
        self.assertEqual(report["source_comparison"]["changed"], ["shell.js"])
        self.assertEqual(report["source_comparison"]["missing"], ["style.css"])
        self.assertFalse(report["source_comparison"]["matches"])
        self.assertTrue(all(len(item["sha256"]) == 64 for item in report["files"]))
        source.write_bytes(zipped({"index.html": b"only"}))
        with self.assertRaises(package.PackageError) as caught:
            package.inspect_package(self.path, source)
        self.assertEqual(caught.exception.code, "source_asset_set")

    def test_nonregular_or_symlink_input_fails_without_blocking(self):
        target = self.root / "target"
        target.write_bytes(zipped(portal()))
        self.path.symlink_to(target)
        with self.assertRaises(package.PackageError):
            package.inspect_package(self.path)
        self.path.unlink()
        import os
        os.mkfifo(self.path)
        with self.assertRaises(package.PackageError) as caught:
            package.inspect_package(self.path)
        self.assertEqual(caught.exception.code, "zip_file_bounds")

    def test_cli_errors_are_json_and_do_not_leak_private_path(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = package.main([str(self.root / "private-name.zip")])
        self.assertEqual(result, 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["error"], "input_unreadable")
        self.assertNotIn("private-name", output.getvalue())


if __name__ == "__main__":
    unittest.main()
