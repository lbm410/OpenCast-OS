import hashlib
from pathlib import Path
import stat
import struct
import warnings
import tempfile
import unittest
import zipfile

from tools import firmware_analysis as firmware


class FirmwareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive = self.root / "sample.zip"

    def tearDown(self):
        self.temp.cleanup()

    def make_zip(self, name="nested/sample.epk", data=b"test firmware"):
        with zipfile.ZipFile(self.archive, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(name, data)

    def test_inventory_and_explicit_extract(self):
        payload = b"test firmware"
        self.make_zip(data=payload)
        report = firmware.inspect_file(self.archive)
        self.assertEqual(report["format"], "zip")
        self.assertFalse(report["members"][0]["crc32_verified"])
        extracted = firmware.extract_member(self.archive, "nested/sample.epk", self.root / "out")
        self.assertEqual(extracted["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertTrue(extracted["crc32_verified"])
        self.assertEqual((self.root / "out/sample.epk").read_bytes(), payload)
        self.assertEqual((self.root / "out/sample.epk").stat().st_mode & 0o222, 0)

    def test_no_overwrite_or_output_symlink(self):
        self.make_zip()
        output = self.root / "out"
        output.mkdir()
        (output / "sample.epk").write_bytes(b"preserve")
        with self.assertRaises(FileExistsError):
            firmware.extract_member(self.archive, "nested/sample.epk", output)
        self.assertEqual((output / "sample.epk").read_bytes(), b"preserve")
        alias = self.root / "alias"
        alias.symlink_to(output)
        with self.assertRaises(ValueError):
            firmware.extract_member(self.archive, "nested/sample.epk", alias)

    def test_reject_unsafe_names(self):
        for name in ("../bad", "/bad", "a/../bad", "a\\bad", "C:/bad", "a//bad", "a/./bad", "bad\nname", "folder/"):
            with self.subTest(name=name):
                self.make_zip(name=name)
                with self.assertRaises(ValueError):
                    firmware.inspect_file(self.archive)

    def test_reject_symlink_member(self):
        info = zipfile.ZipInfo("link.epk")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr(info, "../../secret")
        with self.assertRaises(ValueError):
            firmware.inspect_file(self.archive)

    def test_reject_duplicate_names(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.archive, "w") as archive:
                archive.writestr("same.epk", b"first")
                archive.writestr("same.epk", b"second")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            firmware.inspect_file(self.archive)

    def test_reject_appended_data_and_zip64_markers(self):
        self.make_zip()
        original = self.archive.read_bytes()
        self.archive.write_bytes(original + b"unexpected")
        with self.assertRaises(ValueError):
            firmware.zip_directory(self.archive)
        data = bytearray(original)
        position = data.rfind(b"PK\x05\x06")
        struct.pack_into("<H", data, position + 8, 65535)
        struct.pack_into("<H", data, position + 10, 65535)
        self.archive.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "ZIP64"):
            firmware.zip_directory(self.archive)

    def test_central_directory_limits_before_zipfile(self):
        self.make_zip()
        data = bytearray(self.archive.read_bytes())
        position = data.rfind(b"PK\x05\x06")
        struct.pack_into("<H", data, position + 8, 257)
        struct.pack_into("<H", data, position + 10, 257)
        self.archive.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "limits"):
            firmware.zip_directory(self.archive)

    def test_limits_and_encryption(self):
        info = zipfile.ZipInfo("a.epk")
        info.file_size = firmware.MAX_MEMBER + 1
        with self.assertRaises(ValueError):
            firmware.safe_member(info)
        info.file_size = 2000
        info.compress_size = 1
        with self.assertRaisesRegex(ValueError, "ratio"):
            firmware.safe_member(info)
        info.file_size = 1
        info.flag_bits = 1
        with self.assertRaisesRegex(ValueError, "Encrypted"):
            firmware.safe_member(info)

    def test_bad_crc_removes_only_new_output(self):
        with zipfile.ZipFile(self.archive, "w", zipfile.ZIP_STORED) as archive:
            archive.writestr("sample.epk", b"original")
        data = bytearray(self.archive.read_bytes())
        offset = data.index(b"original")
        data[offset] ^= 1
        self.archive.write_bytes(data)
        output = self.root / "out"
        with self.assertRaises(zipfile.BadZipFile):
            firmware.extract_member(self.archive, "sample.epk", output)
        self.assertFalse((output / "sample.epk").exists())

    def test_unclassified_bytes_are_not_claimed_as_decrypted(self):
        sample = self.root / "sample.epk"
        sample.write_bytes(b"\x01\x02" + b"0004.0022.1000\x00" + b"03.05.000\x00")
        report = firmware.inspect_file(sample)
        self.assertEqual(report["format"], "unclassified_binary")
        self.assertFalse(report["header"]["signature_verified"])
        self.assertEqual(report["header"]["version_like_strings"][0]["offset"], 2)


if __name__ == "__main__":
    unittest.main()
